"""Akışlı danışman yanıtı: rag.answer_akis ve POST /api/sor/akis (SSE).

Ölçüm 2026-10-07: tam yanıt 35-60 sn; panel bu süre boyunca yalnızca spinner gösteriyordu
ve /api/sor'un `message` alanını hiç render etmiyordu."""
import pytest
from sqlalchemy.orm import sessionmaker

import app.main
from app import rag
from app.models import FinancialProfile, Query, Tesvik


@pytest.fixture
def veri(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    db_session.add(Tesvik(id=44, kurum="TUBITAK", baslik="1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç",
                          ozet="KOBİ Ar-Ge projeleri yazılım", detay="d", aktif_mi=True,
                          kaynak_url="https://tubitak.gov.tr/tr/destekler/sanayi/1507",
                          uygunluk_kriterleri={"sektorler": ["arge", "genel"]}))
    db_session.commit()


def _olaylar(uretec):
    return list(uretec)


# ------------------------------------------------------------------ rag katmanı
def test_akis_once_kayitlar_sonra_parcalar(veri, monkeypatch):
    def sahte_akis(query, matches, profil, notlar=None, elenen="", sistem_eki=""):
        yield "### 1. "
        yield "Özet"

    monkeypatch.setattr(rag, "_claude_akis", sahte_akis)
    olaylar = _olaylar(rag.answer_akis("yazılım Ar-Ge desteği", None, llm_kullan=True))
    assert olaylar[0][0] == "kayitlar" and [t.id for t in olaylar[0][1]] == [44]
    assert [o for o in olaylar[1:]] == [("parca", "### 1. "), ("parca", "Özet")]


def test_akis_claude_parca_uretmezse_liste_formatina_duser(veri, monkeypatch):
    monkeypatch.setattr(rag, "_claude_akis", lambda *a, **k: iter(()))
    olaylar = _olaylar(rag.answer_akis("yazılım Ar-Ge desteği", None, llm_kullan=True))
    assert len(olaylar) == 2 and olaylar[1][1] == rag._liste_formati(olaylar[0][1])


def test_akis_riza_yoksa_llm_hic_cagrilmaz(veri, monkeypatch):
    def patlat(*a, **k):
        raise AssertionError("rıza yokken dış çağrı yapıldı")
        yield  # noqa: E501 - üreteç imzası

    monkeypatch.setattr(rag, "_claude_akis", patlat)
    olaylar = _olaylar(rag.answer_akis("yazılım Ar-Ge desteği", None, llm_kullan=False))
    assert olaylar[1][1] == rag._liste_formati(olaylar[0][1])


def test_akis_eslesme_yoksa_bulunamadi_metni(veri, monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda *a, **k: [])
    olaylar = _olaylar(rag.answer_akis("xyz", None, llm_kullan=True))
    assert olaylar == [("kayitlar", []), ("parca", rag.BULUNAMADI_METNI)]


def test_akis_girisim_modunda_prompt_eki_gider(veri, monkeypatch):
    gorulen = {}

    def sahte_akis(query, matches, profil, notlar=None, elenen="", sistem_eki=""):
        gorulen["eki"] = sistem_eki
        gorulen["elenen"] = elenen
        yield "x"

    monkeypatch.setattr(rag, "_claude_akis", sahte_akis)
    # TRL girilmiş profil girişim modunu açar; şirket türü bilinmediği için 1507 elenmez.
    girisim = FinancialProfile(sektor="arge", trl=3)
    _olaylar(rag.answer_akis("yazılım Ar-Ge desteği", None, llm_kullan=True, profil_kaydi=girisim))
    assert gorulen["eki"] == rag.GIRISIM_PROMPT_EKI and "GİRİŞİM MODU BİLGİLERİ" in gorulen["elenen"]


def test_answer_ve_akis_ayni_hazirligi_kullanir(veri, monkeypatch):
    """İki yol ayrışmasın: aynı kayıtlar, aynı notlar, aynı elenen bloğu."""
    gorulen = []

    def sahte_cevap(query, matches, profil, notlar=None, elenen="", sistem_eki=""):
        gorulen.append(([t.id for t in matches], notlar, elenen))
        return "y"

    def sahte_akis(query, matches, profil, notlar=None, elenen="", sistem_eki=""):
        gorulen.append(([t.id for t in matches], notlar, elenen))
        yield "y"

    monkeypatch.setattr(rag, "_claude_cevap", sahte_cevap)
    monkeypatch.setattr(rag, "_claude_akis", sahte_akis)
    ltd = FinancialProfile(sektor="arge", sirket_turu="limited", bolge="Van", calisan_sayisi=5)
    soru = "Yazılım projemiz için 2012/3305 Bölgesel Teşvik'ten yararlanabilir miyim?"
    rag.answer(soru, None, llm_kullan=True, profil_kaydi=ltd)
    _olaylar(rag.answer_akis(soru, None, llm_kullan=True, profil_kaydi=ltd))
    assert gorulen[0] == gorulen[1] and rag.ESKI_SISTEM_NOTU in gorulen[0][2]


# ------------------------------------------------------------------ uç nokta
def _hesap(client, test_org_data):
    r = client.post("/api/auth/signup", json=test_org_data)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sse_coz(metin):
    olaylar = []
    for blok in metin.strip().split("\n\n"):
        tip, veri = None, ""
        for satir in blok.split("\n"):
            if satir.startswith("event:"):
                tip = satir[6:].strip()
            elif satir.startswith("data:"):
                veri += satir[5:].strip()
        olaylar.append((tip, veri))
    return olaylar


def test_sor_akis_olay_sirasi_ve_sorgu_kaydi(client, test_org_data, db_session):
    h = _hesap(client, test_org_data)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    olaylar = _sse_coz(r.text)
    tipler = [t for t, _ in olaylar]
    assert tipler[0] == "kayitlar" and tipler[-1] == "son" and "parca" in tipler
    # rıza yok: KVKK notu parça olarak gelir, LLM çağrılmadı (conftest taklidi llm_kullan=False yazar)
    metin = "".join(v for t, v in olaylar if t == "parca")
    assert "llm_kullan=False" in metin and "/api/organizations/ai-riza" in metin
    assert db_session.query(Query).count() == 1
    import json
    assert json.loads(olaylar[-1][1])["query_id"] == str(db_session.query(Query).first().id)


def test_sor_akis_rizayla_llm_acik(client, test_org_data):
    h = _hesap(client, test_org_data)
    client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    metin = "".join(v for t, v in _sse_coz(r.text) if t == "parca")
    assert "llm_kullan=True" in metin and "/api/organizations/ai-riza" not in metin


def test_sor_akis_yetkisiz_401(client):
    assert client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}).status_code == 401


def test_sor_akis_akis_hatasi_hata_olayi_uretir(client, test_org_data, monkeypatch):
    def bozuk(soru, profil=None, llm_kullan=True, **_kw):
        yield "kayitlar", []
        raise RuntimeError("model çöktü")

    monkeypatch.setattr(app.main, "answer_akis", bozuk)
    h = _hesap(client, test_org_data)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    tipler = [t for t, _ in _sse_coz(r.text)]
    assert tipler == ["kayitlar", "hata"]


# ------------------------------------------------------------------ dayanıklılık (Aşama D)
class _SahteAkis:
    """anthropic messages.stream bağlam yöneticisi: parçaları verir, sonda verilen durumu döndürür."""

    def __init__(self, parcalar, stop_reason, hata_sonra=None):
        self._p, self._s, self._h = parcalar, stop_reason, hata_sonra

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def text_stream(self):
        for p in self._p:
            yield p
        if self._h:
            raise self._h

    def get_final_message(self):
        class M:
            stop_reason = self._s
            usage = None
        return M()


def _akis_kos(monkeypatch, sahte):
    import types
    import sys
    fake = types.SimpleNamespace(Anthropic=lambda api_key=None: types.SimpleNamespace(messages=types.SimpleNamespace(stream=lambda **k: sahte)))
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setattr(rag.settings, "ANTHROPIC_API_KEY", "x")
    return list(rag._claude_akis("soru", [], None))


def test_akis_message_stop_gelmeden_biterse_kesildi_notu(monkeypatch):
    """GERÇEK DENEY: bağlantı akış ortasında kopunca SDK hata vermedi, stop_reason boştu;
    kullanıcı kesik yanıtı tam sanıyordu."""
    cikti = _akis_kos(monkeypatch, _SahteAkis(["### 1. Özet\nKısmi"], None))
    assert cikti[0] == "### 1. Özet\nKısmi" and cikti[-1] == rag.BAGLANTI_KOPTU_NOTU


def test_akis_normal_bitiste_not_eklenmez(monkeypatch):
    assert _akis_kos(monkeypatch, _SahteAkis(["tam yanıt"], "end_turn")) == ["tam yanıt"]


def test_akis_parca_sonrasi_istisna_kesildi_notu(monkeypatch):
    cikti = _akis_kos(monkeypatch, _SahteAkis(["ilk"], "end_turn", hata_sonra=RuntimeError("koptu")))
    assert cikti == ["ilk", rag.BAGLANTI_KOPTU_NOTU]


def test_akis_hic_parca_yoksa_not_yok_liste_formatina_dusulur(monkeypatch):
    assert _akis_kos(monkeypatch, _SahteAkis([], None)) == []
