"""retrieve(): esles() ile aynı uygunluk engelleri; eski sistem (2012/3305) notu.

Ölçüm (2026-10-07, 15 soruluk bağlam denetimi): şirketsiz girişimciye 10962 (TTK şirketi
şart), KOSGEB kredisi, TEKMER işletici programı ve KGF; limited şirkete ortaklık yasaklı
BiGG danışman bağlamına giriyordu. "2012/3305 Bölgesel Teşvik" sorusunda yürürlükten kalkmış
sistem bağlamda hiç yoktu."""
import pytest
from sqlalchemy.orm import sessionmaker

from app import rag
from app.models import FinancialProfile, Tesvik

TUBITAK = "https://tubitak.gov.tr/tr/destekler"


@pytest.fixture
def veri(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    db_session.add_all([
        Tesvik(id=182, kurum="Ticaret Bakanlığı", baslik="Hizmet İhracatı Destekleri – Bilişim Sektörü (10962)",
               ozet="yazılım SaaS yurt dışı", detay="d", aktif_mi=True, kaynak_url="https://t/182",
               hedef_kitle="Bilişim sektöründe faaliyet gösteren, Türkiye'de yerleşik ve TTK'ya göre kurulmuş "
                           "şirketler (yazılım, mobil uygulama, dijital oyun, SaaS); kooperatifler",
               basvuru_sartlari=["Yararlanıcı: TTK hükümlerine göre kurulmuş şirket olmak; şahıs işletmesi ve "
                                 "şirketleşmemiş girişim yararlanıcı tanımına girmez"],
               uygunluk_kriterleri={"sektorler": ["arge", "hizmet", "ihracat"]}),
        Tesvik(id=4, kurum="KOSGEB", baslik="Teknoloji Merkezi Destek Programı", ozet="yazılım girişim",
               detay="d", aktif_mi=True, kaynak_url="https://t/4",
               basvuru_sartlari=["Programdan TEKMER işletici kuruluşu ve TGB yönetici şirketi yararlanabilir."],
               uygunluk_kriterleri={"sektorler": ["arge"]}),
        Tesvik(id=152, kurum="KGF", baslik="TÜBİTAK Transfer Ödemeleri", ozet="yazılım projesi kredi", detay="d",
               aktif_mi=True, kaynak_url="https://t/152", basvuru_sartlari=[],
               uygunluk_kriterleri={"sektorler": ["genel"]}),
        Tesvik(id=174, kurum="TUBITAK", baslik="1512 - Girişimcilik Destek Programı (BiGG)", ozet="yazılım fikir",
               detay="d", aktif_mi=True, kaynak_url=f"{TUBITAK}/sanayi/1512",
               basvuru_sartlari=["herhangi bir işletmenin ortaklık yapısında yer almamak (şirket kurulduysa başvurulamaz)"],
               uygunluk_kriterleri={"sektorler": ["genel", "arge"]}),
        Tesvik(id=44, kurum="TUBITAK", baslik="1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç", ozet="yazılım Ar-Ge",
               detay="d", aktif_mi=True, kaynak_url=f"{TUBITAK}/sanayi/1507", basvuru_sartlari=[],
               uygunluk_kriterleri={"sektorler": ["arge", "genel"]}),
    ])
    db_session.commit()


SORU = "Şirketim yok, yazılım fikrim var, hangi hibelere başvurabilirim?"


def _idler(liste):
    return [t.id for t in liste]


def test_sirketsiz_girisimciye_sirket_gerektiren_programlar_baglama_girmez(veri):
    yok = FinancialProfile(sektor="arge", sirket_turu="yok", trl=4)
    ids = _idler(rag.retrieve(SORU, limit=8, profil_kaydi=yok))
    assert 174 in ids, "BiGG şirketsiz girişimciye açık"
    for kapali in (182, 4, 152, 44):
        assert kapali not in ids, f"{kapali} şirket/aracı kuruluş gerektirir"


def test_limited_sirkete_ortaklik_yasakli_bigg_gelmez_1507_gelir(veri):
    ltd = FinancialProfile(sektor="arge", sirket_turu="limited", calisan_sayisi=12)
    ids = _idler(rag.retrieve(SORU, limit=8, profil_kaydi=ltd))
    assert 174 not in ids and 4 not in ids
    assert 44 in ids and 182 in ids


def test_profil_yoksa_engel_uygulanmaz(veri):
    assert 174 in _idler(rag.retrieve(SORU, limit=8))


@pytest.mark.parametrize("soru", [
    "2012/3305 sayılı Bölgesel Teşvik uygulamasından yararlanabilir miyim?",
    "GENEL TEŞVİK belgesi alabilir miyim",
    "bolgesel tesvik hala var mi",
    "Büyük ölçekli yatırım teşviki",
])
def test_eski_sistem_notu(soru):
    assert rag.ESKI_SISTEM_NOTU in rag.eski_sistem_notu(soru)


def test_eski_sistem_notu_alakasiz_soruda_yok():
    assert rag.eski_sistem_notu("1507 başvurusu için şartlar neler?") == ""


def test_dusuk_olasilik_9903_programi_elenen_blogunda_listelenir(veri, db_session):
    """Ekmek 10.71: Hedef Yatırımlar 'düşük olasılık' ile sıralamada geriye düşüp bağlama
    girmiyor; model programı hiç bilmiyordu. Elenen bloğu artık onu da listeler, bağlamda
    olan kayıt tekrarlanmaz."""
    db_session.add(Tesvik(id=180, kurum="Sanayi ve Teknoloji Bakanlığı",
                          baslik="Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)", ozet="yatırım", detay="d",
                          aktif_mi=True, kaynak_url="https://t/180", uygunluk_kriterleri={"sektorler": ["genel"]}))
    db_session.commit()
    ekmek = FinancialProfile(sektor="imalat", bolge="Konya", nace_kodu="10.71", calisan_sayisi=30, yillik_ciro=80e6)
    m = rag.elenen_9903_metni("yeni üretim hattı için makine yatırımı yapacağım", ekmek)
    assert "Hedef Yatırımlar" in m and "DÜŞÜK OLASILIK" in m and rag.ESKI_SISTEM_NOTU in m
    assert rag.elenen_9903_metni("yeni üretim hattı için makine yatırımı yapacağım", ekmek, haric_idler=[180]) == ""
    assert rag.elenen_9903_metni("1507 şartları neler", ekmek) == "", "yatırım ihtiyacı yoksa blok yok"


def test_answer_eski_sistem_notunu_baglama_ekler(veri, monkeypatch):
    gorulen = {}

    def sahte(query, matches, profil, notlar=None, elenen="", sistem_eki=""):
        gorulen["elenen"] = elenen
        return "yanıt"

    monkeypatch.setattr(rag, "_claude_cevap", sahte)
    ltd = FinancialProfile(sektor="arge", bolge="Van", sirket_turu="limited", calisan_sayisi=12)
    rag.answer("Yazılım Ar-Ge projemiz için 2012/3305 sayılı Bölgesel Teşvik'ten yararlanabilir miyim?",
               None, llm_kullan=True, profil_kaydi=ltd)
    assert gorulen["elenen"].count(rag.ESKI_SISTEM_NOTU) == 1
    gorulen.clear()
    rag.answer("Yazılım Ar-Ge projemiz için 1507 uygun mu?", None, llm_kullan=True, profil_kaydi=ltd)
    assert rag.ESKI_SISTEM_NOTU not in gorulen["elenen"]
