"""
Makro-ekonomik gostergeler (MacroIndicator) ve sektor benchmark'lari
(SectorBenchmark) kullanarak, bir isletmenin ciro/gider profiline gore
"stok maliyeti icin ne kadar ayirmali" ve "reklama ne kadar butce ayirmali"
sorularina kaba bir referans araligi verir.

Bu bir muhasebe/danismanlik tavsiyesi degildir; sektor ortalamalarindan
turetilen bir referans araligidir ve kullaniciya oyle sunulmalidir.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import FinancialProfile, MacroIndicator, SectorBenchmark
from app.models_cilek import PazarFiyati, PazarKaynagi
from app.tmo_fiyatlar import urun_fiyati_bul
from app.ihracat_fiyatlari import ihracat_fiyati_bul
from app.hal_fiyatlari import hal_fiyati_bul
from app.bolgesel_tarim import bolgesel_tavsiye_getir

# urun_turu profil alaninda gecen anahtar kelime -> cilek_pazar_fiyatlari
# tablosundaki gercek Hal Kayit Sistemi (HKS) verisiyle eslestirme.
# TMO'nun aksine (bkz. tmo_fiyatlar.py) bu veri GUNLUK ve kg bazinda, kalite
# sinifina (sofralik standart/premium) gore ayri fiyat/hacim iceriyor - bkz.
# app/scrapers/hal_cilek_fiyat.py ve app/models_cilek.py.
CILEK_ANAHTAR_KELIMELERI = ["çilek", "cilek"]


def _cilek_hal_fiyati_bul(db: Session, urun_turu: str | None) -> dict | None:
    urun_turu_l = (urun_turu or "").strip().lower()
    if not any(k in urun_turu_l for k in CILEK_ANAHTAR_KELIMELERI):
        return None

    son_tarih = (
        db.query(PazarFiyati.tarih)
        .filter(PazarFiyati.kaynak == PazarKaynagi.HAL)
        .order_by(PazarFiyati.tarih.desc())
        .first()
    )
    if son_tarih is None:
        return None

    kayitlar = (
        db.query(PazarFiyati)
        .filter(PazarFiyati.kaynak == PazarKaynagi.HAL, PazarFiyati.tarih == son_tarih[0])
        .all()
    )
    if not kayitlar:
        return None

    return {
        "kaynak_tipi": "hal_cilek",
        "urun_adi": "Çilek",
        "veri_tarihi": son_tarih[0].isoformat(),
        "kaynak": "T.C. Ticaret Bakanlığı Hal Kayıt Sistemi (HKS), günlük ulusal ortalama",
        "kalite_bazli_fiyatlar": [
            {
                "kalite_sinifi": k.kalite_sinifi.value,
                "fiyat_kg": k.fiyat_kg,
                "hacim_kg": k.hacim_kg,
            }
            for k in kayitlar
        ],
    }

VARSAYILAN_SEKTOR = "genel"


@dataclass
class ButceOnerisi:
    sektor: str
    yillik_ciro: float
    stok_maliyeti_min: float
    stok_maliyeti_max: float
    reklam_butcesi_min: float
    reklam_butcesi_max: float
    mevcut_stok_gideri: float | None
    mevcut_reklam_gideri: float | None
    mevcut_toplam_gider: float | None
    ilk_yil_kurulum_gideri: float | None
    yillik_tufe: float | None
    sektor_net_kar_orani: float | None
    tarim_girdi_enflasyonu: dict | None
    en_yuksek_artan_girdi: dict | None
    guncel_urun_fiyati: dict | None
    guncel_ihracat_fiyati: dict | None
    tarim_dis_ticaret: dict | None
    urun_veri_yok_mesaji: str | None
    bolgesel_tavsiye: dict | None
    gider_sapma_yuzdesi: float | None
    notlar: list[str]
    analist_onerileri: list[str]


def _benchmark_getir(db: Session, sektor: str) -> SectorBenchmark | None:
    row = db.query(SectorBenchmark).filter(SectorBenchmark.sektor == sektor).first()
    if row is None:
        row = db.query(SectorBenchmark).filter(SectorBenchmark.sektor == VARSAYILAN_SEKTOR).first()
    return row


# Tarim alt-kategorilerinin (kullanicinin sectigi "ne yapiyorsunuz" secimi)
# stok maliyeti oranina gore GENEL "tarim" satirina uygulanacak carpanlar.
# TCMB Sektor Bilancolari tarimi NACE "A" duzeyinde TEK satirda yayinliyor,
# hayvancilik/bitkisel ayrimi EVDS'ten cekilemiyor - bu yuzden alt kategoriler
# icin AYRI SABIT sayilar tutmak yerine (EVDS canli veri degistikce olcek
# uyusmazligina yol acar - gecmiste yasandi: genel tarim EVDS'ten %66-90
# cikarken sabit hayvancilik satiri %45-65 idi, yani hayvancilik SECİLİNCE
# stok maliyeti DUSUYOR gibi gorunuyordu, ki gercekte hayvancilik yem
# maliyeti yuzunden DAHA YUKSEK olmasi beklenir) genel tarim satirina
# ORANTISAL bir carpan uyguluyoruz. Boylece EVDS canli veri degisse bile
# alt kategoriler daima ayni GORECELI siraya sahip olur.
TARIM_KATEGORI_CARPANLARI = {
    # Hayvancilik: yem/veteriner giderleri agirlikli, genel tarim
    # ortalamasindan belirgin daha yuksek stok maliyeti beklenir.
    "hayvancilik": 1.3,
    "sebze_meyve": 1.0,
    "tahil_baklagil": 0.8,
    "organik": 1.0,
    "sera": 1.15,
    "sulama": 1.0,
    "makinelestirme": 1.0,
    "genel": 1.0,
}


def _tarim_kategori_carpani(tarim_kategori: str | None) -> float:
    return TARIM_KATEGORI_CARPANLARI.get((tarim_kategori or "").strip().lower(), 1.0)


def _indikator_getir(db: Session, anahtar: str) -> float | None:
    row = db.query(MacroIndicator).filter(MacroIndicator.anahtar == anahtar).first()
    return row.deger if row else None


def hesapla(profil: FinancialProfile, db: Session) -> ButceOnerisi:
    if not profil.yillik_ciro or profil.yillik_ciro <= 0:
        raise ValueError("Butce onerisi icin yillik_ciro pozitif bir deger olmali")

    sektor = (profil.sektor or VARSAYILAN_SEKTOR).lower()
    tarim_kategori = (profil.tarim_kategori or "").strip().lower() or None
    benchmark = _benchmark_getir(db, sektor)

    notlar = []
    if benchmark is None:
        raise ValueError("Sektor benchmark verisi bulunamadi; once tuik_macro.run() calistirilmali")
    if benchmark.sektor != sektor:
        notlar.append(f"'{sektor}' icin ozel benchmark bulunamadi, genel sektor ortalamasi kullanildi.")

    # TCMB Sektor Bilancolari tarimi tek NACE satirinda ("A") yayinliyor,
    # hayvancilik/bitkisel ayrimi EVDS'ten cekilemiyor. Kullanici bir tarim
    # alt kategorisi sectiyse, genel tarim oranina ORANTISAL bir carpan
    # uyguluyoruz (bkz. TARIM_KATEGORI_CARPANLARI) - boylece EVDS'in o anki
    # canli degeri ne olursa olsun (sabit sayilarla degil, oranla calistigi
    # icin) hayvancilik daima genel tarimdan daha yuksek, tahil/baklagil
    # daima daha dusuk gorunur; olcek uyumsuzlugu olusmaz.
    kategori_carpani = _tarim_kategori_carpani(tarim_kategori) if sektor == "tarim" else 1.0
    if sektor == "tarim" and tarim_kategori and kategori_carpani != 1.0:
        notlar.append(
            f"Stok maliyeti aralığı, seçtiğiniz '{tarim_kategori}' kategorisine göre genel tarım "
            f"ortalamasının {kategori_carpani:.2f} katı olarak tahmin edildi (TCMB Sektör Bilançoları "
            "tarımı tek kalemde yayınladığı için bu alt kırılım kesin bir istatistik değil, genel "
            "gider yapısına dayalı bir tahmindir)."
        )

    net_kar_orani = benchmark.net_kar_orani

    tufe = _indikator_getir(db, "yillik_tufe")
    if tufe:
        notlar.append(
            f"Yillik TUFE ({tufe:.1f}%) dikkate alindiginda, stok maliyetlerinizin son "
            f"guncellemeden bu yana enflasyon oraninda arttigini varsayarak butce planlayin."
        )

    if net_kar_orani is not None:
        notlar.append(
            f"Turkiye'de '{sektor}' sektorunun TCMB Sektor Bilancolari'na gore ortalama net "
            f"kar orani (net kar/net satislar) %{net_kar_orani * 100:.1f} - bu, "
            f"cironuzun ne kadarinin karla sonuclanmasinin 'normal' sayildigina dair bir referanstir. "
            + ("Not: TCMB tarim sektorunu tek kalemde yayinladigi icin bu oran hayvancilik/bitkisel "
               "ayrimi yapmiyor, tum tarim isletmelerinin ortalamasidir."
               if sektor == "tarim" else "")
        )

    tarim_girdi_enflasyonu = None
    en_yuksek_artan_girdi = None
    if sektor == "tarim":
        girdi_anahtarlari = {
            "gubre": ("tarim_gubre_yillik_degisim", "Gübre"),
            "ilac": ("tarim_ilac_yillik_degisim", "Tarımsal İlaç"),
            "yem": ("tarim_yem_yillik_degisim", "Hayvan Yemi"),
            "bina_sera": ("tarim_bina_yillik_degisim", "Bina/Sera Yapımı"),
            "makine_bakim": ("tarim_makine_bakim_yillik_degisim", "Makine Bakımı"),
        }
        degerler = {}
        etiketler = {}
        for kisa_ad, (anahtar, etiket) in girdi_anahtarlari.items():
            deger = _indikator_getir(db, anahtar)
            if deger is not None:
                degerler[kisa_ad] = deger
                etiketler[kisa_ad] = etiket

        if degerler:
            tarim_girdi_enflasyonu = degerler
            en_yuksek_kisa_ad = max(degerler, key=degerler.get)
            en_yuksek_artan_girdi = {
                "kalem": en_yuksek_kisa_ad,
                "etiket": etiketler[en_yuksek_kisa_ad],
                "artis": degerler[en_yuksek_kisa_ad],
            }
            notlar.append(
                "TUIK Tarimsal Girdi Fiyat Endeksi'ne gore son 1 yillik girdi fiyat "
                "artislari (bu, hangi gubreyi/ne kadar kullanmaniz gerektigi konusunda "
                "bir tavsiye degildir, sadece maliyet planlamasi icindir). Gubre/ilac "
                "secimi ve dozu icin Il/Ilce Tarim Mudurlugu'nden toprak tahlili bazli "
                "tavsiye almanizi oneririz."
            )

    tarim_dis_ticaret = None
    if sektor == "tarim":
        aylik_ihracat = _indikator_getir(db, "tarim_aylik_ihracat_milyon_usd")
        aylik_ithalat = _indikator_getir(db, "tarim_aylik_ithalat_milyon_usd")
        if aylik_ihracat is not None and aylik_ithalat is not None:
            tarim_dis_ticaret = {
                "ihracat_milyon_usd": aylik_ihracat,
                "ithalat_milyon_usd": aylik_ithalat,
                "denge_milyon_usd": round(aylik_ihracat - aylik_ithalat, 1),
            }
            durum = "açık (ithalat ihracattan fazla)" if aylik_ithalat > aylik_ihracat else "fazla (ihracat ithalattan fazla)"
            notlar.append(
                f"Türkiye'nin tarım (bitkisel/hayvansal üretim) sektörü son ay ihracatı "
                f"${aylik_ihracat:,.0f} milyon, ithalatı ${aylik_ithalat:,.0f} milyon "
                f"(TUIK/EVDS) - sektörde dış ticaret {durum} veriyor. Bu, sektörün genel "
                f"rekabet gücüne dair bir referanstır, sizin işletmenizin ihracat/ithalat "
                f"durumunu yansıtmaz."
            )

    guncel_urun_fiyati = None
    if sektor == "tarim":
        guncel_urun_fiyati = _cilek_hal_fiyati_bul(db, profil.urun_turu)
        if guncel_urun_fiyati:
            fiyat_ozetleri = ", ".join(
                f"{k['kalite_sinifi'].replace('_', ' ').title()}: ₺{k['fiyat_kg']:.2f}/kg"
                for k in guncel_urun_fiyati["kalite_bazli_fiyatlar"]
            )
            notlar.append(
                f"Çilek için {guncel_urun_fiyati['veri_tarihi']} tarihli T.C. Ticaret "
                f"Bakanlığı Hal Kayıt Sistemi (HKS) ulusal ortalama fiyatları: "
                f"{fiyat_ozetleri}. Bu, hal üzerinden satışta güncel bir referanstır - "
                f"bölgenize ve kalite sınıfınıza göre gerçek teklifler farklılık gösterebilir."
            )
        else:
            guncel_urun_fiyati = hal_fiyati_bul(db, profil.urun_turu)
            if guncel_urun_fiyati:
                en_yuksek_kalem = max(guncel_urun_fiyati["kalemler"], key=lambda k: k["fiyat_kg"])
                notlar.append(
                    f"{guncel_urun_fiyati['urun_adi']} için {guncel_urun_fiyati['veri_tarihi']} "
                    f"tarihli T.C. Ticaret Bakanlığı Hal Kayıt Sistemi (HKS) ulusal ortalama "
                    f"fiyatı: ₺{en_yuksek_kalem['fiyat_kg']:.2f}/kg ({en_yuksek_kalem['urun_cinsi']}, "
                    f"{en_yuksek_kalem['urun_turu']}). Bu, hal üzerinden satışta güncel bir "
                    f"referanstır - bölgenize ve çeşide göre gerçek teklifler farklılık gösterebilir."
                )
            else:
                guncel_urun_fiyati = urun_fiyati_bul(profil.urun_turu)
                if guncel_urun_fiyati:
                    notlar.append(
                        f"{guncel_urun_fiyati['urun_adi']} icin {guncel_urun_fiyati['sezon']} sezonu "
                        f"TMO alim fiyati ton basina ₺{guncel_urun_fiyati['alim_fiyati_ton']:,.0f} "
                        f"(destekler dahil yaklasik ₺{guncel_urun_fiyati['destekli_gelir_ton']:,.0f}). "
                        f"Bu, urununuzu satabileceginiz guncel resmi taban fiyattir - piyasada bundan "
                        f"daha yuksek teklif de alabilirsiniz."
                    )

    guncel_ihracat_fiyati = None
    if sektor == "tarim":
        guncel_ihracat_fiyati = ihracat_fiyati_bul(db, profil.urun_turu)
        if guncel_ihracat_fiyati:
            en_yuksek_kalem = max(guncel_ihracat_fiyati["kalemler"], key=lambda k: k["fiyat_kg"])
            notlar.append(
                f"{guncel_ihracat_fiyati['urun_adi']} için {guncel_ihracat_fiyati['veri_tarihi']} "
                f"tarihli HKS İhracat Fiyat Bülteni'ne göre referans ihracat fiyatı "
                f"₺{en_yuksek_kalem['fiyat_kg']:.2f}/kg ({en_yuksek_kalem['urun_cinsi']}, "
                f"{en_yuksek_kalem['urun_turu']}). Bu, gümrük/ihracat beyanında kullanılan "
                f"resmi bir referans fiyattır, gerçek satış fiyatınız farklı olabilir."
            )

    # Kullanici bir urun_turu girdi ama ne cilek/hal, ne TMO, ne de ihracat
    # bultenimizde bir karsiligi bulunamadiysa, ekranin sessizce hicbir sey
    # gostermemesi yerine bunu ACIKCA belirtiyoruz - boylece her urun secimi
    # gercekten farkli bir ekrana yol aciyor (ya veri kartlari, ya da bu net
    # "henuz veri yok" bildirimi), "hicbir sey degismedi" hissi olusmuyor.
    urun_turu_girildi_mi = bool((profil.urun_turu or "").strip())
    urun_veri_bulundu_mu = bool(guncel_urun_fiyati or guncel_ihracat_fiyati)
    urun_veri_yok_mesaji = None
    if sektor == "tarim" and urun_turu_girildi_mi and not urun_veri_bulundu_mu:
        urun_veri_yok_mesaji = (
            f"'{profil.urun_turu}' için şu an elimizde özel bir fiyat verisi "
            f"(hal, TMO veya ihracat bülteni) yok - şu an çilek (hal, kalite bazlı), "
            f"buğday/arpa (TMO), ~40 ürün (ihracat bülteni) ve HKS Fiyat Detayları "
            f"bülteninden ~150 sebze/meyve türü için gerçek veri sağlıyoruz. Aşağıdaki "
            f"bütçe önerisi yalnızca genel tarım sektörü ortalamalarına dayanıyor."
        )
        notlar.append(urun_veri_yok_mesaji)

    bolgesel_tavsiye = None
    if sektor == "tarim":
        bolgesel_tavsiye = bolgesel_tavsiye_getir(profil.bolge)
        if bolgesel_tavsiye:
            notlar.append(
                f"{bolgesel_tavsiye['bolge_adi']}'nde öne çıkan tarımsal üretim alanları: "
                f"{', '.join(bolgesel_tavsiye['one_cikan_urunler'])}. {bolgesel_tavsiye['tavsiye']}"
            )

    ciro = profil.yillik_ciro
    giderler = profil.giderler or {}

    stok_min = round(ciro * benchmark.stok_maliyeti_oran_min * kategori_carpani, 2)
    stok_max = round(ciro * benchmark.stok_maliyeti_oran_max * kategori_carpani, 2)
    reklam_min = round(ciro * benchmark.reklam_oran_min, 2)
    reklam_max = round(ciro * benchmark.reklam_oran_max, 2)

    kurulus_gideri = giderler.get("kurulus") if profil.ilk_yil_mi else None

    if profil.ilk_yil_mi:
        if kurulus_gideri:
            notlar.append(
                f"İlk yil / kurulus yili isaretlendi: belirttiginiz ₺{kurulus_gideri:,.0f} kurulus "
                f"gideri (arazi hazirligi, sera, ekipman vb.) tek seferliktir; asagidaki "
                f"karsilastirma bu tutar dusulerek yapildi, boylece duzenli isletme "
                f"gideriniz sektor ortalamasiyla daha adil kiyaslanir."
            )
        else:
            notlar.append(
                "İlk yil / kurulus yili isaretlendi ama kurulus gideri belirtilmedi: "
                "asagidaki oranlar sektordeki olgun/surekli isletmelerin ortalamasidir. "
                "Arazi hazirligi, sera kurulumu, ekipman alimi gibi tek seferlik "
                "yatirimlariniz varsa bunlari ayri girerseniz karsilastirma daha adil olur."
            )

    mevcut_stok_gideri = giderler.get("stok")
    mevcut_reklam_gideri = giderler.get("reklam")

    gider_durumu = None  # "altinda" | "uzerinde" | "uygun"
    gider_sapma_yuzdesi = None  # sektor araliginin orta noktasina gore % sapma

    mevcut_toplam = giderler.get("toplam")
    if mevcut_toplam is not None and giderler.get("stok") is None and giderler.get("reklam") is None:
        duzenli_gider = mevcut_toplam - (kurulus_gideri or 0)
        toplam_min = stok_min + reklam_min
        toplam_max = stok_max + reklam_max
        toplam_orta = (toplam_min + toplam_max) / 2
        etiket = "duzenli isletme gideriniz (kurulus gideri dusuldukten sonra)" if kurulus_gideri else "toplam gideriniz"

        gider_sapma_yuzdesi = round((duzenli_gider - toplam_orta) / toplam_orta * 100, 1) if toplam_orta else None
        sapma_ifadesi = f" (sektor ortalamasindan %{abs(gider_sapma_yuzdesi):.0f} {'dusuk' if gider_sapma_yuzdesi < 0 else 'yuksek'})" if gider_sapma_yuzdesi is not None else ""

        if duzenli_gider < toplam_min:
            gider_durumu = "altinda"
            notlar.append(
                f"Girdiginiz {etiket} (₺{duzenli_gider:,.0f}), sektor ortalamasi olan "
                f"₺{toplam_min:,.0f}-₺{toplam_max:,.0f} araliginin altinda{sapma_ifadesi}; stok/reklam ayrimini "
                f"girerseniz daha net bir karsilastirma yapabiliriz."
            )
        elif duzenli_gider > toplam_max:
            gider_durumu = "uzerinde"
            notlar.append(
                f"Girdiginiz {etiket} (₺{duzenli_gider:,.0f}), sektor ortalamasi olan "
                f"₺{toplam_min:,.0f}-₺{toplam_max:,.0f} araliginin uzerinde{sapma_ifadesi}."
            )
        else:
            gider_durumu = "uygun"
            notlar.append(
                f"Girdiginiz {etiket} (₺{duzenli_gider:,.0f}), sektor ortalamasi olan "
                f"₺{toplam_min:,.0f}-₺{toplam_max:,.0f} araligina uygun{sapma_ifadesi}."
            )

        # Ayri stok/reklam girilmediginde, "mevcut gideriniz" kartlarinda hala
        # eski toplam (kurulus dahil) tutar gorunmesin diye duzeltilmis gideri
        # stok karsilastirmasi icin kullaniyoruz (reklam ayrimi bilinmiyor).
        mevcut_stok_gideri = duzenli_gider

    # Analist Onerileri: yukarida hesaplanan degerlerden turetilen, madde
    # madde eyleme donuk tavsiyeler. Bunlar da muhasebe/yatirim tavsiyesi
    # degildir, sektor ortalamalarindan turetilen genel yol gostericilerdir.
    analist_onerileri: list[str] = []

    if gider_durumu == "altinda":
        sapma_metni = f" (sektor ortalamasinin %{abs(gider_sapma_yuzdesi):.0f} altinda)" if gider_sapma_yuzdesi is not None else ""
        analist_onerileri.append(
            f"Gideriniz sektor ortalamasinin altinda{sapma_metni}. Bu iyi bir maliyet yonetimi "
            "olabilecegi gibi, yetersiz yatirim/kapasite kullanimi anlamina da "
            "gelebilir - buyume hedefiniz varsa KOSGEB/TKDK yatirim destekleri "
            "icin 'Uygun Destekleri Bul' bolumunu kontrol edin."
        )
    elif gider_durumu == "uzerinde":
        sapma_metni = f" (sektor ortalamasinin %{abs(gider_sapma_yuzdesi):.0f} uzerinde)" if gider_sapma_yuzdesi is not None else ""
        analist_onerileri.append(
            f"Gideriniz sektor ortalamasinin uzerinde{sapma_metni}. Maliyet kalemlerinizi "
            "(ozellikle en hizli artan girdinizi) tedarikci karsilastirmasi "
            "yaparak veya toplu alim/kooperatif secenekleriyle gozden gecirmenizi "
            "oneririz."
        )

    if en_yuksek_artan_girdi:
        analist_onerileri.append(
            f"En hizli artan gideriniz {en_yuksek_artan_girdi['etiket']} "
            f"(son 1 yilda %{en_yuksek_artan_girdi['artis']:.1f}). Bu kalem icin "
            f"one alarak fiyat kilitleme (sozlesmeli tedarik) veya kooperatif "
            f"uzerinden toplu alim gibi yontemleri arastirmanizi oneririz."
        )

    if profil.ilk_yil_mi and kurulus_gideri:
        analist_onerileri.append(
            f"İlk yil kurulus yatiriminiz (₺{kurulus_gideri:,.0f}) tek seferliktir. "
            f"Onumuzdeki yil sadece duzenli isletme giderinizi takip ederek "
            f"sektor ortalamasiyla daha saglikli bir kiyaslama yapabilirsiniz."
        )

    if guncel_urun_fiyati and guncel_urun_fiyati.get("kaynak_tipi") == "hal_cilek":
        en_iyi = max(guncel_urun_fiyati["kalite_bazli_fiyatlar"], key=lambda k: k["fiyat_kg"])
        analist_onerileri.append(
            f"Çilek için hal ortalaması en yüksek {en_iyi['kalite_sinifi'].replace('_', ' ').title()} "
            f"kalitesinde ₺{en_iyi['fiyat_kg']:.2f}/kg. Zincir market/ihracat kanalı gibi "
            f"alternatif satış kanallarının fiyatını da bu hal ortalamasıyla karşılaştırıp "
            f"en yüksek getiriyi sağlayan kanalı tercih edin."
        )
    elif guncel_urun_fiyati and guncel_urun_fiyati.get("kaynak_tipi") == "hal_genel":
        en_iyi = max(guncel_urun_fiyati["kalemler"], key=lambda k: k["fiyat_kg"])
        analist_onerileri.append(
            f"{guncel_urun_fiyati['urun_adi']} için hal ortalaması en yüksek "
            f"₺{en_iyi['fiyat_kg']:.2f}/kg ({en_iyi['urun_cinsi']}). Zincir market/ihracat "
            f"kanalı gibi alternatif satış kanallarının fiyatını da bu hal ortalamasıyla "
            f"karşılaştırıp en yüksek getiriyi sağlayan kanalı tercih edin."
        )
    elif guncel_urun_fiyati:
        analist_onerileri.append(
            f"{guncel_urun_fiyati['urun_adi']} icin TMO'ya satarsaniz ton basina "
            f"₺{guncel_urun_fiyati['alim_fiyati_ton']:,.0f} garanti taban fiyati var; "
            f"ozel sektore/tuccara satmadan once bu fiyati bir referans olarak kullanin "
            f"ve teklifleri karsilastirin."
        )

    if guncel_ihracat_fiyati:
        en_yuksek_kalem = max(guncel_ihracat_fiyati["kalemler"], key=lambda k: k["fiyat_kg"])
        analist_onerileri.append(
            f"{guncel_ihracat_fiyati['urun_adi']} için ihracat referans fiyatı "
            f"₺{en_yuksek_kalem['fiyat_kg']:.2f}/kg. İhracat kanalını değerlendiriyorsanız "
            f"bu fiyatı yurt içi hal/market fiyatınızla karşılaştırıp hangi kanalın daha "
            f"kazançlı olduğunu görebilirsiniz."
        )

    if net_kar_orani is not None:
        beklenen_kar = ciro * net_kar_orani
        analist_onerileri.append(
            f"Sektor ortalamasina gore cironuzdan beklenen net kar yaklasik "
            f"₺{beklenen_kar:,.0f} (%{net_kar_orani * 100:.1f}). "
            f"Gerceklesen karinizi bu referansla kiyaslayarak isletmenizin "
            f"sektore gore performansini degerlendirebilirsiniz."
        )

    return ButceOnerisi(
        sektor=sektor,
        yillik_ciro=ciro,
        stok_maliyeti_min=stok_min,
        stok_maliyeti_max=stok_max,
        reklam_butcesi_min=reklam_min,
        reklam_butcesi_max=reklam_max,
        mevcut_stok_gideri=mevcut_stok_gideri,
        mevcut_reklam_gideri=mevcut_reklam_gideri,
        mevcut_toplam_gider=mevcut_toplam,
        ilk_yil_kurulum_gideri=kurulus_gideri,
        yillik_tufe=tufe,
        sektor_net_kar_orani=net_kar_orani,
        tarim_girdi_enflasyonu=tarim_girdi_enflasyonu,
        en_yuksek_artan_girdi=en_yuksek_artan_girdi,
        guncel_urun_fiyati=guncel_urun_fiyati,
        guncel_ihracat_fiyati=guncel_ihracat_fiyati,
        tarim_dis_ticaret=tarim_dis_ticaret,
        urun_veri_yok_mesaji=urun_veri_yok_mesaji,
        bolgesel_tavsiye=bolgesel_tavsiye,
        gider_sapma_yuzdesi=gider_sapma_yuzdesi,
        notlar=notlar,
        analist_onerileri=analist_onerileri,
    )
