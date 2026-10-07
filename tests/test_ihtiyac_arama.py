"""İhtiyaç türü + profil farkındalıklı arama (app/ihtiyac.py, app/rag.retrieve).

Ölçüm (2026-10-07): "ekmek hattı için makine + ürün geliştirme" sorusunda kelime
araması 5 kaydın 3'ünü tarım programlarına veriyor, 9903 yatırım teşviklerini
hiç getirmiyordu. Testler bu vakayı ve yan etkilerini sabitler.
"""
import pytest

from app import rag
from app.ihtiyac import isletmeye_yonelik_mi, program_ihtiyaclari, soru_ihtiyaclari
from app.models import FinancialProfile, Tesvik

from sqlalchemy.orm import sessionmaker

TUBITAK = "https://tubitak.gov.tr/tr/destekler"


@pytest.fixture
def veri(db_session, monkeypatch):
    # conftest'i yeniden import etmek ayrı bir bellek-içi DB açardı; aynı bağlantıyı kullan.
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    kayitlar = [
        Tesvik(id=78, kurum="Tarım Bakanlığı", baslik="Tarımsal Makineleştirme Destekleri",
               ozet="Tarım makineleri alımı için hibe.", detay="makine alımı traktör",
               kaynak_url="https://t/78", uygunluk_kriterleri={"sektorler": ["tarim"]}),
        Tesvik(id=180, kurum="Sanayi ve Teknoloji Bakanlığı",
               baslik="Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)",
               ozet="Yatırım teşvik belgesi ile vergi indirimi.", detay="d", aktif_mi=True,
               kaynak_url="https://t/180", uygunluk_kriterleri={"sektorler": ["genel", "imalat"]}),
        Tesvik(id=44, kurum="TUBITAK", baslik="1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç Destek Programı",
               ozet="KOBİ Ar-Ge projeleri.", detay="d", aktif_mi=True,
               kaynak_url=f"{TUBITAK}/sanayi/1507", uygunluk_kriterleri={"sektorler": ["arge", "genel"]}),
        Tesvik(id=40, kurum="TUBITAK",
               baslik="1601 - Yenilik Girişimcilik Alanlarında Kapasite Artırılmasına Yönelik D.P.",
               ozet="Ürün geliştirme ve kapasite ekosistemi.", detay="geliştirme kapasite", aktif_mi=True,
               kaynak_url=f"{TUBITAK}/sanayi/1601", uygunluk_kriterleri={"sektorler": ["arge", "genel"]}),
        Tesvik(id=45, kurum="TUBITAK", baslik="2224-A Yurt Dışı Bilimsel Etkinliklere Katılımı Destekleme",
               ozet="Yurt dışı etkinlik katılımı.", detay="yurt dışı fuar etkinlik",
               kaynak_url=f"{TUBITAK}/bilimsel-etkinlik/2224", uygunluk_kriterleri={"sektorler": ["arge"]}),
        Tesvik(id=162, kurum="Ticaret Bakanlığı", baslik="E-İhracat Destekleri (5986 Sayılı Karar)",
               ozet="Yurt dışı pazar ve e-ihracat.", detay="d", aktif_mi=True,
               kaynak_url="https://t/162", uygunluk_kriterleri={"sektorler": ["e-ticaret", "ihracat"]}),
        Tesvik(id=103, kurum="KGF", baslik="YKB Teknoloji Geliştirme Bölgeleri Kredisi",
               ozet="Ürün geliştirme kredisi.", detay="geliştirme makine", aktif_mi=False,
               kaynak_url="https://t/103", uygunluk_kriterleri={"sektorler": ["genel"]}),
    ]
    db_session.add_all(kayitlar)
    db_session.commit()
    return kayitlar


SORU = "Yeni ekmek üretim hattı için makine alacağım ve ürün geliştirme yapacağım"


def _idler(liste):
    return [t.id for t in liste]


# ------------------------------------------------------------ saf fonksiyonlar
@pytest.mark.parametrize("soru,beklenen", [
    (SORU, ["yatirim", "arge"]),
    ("yurt dışı fuara katılmak istiyorum", ["ihracat"]),
    ("eleman alacağım destek var mı", ["istihdam"]),
    ("işletme kredisi lazım", ["finansman"]),
    ("KOSGEB desteği", []),
    ("ÇİLEK SERASI İÇİN HİBE", []),
])
def test_soru_ihtiyaclari(soru, beklenen):
    assert soru_ihtiyaclari(soru) == beklenen


def test_program_ihtiyaclari_veriye_dayali(veri):
    p = {t.id: program_ihtiyaclari(t) for t in veri}
    assert "yatirim" in p[180] and "arge" in p[44]
    assert "arge" not in p[40] and "yatirim" not in p[40], "1601 ekosistem programı, firma Ar-Ge'si değil"
    assert "arge" not in p[45], "akademik etkinlik çağrısı"
    assert "ihracat" in p[162] and "finansman" in p[103]


def test_bigg_yatirim_tabanli_yatirim_programi_sayilmaz():
    t = Tesvik(kurum="TUBITAK", baslik="1812 - Yatırım Tabanlı Girişimcilik Destek Programı (BiGG Yatırım)",
               kaynak_url=f"{TUBITAK}/sanayi/1812", uygunluk_kriterleri={})
    assert program_ihtiyaclari(t) == set()


def test_akademik_tubitak_isletmeye_yonelik_degil(veri):
    sonuc = {t.id: isletmeye_yonelik_mi(t) for t in veri}
    assert sonuc[45] is False and sonuc[44] is True and sonuc[78] is True


# ------------------------------------------------------------------- arama
def test_imalat_profili_tarim_programini_elemez_9903_ve_firma_argesini_getirir(veri):
    imalat = FinancialProfile(sektor="imalat", calisan_sayisi=30, yillik_ciro=80e6, nace_kodu="10.71")
    sonuc = _idler(rag.retrieve(SORU, limit=4, profil_kaydi=imalat))
    assert 78 not in sonuc, "çiftçiye yönelik program imalatçıya gelmemeli"
    assert 44 in sonuc, "Ar-Ge ihtiyacı temsil edilmeli"
    # 10.71 (ekmek) 9903 EK-3'te yok: Hedef Yatırımlar kesin olarak desteklemez (MADDE 5/1, 10).
    assert 180 not in sonuc


def test_ek3_kapsamindaki_imalatciya_hedef_yatirimlar_gelir(veri):
    makine = FinancialProfile(sektor="imalat", calisan_sayisi=30, yillik_ciro=80e6, nace_kodu="28.93")
    sonuc = _idler(rag.retrieve(SORU, limit=4, profil_kaydi=makine))
    assert 180 in sonuc and 44 in sonuc, "iki ihtiyacın her biri temsil edilmeli"
    assert sonuc.index(44) < sonuc.index(40) if 40 in sonuc else True


def test_kapali_program_aktiflerin_onune_gecmez(veri):
    sonuc = _idler(rag.retrieve(SORU, limit=6))
    assert sonuc[-1] == 103 or 103 not in sonuc


def test_tarim_profili_sektore_ozgu_programi_one_alir(veri):
    tarim = FinancialProfile(sektor="tarim", calisan_sayisi=3, yillik_ciro=2e6)
    sonuc = _idler(rag.retrieve("traktör almak için makine desteği", limit=3, profil_kaydi=tarim))
    assert sonuc[0] == 78


def test_akademik_cagri_ihtiyac_sorusunda_kotayi_doldurmaz(veri):
    sonuc = _idler(rag.retrieve("yurt dışı fuara katılım desteği", limit=3))
    assert 45 not in sonuc and 162 in sonuc


def test_program_kodu_yazilirsa_akademik_cagri_korunur(veri):
    assert 45 in _idler(rag.retrieve("2224 yurt dışı fuar etkinlik", limit=3))


def test_ihtiyac_ve_profil_yoksa_eski_kelime_aramasi_degismez(veri):
    assert _idler(rag.retrieve("ÇİLEK SERASI İÇİN HİBE", limit=3)) == \
        _idler(rag._metin_aramasi("ÇİLEK SERASI İÇİN HİBE", 3))


def test_answer_profili_yalnizca_yerel_elemede_kullanir(veri, monkeypatch):
    """profil_kaydi dışarı gönderilmez; LLM'e giden bağlamda tarım programı olmamalı."""
    gorulen = {}

    def sahte_claude(query, matches, profil, notlar=None):
        gorulen["idler"] = _idler(matches)
        gorulen["profil"] = profil
        return "yanıt"

    monkeypatch.setattr(rag, "_claude_cevap", sahte_claude)
    imalat = FinancialProfile(sektor="imalat", calisan_sayisi=30, yillik_ciro=80e6)
    rag.answer(SORU, None, llm_kullan=True, profil_kaydi=imalat)
    assert 78 not in gorulen["idler"] and gorulen["profil"] is None


def test_tubitak_1511_hamle_kelimesiyle_yatirim_sayilmaz():
    t = Tesvik(kurum="TUBITAK", kaynak_url=f"{TUBITAK}/sanayi/1511", uygunluk_kriterleri={},
               baslik="1511 - TÜBİTAK Öncelikli Alanlar Araştırma Teknoloji Geliştirme ve Yenilik P. D. P."
                      "(Teknoloji Odaklı Sanayi Hamlesi Programı)")
    assert program_ihtiyaclari(t) == {"arge"}
