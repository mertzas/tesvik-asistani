"""'girisim' ihtiyaç türü: şirketsiz girişim sorusunda BiGG/KOSGEB Girişimci gelmeli,
ekosistem programları (uygulayıcı kuruluş, girişim sermayesi, kapasite artırma) gelmemeli."""
import pytest
from sqlalchemy.orm import sessionmaker

from app import rag
from app.ihtiyac import program_ihtiyaclari, soru_ihtiyaclari
from app.models import FinancialProfile, Tesvik

TUBITAK = "https://tubitak.gov.tr/tr/destekler"


@pytest.mark.parametrize("soru,beklenen", [
    ("Henüz şirket kurmadık, prototipimiz var, hangi hibeler var?", ["girisim"]),
    ("Yazılım girişimim için BiGG'e başvurabilir miyim?", ["girisim"]),
    ("startup için tohum yatırımı desteği", ["girisim"]),
    ("buğday için dekar desteği", []),
])
def test_soru_girisim_ihtiyaci(soru, beklenen):
    assert [x for x in soru_ihtiyaclari(soru) if x == "girisim"] == beklenen


def _t(id, baslik, url, kurum="TUBITAK", aktif=True, kriter=None):
    return Tesvik(id=id, kurum=kurum, baslik=baslik, ozet="o", detay="d", aktif_mi=aktif, kaynak_url=url,
                  uygunluk_kriterleri=kriter or {"sektorler": ["genel", "arge"]})


@pytest.fixture
def veri(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    kayitlar = [
        _t(174, "1512 - Girişimcilik Destek Programı (BiGG - Bireysel Genç Girişim)", f"{TUBITAK}/sanayi/1512"),
        _t(49, "1812 - Yatırım Tabanlı Girişimcilik Destek Programı (BiGG Yatırım)", f"{TUBITAK}/sanayi/1812"),
        _t(1, "Girişimci Destek Programı", "https://t/1", kurum="KOSGEB", aktif=None),
        _t(35, "1612 - BiGG - 1.Aşama Uygulayıcı Kuruluş Çağrısı", f"{TUBITAK}/sanayi/1612"),
        _t(23, "1514 - Girişim Sermayesi Destekleme Programı (Tech-InvesTR)", f"{TUBITAK}/sanayi/1514"),
        _t(40, "1601 - Yenilik Girişimcilik Alanlarında Kapasite Artırılmasına Yönelik D.P.", f"{TUBITAK}/sanayi/1601"),
        _t(44, "1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç Destek Programı", f"{TUBITAK}/sanayi/1507"),
    ]
    db_session.add_all(kayitlar)
    db_session.commit()
    return kayitlar


def test_program_siniflamasi(veri):
    p = {t.id: program_ihtiyaclari(t) for t in veri}
    assert p[174] == {"girisim"} and p[49] == {"girisim"} and "girisim" in p[1]
    assert "girisim" not in p[35] and "girisim" not in p[23] and "girisim" not in p[40]
    assert p[44] == {"arge"}


def test_sirketsiz_girisim_sorusunda_bigg_gelir_ekosistem_programlari_gelmez(veri):
    profil = FinancialProfile(sektor="arge", sirket_turu="yok", trl=4)
    sonuc = [t.id for t in rag.retrieve(
        "Prototipimizi yaptık, henüz şirket kurmadık; hangi hibelere başvurabiliriz?", limit=4, profil_kaydi=profil)]
    assert 174 in sonuc and 49 in sonuc
    assert not {35, 23, 40} & set(sonuc)
