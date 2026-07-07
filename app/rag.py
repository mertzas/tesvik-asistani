"""
Anahtar-kelime tabanli retrieval + saf liste formatinda cevap.

Disari (Anthropic vb.) hicbir API cagrisi yapilmaz.

Not: Yerel Ollama (Gemma) ile dogal dil cevap uretimi denendi ama bu
makinede tek bir cevap ~130-140 saniye surdu (CPU-bound inference) --
interaktif bir chat icin pratik degil. O yuzden LLM katmani KAPALI;
ASAGIDAKI OLLAMA_ETKIN = True yapip answer() icindeki _ollama_cevap
cagrisini geri actiginda tekrar devreye girer (fonksiyonlar hala
mevcut, silinmedi).

Prototip asamasinda embedding/vektor DB yerine SQLite LIKE sorgusu
kullaniyoruz; veri seti buyudukce (yuzlerce/binlerce kayit) bunu
Chroma/pgvector gibi bir vektor DB ile degistirmek gerekir.
"""
import requests

from app.models import SessionLocal, Tesvik
from sqlalchemy import or_

OLLAMA_ETKIN = False  # True yapinca Gemma ile dogal dil cevap tekrar devreye girer
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4"
OLLAMA_TIMEOUT_SEC = 150

# Anlamli sinyal tasimayan, aramada gurultu yaratan kisa/genel kelimeler.
DURAK_KELIMELER = {
    "için", "ile", "hangi", "nasıl", "var", "mı", "mi", "bir",
    "the", "and", "des", "des",
}


def _terimlere_ayir(query: str) -> list[str]:
    terms = [t.strip(".,!?").lower() for t in query.split()]
    return [t for t in terms if len(t) > 2 and t not in DURAK_KELIMELER]


def retrieve(query: str, limit: int = 5) -> list[Tesvik]:
    db = SessionLocal()
    terms = _terimlere_ayir(query)
    q = db.query(Tesvik)
    if terms:
        conditions = [
            Tesvik.baslik.ilike(f"%{t}%") | Tesvik.ozet.ilike(f"%{t}%") | Tesvik.detay.ilike(f"%{t}%")
            for t in terms
        ]
        q = q.filter(or_(*conditions))
    candidates = q.order_by(Tesvik.guncelleme_tarihi.desc()).limit(200).all()
    db.close()

    if not terms:
        return candidates[:limit]

    def skor(t: Tesvik) -> int:
        metin = f"{t.baslik} {t.ozet} {t.detay}".lower()
        return sum(metin.count(term) for term in terms) + (2 * sum(term in t.baslik.lower() for term in terms))

    candidates.sort(key=skor, reverse=True)
    return candidates[:limit]


def _kisalt(metin: str, uzunluk: int = 220) -> str:
    metin = " ".join(metin.split())
    if len(metin) <= uzunluk:
        return metin
    return metin[:uzunluk].rsplit(" ", 1)[0] + "…"


def _liste_formati(matches: list[Tesvik]) -> str:
    """LLM'siz fallback: kayitlari duz liste olarak formatlar."""
    baslik_satiri = f"Sorunuzla ilgili {len(matches)} destek/teşvik programı buldum:\n"
    satirlar = [baslik_satiri]
    for i, m in enumerate(matches, start=1):
        satirlar.append(
            f"\n{i}. [{m.kurum}] {m.baslik}\n"
            f"   {_kisalt(m.ozet)}\n"
            f"   Kaynak: {m.kaynak_url}"
        )
    satirlar.append(
        "\n\nNot: Bu cevap veritabanındaki kayıtlardan otomatik oluşturuldu, "
        "kesin başvuru şartları için ilgili kurumun sayfasını kontrol edin."
    )
    return "".join(satirlar)


def _ollama_cevap(query: str, matches: list[Tesvik]) -> str | None:
    """Yerel Ollama (gemma4) ile bulunan kayitlari dogal dilde yorumlar.
    Ollama'ya erisilemezse (kapali, model yok, timeout) None doner --
    cagiran taraf bu durumda liste formatina duser."""
    baglam = "\n\n".join(
        f"[{m.kurum}] {m.baslik}\nKaynak: {m.kaynak_url}\n{_kisalt(m.detay, 500)}"
        for m in matches
    )
    prompt = (
        "Sen Turkiye'deki KOSGEB, TUBITAK, KGF ve Hazine/Ticaret Bakanligi "
        "tesvik/destek programlari konusunda kullaniciya rehberlik eden bir "
        "asistansin. SADECE asagida verilen baglami kullanarak cevap ver, "
        "baglamda olmayan bilgi uydurma. Her bahsettigin programin yaninda "
        "kaynak URL'sini de belirt. Emin olmadigin durumda kullaniciyi "
        "ilgili kurumun resmi sitesine yonlendir. Kisa ve net Turkce cevap ver.\n\n"
        f"Baglam:\n{baglam}\n\nKullanici sorusu: {query}"
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        data = resp.json()
        cevap = data.get("response", "").strip()
        return cevap or None
    except (requests.RequestException, ValueError):
        return None


def answer(query: str) -> str:
    matches = retrieve(query)

    if not matches:
        return (
            "Bu soruyla eşleşen bir teşvik/destek programı bulamadım. "
            "Farklı anahtar kelimelerle (örn. kurum adı, sektör, \"girişimci\", "
            "\"dijital dönüşüm\" gibi) tekrar deneyebilir ya da doğrudan "
            "KOSGEB, TÜBİTAK, KGF veya Ticaret Bakanlığı'nın resmi sitelerine "
            "bakabilirsiniz."
        )

    if OLLAMA_ETKIN:
        llm_cevap = _ollama_cevap(query, matches)
        if llm_cevap is not None:
            return llm_cevap

    return _liste_formati(matches)
