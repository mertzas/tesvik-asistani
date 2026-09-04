"""
Butce motoru regresyon testleri.

Bu dosyadaki her test, uretimde GERCEKTEN bulunmus ve duzeltilmis bir
hatayi kilitler. Hicbiri teorik degil - hepsi kullaniciya yanlis rakam
gosteren canli hatalardi ve hicbir test olmadigi icin aylarca fark
edilmediler. Java/Spring Boot portu yapilirken bu testlerin esdegerleri
once yazilmali, sonra tasima yapilmalidir.
"""
import pytest

from app.budget import hesapla, STOK_ORAN_TAVANI
from app.models import FinancialProfile, MacroIndicator, SectorBenchmark


@pytest.fixture
def benchmark_seed(db_session):
    """EVDS'ten gelen gercek oranlara yakin bir benchmark seti + TUFE."""
    db_session.add_all([
        SectorBenchmark(
            sektor="tarim",
            stok_maliyeti_oran_min=0.663, stok_maliyeti_oran_max=0.897,
            reklam_oran_min=0.0201, reklam_oran_max=0.0271,
            net_kar_orani=0.058,
        ),
        SectorBenchmark(
            sektor="e-ticaret",
            stok_maliyeti_oran_min=0.7097, stok_maliyeti_oran_max=0.9602,
            reklam_oran_min=0.0173, reklam_oran_max=0.0235,
            net_kar_orani=0.022,
        ),
        SectorBenchmark(
            sektor="genel",
            stok_maliyeti_oran_min=0.646, stok_maliyeti_oran_max=0.874,
            reklam_oran_min=0.0218, reklam_oran_max=0.0294,
            net_kar_orani=0.044,
        ),
    ])
    db_session.add_all([
        MacroIndicator(anahtar="yillik_tufe", deger=30.6),
        # Gercek EVDS degerleri: gubre en hizli artan, ama hayvancilik icin
        # ilgili kalem yem'dir.
        MacroIndicator(anahtar="tarim_gubre_yillik_degisim", deger=62.77),
        MacroIndicator(anahtar="tarim_yem_yillik_degisim", deger=37.07),
        MacroIndicator(anahtar="tarim_ilac_yillik_degisim", deger=21.64),
        MacroIndicator(anahtar="tarim_bina_yillik_degisim", deger=27.74),
        MacroIndicator(anahtar="tarim_makine_bakim_yillik_degisim", deger=24.04),
    ])
    db_session.commit()
    return db_session


def test_stok_onerisi_ciroyu_asamaz(benchmark_seed):
    """HATA: hayvancilik carpani (1.3) EVDS max oranina (%89.7) uygulaninca
    stok onerisi cironun %116'sina cikiyordu - yani kullaniciya kazandigindan
    fazlasini stoga ayirmasi oneriliyordu."""
    profil = FinancialProfile(sektor="tarim", tarim_kategori="hayvancilik", yillik_ciro=1_000_000)
    sonuc = hesapla(profil, benchmark_seed)

    assert sonuc.stok_maliyeti_max <= sonuc.yillik_ciro, "stok onerisi ciroyu asiyor"
    assert sonuc.stok_maliyeti_max == pytest.approx(1_000_000 * STOK_ORAN_TAVANI)
    assert any("sınırlandı" in n for n in sonuc.notlar), "kirpma kullaniciya bildirilmeli"


def test_gelecek_yil_projeksiyonu_tufe_ile_olceklenir(benchmark_seed):
    """HATA: 'seneye ne kadar ayirmaliyim' sorusunun cevabi hic yoktu,
    sadece bu yilki aralik gosteriliyordu."""
    profil = FinancialProfile(sektor="e-ticaret", yillik_ciro=500_000)
    sonuc = hesapla(profil, benchmark_seed)

    assert sonuc.gelecek_yil_stok_min is not None
    beklenen = sonuc.stok_maliyeti_max * 1.306
    assert sonuc.gelecek_yil_stok_max == pytest.approx(beklenen, rel=1e-3)
    assert sonuc.gelecek_yil_reklam_max > sonuc.reklam_butcesi_max


def test_kurulus_gideri_toplamdan_buyukse_negatif_gider_gosterilmez(benchmark_seed):
    """HATA: kurulus gideri toplamdan buyuk girilince ekranda
    '-₺200.000 gideriniz' gibi negatif bir rakam gosteriliyordu."""
    profil = FinancialProfile(
        sektor="tarim", yillik_ciro=1_000_000, ilk_yil_mi=True,
        giderler={"toplam": 400_000, "kurulus": 600_000},
    )
    sonuc = hesapla(profil, benchmark_seed)

    assert sonuc.mevcut_stok_gideri is None or sonuc.mevcut_stok_gideri >= 0
    assert sonuc.gider_sapma_yuzdesi is None, "gecersiz veriyle kiyas yapilmamali"
    assert any("hatalı girilmiş" in n for n in sonuc.notlar)


def test_en_hizli_artan_girdi_kategoriye_gore_secilir(benchmark_seed):
    """HATA: gubre en hizli artan girdi oldugu icin (%62.8) hayvancilik
    yapan kullaniciya da 'en hizli artan gideriniz: Gubre' deniyordu;
    oysa hayvancilikta ilgili kalem yem (%37.1)."""
    hayvancilik = FinancialProfile(sektor="tarim", tarim_kategori="hayvancilik", yillik_ciro=1_000_000)
    sonuc = hesapla(hayvancilik, benchmark_seed)
    assert sonuc.en_yuksek_artan_girdi["kalem"] == "yem"

    # Tum veriler yine de gorunur kalmali - sadece ONERI daraliyor.
    assert "gubre" in sonuc.tarim_girdi_enflasyonu

    # Kategori secilmemisse eski davranis korunur (genel havuzdan en yuksek).
    genel = FinancialProfile(sektor="tarim", yillik_ciro=1_000_000)
    assert hesapla(genel, benchmark_seed).en_yuksek_artan_girdi["kalem"] == "gubre"


def test_ayri_stok_reklam_girisi_de_kiyaslanir(benchmark_seed):
    """HATA: sistem 'stok/reklam ayrimini girerseniz daha net kiyas
    yapariz' diyordu ama ayri girildiginde HIC kiyas yapilmiyordu -
    kiyas sadece tek 'toplam' rakami girilince calisiyordu."""
    profil = FinancialProfile(
        sektor="e-ticaret", yillik_ciro=1_000_000,
        giderler={"stok": 900_000, "reklam": 15_000},
    )
    sonuc = hesapla(profil, benchmark_seed)

    assert any("Stok gideriniz" in n for n in sonuc.notlar)
    assert any("Reklam gideriniz" in n for n in sonuc.notlar)


def test_stok_uygun_reklam_dusukse_genel_durum_uygun_kalmaz(benchmark_seed):
    """HATA (yukaridaki duzeltmenin kendi hatasi): stok 'uygun' cikinca
    reklamin 'altinda' olmasi genel gider_durumu'na hic yansimiyordu,
    dolayisiyla analist onerisi bu sapmayi hic gormuyordu."""
    profil = FinancialProfile(
        sektor="e-ticaret", yillik_ciro=1_000_000,
        giderler={"stok": 900_000, "reklam": 15_000},  # stok uygun, reklam dusuk
    )
    sonuc = hesapla(profil, benchmark_seed)

    assert any("altinda" in o or "altında" in o for o in sonuc.analist_onerileri), \
        "reklam sapmasi analist onerisine yansimali"


def test_sifir_ciro_reddedilir(benchmark_seed):
    profil = FinancialProfile(sektor="tarim", yillik_ciro=0)
    with pytest.raises(ValueError):
        hesapla(profil, benchmark_seed)
