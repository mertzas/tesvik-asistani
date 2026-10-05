"""
Finansal profil (FinancialProfile) ile tesvikler tablosundaki
uygunluk_kriterleri arasinda skor bazli esleme yapar.

/api/sor endpoint'indeki serbest metin RAG aramasindan farkli olarak, burada
kullanicinin yapilandirilmis profili (sektor, hedef, ciro, calisan sayisi)
uzerinden deterministik bir skorlama yapilir; LLM sadece sonucu insan
diline cevirmek icin kullanilabilir (bkz. rag.answer), skorlama kendisi
kural tabanlidir ve tekrarlanabilir/aciklanabilir olmalidir.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, selectinload

from app.match_adapter import company_from_profile, program_from_tesvik
from app.match_scoring import hard_filter
from app.nace_hiyerarsi import sector_match
from app.models import FinancialProfile, Tesvik
from app.urun_sektor_anahtarlari import (
    BELIRTILMEMIS_KATEGORILER,
    urun_turunden_tarim_kategorisi,
)

# Turkce karakterleri sadelestirerek esnek eslesme yapmak icin (bkz. app/ihracat_fiyatlari.py).
_TR_CEVIRI = str.maketrans("çÇğĞıİöÖşŞüÜ", "cCgGiIoOsSuU")


def _sadelestir(metin: str) -> str:
    return metin.translate(_TR_CEVIRI).lower().strip()


@dataclass
class TesvikEslesmeSonucu:
    tesvik: Tesvik
    skor: float
    gerekce: list[str] = field(default_factory=list)
    eksik_kriterler: list[str] = field(default_factory=list)


def _tutari_parse(tesvil_tutari: str | None) -> tuple[float | None, float | None]:
    """'₺100.000 - ₺500.000' gibi bir araligi (min, max) TL olarak cikarmaya calisir."""
    if not tesvil_tutari:
        return None, None

    import re

    sayilar = re.findall(r"[\d.,]+", tesvil_tutari.replace("₺", ""))
    degerler = []
    for s in sayilar:
        temiz = s.replace(".", "").replace(",", ".")
        try:
            degerler.append(float(temiz))
        except ValueError:
            continue

    if not degerler:
        return None, None
    if len(degerler) == 1:
        return degerler[0], degerler[0]
    return min(degerler), max(degerler)


def _kurum_ile_cesitlendir(sonuclar: list["TesvikEslesmeSonucu"]) -> list["TesvikEslesmeSonucu"]:
    """Ayni skora sahip sonuclar arasinda TEK bir kurumun listeye hakim
    olmasini engeller. Ornegin TUBITAK basliklari rakamla basladigi icin
    ("1000 - ...") alfabetik siralamada KOSGEB/KGF'den (harfle baslayan)
    HER ZAMAN once gelir; 66 TUBITAK kaydi karsisinda 9 KOSGEB + 79 KGF
    kaydi limit=10'a hic giremezdi. Bunun yerine esit-skorlu bloklar
    icinde kurumlara gore round-robin dagitim yapiyoruz (skor sirasi
    bloklar arasinda korunur, sadece ayni blok icinde kurum cesitliligi
    saglanir)."""
    sonuc: list[TesvikEslesmeSonucu] = []
    i = 0
    n = len(sonuclar)
    while i < n:
        j = i
        while j < n and sonuclar[j].skor == sonuclar[i].skor:
            j += 1
        blok = sonuclar[i:j]

        kurum_gruplari: dict[str, list[TesvikEslesmeSonucu]] = {}
        for s in blok:
            kurum_gruplari.setdefault(s.tesvik.kurum, []).append(s)

        kurumlar = sorted(kurum_gruplari.keys())
        while any(kurum_gruplari[k] for k in kurumlar):
            for k in kurumlar:
                if kurum_gruplari[k]:
                    sonuc.append(kurum_gruplari[k].pop(0))

        i = j
    return sonuc


def esles(profil: FinancialProfile, db: Session, limit: int = 20) -> list[TesvikEslesmeSonucu]:
    profil_sektorler = {(profil.sektor or "").lower()}
    profil_hedefler = {h.lower() for h in (profil.hedefler or [])}

    sonuclar: list[TesvikEslesmeSonucu] = []
    sirket = company_from_profile(profil)

    for t in db.query(Tesvik).options(selectinload(Tesvik.nace_kayitlari)).all():
        # KAPANDIGI DOGRULANMIS programlari hic onerme. Bunlar bir firsat
        # degil; kullanici arayip "bu program bitti" cevabi alir ve sistemin
        # tamamina olan guveni sarsilir. (Tespit: imalat profiline gelen ilk
        # 20 onerinin 5'i kapali programdi - 2021 Nefes Kredisi, 6 Subat
        # paketleri gibi.) Kapali programlar RAG/arama tarafinda hala
        # bilgi amacli gorunur, orada "artik aktif degil" diye isaretleniyor.
        if t.aktif_mi is False:
            continue

        kriterler = t.uygunluk_kriterleri or {}
        tesvik_sektorler = {s.lower() for s in kriterler.get("sektorler", [])}

        if not tesvik_sektorler:
            continue

        # Katı eleme (app/match_scoring.py Aşama 1): zorunlu hedef kitle,
        # çalışan sayısı ve il kısıtı. Profilde olmayan veri ELEMEZ (yokluk
        # ihlal değildir); yalnızca olumlu beyan gerektiren hedef kitle
        # etiketi eksikse elenir. Sektör kontrolü aşağıdaki mevcut mantıkta.
        program = program_from_tesvik(t)
        sebepler, _ = hard_filter(sirket, program, strict_sector=True)
        if sebepler:
            continue

        skor = 0.0
        gerekce: list[str] = []
        eksik: list[str] = []

        ortak_sektor = tesvik_sektorler & profil_sektorler
        if ortak_sektor or "genel" in tesvik_sektorler:
            if ortak_sektor:
                skor += 0.6
                gerekce.append(f"Sektorunuz ({profil.sektor}) bu destegin kapsamina uygun.")
            else:
                skor += 0.2
                gerekce.append("Bu destek sektor bagimsiz genel bir programdir.")
        else:
            continue  # sektor hic uyusmuyorsa listeye alma

        # NACE: program sektörlüyse ve işletmenin kodu biliniyorsa uyum
        # gerekçeye yazılır (eleme yukarıda yapıldı; skor değişmiyor - sıralamaya
        # bağlanması ayrı bir adım). Kod girilmemişse kullanıcı bilgilendirilir.
        if program.nace_codes:
            if sirket.nace_codes:
                uyum = sector_match(sirket.nace_codes[0], program.nace_codes)
                gerekce.append(f"Faaliyet kodunuz: {uyum.aciklama}.")
            else:
                eksik.append(
                    "Bu destek belirli sektörlere özeldir. Profilinize faaliyet (NACE) "
                    "kodunuzu girerseniz uygunluğu netleşir."
                )

        bolge_kisitli = kriterler.get("bolge_kisitli")
        if bolge_kisitli:
            profil_bolge = (profil.bolge or "").strip().lower()
            if profil_bolge:
                bolge_uyumlu = any(
                    il in profil_bolge or profil_bolge in il for il in bolge_kisitli
                )
                if not bolge_uyumlu:
                    continue  # bu program baska illere ozel, kullaniciya gosterme
                gerekce.append(f"Bölgeniz ({profil.bolge}) bu programın kapsamındaki iller arasında.")
            else:
                skor *= 0.5
                eksik.append(
                    "Bu destek yalnızca belirli illerde faaliyet gösteren/yatırım yapacak "
                    "işletmeler içindir (" + ", ".join(il.title() for il in bolge_kisitli) + "). "
                    "Bölgenizi girerseniz size uygun olup olmadığını netleştirebiliriz."
                )

        hedef_metni = f"{t.baslik} {t.ozet}".lower()

        if profil_hedefler:
            hedef_eslesme = [h for h in profil_hedefler if h in hedef_metni]
            if hedef_eslesme:
                skor += 0.3
                gerekce.append(f"Belirttiginiz hedef(ler) ile eslesiyor: {', '.join(hedef_eslesme)}.")
            else:
                eksik.append("Belirttiginiz hedeflerle dogrudan eslesme bulunamadi, detaylari kontrol edin.")

        urun_turu = (profil.urun_turu or "").strip().lower()
        if urun_turu and urun_turu in hedef_metni:
            skor += 0.15
            gerekce.append(f"Yetistirdiginiz urun/faaliyet ({profil.urun_turu}) bu destekte gecmektedir.")

        # Bazi tarim destekleri dar bir alt kategoriye ozeldir (orn. sadece
        # hayvancilik). Kullanicinin profilinde YAPILANDIRILMIS bir kategori
        # secimi (tarim_kategori dropdown - serbest metin degil) varsa bunu
        # kesin sinyal olarak kullaniyoruz: tam eslesirse guclu bonus, tam
        # eslesmezse ceza. Yapilandirilmis secim YOKSA (kullanici bos
        # birakti) eski serbest-metin (urun_turu/hedefler) ipucuna bakariz;
        # o da yoksa CEZA UYGULAMIYORUZ artik - eskiden kategori sinyali
        # hic yokken bile sabit ceza uygulaniyordu, bu da 5 tarim destegini
        # ayni skora dusurup alfabetik sirada hep "Hayvancilik"in kazanmasina
        # yol aciyordu. Bunun yerine sadece "genislik" etiketine gore hafif
        # bir ayrim yapiyoruz: dar/spesifik programlar (orn. hayvancilik,
        # sera) belirsizlikte hafif geride kalir, genis/genel programlar
        # (orn. sulama, makinelestirme, organik) etkilenmez.
        alt_kategori = kriterler.get("alt_kategori")
        if alt_kategori:
            tarim_kategori = (profil.tarim_kategori or "").strip().lower()
            genislik = kriterler.get("genislik", "genis")

            # "genel" / "Belirtmek istemiyorum" GERCEK bir kategori degil:
            # hicbir tesvik kaydinda alt_kategori="genel" yok, dolayisiyla
            # bunu gercek bir secim gibi islemek "hicbiriyle eslesmedi"
            # sayilip her kategorili kaydin skorunu 0.25 dusuruyordu. Sonuc:
            # kullanici "Belirtmek istemiyorum" secince ALANI BOS
            # BIRAKMAKTAN DAHA KOTU sonuc aliyordu (olcum 2026-09-26: tum
            # tarim destekleri 0.70/0.60 -> 0.45). Belirtilmemis kabul edip
            # asagidaki serbest-metin ipucu yoluna dusuyoruz.
            if tarim_kategori in BELIRTILMEMIS_KATEGORILER:
                tarim_kategori = ""

            # Kategori secilmemis ama urun adi girilmisse kategoriyi urunden
            # cikar: "bugday" -> tahil_baklagil. Eskiden yalnizca
            # "alt_kategori metni urun_turu icinde geciyor mu" bakiliyordu ve
            # "tahil_baklagil" ifadesi "bugday" icinde gecmedigi icin bu ipucu
            # hic calismiyordu - urun_turu="bugday" girmis bir ciftci icin tam
            # uyan "Hububat ve Baklagil Uretim Destekleri" kaydi, alakasiz
            # "Hayvancilik Destekleri" ile ayni skoru aliyordu.
            urunden_kategori = None
            if not tarim_kategori:
                urunden_kategori = urun_turunden_tarim_kategorisi(profil.urun_turu)

            if tarim_kategori:
                if tarim_kategori == alt_kategori:
                    skor += 0.3
                    gerekce.append(f"Seçtiğiniz tarım kategorisi ('{tarim_kategori}') bu destekle tam eşleşiyor.")
                elif genislik == "dar":
                    skor -= 0.25
                    eksik.append(
                        f"Bu destek '{alt_kategori}' kategorisine özeldir; seçtiğiniz kategori "
                        f"('{tarim_kategori}') farklı."
                    )
                # genislik == "genis" olan programlar (sulama, makinelestirme,
                # organik) URUN TURUNDEN BAGIMSIZDIR: bugday eken bir ciftci de
                # organik sertifikasyon alabilir, sulama yatirimi yapabilir,
                # traktor destegine basvurabilir. Bunlari "kategori uyusmadi"
                # diye cezalandirmak somut bir hataya yol aciyordu (olcum
                # 2026-09-26): tahil_baklagil secen ciftci icin Organik/Sulama/
                # Makinelestirme destekleri 0.70'ten 0.45'e dusuyor, yani
                # kategoriyi DOGRU secmek bu uc gecerli destegin siralamasini
                # kotulestiriyordu. Uyusmazlik cezasi artik yalnizca gercekten
                # dislayici ("dar") programlara uygulaniyor.
            elif urunden_kategori == alt_kategori:
                # Urun adindan cikarilan kategori: acilir listeden gelen kesin
                # secim kadar guvenilir degil (kullanici birden fazla urun
                # yetistiriyor olabilir), bu yuzden bonus daha dusuk ve
                # uyusmayan kayitlara CEZA UYGULANMIYOR.
                skor += 0.25
                gerekce.append(
                    f"Girdiginiz urun ('{profil.urun_turu}') bu destegin kategorisine "
                    f"('{alt_kategori}') giriyor."
                )
            else:
                urun_turu_sade = _sadelestir(urun_turu)
                hedefler_sade = {_sadelestir(h) for h in profil_hedefler}
                serbest_metin_isareti = (
                    alt_kategori in urun_turu_sade
                    or any(alt_kategori in h for h in hedefler_sade)
                )
                if serbest_metin_isareti:
                    skor += 0.2
                    gerekce.append(f"'{alt_kategori}' kategorisiyle eslesiyor.")
                elif urunden_kategori is not None:
                    # Urun baska bir kategoriye isaret ediyor. Ceza yerine
                    # sadece bonus vermiyoruz: urun bilgisi acilir liste kadar
                    # kesin olmadigi icin yanlis olma ihtimali var.
                    eksik.append(
                        f"Bu destek '{alt_kategori}' kategorisine ozeldir; girdiginiz "
                        f"urun ('{profil.urun_turu}') '{urunden_kategori}' kategorisine "
                        "isaret ediyor."
                    )
                elif genislik == "dar":
                    skor -= 0.1
                    eksik.append(
                        f"Bu destek '{alt_kategori}' kategorisine özeldir. Profilinizde 'Tarım "
                        "Kategorisi' alanını doldurursanız size gerçekten uygun olup olmadığı netleşir."
                    )

        if profil.calisan_sayisi is not None:
            skor += 0.1
            if profil.calisan_sayisi == 0:
                gerekce.append("Sahis isletmesi / tek kisilik faaliyet olarak degerlendirildi.")
        else:
            eksik.append("Calisan sayinizi girerseniz eslesme dogrulugu artar.")

        sonuclar.append(TesvikEslesmeSonucu(tesvik=t, skor=round(max(min(skor, 1.0), 0.0), 2), gerekce=gerekce, eksik_kriterler=eksik))

    # Skor esitliginde veritabani ekleme sirasina (id) gore rastgele/anlamsiz
    # bir siralama olusmasin diye ikincil olarak baslige gore alfabetik
    # siraliyoruz - en azindan ongorulebilir ve kullaniciya aciklanabilir.
    # Ayni skorda: aktif oldugu DOGRULANMIS program, aktifligi hic kontrol
    # edilmemis olanin onune gecer. Skoru degistirmiyoruz (aciklanabilirlik
    # bozulmasin) - sadece esitlik bozma sirasi.
    sonuclar.sort(key=lambda s: (-s.skor, 0 if s.tesvik.aktif_mi is True else 1, (s.tesvik.baslik or "").lower()))
    sonuclar = _kurum_ile_cesitlendir(sonuclar)
    return sonuclar[:limit]


def _tutar_olcek_faktoru(kriter: str, profil: FinancialProfile) -> float | None:
    """tutari_min/tutari_max (TL cinsinden BIRIM fiyat - orn. 'dekar basina')
    ile kullanicinin profilindeki gercek buyuklugu carparak MUTLAK tahmini
    tutara cevirmek icin kullanilan olcek katsayisini doner. Ilgili profil
    alani eksikse None doner - cagiran taraf bu durumda tahmin uretmemeli,
    aksi halde 'dekar basina 500 TL' 500 TL toplam gibi gosterilir (bkz.
    toplam_tahmini_destek'teki eski hata)."""
    kriter = kriter.lower()
    if kriter == "dekar":
        return profil.arazi_buyuklugu_dekar if profil.arazi_buyuklugu_dekar else None
    elif kriter == "calisan":
        return (profil.calisan_sayisi or 1) if profil.calisan_sayisi is not None else None
    elif kriter in ("ciro", "genel"):
        # tutari_min/max zaten MUTLAK TL toplami (birim fiyat degil) - olcek 1.
        return 1.0
    return None


def tutari_tahmini_hesapla(tesvik, profil: FinancialProfile) -> float | None:
    """Teşvik tutarı ve profil bilgisine göre tahmini destek tutarı hesapla.

    Örn: 50 dekar arazi, makineleştirme desteği (dekar başına ₺X-Y) -> tahmini
    """
    if not tesvik.tutari_hesaplama_kriteri or tesvik.tutari_min is None:
        return None

    ort_tutar = (tesvik.tutari_min + (tesvik.tutari_max or tesvik.tutari_min)) / 2
    olcek = _tutar_olcek_faktoru(tesvik.tutari_hesaplama_kriteri, profil)
    if olcek is None:
        return None
    return olcek * ort_tutar


KREDI_KEFALET_KURUMLARI = {"kgf"}


def _proje_bazli_tavan_mi(tesvik) -> bool:
    """Kaydin tutari, programin UST SINIRI mi (kullanicinin alacagi tutar degil)?

    Metinden tahmin etmiyoruz - veride acikca isaretli olmasi gerekiyor:
        uygunluk_kriterleri["tutar_niteligi"] == "proje_bazli_tavan"
    Boylece hangi kaydin neden toplama girmedigi denetlenebilir kaliyor
    (bkz. scripts/backfill_tarim_tutar_2026.py).
    """
    return _tutar_niteligi(tesvik) == "proje_bazli_tavan"


# uygunluk_kriterleri["tutar_niteligi"] degerleri. Tutarin NE oldugunu
# soyler; "toplam tahmini destek"e hangi kaydin girecegini bu belirler.
#   "hibe"              -> geri odemesiz, cepten alinir. TOPLAMA GIRER.
#   "kredi_kefalet"     -> kredi ana parasi / kefalet limiti. Girmez.
#   "faiz_destegi"      -> kurum kredinin FAIZINI odiyor, ana parayi degil;
#                          bastaki buyuk rakam kredi limitidir. Girmez.
#   "proje_bazli_tavan" -> programin ust siniri, kullaniciya ozel degil. Girmez.
TOPLAMA_GIRMEYEN_NITELIKLER = {"kredi_kefalet", "faiz_destegi", "proje_bazli_tavan"}

_NITELIK_ACIKLAMALARI = {
    "kredi_kefalet": "Bu bir kredi/kefalet ürünü: rakam bankadan "
                     "kullanabileceğiniz kredinin üst sınırıdır, size "
                     "ödenecek hibe değildir.",
    "faiz_destegi": "Kurum kredinin ANA PARASINI değil FAİZİNİ karşılıyor; "
                    "baştaki büyük rakam kredi limitidir. Eline geçen destek "
                    "ödenen faiz kadardır.",
    "proje_bazli_tavan": "Tutar proje bazlı belirlenir; metindeki rakam "
                         "programın üst sınırıdır, sizin alacağınız tutar "
                         "değildir.",
}


def _tutar_niteligi(tesvik) -> str | None:
    return (tesvik.uygunluk_kriterleri or {}).get("tutar_niteligi")


def _kredi_kefaleti_mi(tesvik) -> bool:
    """Bu kaydin tutari hibe DISI mi (kredi/kefalet/faiz destegi)?

    ONCE acik isarete bakar. Isaret yoksa metin sezgisine duser, ama bu sezgi
    KAYIP VERIYOR: "kredi" kelimesi gecen her kayit tamamen disari atiliyordu
    ve boylece KOSGEB Girisimci Destek Programi'ndaki GERI ODEMESIZ 10.000 TL
    kurulus destegi de toplamdan dusuyordu (olcum 2026-09-26; metinde "%80
    geri odemeli" ve "Faiz/Kar Payi" ifadeleri geciyor diye). Bu yuzden
    kayitlarin tutar_niteligi ile acikca isaretlenmesi gerekiyor
    (bkz. scripts/backfill_tutar_niteligi.py).
    """
    nitelik = _tutar_niteligi(tesvik)
    if nitelik:
        return nitelik in TOPLAMA_GIRMEYEN_NITELIKLER
    if (tesvik.kurum or "").strip().lower() in KREDI_KEFALET_KURUMLARI:
        return True
    metin = (tesvik.tesvil_tutari or "") + " " + (tesvik.tutari_hesaplama_formulu or "")
    return "kredi" in metin.lower()


def toplam_tahmini_destek(sonuclar: list[TesvikEslesmeSonucu], profil: FinancialProfile) -> tuple[float, float]:
    """Eslesen tesviklerin tutar araliklarini toplayarak kaba bir 'toplam
    alinabilecek destek' araligi verir.

    ONCEKI HATA: bu fonksiyon tesvil_tutari SERBEST METNINI (orn. 'Dekar
    basina 500-2000 TL') duz metin olarak parse edip MUTLAK bir tutarmis
    gibi topluyordu - yani 50 dekarlik bir ciftci icin gercekte
    50*500=25.000 TL olmasi gereken bir destek, ekranda 500 TL olarak
    gorunuyordu (kullanicinin arazi buyuklugu hic carpilmiyordu). Simdi
    yapisal tutari_min/tutari_max + tutari_hesaplama_kriteri alanlari
    doluysa (guvenilir, olcekli hesap) o kullanilir; sadece bu alanlar bos
    olan eski/is-lenmemis kayitlar icin metin parse'ina (yaklasik, olceksiz)
    dusulur.

    IKINCI HATA (bununla birlikte duzeltildi): KGF'nin urunleri HIBE degil
    KREDI KEFALETIDIR (bkz. app/models.py KurumIletisim dokumantasyonu,
    scripts/seed_kurum_iletisim.py) - "₺20.000.000'a kadar kredi" bir
    banka kredisinin ust siniridir, cepten alinacak bir para degildir.
    Bunlari diger kurumlarin (KOSGEB, Tarim Bakanligi, TUBITAK) gercek
    hibe/nakit destekleriyle toplamak kategori hatasidir ve "toplam
    tahmini destek" rakamini anlamsiz sekilde sisirir (test: genel bir
    tarim profiline 20 kayit eslesip toplam ₺43 milyona cikiyordu, buyuk
    kismi KGF kredi limitlerinden). KGF kayitlari bu toplamdan haric
    tutulur; kullanici bunlari ayri bir 'kredi/kefalet secenekleri'
    listesi olarak gormelidir, nakit destek toplamiyla karistirilmamalidir."""
    # UCUNCU HATA: birbirini DISLAYAN kayitlar birlikte toplaniyordu. 50 dekar
    # bugday eken bir ciftcinin toplamina "Meyve-Sebze Uretim Destekleri" ve
    # "Sera/Ortualti Tarim Destekleri" de ekleniyordu (olcum 2026-09-26) - ayni
    # tarlada hem bugday hem serada sebze yetistirmiyor. Kaydin alt_kategori'si
    # kullanicinin kategorisiyle celisiyorsa toplama KATILMIYOR. Kayit listede
    # gorunmeye devam eder (bilgi degerli), yalnizca toplama girmez.
    #
    # DORDUNCU HATA: proje bazli hibelerin PROGRAM TAVANI toplama giriyordu.
    # "Sulama Yatirimi Destekleri" metninde 100.000-1.000.000 TL yaziyor ama bu
    # programin ust siniri; 50 dekarlik bir ciftcinin alacagi tutar degil.
    # Boyle iki kayit, o ciftcinin toplamini 1,6 milyon TL'ye cikariyordu
    # (olcum 2026-09-26) - KGF kredi limitleriyle ayni kategori hatasi.
    #
    # Cozum metinden TAHMIN ETMEK degil, veride ISARETLEMEK: proje bazli
    # kayitlarda uygunluk_kriterleri["tutar_niteligi"] == "proje_bazli_tavan".
    # Mutlak hibe araliklari (orn. KOSGEB "100.000-200.000 TL") toplama
    # girmeye devam eder, cunku bunlar gercekten alinabilecek tutarlardir.
    # Isaretli kayitlar proje_bazli_destekler() ile ayri sunulur.
    profil_kategorisi = (profil.tarim_kategori or "").strip().lower()
    if profil_kategorisi in BELIRTILMEMIS_KATEGORILER:
        profil_kategorisi = urun_turunden_tarim_kategorisi(profil.urun_turu) or ""

    toplam_min = 0.0
    toplam_max = 0.0
    for s in sonuclar:
        tesvik = s.tesvik
        if _kredi_kefaleti_mi(tesvik):
            continue
        if tesvik.aktif_mi is False:
            continue  # kapanmis programin tutari toplama girmemeli

        alt_kategori = (tesvik.uygunluk_kriterleri or {}).get("alt_kategori")
        if (alt_kategori and profil_kategorisi
                and alt_kategori != profil_kategorisi
                and (tesvik.uygunluk_kriterleri or {}).get("genislik") == "dar"):
            # Yalnizca "dar" (dislayici) programlar atlanir; sulama/organik/
            # makinelestirme gibi "genis" programlar urun turunden bagimsizdir.
            continue

        if _proje_bazli_tavan_mi(tesvik):
            continue

        if tesvik.tutari_hesaplama_kriteri and tesvik.tutari_min is not None:
            olcek = _tutar_olcek_faktoru(tesvik.tutari_hesaplama_kriteri, profil)
            if olcek is None:
                continue  # profildeki ilgili alan (dekar/calisan) eksik
            toplam_min += olcek * tesvik.tutari_min
            toplam_max += olcek * (tesvik.tutari_max or tesvik.tutari_min)
            continue

        alt, ust = _tutari_parse(tesvik.tesvil_tutari)
        if alt is not None:
            toplam_min += alt
            toplam_max += ust

    return round(toplam_min, 2), round(toplam_max, 2)


def proje_bazli_destekler(sonuclar: list[TesvikEslesmeSonucu]) -> list[dict]:
    """Yapisal (olceklenebilir) tutari olmayan, proje bazli degerlendirilen
    destekler.

    Bunlar toplam tahmini destege KATILMAZ cunku metinlerindeki rakam
    kullanicinin olcegiyle iliskili degil, programin ust siniridir. Ama
    kullanicinin bu programlari gormesi gerekir - sadece "bu tutar sizin
    icin hesaplanamaz" bilgisiyle birlikte.
    """
    liste = []
    for s in sonuclar:
        t = s.tesvik
        if t.aktif_mi is False:
            continue
        if not (_kredi_kefaleti_mi(t) or _proje_bazli_tavan_mi(t)):
            continue  # toplama girdi, burada tekrar gosterilmez
        metin = (t.tesvil_tutari or "").strip()
        if not metin:
            continue
        liste.append({
            "baslik": t.baslik,
            "kurum": t.kurum,
            "program_tutari_metni": metin,
            "kredi_kefalet_mi": _kredi_kefaleti_mi(t),
            "tutar_niteligi": _tutar_niteligi(t),
            "not": _NITELIK_ACIKLAMALARI.get(
                _tutar_niteligi(t) or "",
                "Bu kaydın tutarı sizin ölçeğinize göre hesaplanamıyor; "
                "metindeki rakam programın üst sınırı olabilir."),
        })
    return liste
