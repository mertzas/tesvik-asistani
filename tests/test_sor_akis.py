"""Akışlı danışman yanıtı: rag.answer_akis ve POST /api/sor/akis (SSE).

Ölçüm 2026-10-07: tam yanıt 35-60 sn; panel bu süre boyunca yalnızca spinner gösteriyordu.
2026-10-11: dış modelin yanıtı dayanak denetiminden geçmeden kullanıcıya gösterilmez; akış tamponlanır, denetimden
geçerse paragraf paragraf gönderilir. Kesik, bitişsiz ya da denetimden geçmeyen yanıt yerel danışmana düşer (eski
"kesildi" notları gereksizleşti: kullanıcı yarım yanıt görmez)."""
import json

import pytest
from sqlalchemy.orm import sessionmaker

import app.main
from app import rag
from app.models import FinancialProfile, Query, Tesvik

SORU = "yazılım Ar-Ge desteği"


@pytest.fixture
def veri(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    db_session.add(Tesvik(id=44, kurum="TUBITAK", baslik="1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç",
                          ozet="KOBİ Ar-Ge projeleri yazılım", detay="d", aktif_mi=True,
                          kaynak_url="https://tubitak.gov.tr/tr/destekler/sanayi/1507",
                          tesvil_tutari="600.000 TL'ye kadar, %75 hibe",
                          uygunluk_kriterleri={"sektorler": ["arge", "genel"]}))
    db_session.commit()


def _metin(olaylar):
    return "".join(v for t, v in olaylar if t == "parca")


# ------------------------------------------------------------------ rag katmanı
def test_akis_once_kayitlar_sonra_denetlenmis_parcalar(veri, dis_model):
    dis_model.metin = "### 1. Özet\n\n1507 600.000 TL'ye kadar destek verir.\n\nKaynak: " \
                      "https://tubitak.gov.tr/tr/destekler/sanayi/1507"
    olaylar = list(rag.answer_akis(SORU, None, llm_kullan=True))
    assert olaylar[0][0] == "kayitlar" and [t.id for t in olaylar[0][1]] == [44]
    assert len(olaylar) > 2 and all(t == "parca" for t, _ in olaylar[1:]), "paragraf paragraf gönderilmeli"
    assert _metin(olaylar) == dis_model.metin


def test_akis_dis_model_yoksa_yerel_danisman(veri):
    metin = _metin(rag.answer_akis(SORU, None, llm_kullan=True))
    assert "1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç" in metin and "600.000 TL'ye kadar, %75 hibe" in metin
    assert "yerel danışmanı" in metin


def test_akis_rizasizda_dis_cagri_yok(veri, dis_model):
    metin = _metin(rag.answer_akis(SORU, None, llm_kullan=False))
    assert dis_model.cagrilar == [] and "yerel danışmanı" in metin


def test_akis_eslesme_yoksa_bulunamadi_metni(veri, monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda *a, **k: [])
    assert list(rag.answer_akis("xyz", None, llm_kullan=True)) == [("kayitlar", []), ("parca", rag.BULUNAMADI_METNI)]


def test_akis_girisim_modunda_prompt_eki_ve_huks_gider(veri, dis_model):
    # TRL girilmiş profil girişim modunu açar; şirket türü bilinmediği için 1507 elenmez.
    girisim = FinancialProfile(sektor="arge", trl=3)
    list(rag.answer_akis(SORU, None, llm_kullan=True, profil_kaydi=girisim))
    istek = dis_model.cagrilar[0]["messages"]
    assert istek[0]["content"].endswith(rag.GIRISIM_PROMPT_EKI) and "GİRİŞİM MODU BİLGİLERİ" in istek[1]["content"]


def test_yerel_girisim_modunda_huks_blogu_kullaniciya_gosterilir(veri):
    metin = _metin(rag.answer_akis(SORU, None, llm_kullan=False, profil_kaydi=FinancialProfile(sektor="arge", trl=3)))
    assert "Girişim ön değerlendirmesi" in metin and "HUKS ÖN SKORU" in metin


def test_answer_ve_akis_ayni_hazirligi_kullanir(veri, monkeypatch):
    """İki yol ayrışmasın: aynı kayıtlar, aynı notlar, aynı elenen bloğu, aynı yerel yanıt."""
    monkeypatch.setenv("LLM_SAGLAYICI", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "test")
    gorulen = []

    def sahte(query, matches, profil, notlar=None, elenen="", sistem_eki=""):
        gorulen.append(([t.id for t in matches], notlar, elenen))
        return None

    monkeypatch.setattr(rag, "_llm_cevap", sahte)
    ltd = FinancialProfile(sektor="arge", sirket_turu="limited", bolge="Van", calisan_sayisi=5)
    soru = "Yazılım projemiz için 2012/3305 Bölgesel Teşvik'ten yararlanabilir miyim?"
    tek = rag.answer(soru, None, llm_kullan=True, profil_kaydi=ltd)
    akis = _metin(rag.answer_akis(soru, None, llm_kullan=True, profil_kaydi=ltd))
    assert gorulen[0] == gorulen[1] and rag.ESKI_SISTEM_NOTU in gorulen[0][2]
    assert tek == akis and rag.ESKI_SISTEM_NOTU in tek
    assert "Google Gemini servisine gönderildi" in tek, "dış servis denendiyse yöntem notu bunu söylemeli (KVKK)"


def test_dis_model_beklenirken_akis_bekleme_sinyali_verir(veri, dis_model, monkeypatch):
    """Opus incelemesi: dış yanıt tamponlanırken SSE'ye hiçbir şey gitmiyor, vekil bağlantıyı kesebiliyordu."""
    import time
    monkeypatch.setattr(rag, "BEKLEME_SINYALI_SN", 0.05)
    gercek = rag._llm_cevap

    def yavas(*a, **k):
        time.sleep(0.3)
        return gercek(*a, **k)
    monkeypatch.setattr(rag, "_llm_cevap", yavas)
    tipler = [t for t, _ in rag.answer_akis(SORU, None, llm_kullan=True)]
    assert "bekle" in tipler and tipler[0] == "kayitlar" and tipler[-1] == "parca"


def test_sor_akis_bekleme_olayini_sse_yorumu_olarak_gonderir(client, test_org_data, monkeypatch):
    def akis(soru, profil=None, llm_kullan=True, **_kw):
        yield "kayitlar", []
        yield "bekle", None
        yield "parca", "yanıt"
    monkeypatch.setattr(app.main, "answer_akis", akis)
    h = _hesap(client, test_org_data)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    assert ": bekleniyor" in r.text and [t for t, _ in _sse_coz(r.text) if t] == ["kayitlar", "parca", "son"]


# ------------------------------------------------------------------ dayanıklılık (Aşama D, yeni davranış)
@pytest.mark.parametrize("durma,metin", [(None, "### 1. Özet\nKısmi"), ("length", "### 1. Yarım")])
def test_bitissiz_ya_da_kesik_dis_yanit_yerele_duser(veri, dis_model, durma, metin):
    """GERÇEK DENEY (2026-10-07): bağlantı akış ortasında kopunca bitiş bilgisi boş kalıyordu; kullanıcı kesik
    yanıtı tam sanıyordu. Artık kesik yanıt hiç gösterilmez."""
    dis_model.metin, dis_model.durma = metin, durma
    cikti = _metin(rag.answer_akis(SORU, None, llm_kullan=True))
    assert "Kısmi" not in cikti and "Yarım" not in cikti and "yerel danışmanı" in cikti


def test_dis_model_istisnasi_yerele_duser(veri, dis_model):
    dis_model.hata = RuntimeError("koptu")
    assert "yerel danışmanı" in _metin(rag.answer_akis(SORU, None, llm_kullan=True))


def test_analiz_blogu_kullaniciya_gitmez(veri, dis_model):
    dis_model.metin = "<analiz>\n- mod: ANALİZ\n- kayıt: öner</analiz>\n\n### 1. Özet"
    assert _metin(rag.answer_akis(SORU, None, llm_kullan=True)) == "### 1. Özet"


def test_yalniz_analiz_ureten_yanit_yerele_duser(veri, dis_model):
    dis_model.metin = "<analiz>\n- uzun analiz</analiz>"
    assert "yerel danışmanı" in _metin(rag.answer_akis(SORU, None, llm_kullan=True))


# ------------------------------------------------------------------ uç nokta
def _hesap(client, test_org_data):
    r = client.post("/api/auth/signup", json=test_org_data)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sse_coz(metin):
    olaylar = []
    for blok in metin.strip().split("\n\n"):
        tip, veri_ = None, ""
        for satir in blok.split("\n"):
            if satir.startswith("event:"):
                tip = satir[6:].strip()
            elif satir.startswith("data:"):
                veri_ += satir[5:].strip()
        olaylar.append((tip, veri_))
    return olaylar


def test_sor_akis_olay_sirasi_ve_sorgu_kaydi(client, test_org_data, db_session):
    h = _hesap(client, test_org_data)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    olaylar = _sse_coz(r.text)
    tipler = [t for t, _ in olaylar]
    assert tipler[0] == "kayitlar" and tipler[-1] == "son" and "parca" in tipler
    metin = "".join(v for t, v in olaylar if t == "parca")
    # yerel danışman: dış çağrı yok, rıza notu da yok (conftest taklidi llm_kullan=False yazar)
    assert "llm_kullan=False" in metin and "rıza" not in metin
    assert db_session.query(Query).count() == 1
    assert json.loads(olaylar[-1][1])["query_id"] == str(db_session.query(Query).first().id)


def test_sor_akis_dis_servis_rizasizken_not_ve_rizayla_acik(client, test_org_data, monkeypatch):
    monkeypatch.setenv("LLM_SAGLAYICI", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "test")
    h = _hesap(client, test_org_data)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    metin = "".join(v for t, v in _sse_coz(r.text) if t == "parca")
    assert "llm_kullan=False" in metin and "açık rıza" in metin and "Google Gemini" in metin
    client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    metin = "".join(v for t, v in _sse_coz(r.text) if t == "parca")
    assert "llm_kullan=True" in metin and "açık rıza" not in metin


def test_sor_akis_yetkisiz_401(client):
    assert client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}).status_code == 401


def test_sor_akis_akis_hatasi_hata_olayi_uretir(client, test_org_data, monkeypatch):
    def bozuk(soru, profil=None, llm_kullan=True, **_kw):
        yield "kayitlar", []
        raise RuntimeError("model çöktü")

    monkeypatch.setattr(app.main, "answer_akis", bozuk)
    h = _hesap(client, test_org_data)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    assert [t for t, _ in _sse_coz(r.text)] == ["kayitlar", "hata"]
