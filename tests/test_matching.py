"""
Eslesme motoru regresyon testleri.

test_budget.py ile ayni prensip: her test uretimde bulunmus gercek bir
hatayi kilitler.
"""
import pytest

from app.matching import esles, toplam_tahmini_destek, tutari_tahmini_hesapla
from app.models import FinancialProfile, Tesvik


def _tesvik(**kw):
    """Testlerde tekrar eden zorunlu alanlari dolduran yardimci."""
    varsayilan = dict(
        kurum="KOSGEB",
        baslik="Test Programi",
        ozet="ozet",
        detay="detay",
        kaynak_url=f"https://example.test/{kw.get('baslik', 'x')}",
        uygunluk_kriterleri={"sektorler": ["genel"]},
    )
    varsayilan.update(kw)
    return Tesvik(**varsayilan)


def test_kapali_program_onerilmez(db_session):
    """HATA: sistem kapandigini BILDIGI programlari oneriyordu. Imalat
    profiline gelen ilk 20 onerinin 5'i kapali programdi (2021 Nefes
    Kredisi, 6 Subat paketleri) - kullanici arayip 'bu bitti' cevabi
    aliyordu."""
    db_session.add_all([
        _tesvik(baslik="Kapali Program", kaynak_url="https://t/1", aktif_mi=False),
        _tesvik(baslik="Acik Program", kaynak_url="https://t/2", aktif_mi=True),
        _tesvik(baslik="Belirsiz Program", kaynak_url="https://t/3", aktif_mi=None),
    ])
    db_session.commit()

    sonuclar = esles(FinancialProfile(sektor="imalat", yillik_ciro=1_000_000), db_session)
    basliklar = [s.tesvik.baslik for s in sonuclar]

    assert "Kapali Program" not in basliklar
    assert "Acik Program" in basliklar
    assert "Belirsiz Program" in basliklar


def test_dogrulanmis_acik_program_esit_skorda_one_gecer(db_session):
    db_session.add_all([
        _tesvik(baslik="Zzz Belirsiz", kaynak_url="https://t/1", aktif_mi=None),
        _tesvik(baslik="Zzz Acik", kaynak_url="https://t/2", aktif_mi=True),
    ])
    db_session.commit()

    sonuclar = esles(FinancialProfile(sektor="imalat", yillik_ciro=1_000_000), db_session)
    assert sonuclar[0].tesvik.baslik == "Zzz Acik"


def test_uygunluk_kriterleri_olmayan_kayit_gorunmez_kalmaz_uyarisi(db_session):
    """HATA: uygunluk_kriterleri doldurulmadan eklenen 6 kayit (e-ihracat
    destekleri dahil) HICBIR profile eslesmiyordu - sessizce gorunmezdi.
    Bu test, o alanin bos birakilmasinin sonucunu acikca belgeler."""
    db_session.add(_tesvik(baslik="Kriteri Olmayan", kaynak_url="https://t/1", uygunluk_kriterleri=None))
    db_session.add(_tesvik(baslik="Kriteri Olan", kaynak_url="https://t/2"))
    db_session.commit()

    basliklar = [s.tesvik.baslik for s in esles(FinancialProfile(sektor="imalat", yillik_ciro=1), db_session)]
    assert "Kriteri Olan" in basliklar
    assert "Kriteri Olmayan" not in basliklar, \
        "uygunluk_kriterleri bos olan kayit eslesmez - yeni kayit eklerken bu alan ZORUNLU"


def test_sektore_ozel_kayit_genel_kayittan_yuksek_skor_alir(db_session):
    db_session.add_all([
        _tesvik(baslik="E-ticarete Ozel", kaynak_url="https://t/1",
                uygunluk_kriterleri={"sektorler": ["e-ticaret", "ihracat"]}),
        _tesvik(baslik="Genel Program", kaynak_url="https://t/2",
                uygunluk_kriterleri={"sektorler": ["genel"]}),
    ])
    db_session.commit()

    sonuclar = esles(FinancialProfile(sektor="e-ticaret", yillik_ciro=1_000_000), db_session)
    skorlar = {s.tesvik.baslik: s.skor for s in sonuclar}
    assert skorlar["E-ticarete Ozel"] > skorlar["Genel Program"]


def test_birim_bazli_tutar_profil_buyuklugu_ile_olceklenir(db_session):
    """HATA: 'Dekar basina 500-2000 TL' gibi BIRIM fiyatlar mutlak tutar
    sanilip oldugu gibi toplaniyordu - 50 dekarlik ciftcinin 25.000 TL'lik
    destegi ekranda 500 TL gorunuyordu."""
    t = _tesvik(
        baslik="Dekar Bazli", kaynak_url="https://t/1",
        tutari_min=500, tutari_max=2000, tutari_hesaplama_kriteri="dekar",
    )
    profil = FinancialProfile(sektor="tarim", yillik_ciro=500_000, arazi_buyuklugu_dekar=50)

    assert tutari_tahmini_hesapla(t, profil) == pytest.approx(50 * 1250)

    # Arazi bilgisi yoksa tahmin uretilmemeli (500 TL gibi yanlis bir sayi yerine).
    assert tutari_tahmini_hesapla(t, FinancialProfile(sektor="tarim", yillik_ciro=1)) is None


def test_kredi_kefaleti_hibe_toplamina_katilmaz(db_session):
    """HATA: KGF'nin kredi KEFALET limitleri (orn. '20.000.000 TL'ye kadar
    kredi') gercek hibelerle toplanip 'toplam tahmini destek' rakamini
    43 milyon TL'ye sisiriyordu. Kredi limiti cepten alinacak para degil."""
    db_session.add_all([
        _tesvik(kurum="KGF", baslik="Kefalet", kaynak_url="https://t/1",
                tesvil_tutari="₺1.000.000 - ₺20.000.000 kredi"),
        _tesvik(kurum="KOSGEB", baslik="Gercek Hibe", kaynak_url="https://t/2",
                tesvil_tutari="₺100.000 - ₺200.000"),
    ])
    db_session.commit()

    profil = FinancialProfile(sektor="imalat", yillik_ciro=1_000_000)
    sonuclar = esles(profil, db_session)
    alt, ust = toplam_tahmini_destek(sonuclar, profil)

    assert ust == pytest.approx(200_000), "kredi limiti hibe toplamina karismamali"
    assert alt == pytest.approx(100_000)


def test_kosgeb_adi_altindaki_kredi_urunu_de_haric_tutulur(db_session):
    """Kurum etiketi guvenilir degil: bazi kayitlar KOSGEB adina girilmis
    olsa da icerik olarak kredi urunu (metin bazli tespit gerekiyor)."""
    db_session.add(_tesvik(kurum="KOSGEB", baslik="Aslinda Kredi", kaynak_url="https://t/1",
                           tesvil_tutari="₺20.000.000 (kredi limiti)"))
    db_session.commit()

    profil = FinancialProfile(sektor="imalat", yillik_ciro=1_000_000)
    alt, ust = toplam_tahmini_destek(esles(profil, db_session), profil)
    assert (alt, ust) == (0.0, 0.0)
