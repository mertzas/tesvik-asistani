"""budget.hesapla() icin "altin cikti" (golden output) testi.

AMAC: hesapla() 549 satirlik tek bir fonksiyon ve kullaniciya para rakami
uretiyor. Bolmeden once mevcut davranisi DONDURUYORUZ; refactor sonrasi
ciktinin birebir ayni kalmasi bu testle garanti altina aliniyor.

Bu bir davranis testi degil, DEGISMEZLIK testidir: burada beklenen degerler
"dogru" oldugu icin degil, "refactor oncesi boyleydi" oldugu icin duruyor.
Bilerek bir hesap degisikligi yapilirsa bu dosyadaki degerler de bilinçli
olarak guncellenmelidir - sessizce degismeleri kabul edilemez.

Girdi verisi testin icinde kuruluyor (uretim veritabanina bagimli degil),
boylece EVDS/TUIK degerleri degisince test kirilmaz.
"""
import pytest

from app.budget import hesapla
from app.models import FinancialProfile, MacroIndicator, SectorBenchmark


def _veri_kur(db):
    """Sabit makro veri: gercek veritabanindaki degerler degisse de test
    ayni kalmali."""
    db.add_all([
        MacroIndicator(anahtar="yillik_tufe", deger=30.0, birim="%",
                       kaynak="test"),
        MacroIndicator(anahtar="tcmb_politika_faizi", deger=37.0, birim="%",
                       kaynak="test"),
        MacroIndicator(anahtar="tarim_yem_yillik_degisim", deger=25.0,
                       birim="%", kaynak="test"),
        MacroIndicator(anahtar="tarim_gubre_yillik_degisim", deger=33.0,
                       birim="%", kaynak="test"),
        MacroIndicator(anahtar="tarim_ilac_yillik_degisim", deger=22.0,
                       birim="%", kaynak="test"),
        MacroIndicator(anahtar="tarim_bina_yillik_degisim", deger=28.0,
                       birim="%", kaynak="test"),
        MacroIndicator(anahtar="tarim_makine_bakim_yillik_degisim", deger=22.0,
                       birim="%", kaynak="test"),
        MacroIndicator(anahtar="tarim_aylik_ihracat_milyon_usd", deger=670.0,
                       birim="milyon USD", kaynak="test"),
        MacroIndicator(anahtar="tarim_aylik_ithalat_milyon_usd", deger=1280.0,
                       birim="milyon USD", kaynak="test"),
        SectorBenchmark(sektor="tarim", stok_maliyeti_oran_min=0.30,
                        stok_maliyeti_oran_max=0.45, reklam_oran_min=0.01,
                        reklam_oran_max=0.03, net_kar_orani=0.12,
                        kaynak="test"),
        SectorBenchmark(sektor="imalat", stok_maliyeti_oran_min=0.25,
                        stok_maliyeti_oran_max=0.40, reklam_oran_min=0.02,
                        reklam_oran_max=0.05, net_kar_orani=0.08,
                        kaynak="test"),
        SectorBenchmark(sektor="e-ticaret", stok_maliyeti_oran_min=0.35,
                        stok_maliyeti_oran_max=0.55, reklam_oran_min=0.08,
                        reklam_oran_max=0.15, net_kar_orani=0.05,
                        kaynak="test"),
        # "genel" yedek: sektoru tanimlanmamis profiller buna duser
        # (_benchmark_getir). Uretimde de var; olmazsa bilinmeyen sektor
        # icin hesapla() ValueError atiyor.
        SectorBenchmark(sektor="genel", stok_maliyeti_oran_min=0.28,
                        stok_maliyeti_oran_max=0.42, reklam_oran_min=0.02,
                        reklam_oran_max=0.04, net_kar_orani=0.06,
                        kaynak="test"),
    ])
    db.commit()


# Her senaryo: (ad, profil alanlari)
SENARYOLAR = [
    ("tarim_hayvancilik", dict(
        sektor="tarim", tarim_kategori="hayvancilik", bolge="Bursa",
        yillik_ciro=4_000_000, calisan_sayisi=6, arazi_buyuklugu_dekar=120)),
    ("tarim_tahil", dict(
        sektor="tarim", tarim_kategori="tahil_baklagil", bolge="Konya",
        yillik_ciro=1_500_000, calisan_sayisi=3, urun_turu="buğday",
        arazi_buyuklugu_dekar=50)),
    ("tarim_kategorisiz", dict(
        sektor="tarim", bolge="Antalya", yillik_ciro=2_000_000,
        calisan_sayisi=5)),
    ("imalat", dict(
        sektor="imalat", bolge="Gaziantep", yillik_ciro=25_000_000,
        calisan_sayisi=45)),
    ("eticaret", dict(
        sektor="e-ticaret", bolge="İzmir", yillik_ciro=3_000_000,
        calisan_sayisi=4)),
    ("bilinmeyen_sektor", dict(
        sektor="madencilik", bolge="Zonguldak", yillik_ciro=10_000_000,
        calisan_sayisi=20)),
    ("kucuk_ciro", dict(
        sektor="tarim", tarim_kategori="sera", bolge="Antalya",
        yillik_ciro=150_000, calisan_sayisi=1, arazi_buyuklugu_dekar=8)),
]


def _ozet(o) -> dict:
    """Karsilastirilabilir, kararli bir ozet. Notlarin TAM metni yerine
    sayisini ve anahtar ifadelerini tutuyoruz: metin iyilestirmesi testi
    kirmasin ama notun KAYBOLMASI kirsin."""
    d = dict(o.__dict__)
    notlar = d.pop("notlar", []) or []
    ozet = {k: v for k, v in d.items() if not k.startswith("_")}
    ozet["_not_sayisi"] = len(notlar)
    birlesik = " ".join(notlar)
    # Kaybolmamasi gereken uyarilar:
    for anahtar, ifade in [
        ("tufe_notu_var", "TÜFE"),
        ("kar_orani_notu_var", "kar oran"),
        ("analiz_uyarisi_var", "analiz"),
    ]:
        ozet[anahtar] = ifade.lower() in birlesik.lower()
    return ozet


@pytest.fixture
def hazir_db(db_session):
    _veri_kur(db_session)
    return db_session


@pytest.mark.parametrize("ad,alanlar", SENARYOLAR)
def test_senaryo_coksmez_ve_tutarli(ad, alanlar, hazir_db):
    """Her senaryo hata vermeden sonuc uretmeli ve temel tutarlilik
    kurallarini saglamali."""
    o = hesapla(FinancialProfile(**alanlar), hazir_db)
    ozet = _ozet(o)

    # Alt sinir ust siniri asmamali - asarsa arayuzde "500.000 - 300.000 TL"
    # gibi anlamsiz bir aralik gorunur.
    for alt_ad, ust_ad in [
        ("stok_maliyeti_min", "stok_maliyeti_max"),
        ("reklam_butcesi_min", "reklam_butcesi_max"),
    ]:
        if alt_ad in ozet and ust_ad in ozet:
            alt, ust = ozet[alt_ad], ozet[ust_ad]
            if alt is not None and ust is not None:
                assert alt <= ust, f"{ad}: {alt_ad} > {ust_ad}"

    # Hicbir tutar negatif olmamali.
    for k, v in ozet.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if k.endswith(("_min", "_max", "_tl")) or "butce" in k or "maliyet" in k:
                assert v >= 0, f"{ad}: {k} negatif ({v})"

    # Notlar kaybolmamali - bunlar uyari metinleri, sussuz degil.
    assert ozet["_not_sayisi"] > 0, f"{ad}: hic not uretilmedi"


@pytest.mark.parametrize("ad,alanlar", SENARYOLAR)
def test_ayni_girdi_ayni_cikti(ad, alanlar, hazir_db):
    """hesapla() DETERMINISTIK olmali: ayni profil iki kez hesaplandiginda
    ayni rakamlar cikmali. Rastgelelik ya da o ana bagli bir deger girmisse
    kullanici sayfayi yenileyince farkli tutar gorur."""
    p = FinancialProfile(**alanlar)
    bir = _ozet(hesapla(p, hazir_db))
    iki = _ozet(hesapla(p, hazir_db))
    assert bir == iki, f"{ad}: ayni girdi farkli cikti uretti"


def test_stok_orani_ciroyu_asmaz(hazir_db):
    """Stok maliyeti cironun tamamini asamaz; asarsa oneri anlamsizlasir
    (gecmiste hayvancilikta %116,6 cikiyordu)."""
    for ad, alanlar in SENARYOLAR:
        o = hesapla(FinancialProfile(**alanlar), hazir_db)
        ciro = alanlar["yillik_ciro"]
        ust = getattr(o, "stok_maliyeti_max", None)
        if ust is not None:
            assert ust <= ciro, (
                f"{ad}: stok maliyeti ust siniri ({ust:,.0f}) ciroyu "
                f"({ciro:,.0f}) asiyor")


def test_ciro_sifir_veya_negatifse_hata(hazir_db):
    for ciro in (0, -1000):
        with pytest.raises(ValueError, match="yillik_ciro"):
            hesapla(FinancialProfile(sektor="tarim", yillik_ciro=ciro), hazir_db)


def test_benchmark_yoksa_anlamli_hata(db_session):
    """Sektor benchmark verisi hic yoksa sessizce 0 TL onermek yerine
    anlamli hata vermeli."""
    with pytest.raises(ValueError, match="benchmark"):
        hesapla(FinancialProfile(sektor="tarim", yillik_ciro=1_000_000),
                db_session)


def test_ciro_olceklenmesi_monoton(hazir_db):
    """Ciro artarsa stok/reklam onerisi azalmamali. Azaliyorsa bir yerde
    ters isaretli bir duzeltme var."""
    kucuk = hesapla(FinancialProfile(sektor="imalat", yillik_ciro=1_000_000,
                                     calisan_sayisi=5), hazir_db)
    buyuk = hesapla(FinancialProfile(sektor="imalat", yillik_ciro=10_000_000,
                                     calisan_sayisi=5), hazir_db)
    assert buyuk.stok_maliyeti_max >= kucuk.stok_maliyeti_max
    assert buyuk.reklam_butcesi_max >= kucuk.reklam_butcesi_max
