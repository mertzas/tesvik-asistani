"""Denetim 2 / Aşama B gerçek kullanıcı yolculuğu bulguları (2026-10-07):
- şirketsiz girişimciye SGK/İŞKUR işveren teşviki geliyordu;
- hedefi ihracat olan imalatçının sorusunda E-İhracat kayıtları danışman bağlamına girmiyordu;
- "50 baş süt ineği" sorusunda Organik Tarım, "traktör ve mibzer" sorusunda Sera 1. geliyordu."""
import pytest
from sqlalchemy.orm import sessionmaker

from app import rag
from app.matching import esles, uygunluk_engeli
from app.models import FinancialProfile, Tesvik
from app.urun_sektor_anahtarlari import urun_turunden_tarim_kategorisi


def _t(id, kurum, baslik, sektorler, alt_kategori=None, ozet="o"):
    uk = {"sektorler": list(sektorler)}
    if alt_kategori:
        uk["alt_kategori"] = alt_kategori
    return Tesvik(id=id, kurum=kurum, baslik=baslik, ozet=ozet, detay="d", aktif_mi=True,
                  kaynak_url=f"https://t/{id}", uygunluk_kriterleri=uk, basvuru_sartlari=[])


@pytest.fixture
def veri(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    db_session.add_all([
        _t(185, "SGK / İŞKUR", "Kadın, Genç ve MYB İstihdamı Teşviki (4447 geçici 10)", ["genel"], ozet="istihdam işe alım SGK"),
        _t(174, "TUBITAK", "1512 - Girişimcilik Destek Programı (BiGG)", ["genel", "arge"], ozet="şirketi olmayan girişimci yazılım fikir"),
        _t(162, "Ticaret Bakanlığı", "E-İhracat Destekleri (5986 Sayılı Karar)", ["e-ticaret", "ihracat"], ozet="yurt dışı pazaryeri ihracat"),
        _t(180, "Sanayi ve Teknoloji Bakanlığı", "Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)", ["genel", "imalat"], ozet="yatırım teşvik belgesi ihracat"),
        _t(76, "Tarım Bakanlığı", "Hayvancılık Destekleri", ["tarim"], "hayvancilik", ozet="büyükbaş küçükbaş destek"),
        _t(77, "Tarım Bakanlığı", "Organik Tarım Destekleri", ["tarim"], "organik", ozet="organik tarım süt ineği destek"),
        _t(79, "Tarım Bakanlığı", "Sera/Örtüaltı Tarım Destekleri", ["tarim"], "sera", ozet="sera traktör mibzer destek"),
        _t(78, "Tarım Bakanlığı", "KKYP Makine Parkı Hibeleri", ["tarim"], "makinelestirme", ozet="makine ekipman hibe"),
    ])
    db_session.commit()


def test_sgk_iskur_isveren_tesviki_sirketsiz_girisimciye_gelmez(veri, db_session):
    yok = FinancialProfile(sektor="arge", bolge="Ankara", sirket_turu="yok", trl=4, nace_kodu="62.01")
    assert "işletme" in uygunluk_engeli(db_session.get(Tesvik, 185), yok)
    ids = [s.tesvik.id for s in esles(yok, db_session)]
    assert 174 in ids and 185 not in ids
    assert 185 not in [t.id for t in rag.retrieve("şirketim yok hangi hibeler", limit=8, profil_kaydi=yok)]
    ltd = FinancialProfile(sektor="imalat", sirket_turu="limited", hedefler=["istihdam"])
    assert uygunluk_engeli(db_session.get(Tesvik, 185), ltd) is None


def test_hedefi_ihracat_olan_imalatci_eihracat_kaydini_baglamda_gorur(veri, db_session):
    imalat = FinancialProfile(sektor="imalat", bolge="İzmir", calisan_sayisi=12, yillik_ciro=60e6,
                              nace_kodu="13.20", sirket_turu="limited", hedefler=["yatirim", "ihracat"])
    ids = [t.id for t in rag.retrieve("Almanya'ya ihracata başlayacağız, hangi destekler var?", limit=8, profil_kaydi=imalat)]
    assert 162 in ids
    yatirim = FinancialProfile(sektor="imalat", sirket_turu="limited", hedefler=["yatirim"])
    assert 162 not in [t.id for t in rag.retrieve("ihracat desteği", limit=8, profil_kaydi=yatirim)], \
        "hedefinde ihracat yoksa e-ticaret/ihracat etiketli kayıt sektör filtresine takılır"


@pytest.mark.parametrize("metin,beklenen", [
    ("50 baş süt ineği için destek", "hayvancilik"),
    ("traktör ve mibzer almak istiyorum", "makinelestirme"),
    ("damla sulama sistemi kuracağım", "sulama"),
    ("180 dekar buğday", "tahil_baklagil"),
])
def test_soru_metninden_tarim_kategorisi(metin, beklenen):
    assert urun_turunden_tarim_kategorisi(metin) == beklenen


def test_tarim_sorusunda_alt_kategori_uyumlu_kayit_one_gecer(veri, db_session):
    ciftci = FinancialProfile(sektor="tarim", bolge="Konya", calisan_sayisi=3, urun_turu="buğday")
    ids = [t.id for t in rag.retrieve("Hayvancılığa geçmek istiyorum, 50 baş süt ineği için destek var mı?", limit=4, profil_kaydi=ciftci)]
    assert ids[0] == 76, ids
    ids = [t.id for t in rag.retrieve("Traktör ve mibzer almak istiyorum, hibe var mı?", limit=4, profil_kaydi=ciftci)]
    assert ids[0] == 78, ids


def test_tarim_disi_soruda_alt_kategori_bonusu_yok(veri, db_session):
    imalat = FinancialProfile(sektor="imalat", sirket_turu="limited", hedefler=["yatirim"])
    ids = [t.id for t in rag.retrieve("makine yatırımı için teşvik belgesi", limit=4, profil_kaydi=imalat)]
    assert 78 not in ids and 180 in ids
