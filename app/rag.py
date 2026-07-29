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

from app.models import SessionLocal, Tesvik, TesvikChunk, KurumIletisim, IlTarimMudurlugu, IlKosgebMudurlugu, settings


def retrieve_hybrid_rrf(query: str, limit: int = 5) -> list[Tesvik]:
    """Parent-Child Chunking tabanlı Hibrit Arama (BM25 Keyword + Vector Embedding)
    ve Reciprocal Rank Fusion (RRF) sıralaması."""
    db = SessionLocal()
    terms = _terimlere_ayir(query)
    if not terms:
        res = db.query(Tesvik).limit(limit).all()
        db.close()
        return res

    child_chunks = db.query(TesvikChunk).filter(TesvikChunk.chunk_type == "child").all()
    if not child_chunks:
        db.close()
        return retrieve(query, limit=limit)

    # 1. Child Chunk'lar üzerinde metin araması (BM25 Rank)
    keyword_ranks = {}
    for c in child_chunks:
        c_text = c.metin.lower()
        score = sum(c_text.count(t) for t in terms)
        if score > 0:
            keyword_ranks[c.id] = score

    sorted_keyword = sorted(keyword_ranks.keys(), key=lambda cid: keyword_ranks[cid], reverse=True)
    keyword_rank_map = {cid: idx + 1 for idx, cid in enumerate(sorted_keyword)}

    # 2. Vektör Araması (Vector Similarity Rank)
    from app.chunking import _simple_embedding
    q_vec = _simple_embedding(query)

    def cos_sim(v1, v2):
        if not v1 or not v2:
            return 0.0
        return sum(a * b for a, b in zip(v1, v2))

    vector_scores = {}
    for c in child_chunks:
        if c.embedding:
            sim = cos_sim(q_vec, c.embedding)
            if sim > 0.1:
                vector_scores[c.id] = sim

    sorted_vector = sorted(vector_scores.keys(), key=lambda cid: vector_scores[cid], reverse=True)
    vector_rank_map = {cid: idx + 1 for idx, cid in enumerate(sorted_vector)}

    # 3. Reciprocal Rank Fusion (RRF)
    rrf_scores = {}
    all_cids = set(keyword_rank_map.keys()) | set(vector_rank_map.keys())

    for cid in all_cids:
        k_rank = keyword_rank_map.get(cid, 999)
        v_rank = vector_rank_map.get(cid, 999)
        rrf_scores[cid] = (1.0 / (60 + k_rank)) + (1.0 / (60 + v_rank))

    sorted_cids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    # 4. Top Child Chunk'lardan Parent Teşvik kayıtlarını çıkarma
    matched_tesvik_ids = []
    seen = set()
    for cid in sorted_cids:
        chunk = db.query(TesvikChunk).filter(TesvikChunk.id == cid).first()
        if chunk and chunk.tesvik_id not in seen:
            seen.add(chunk.tesvik_id)
            matched_tesvik_ids.append(chunk.tesvik_id)

    matched_tesvikler = [
        db.query(Tesvik).filter(Tesvik.id == tid).first()
        for tid in matched_tesvik_ids
        if db.query(Tesvik).filter(Tesvik.id == tid).first() is not None
    ]
    db.close()

    return matched_tesvikler[:limit] if matched_tesvikler else retrieve(query, limit=limit)

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

AKTİFLİK KURALI: Bir kaydın yanında "⚠️ DURUM: ARTIK AKTİF DEĞİL" yazıyorsa, \
bu programı kullanıcıya başvurabileceği bir seçenek gibi SUNMA - varlığından \
bahsedebilirsin ama açıkça "bu program artık kapalı/geçmiş" de. "DURUM: \
Doğrulanmış, güncel/aktif program" yazan kayıtları güvenle önerebilirsin. \
Hiçbir durum notu yoksa (aktiflik hiç kontrol edilmemişse), kullanıcıya \
"bu programın hâlâ açık olup olmadığını kurumun kendi sayfasından teyit edin" \
diye açıkça hatırlat.

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

    def skor(t: Tesvik) -> float:
        # Ham terim sayimi, uzun "detay" metinli kayitlari (genel gecer
        # kelimeleri cok kez tekrarladiklari icin) tam program kodu eslesmesi
        # (orn. "1507") yapan kisa kayitlara karsi haksiz yere on plana
        # cikariyordu - detay/ozet katkisini metin uzunluguna gore normalize
        # ediyoruz, baslik eslesmesine (ozellikle program kodu gibi tam
        # eslesmelere) çok daha yuksek agirlik veriyoruz.
        gövde = f"{t.ozet or ''} {t.detay or ''}".lower()
        gövde_skoru = sum(gövde.count(term) for term in terms) / max(len(gövde), 1) * 1000
        baslik_kucuk = t.baslik.lower()
        baslik_skoru = sum(10 for term in terms if term in baslik_kucuk)
        tam_kod_bonus = sum(20 for term in terms if term.isdigit() and baslik_kucuk.startswith(term))
        return gövde_skoru + baslik_skoru + tam_kod_bonus

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


def _il_iletisim_metni(profil: dict | None) -> str:
    """Kullanicinin profilindeki 'bölge' (il adi) alaniyla eslesen Tarim Il
    Mudurlugu satirini doner. Telefon/adres o il icin dogrulanmamissa
    (url_dogrulandi=False) SADECE resmi linki verir, numara/adres uydurmaz -
    LLM'e "bu ilin telefonu dogrulanmadi, linke yonlendir" bilgisini de
    acikca gecirir."""
    if not profil:
        return ""
    il_adi = (profil.get("bölge") or "").strip()
    if not il_adi:
        return ""

    db = SessionLocal()
    try:
        il = db.query(IlTarimMudurlugu).filter(IlTarimMudurlugu.il_adi.ilike(il_adi)).first()
        if il is None:
            return ""
        if il.url_dogrulandi:
            return (
                f"{il.il_adi} Tarım ve Orman İl Müdürlüğü: Telefon {il.telefon}, "
                f"Adres: {il.adres}. (Doğrulama kaynağı: {il.kaynak_url}, "
                f"doğrulama tarihi: {il.dogrulama_tarihi})"
            )
        return (
            f"{il.il_adi} Tarım ve Orman İl Müdürlüğü için telefon/adres henüz "
            f"doğrulanmadı - kullanıcıyı resmi sayfaya yönlendir: {il.kaynak_url} "
            f"(telefon numarası UYDURMA, sadece bu linki ver)."
        )
    finally:
        db.close()


def _kosgeb_il_iletisim_metni(profil: dict | None) -> str:
    """Kullanicinin 'bölge' alaniyla eslesen KOSGEB Il Mudurlugu satirini
    doner. IlTarimMudurlugu'ndan farkli olarak buradaki 81 ilin TAMAMI
    dogrulandi (bkz. scripts/seed_il_kosgeb_mudurlugu.py), o yuzden burada
    "dogrulanmadi" dalina hic gerek yok."""
    if not profil:
        return ""
    il_adi = (profil.get("bölge") or "").strip()
    if not il_adi:
        return ""

    db = SessionLocal()
    try:
        il = db.query(IlKosgebMudurlugu).filter(IlKosgebMudurlugu.il_adi.ilike(il_adi)).first()
        if il is None:
            return ""
        metin = (
            f"{il.mudurluk_adi}: Telefon {il.telefon}, Adres: {il.adres}"
            + (f", E-posta: {il.eposta}" if il.eposta else "")
            + f". (Doğrulama kaynağı: {il.kaynak_url}, doğrulama tarihi: {il.dogrulama_tarihi})"
        )
        if il.ek_mudurlukler:
            for ek in il.ek_mudurlukler:
                metin += f"\nAyrıca: {ek.get('ad')}: Telefon {ek.get('telefon')}, Adres: {ek.get('adres')}"
        return metin
    finally:
        db.close()


def _tesvik_detay_metni(m: Tesvik) -> str:
    """Tesvik kaydinin TUM yapilandirilmis alanlarini (sadece serbest metin
    detay degil) LLM baglamina yazar - basvuru_sartlari/tutar/aktif_mi gibi
    Faz 3'te doldurulan alanlar bu fonksiyon olmadan LLM'e hic gorunmezdi."""
    satirlar = [f"[{m.kurum}] {m.baslik}", f"Kaynak: {m.kaynak_url}", _kisalt(m.detay, 500)]

    if m.aktif_mi is False:
        satirlar.append(f"⚠️ DURUM: ARTIK AKTİF DEĞİL. {m.durum_notu or ''}")
    elif m.aktif_mi is True:
        satirlar.append(f"DURUM: Doğrulanmış, güncel/aktif program. {m.durum_notu or ''}")

    if m.basvuru_sartlari:
        satirlar.append("Başvuru şartları: " + "; ".join(m.basvuru_sartlari))
    if m.gerekli_belgeler:
        satirlar.append("Gerekli belgeler: " + "; ".join(m.gerekli_belgeler))
    if m.basvuru_yeri:
        satirlar.append(f"Başvuru yeri: {m.basvuru_yeri}")
    if m.basvuru_suresi:
        satirlar.append(f"Başvuru süresi/dönemi: {m.basvuru_suresi}")
    if m.destek_verilme_suresi:
        satirlar.append(f"Destek/proje süresi: {m.destek_verilme_suresi}")
    if m.tutari_hesaplama_formulu:
        satirlar.append(f"Tutar/oran: {m.tutari_hesaplama_formulu}")
    elif m.tutari_max:
        satirlar.append(f"Azami tutar: ₺{m.tutari_max:,.0f}")

    return "\n".join(satirlar)


def _baglam_metni(matches: list[Tesvik], profil: dict | None) -> str:
    kayitlar = "\n\n".join(_tesvik_detay_metni(m) for m in matches)
    iletisim = _kurum_iletisim_metni(matches)
    iletisim_blogu = (
        f"\n\nDOĞRULANMIŞ KURUM İLETİŞİM BİLGİLERİ (bu numaraları/adresleri "
        f"kullanabilirsin, kaynağı gösterilmiştir):\n{iletisim}"
        if iletisim else ""
    )

    il_iletisim = _il_iletisim_metni(profil)
    il_blogu = f"\n\nKULLANICININ İLİNE ÖZEL TARIM İLETİŞİMİ: {il_iletisim}" if il_iletisim else ""

    kosgeb_il_iletisim = _kosgeb_il_iletisim_metni(profil)
    kosgeb_il_blogu = (
        f"\n\nKULLANICININ İLİNE ÖZEL KOSGEB MÜDÜRLÜĞÜ: {kosgeb_il_iletisim}"
        if kosgeb_il_iletisim else ""
    )

    if not profil:
        return f"TEŞVİK KAYITLARI:\n{kayitlar}{iletisim_blogu}\n\nKULLANICI PROFİLİ: (henüz girilmemiş)"

    profil_satirlari = "\n".join(f"- {k}: {v}" for k, v in profil.items() if v not in (None, "", []))
    return (
        f"TEŞVİK KAYITLARI:\n{kayitlar}{iletisim_blogu}{il_blogu}{kosgeb_il_blogu}\n\n"
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
    matches = retrieve_hybrid_rrf(query)

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
