"""app/veri_tazeligi.py testleri.

Kritik nokta: esikler kaynaga GORE farkli. TCMB sektor bilancolari yilda bir
yayinlandigi icin 69 gunluk veri "taze"; TUIK enflasyonu ayda bir
aciklandigi icin ayni 69 gun "eskiyor" olmali. Bu ayrimi bir testle
sabitliyoruz, yoksa ileride "hepsine 30 gun verelim" diye sadelestirilip
yanlis uyari uretmeye baslar.
"""
from datetime import date, datetime, timedelta, timezone

from app.models import HalFiyati, MacroIndicator, SectorBenchmark
from app.veri_tazeligi import (
    KAYNAKLAR,
    genel_durum,
    kaynak_tazeligi,
    tazelik_raporu,
)


def _gun_once(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def test_veri_yoksa_veri_yok_durumu(db_session):
    t = kaynak_tazeligi(db_session, "makro")
    assert t is not None
    assert t.durum == "veri_yok"
    assert t.kayit_sayisi == 0
    assert t.sorunlu_mu is True


def test_taze_veri_uyari_uretmez(db_session):
    db_session.add(MacroIndicator(
        anahtar="yillik_tufe", deger=30.6, birim="%",
        guncelleme_tarihi=_gun_once(3),
    ))
    db_session.commit()

    t = kaynak_tazeligi(db_session, "makro")
    assert t.durum == "taze"
    assert t.uyari is None
    assert t.yas_gun == 3


def test_ayni_yas_kaynaga_gore_farkli_degerlendirilir(db_session):
    """69 gun: TUIK icin eski, TCMB sektor bilancosu icin normal."""
    yas = 69
    db_session.add(MacroIndicator(
        anahtar="yillik_tufe", deger=30.6, guncelleme_tarihi=_gun_once(yas),
    ))
    db_session.add(SectorBenchmark(
        sektor="tarim", net_kar_orani=0.12, guncelleme_tarihi=_gun_once(yas),
    ))
    db_session.commit()

    makro = kaynak_tazeligi(db_session, "makro")
    benchmark = kaynak_tazeligi(db_session, "sektor_benchmark")

    assert makro.yas_gun == benchmark.yas_gun == yas
    assert makro.durum == "eskiyor"
    assert benchmark.durum == "taze"


def test_esigi_asan_veri_bayat_sayilir(db_session):
    db_session.add(MacroIndicator(
        anahtar="yillik_tufe", deger=30.6, guncelleme_tarihi=_gun_once(200),
    ))
    db_session.commit()

    t = kaynak_tazeligi(db_session, "makro")
    assert t.durum == "bayat"
    assert t.sorunlu_mu is True
    assert "200" in t.uyari


def test_date_sutunu_da_okunabiliyor(db_session):
    """hal_fiyatlari.tarih bir Date, DateTime degil - _yas_gun ikisini de
    karsilamali, yoksa hal verisi hep 'veri_yok' gorunurdu."""
    db_session.add(HalFiyati(
        urun_adi="DOMATES", tarih=date.today() - timedelta(days=2), fiyat_kg=25.0,
    ))
    db_session.commit()

    t = kaynak_tazeligi(db_session, "hal_fiyatlari")
    assert t.durum == "taze"
    assert t.yas_gun == 2
    assert t.son_guncelleme is not None


def test_rapor_tum_kaynaklari_kapsar_ve_sorunlulari_one_alir(db_session):
    db_session.add(MacroIndicator(
        anahtar="yillik_tufe", deger=30.6, guncelleme_tarihi=_gun_once(2),
    ))
    db_session.commit()

    rapor = tazelik_raporu(db_session)
    assert len(rapor) == len(KAYNAKLAR)
    # Veri girilen tek kaynak taze; digerleri bos -> sorunlular basta olmali.
    assert rapor[0].durum == "veri_yok"
    assert rapor[-1].anahtar == "makro"
    assert genel_durum(rapor) == "veri_yok"


def test_bilinmeyen_kaynak_none_doner(db_session):
    assert kaynak_tazeligi(db_session, "olmayan_kaynak") is None


def test_tazeleme_komutlari_gercek_modulleri_gosterir():
    """Komutlar kullaniciya "bunu calistir" diye sunuluyor; var olmayan bir
    modul adi yazmak sessiz bir yalan olurdu."""
    import importlib

    for k in KAYNAKLAR:
        assert k.tazeleme_komutu, f"{k.anahtar} icin tazeleme komutu yok"
        modul = k.tazeleme_komutu.split()[-1]
        importlib.import_module(modul)
