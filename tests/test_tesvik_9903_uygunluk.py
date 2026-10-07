"""9903 ön uygunluğu (app/tesvik_9903_uygunluk.py) ve arama/eşleşme/bağlam entegrasyonu.

Kurallar Karar metninden (R.G. 30/05/2025) okundu: EK-3 şartı Hedef ve Öncelikli
Yatırımlarda aranır, Kalkınma Hamlesi programlarında aranmaz (MADDE 5/1)."""
import pytest
from sqlalchemy.orm import sessionmaker

from app import rag
from app.matching import esles
from app.models import FinancialProfile, Tesvik
from app.tesvik_9903_uygunluk import degerlendir, program_turu, teknoloji_sinifi


@pytest.mark.parametrize("nace,beklenen", [
    ("21", "yuksek"), ("26.11", "yuksek"), ("30.3", "yuksek"),
    ("28.93", "orta_yuksek"), ("20.1", "orta_yuksek"), ("25.3", "orta_yuksek"), ("32.5", "orta_yuksek"),
    ("30.2", "orta_yuksek"), ("30.1", None),          # 30.1 orta-yüksekten hariç (MADDE 2/ı)
    ("25.4", None), ("10.71", None), ("C", None), (None, None),
])
def test_teknoloji_sinifi_ek1(nace, beklenen):
    assert teknoloji_sinifi(nace) == beklenen


@pytest.mark.parametrize("baslik,program", [
    ("Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)", "hedef_yatirimlar"),
    ("Öncelikli Yatırımlar Teşvik Sistemi (9903 sayılı Karar)", "oncelikli_yatirimlar"),
    ("Teknoloji Hamlesi Programı (9903 sayılı Karar)", "teknoloji_hamlesi"),
    ("Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar)", "yerel_kalkinma_hamlesi"),
    ("Stratejik Hamle Programı (9903 sayılı Karar)", "stratejik_hamle"),
    ("Stratejik Yatırımların Teşviki", None),           # yürürlükten kalkan eski sistem
    ("İmalat Sanayii Destek Paketi", None),
])
def test_program_turu(baslik, program):
    assert program_turu(baslik) == program


def test_ek3te_bolumu_hic_olmayan_konu_hedef_ve_oncelikliden_kesin_elenir():
    """47 (perakende) EK-3'te hiç yok -> kesin uygun değil."""
    for p in ("hedef_yatirimlar", "oncelikli_yatirimlar"):
        u = degerlendir(p, "47.11", "Konya", "kucuk")
        assert u.durum == "uygun_degil" and "EK-3" in u.gerekce and "MADDE 5/1" in u.madde


def test_ayni_bolumde_kalem_varsa_kesin_elenmez_kardes_kodlar_gosterilir():
    """GERÇEK OLAY: Rev.2 '62.01' (bilgisayar programlama) EK-3'teki Rev.2.1 '62.1' ile
    eşleşmeyip yazılım firmasını yanlış gerekçeyle eliyordu. Ekmek (10.71) için de EK-3'te
    yalnızca kardeş kodlar var; karar teyide bırakılır, sıralamada en alta iner."""
    for kod in ("62.01", "10.71"):
        u = degerlendir("hedef_yatirimlar", kod, "Konya", "kucuk")
        assert u.durum == "dusuk", kod
        assert "Rev.2.1" in u.gerekce and "aynı bölümde" in u.gerekce
    assert "62.1" in degerlendir("hedef_yatirimlar", "62.01", "Konya").gerekce
    assert "10.72" in degerlendir("hedef_yatirimlar", "10.71", "Konya").gerekce


def test_kalkinma_hamlesi_programlarinda_ek3_sarti_aranmaz():
    """MADDE 5/1: Hamle programları EK-3'te olmayan konuyu da destekleyebilir."""
    for p in ("teknoloji_hamlesi", "yerel_kalkinma_hamlesi", "stratejik_hamle"):
        assert degerlendir(p, "10.71", "Konya", "orta").durum != "uygun_degil", p


def test_ek3_kalemi_ve_sartlari():
    assert degerlendir("hedef_yatirimlar", "28.93", "Konya").durum == "uygun"
    sartli = degerlendir("hedef_yatirimlar", "13.20", "Konya")
    assert sartli.durum == "sartli" and "13.10.12" in sartli.gerekce, "EK-3 şart metni gösterilmeli"


def test_genis_kod_alt_kollara_isaret_eder():
    u = degerlendir("hedef_yatirimlar", "10", "Konya")
    assert u.durum == "sartli" and "10.1" in u.gerekce


def test_kod_yoksa_belirlenemedi():
    assert degerlendir("hedef_yatirimlar", None, "Konya").durum == "bilinmiyor"
    assert degerlendir("hedef_yatirimlar", "C", "Konya").durum == "bilinmiyor"


def test_oncelikli_bentleri():
    assert degerlendir("oncelikli_yatirimlar", "26.11", "Konya").durum == "sartli"          # 9/1-b
    assert degerlendir("oncelikli_yatirimlar", "28.93", "Konya").durum == "sartli"          # 9/1-c
    assert degerlendir("oncelikli_yatirimlar", "28.93", "İstanbul").durum == "dusuk"        # İstanbul hariç
    assert degerlendir("oncelikli_yatirimlar", "13.20", "Van").durum == "sartli", \
        "6. bölge (9/1-ç) ama EK-3 kalemi şartlı: sonuç uygun olamaz"
    assert degerlendir("oncelikli_yatirimlar", "28.93", "Van").durum == "uygun"
    assert degerlendir("oncelikli_yatirimlar", "13.20", "Konya").durum == "dusuk"


def test_teknoloji_hamlesi_ve_stratejik_hamle():
    assert degerlendir("teknoloji_hamlesi", "26.11", "Konya").durum == "sartli"
    assert degerlendir("teknoloji_hamlesi", "10.71", "Konya").durum == "dusuk"
    assert degerlendir("stratejik_hamle", "26.11", "Konya", "kucuk").durum == "dusuk"
    assert degerlendir("stratejik_hamle", "26.11", "Konya", "buyuk").durum == "sartli"
    assert degerlendir("yerel_kalkinma_hamlesi", "26.11", "Konya").durum == "bilinmiyor"


def test_her_sonuc_madde_numarasi_tasir():
    for p in ("hedef_yatirimlar", "oncelikli_yatirimlar", "teknoloji_hamlesi",
              "yerel_kalkinma_hamlesi", "stratejik_hamle"):
        for n in ("10.71", "28.93", None):
            assert "MADDE" in degerlendir(p, n, "Konya", "kucuk").madde


# --------------------------------------------------------------- entegrasyon
def _programlar(db):
    ortak = dict(kurum="Sanayi ve Teknoloji Bakanlığı", detay="d", aktif_mi=True,
                 uygunluk_kriterleri={"sektorler": ["imalat", "genel"]})
    db.add_all([
        Tesvik(id=180, baslik="Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)",
               ozet="Yatırım teşvik belgesi", kaynak_url="https://t/180", **ortak),
        Tesvik(id=177, baslik="Teknoloji Hamlesi Programı (9903 sayılı Karar)",
               ozet="Yüksek teknoloji yatırımları", kaynak_url="https://t/177", **ortak),
        Tesvik(id=179, baslik="Stratejik Hamle Programı (9903 sayılı Karar)",
               ozet="Stratejik yatırımlar", kaynak_url="https://t/179", **ortak),
    ])
    db.commit()


def _profil(nace, calisan=30, ciro=80e6, il="Konya"):
    return FinancialProfile(sektor="imalat", bolge=il, calisan_sayisi=calisan, yillik_ciro=ciro, nace_kodu=nace)


def test_arama_9903_programlarini_profile_gore_siralar_ve_eler(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    _programlar(db_session)
    soru = "makine yatırımı için teşvik"
    assert 180 not in [t.id for t in rag.retrieve(soru, 5, profil_kaydi=_profil("47.11"))]
    ekmek = [t.id for t in rag.retrieve(soru, 5, profil_kaydi=_profil("10.71"))]
    assert 180 in ekmek, "10.71: elenmez ('düşük olasılık' ile gösterilir, kesin değil)"
    sirali = [t.id for t in rag.retrieve(soru, 5, profil_kaydi=_profil("26.11", 300, 5e9))]
    assert set(sirali) == {177, 179, 180}
    # elektronik (yüksek teknoloji, EK-3'te): Hedef "uygun", Teknoloji Hamlesi "şartlı"
    assert sirali[0] == 180


def test_kucuk_isletmede_stratejik_hamle_geri_plana_duser(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    _programlar(db_session)
    sirali = [t.id for t in rag.retrieve("makine yatırımı için teşvik", 5, profil_kaydi=_profil("26.11"))]
    assert sirali[-1] == 179


def test_danisman_baglamina_sistem_degerlendirmesi_eklenir(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    _programlar(db_session)
    gorulen = {}

    def sahte(query, matches, profil, notlar=None, elenen=""):
        gorulen["notlar"] = notlar
        gorulen["baglam"] = rag._baglam_metni(matches, profil, notlar)
        return "yanıt"

    monkeypatch.setattr(rag, "_claude_cevap", sahte)
    rag.answer("makine yatırımı için teşvik", {"sektör": "imalat"}, profil_kaydi=_profil("10.71"))
    assert "SİSTEM ÖN DEĞERLENDİRMESİ" in gorulen["baglam"]
    assert any("DÜŞÜK OLASILIK" in n for n in gorulen["notlar"].values())
    assert "UYGUN DEĞİL" not in gorulen["baglam"], "elenen program bağlama girmemeli"


def test_prompt_sistem_degerlendirmesini_kullanmayi_soyler():
    assert "SİSTEM ÖN DEĞERLENDİRMESİ" in rag.SISTEM_PROMPTU


def test_esles_ek3_disindaki_konuya_hedef_yatirimlari_gostermez(db_session):
    _programlar(db_session)
    hedef_adi = "Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)"
    assert hedef_adi not in [s.tesvik.baslik for s in esles(_profil("47.11"), db_session)]
    ekmek = {s.tesvik.baslik: s for s in esles(_profil("10.71"), db_session)}
    assert any("DÜŞÜK OLASILIK" in e for e in ekmek[hedef_adi].eksik_kriterler)
    makine = {s.tesvik.baslik: s for s in esles(_profil("28.93"), db_session)}
    assert makine[hedef_adi].skor > ekmek[hedef_adi].skor, "ön değerlendirme sıralamaya yansımalı"
    sonuc = {s.tesvik.baslik: s for s in esles(_profil("28.93"), db_session)}
    assert any("9903 ön değerlendirmesi" in g for g in sonuc[hedef_adi].gerekce)


def test_seed_sartlari_ek3_sartini_yalnizca_ilgili_programlara_yazar():
    """MADDE 5/1: EK-3 şartı Hedef/Öncelikli'de var, Hamle programlarında yok."""
    from scripts.mark_9903_yururlukten_kalkanlar import program_sartlari
    for parca in ("hedef-yatirimlar", "oncelikli-yatirimlar"):
        assert "yer alması" in program_sartlari(parca)[0] and "EK-3" in program_sartlari(parca)[0]
    for parca in ("teknoloji-hamlesi", "yerel-kalkinma-hamlesi", "stratejik-hamle"):
        assert "ARANMAZ" in program_sartlari(parca)[0], parca
    assert any("MADDE 5/6" in x for x in program_sartlari("stratejik-hamle")), "genel şartlar korunmalı"


def test_elenen_9903_programlari_baglama_gerekceyle_girer(db_session, monkeypatch):
    """Elenen program bağlamda hiç olmazsa danışman 'teşvik belgesi alabilir miyim'
    sorusuna 'bilgim yok' diyordu."""
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    _programlar(db_session)
    metin = rag.elenen_9903_metni("makine yatırımı için teşvik belgesi", _profil("47.11"))
    assert "Hedef Yatırımlar" in metin and "UYGUN DEĞİL" in metin and "MADDE 5/1" in metin
    assert "yürürlükten kalkmıştır" in metin
    assert "Teknoloji Hamlesi" not in metin, "yalnızca elenenler listelenir"
    assert rag.elenen_9903_metni("makine yatırımı", _profil("28.93")) == ""
    assert rag.elenen_9903_metni("makine yatırımı", _profil("10.71")) == "", "kesin elenmeyen program listelenmez"
    assert rag.elenen_9903_metni("ihracat desteği", _profil("10.71")) == "", "yatırım sorusu değil"
    assert rag.elenen_9903_metni("makine yatırımı", None) == ""


def test_elenen_blok_danisman_baglamina_eklenir(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    _programlar(db_session)
    gorulen = {}

    def sahte(query, matches, profil, notlar=None, elenen=""):
        gorulen["baglam"] = rag._baglam_metni(matches, profil, notlar, elenen)
        return "yanıt"

    monkeypatch.setattr(rag, "_claude_cevap", sahte)
    rag.answer("makine yatırımı için teşvik", {"sektör": "imalat"}, profil_kaydi=_profil("47.11"))
    assert "SİSTEMİN ELEDİĞİ 9903 PROGRAMLARI" in gorulen["baglam"]
    assert "SİSTEMİN ELEDİĞİ" in rag.SISTEM_PROMPTU
