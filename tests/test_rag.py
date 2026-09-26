"""app/rag.py testleri - AI danışmanın "uydurma yapmama" sözleşmesi.

Bu modülün en kritik özelliği ne kadar akıllı cevap verdiği değil, YANLIŞ
bilgi üretmemesi: sistem promptu Claude'a bağlamda olmayan hiçbir somut
veriyi (telefon, oran, tutar, tarih) icat etmemesini söylüyor ve kapalı
programları "başvurabilirsiniz" diye sunmamasını emrediyor. Kullanıcı bu
çıktıya göre kuruma gidiyor; uydurma bir oran ya da kapanmış bir program
gerçek zaman ve para kaybı demek.

Testler ağ çağrısı yapmaz: Claude katmanı taklit edilir (monkeypatch), böylece
hem API anahtarı olmadan çalışır hem de "Claude çökerse ne olur" yolu gerçekten
sınanır - bu yol üretimde sessizce devreye giriyor.
"""
import pytest

from app import rag
from app.models import Tesvik


def _tesvik(baslik, ozet="", detay="", kurum="KOSGEB", **kw):
    return Tesvik(baslik=baslik, ozet=ozet, detay=detay, kurum=kurum, **kw)


# ------------------------------------------------------- terim ayrıştırma

def test_durak_kelimeler_ve_kisa_terimler_atilir():
    """Dolgu kelimeler ILIKE '%...%' ile veritabanının çoğuna eşleşiyordu.

    Ölçüm (2026-09-26): "ben" 176 kaydın 46'sına ("benzeri", "beklenen"
    içinde), "ile" 168'ine eşleşiyordu. Yani "ben çilek yetiştiriyorum"
    sorgusunda sonuç kümesi neredeyse tüm veritabanı oluyor ve sıralama
    anlamsızlaşıyordu.
    """
    terimler = rag._terimlere_ayir("Ben bir KOSGEB desteği arıyorum")
    assert terimler == ["kosgeb", "desteği"], terimler
    assert all(len(t) > 2 for t in terimler)


def test_anlamli_kelimeler_durak_listesine_karismamis():
    """Liste büyütülürken "destek"/"hibe"/"kredi" gibi kelimeler yanlışlıkla
    eklenirse arama tamamen çalışmaz hale gelir."""
    for kelime in ("destek", "hibe", "kredi", "kosgeb", "tübitak", "tarım",
                   "başvuru", "faiz", "kefalet", "yatırım"):
        assert kelime not in rag.DURAK_KELIMELER


def test_noktalama_temizlenir():
    assert rag._terimlere_ayir("Ar-Ge desteği?") == ["ar-ge", "desteği"]


def test_buyuk_harfle_yazilan_sorgu_calisir():
    """Python'un str.lower()'i Türkçe "İ"yi bozuyor ("i" + birleşik nokta);
    caps lock ile yazan kullanıcının hiçbir terimi kayda eşleşmiyordu."""
    terimler = rag._terimlere_ayir("ÇİLEK SERASI İÇİN HİBE VAR MI")
    assert "çilek" in terimler
    assert "hibe" in terimler
    # Bozulmuş biçim (i + U+0307) hiç üretilmemeli.
    assert not any("̇" in t for t in terimler)


# --------------------------------------------------------------- kısaltma

def test_kisalt_uzunlugu_asmaz_ve_kelimeyi_bolmez():
    metin = "kelime " * 100
    k = rag._kisalt(metin, uzunluk=50)
    assert len(k) <= 52  # + üç nokta
    assert k.endswith("…")
    # Kelime ortasından kesilmemeli.
    assert not k.replace("…", "").endswith("keli")


def test_kisalt_kisa_metni_degistirmez():
    assert rag._kisalt("kısa metin", uzunluk=100) == "kısa metin"


# --------------------------------------------- sistem promptu sözleşmesi

def test_sistem_promptu_uydurma_yasagini_iceriyor():
    """Bu cümle promptan silinirse model serbestçe telefon/oran icat eder.

    Somut bir olay: daha önce modele kurum telefonları sorulduğunda bağlamda
    olmayan numaralar üretiliyordu; kullanıcı yanlış numarayı arıyordu.
    """
    p = rag.SISTEM_PROMPTU
    assert "UYDURMA" in p
    assert "telefon" in p.lower()


def test_sistem_promptu_kapali_program_kuralini_iceriyor():
    """Kapanmış bir programı "başvurabilirsiniz" diye sunmak, kullanıcıyı
    boşa evrak toplamaya gönderir."""
    p = rag.SISTEM_PROMPTU
    assert "AKTİF DEĞİL" in p or "aktif değil" in p.lower()
    assert "kapalı" in p.lower() or "kapandı" in p.lower() or "geçmiş" in p.lower()


def test_sistem_promptu_dogrulanmamis_kayit_icin_teyit_istiyor():
    p = rag.SISTEM_PROMPTU
    assert "teyit" in p.lower()


# ------------------------------------------------------- liste formatı (yedek)

def test_liste_formati_kayitlari_ve_kurumu_gosterir():
    kayitlar = [
        _tesvik("İşletme Geliştirme Desteği", ozet="KOBİ'lere yönelik destek."),
        _tesvik("1507 KOBİ Ar-Ge Başlangıç", ozet="Ar-Ge projeleri.", kurum="TÜBİTAK"),
    ]
    metin = rag._liste_formati(kayitlar)
    assert "İşletme Geliştirme Desteği" in metin
    assert "1507" in metin
    assert "TÜBİTAK" in metin
    assert "2" in metin  # kaç program bulunduğu


def test_liste_formati_bos_listede_coksmez():
    metin = rag._liste_formati([])
    assert isinstance(metin, str)


# ------------------------------------------------ answer() akışı ve yedeğe düşme

def test_eslesme_yoksa_yonlendirme_metni_doner(monkeypatch):
    """Sonuç yoksa uydurma bir program değil, kurumlara yönlendirme dönmeli."""
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5: [])
    cevap = rag.answer("bu sorguyla hiçbir şey eşleşmeyecek xyzzy")
    assert "bulamadım" in cevap
    assert "KOSGEB" in cevap


def test_claude_cevap_verirse_o_kullanilir(monkeypatch):
    kayit = _tesvik("Dijital Dönüşüm Desteği", ozet="Yazılım ve makine desteği.")
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5: [kayit])
    monkeypatch.setattr(rag, "_claude_cevap",
                        lambda q, m, p: "### 📊 Durum Analizi\nAI cevabı")
    cevap = rag.answer("dijital dönüşüm")
    assert "AI cevabı" in cevap


def test_claude_yoksa_liste_formatina_dusulur(monkeypatch):
    """Üretimde sessizce devreye giren yol: anahtar yok / kota bitti / ağ hatası.

    Kullanıcı boş ekran değil, en azından gerçek kayıtların listesini görmeli.
    """
    kayit = _tesvik("Dijital Dönüşüm Desteği", ozet="Yazılım ve makine desteği.")
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5: [kayit])
    monkeypatch.setattr(rag, "_claude_cevap", lambda q, m, p: None)
    monkeypatch.setattr(rag, "OLLAMA_ETKIN", False)

    cevap = rag.answer("dijital dönüşüm")
    assert "Dijital Dönüşüm Desteği" in cevap


def test_claude_patlarsa_uygulama_coksmez_ve_gunluge_yazilir(monkeypatch, caplog):
    """_claude_cevap içindeki istisna yutuluyor ama İZ BIRAKMALI.

    Daha önce sebep hiçbir yere yazılmıyordu; "AI cevap vermiyor" şikayeti
    geldiğinde (kota mı, anahtar mı, ağ mı) anlamanın yolu yoktu.
    """
    import logging

    kayit = _tesvik("Test Programı", ozet="özet")
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5: [kayit])
    monkeypatch.setattr(rag, "OLLAMA_ETKIN", False)

    class SahteIstemci:
        def __init__(self, *a, **kw):
            raise RuntimeError("kota bitti")

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", SahteIstemci)
    monkeypatch.setattr(rag.settings, "ANTHROPIC_API_KEY", "sk-test-anahtar")

    with caplog.at_level(logging.WARNING, logger="app.rag"):
        cevap = rag.answer("test")

    assert "Test Programı" in cevap, "yedek liste formatına düşülmeliydi"
    assert any("kota bitti" in k.message or "kota bitti" in str(k.args)
               or "RuntimeError" in k.getMessage() for k in caplog.records), \
        f"başarısızlık sebebi günlüğe yazılmadı: {[k.getMessage() for k in caplog.records]}"


def test_anahtar_yoksa_claude_cagrilmaz(monkeypatch):
    """Anahtar boşsa boşuna ağ çağrısı yapılmamalı."""
    monkeypatch.setattr(rag.settings, "ANTHROPIC_API_KEY", "")
    assert rag._claude_cevap("soru", [_tesvik("x")], None) is None
