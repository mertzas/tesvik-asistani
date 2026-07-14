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

from sqlalchemy.orm import Session

from app.models import FinancialProfile, Tesvik

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

    for t in db.query(Tesvik).all():
        kriterler = t.uygunluk_kriterleri or {}
        tesvik_sektorler = {s.lower() for s in kriterler.get("sektorler", [])}

        if not tesvik_sektorler:
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

            if tarim_kategori:
                if tarim_kategori == alt_kategori:
                    skor += 0.3
                    gerekce.append(f"Seçtiğiniz tarım kategorisi ('{tarim_kategori}') bu destekle tam eşleşiyor.")
                else:
                    skor -= 0.25
                    eksik.append(
                        f"Bu destek '{alt_kategori}' kategorisine özeldir; seçtiğiniz kategori "
                        f"('{tarim_kategori}') farklı."
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
    sonuclar.sort(key=lambda s: (-s.skor, (s.tesvik.baslik or "").lower()))
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
    KREDI_KEFALET_KURUMLARI = {"kgf"}

    def _kredi_kefaleti_mi(tesvik) -> bool:
        if (tesvik.kurum or "").strip().lower() in KREDI_KEFALET_KURUMLARI:
            return True
        # Bazi kayitlar KOSGEB adina girilmis olsa da icerik olarak KGF'nin
        # yurutgu kredi/kefalet urunleridir (orn. 'Kapasite Gelistirme Destek
        # Programi' KOSGEB basligi altinda ama tesvil_tutari'nda '20.000.000
        # kredi limiti' yaziyor) - kurum etiketi guvenilir degil, metin
        # icerigine bakmak gerekiyor.
        metin = (tesvik.tesvil_tutari or "") + " " + (tesvik.tutari_hesaplama_formulu or "")
        return "kredi" in metin.lower()

    toplam_min = 0.0
    toplam_max = 0.0
    for s in sonuclar:
        tesvik = s.tesvik
        if _kredi_kefaleti_mi(tesvik):
            continue
        if tesvik.tutari_hesaplama_kriteri and tesvik.tutari_min is not None:
            olcek = _tutar_olcek_faktoru(tesvik.tutari_hesaplama_kriteri, profil)
            if olcek is None:
                continue  # profildeki ilgili alan (dekar/calisan) eksik - tahmin uretilemez
            toplam_min += olcek * tesvik.tutari_min
            toplam_max += olcek * (tesvik.tutari_max or tesvik.tutari_min)
            continue

        alt, ust = _tutari_parse(tesvik.tesvil_tutari)
        if alt is not None:
            toplam_min += alt
            toplam_max += ust
    return toplam_min, toplam_max
