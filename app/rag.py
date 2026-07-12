"""
Anahtar-kelime tabanli retrieval + Claude API ile dogal dil cevap uretimi.

Onceki surumde yerel Ollama (Gemma) denenmisti ama tek cevap 130-140sn
suruyordu (CPU-bound) - interaktif chat icin kullanilamaz oldugu icin
kapatilmisti (OLLAMA_ETKIN=False, kod hala asagida duruyor). Su an
birincil yol Claude API (Anthropic) - ANTHROPIC_API_KEY .env'de tanimliysa
kullanilir; tanimli degilse veya cagri basarisiz olursa OTOMATIK olarak
LLM'siz duz liste formatina (_liste_formati) duser - kullanici hicbir
zaman bos/hatali bir ekranla karsilasmaz.

KRITIK KURAL: LLM'e verilen sistem promptu SADECE veritabanindan (Tesvik
kayitlari + KurumIletisim rehberi + kullanicinin FinancialProfile'i) gelen
bilgiyi kullanmasini, telefon numarasi/oran/tutar gibi somut rakamlari
UYDURMAMASINI acikca soyler. KurumIletisim tablosundaki her telefon
numarasi resmi kurum sayfasindan WebFetch ile tek tek dogrulanmistir
(bkz. scripts/seed_kurum_iletisim.py, app/models.py KurumIletisim
docstring'i) - LLM egitim verisinden gelen "hatirlanan" numaralar degil.
"""
import requests

from app.models import SessionLocal, Tesvik, KurumIletisim, settings
from sqlalchemy import or_

OLLAMA_ETKIN = False  # True yapinca Gemma ile dogal dil cevap tekrar devreye girer
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4"
OLLAMA_TIMEOUT_SEC = 150

CLAUDE_TIMEOUT_SEC = 30
CLAUDE_MAX_TOKENS = 1800

# Anlamli sinyal tasimayan, aramada gurultu yaratan kisa/genel kelimeler.
DURAK_KELIMELER = {
    "için", "ile", "hangi", "nasıl", "var", "mı", "mi", "bir",
    "the", "and", "des", "des",
}

SISTEM_PROMPTU = """Sen, Türkiye'deki KOBİ'ler, çiftçiler, e-ticaret girişimcileri ve esnaflar için \
çalışan kıdemli bir Teşvik ve Strateji Asistanısın.

TEMEL PRENSİPLER:
- Net ve gerçekçi ol: teşvik ihtimali düşükse veya şartlar ağırsa açıkça söyle, umut tacirliği yapma.
- Kısa maddeler ve kalın başlıklar kullan, uzun paragraflardan kaçın.
- Her önerinin arkasından "hangi kurum, hangi kanal" sorusunun cevabını ver.

MUTLAK KURAL - UYDURMA YASAK: Sana aşağıda "BAĞLAM" başlığı altında verilen \
teşvik kayıtları ve kullanıcı profili DIŞINDA hiçbir somut bilgi (telefon \
numarası, başvuru oranı, tutar, tarih, kurum adı) UYDURMA. Bağlamda olmayan \
bir bilgiye ihtiyaç varsa, kullanıcıyı ilgili kurumun bağlamdaki kaynak \
URL'sine yönlendir ya da "bu bilgi elimde yok, X kurumunun resmi sitesinden \
teyit edin" de. Sayısal bir rakam (telefon, oran, TL tutarı) bağlamda \
geçmiyorsa ASLA kendi bilginden tahmin/icat etme.

Yanıtını şu 4 başlık altında yapılandır:

### 📊 Durum Analizi & Gerçekçi Yaklaşım
Kullanıcının profilinden (varsa) ve bağlamdaki kayıtlardan yola çıkarak kısa bir durum özeti.

### 🚀 Nokta Atışı Teşvik ve Hibe Eşleşmesi
Bağlamda geçen programlardan kullanıcıya en uygun olanları: Teşvik Adı, \
Destek Oranı/Limiti (SADECE bağlamda geçiyorsa), Bütçeye Etkisi.

### 💡 Stratejik Değerlendirme
Bağlamdaki bilgilerden çıkarılabilecek, kullanıcının fark etmemiş olabileceği bir bağlantı/fırsat.

### 📞 Doğrudan Temas & Aksiyon Planı
Bağlamdaki kaynak URL'lerini ve kurum adlarını kullanarak somut sonraki adım.

Emin olmadığın her yerde bunu açıkça belirt. Kısa ve net Türkçe cevap ver."""


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


def _kurum_iletisim_metni(matches: list[Tesvik]) -> str:
    """Bulunan kayitlarin ait oldugu kurumlarin dogrulanmis iletisim
    bilgilerini doner - bos ise (kurum rehberde yoksa) o kurum icin
    satir eklenmez, LLM'in numara icat etmesine gerek kalmaz."""
    kurumlar = sorted({m.kurum for m in matches if m.kurum})
    if not kurumlar:
        return ""

    db = SessionLocal()
    try:
        satirlar = []
        for kurum in kurumlar:
            k = db.query(KurumIletisim).filter(KurumIletisim.kurum == kurum).first()
            if k is None:
                continue
            satirlar.append(
                f"- {k.kurum} ({k.kurum_tam_ad or ''}): Çağrı merkezi {k.cagri_merkezi_no or '—'}, "
                f"Genel merkez {k.genel_merkez_no or '—'}, Adres: {k.adres or '—'}. "
                f"(Doğrulama kaynağı: {k.kaynak_url}, doğrulama tarihi: {k.dogrulama_tarihi})"
            )
        return "\n".join(satirlar)
    finally:
        db.close()


def _baglam_metni(matches: list[Tesvik], profil: dict | None) -> str:
    kayitlar = "\n\n".join(
        f"[{m.kurum}] {m.baslik}\nKaynak: {m.kaynak_url}\n{_kisalt(m.detay, 600)}"
        for m in matches
    )
    iletisim = _kurum_iletisim_metni(matches)
    iletisim_blogu = (
        f"\n\nDOĞRULANMIŞ KURUM İLETİŞİM BİLGİLERİ (bu numaraları/adresleri "
        f"kullanabilirsin, kaynağı gösterilmiştir):\n{iletisim}"
        if iletisim else ""
    )

    if not profil:
        return f"TEŞVİK KAYITLARI:\n{kayitlar}{iletisim_blogu}\n\nKULLANICI PROFİLİ: (henüz girilmemiş)"

    profil_satirlari = "\n".join(f"- {k}: {v}" for k, v in profil.items() if v not in (None, "", []))
    return (
        f"TEŞVİK KAYITLARI:\n{kayitlar}{iletisim_blogu}\n\n"
        f"KULLANICI PROFİLİ:\n{profil_satirlari or '(profil alanları boş)'}"
    )


def _claude_cevap(query: str, matches: list[Tesvik], profil: dict | None) -> str | None:
    """Claude API ile bulunan kayitlari + kullanici profilini yorumlayip
    yapilandirilmis cevap uretir. API anahtari yoksa veya cagri basarisiz
    olursa None doner - cagiran taraf liste formatina duser, hicbir zaman
    crash etmez."""
    if not settings.ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    baglam = _baglam_metni(matches, profil)

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=SISTEM_PROMPTU,
            messages=[{
                "role": "user",
                "content": f"BAĞLAM:\n{baglam}\n\nKULLANICI SORUSU: {query}",
            }],
            timeout=CLAUDE_TIMEOUT_SEC,
        )
        parcalar = [blok.text for blok in resp.content if getattr(blok, "type", None) == "text"]
        cevap = "".join(parcalar).strip()
        return cevap or None
    except Exception:
        # Ag hatasi, rate limit, gecersiz anahtar, timeout - hepsi ayni
        # sekilde ele alinir: sessizce fallback'e dus, kullaniciyi
        # hata mesajiyla degil cevapla karsila.
        return None


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


def answer(query: str, profil: dict | None = None) -> str:
    matches = retrieve(query)

    if not matches:
        return (
            "Bu soruyla eşleşen bir teşvik/destek programı bulamadım. "
            "Farklı anahtar kelimelerle (örn. kurum adı, sektör, \"girişimci\", "
            "\"dijital dönüşüm\" gibi) tekrar deneyebilir ya da doğrudan "
            "KOSGEB, TÜBİTAK, KGF veya Ticaret Bakanlığı'nın resmi sitelerine "
            "bakabilirsiniz."
        )

    claude_cevap = _claude_cevap(query, matches, profil)
    if claude_cevap is not None:
        return claude_cevap

    if OLLAMA_ETKIN:
        llm_cevap = _ollama_cevap(query, matches)
        if llm_cevap is not None:
            return llm_cevap

    return _liste_formati(matches)
