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
import logging

import requests

from app.models import SessionLocal, Tesvik, KurumIletisim, IlTarimMudurlugu, IlKosgebMudurlugu, settings
from sqlalchemy import or_

from app.urun_sektor_anahtarlari import (
    anahtar_kelimeden_sektor_bul,
    govde,
    kucult,
)

logger = logging.getLogger(__name__)

OLLAMA_ETKIN = False  # True yapinca Gemma ile dogal dil cevap tekrar devreye girer
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4"
OLLAMA_TIMEOUT_SEC = 150

CLAUDE_TIMEOUT_SEC = 30
CLAUDE_MAX_TOKENS = 1800

# Anlamli sinyal tasimayan, aramada gurultu yaratan kisa/genel kelimeler.
# Aramada anlamsiz olan ama ILIKE '%...%' ile veritabaninin cogunluguna
# eslesen kelimeler. Olcum (2026-09-26): "ben" 176 kaydin 46'sina ("benzeri",
# "beklenen" icinde), "ile" 168'ine eslesiyordu - yani kullanici "ben cilek
# yetistiriyorum" yazdiginda sonuc kumesi neredeyse tum veritabani oluyor ve
# siralama anlamsizlasıyordu. Liste bilerek yalnizca islev kelimelerini
# iceriyor; "destek", "hibe", "kredi" gibi anlam tasiyan kelimeler DISARIDA.
DURAK_KELIMELER = {
    # soru ve baglac
    "için", "icin", "ile", "hangi", "hangisi", "nasıl", "nasil", "nedir",
    "neler", "nelerdir", "kimler", "veya", "ya", "yada", "ama", "ancak",
    "ise", "gibi", "kadar", "göre", "gore",
    # zamir
    "ben", "bana", "benim", "sen", "size", "siz", "sizin", "biz", "bize",
    "bizim", "bunu", "bunlar", "bunları", "bunlari", "onlar", "kendi",
    # yaygin dolgu
    "var", "yok", "olan", "olur", "olabilir", "daha", "çok", "cok", "şey",
    "sey", "sonra", "önce", "once", "istiyorum", "istiyoruz", "yapmak",
    "almak", "arıyorum", "ariyorum", "hakkında", "hakkinda", "mı", "mi", "mu", "mü", "bir", "bu",
    "şu", "su",
    "the", "and", "des",
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
    # kucult() kullaniliyor, str.lower() DEGIL: Python'da "İ".lower() tek harf
    # degil "i̇" (i + U+0307 birlesik nokta) uretiyor, dolayisiyla caps lock
    # ile yazan kullanicinin terimleri hicbir kayda eslesmiyordu
    # (dogrulandi 2026-09-26, bkz. app/urun_sektor_anahtarlari.kucult).
    terms = [kucult(t.strip(".,!?:;\"'()")) for t in query.split()]
    return [t for t in terms if len(t) > 2 and t not in DURAK_KELIMELER]


def retrieve(query: str, limit: int = 5) -> list[Tesvik]:
    db = SessionLocal()
    terms = _terimlere_ayir(query)
    q = db.query(Tesvik)
    if terms:
        # Her terim icin hem tam hali hem govdesi araniyor (bkz. govde()).
        aranacak = []
        for t in terms:
            aranacak.append(t)
            g = govde(t)
            if g != t:
                aranacak.append(g)
        conditions = [
            Tesvik.baslik.ilike(f"%{t}%") | Tesvik.ozet.ilike(f"%{t}%") | Tesvik.detay.ilike(f"%{t}%")
            for t in aranacak
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
        metin = kucult(f"{t.ozet or ''} {t.detay or ''}")
        baslik_kucuk = kucult(t.baslik or "")
        # Tam terim eslesmesi govde eslesmesinden daha degerli: "serası" ile
        # birebir eslesen kayit, yalnizca "sera" govdesiyle eslesenin onunde
        # olmali.
        metin_skoru = 0.0
        baslik_skoru = 0.0
        for term in terms:
            g = govde(term)
            metin_skoru += metin.count(term) * 1.0
            baslik_skoru += 10 if term in baslik_kucuk else 0
            if g != term:
                metin_skoru += metin.count(g) * 0.5
                baslik_skoru += 6 if g in baslik_kucuk else 0
        metin_skoru = metin_skoru / max(len(metin), 1) * 1000
        tam_kod_bonus = sum(20 for term in terms
                            if term.isdigit() and baslik_kucuk.startswith(term))
        return metin_skoru + baslik_skoru + tam_kod_bonus

    candidates.sort(key=skor, reverse=True)

    # SEKTOR GENISLEMESI
    #
    # Sorguda taninan bir urun/faaliyet adi geciyorsa (orn. "cilek", "sut"),
    # o sektore etiketli kayitlar gevsek bir ILIKE eslesmesinden DAHA
    # alakalidir. Program adlari nadiren urun adi gecirdigi icin
    # (bkz. app/urun_sektor_anahtarlari.py) literal arama tek basina
    # yaniltici sonuc veriyor.
    #
    # Iki somut hata bu blokla kapandi (ikisi de 2026-09-26'da olculdu):
    #
    # 1) Genisleme yalnizca app/main.py sor() icinde, kullaniciya gosterilen
    #    SONUC LISTESI icin yapiliyordu; answer() ham soruyla cagrildigi icin
    #    Claude bu kayitlari HIC gormuyordu. "CILEK SERASI ICIN HIBE VAR MI"
    #    sorgusu listede 10 dogru kayit ("Sera/Ortualti Tarim Destekleri"
    #    dahil) gosterirken ayni yanitin mesaj alani "eslesen bir tesvik
    #    bulamadim" diyordu - ayni ekranda birbiriyle celisen iki cevap.
    #
    # 2) Genislemeyi "literal sonuc azsa ekle" seklinde yazmak yetmiyor:
    #    ayni sorguda "hibe" kelimesi 5 alakasiz KGF kredi kaydina eslesip
    #    kotayi doldurdugu icin genisleme HIC tetiklenmiyordu. Bu yuzden
    #    sektor eslesmelerine kotanin bir kismi AYRILIYOR.
    hedef_sektor = anahtar_kelimeden_sektor_bul(query)
    if not hedef_sektor:
        return candidates[:limit]

    literal_idler = {t.id for t in candidates}
    sektor_kayitlari = _sektor_kayitlari(hedef_sektor, skor)

    # Kotanin en az %60'i sektor eslesmelerine ayrilir; kalan yer literal
    # eslesmelere kalir, boylece program kodu gibi tam eslesmeler kaybolmaz.
    sektor_payi = max(1, round(limit * 0.6))
    secilen = sektor_kayitlari[:sektor_payi]
    secilen_idler = {t.id for t in secilen}
    for t in candidates:
        if len(secilen) >= limit:
            break
        if t.id not in secilen_idler:
            secilen.append(t)
            secilen_idler.add(t.id)

    # Kota dolmadiysa kalan sektor kayitlariyla tamamla.
    for t in sektor_kayitlari[sektor_payi:]:
        if len(secilen) >= limit:
            break
        if t.id not in secilen_idler:
            secilen.append(t)
            secilen_idler.add(t.id)

    # Sektor kayitlari kendi metin skoruna gore one gecsin, ama literal
    # eslesme yapanlar (ayni zamanda sektorde olanlar) en ustte kalsin.
    secilen.sort(key=lambda t: (t.id not in literal_idler, -skor(t)))
    return secilen[:limit]


def _sektor_kayitlari(sektor: str, skor) -> list[Tesvik]:
    """Verilen sektore etiketli tesvikleri, metin skoruna gore sirali doner."""
    db = SessionLocal()
    try:
        bulunan = []
        for t in db.query(Tesvik).all():
            if t.aktif_mi is False:
                continue  # kapanmis programi one cikarmanin anlami yok
            etiketler = {
                x.lower()
                for x in (t.uygunluk_kriterleri or {}).get("sektorler", [])
            }
            if sektor in etiketler:
                db.expunge(t)  # oturum kapandiktan sonra alanlar okunabilsin
                bulunan.append(t)
        bulunan.sort(key=skor, reverse=True)
        return bulunan
    finally:
        db.close()


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
    except Exception as e:
        # Ag hatasi, rate limit, gecersiz anahtar, timeout - hepsi ayni
        # sekilde ele alinir: KULLANICI acisindan sessizce fallback'e dus,
        # onu hata mesajiyla degil cevapla karsila. Ama sebebi MUTLAKA
        # gunluge yaz - aksi halde "AI cevap vermiyor" sikayetinin sebebini
        # (kota? anahtar? ag?) anlamanin hicbir yolu kalmiyor.
        logger.warning("Claude cagrisi basarisiz, liste formatina dusuluyor: %s: %s",
                       type(e).__name__, e)
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
