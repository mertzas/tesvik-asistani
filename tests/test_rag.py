"""app/rag.py testleri - AI danışmanın "uydurma yapmama" sözleşmesi.

Bu modülün en kritik özelliği ne kadar akıllı cevap verdiği değil, YANLIŞ
bilgi üretmemesi: sistem promptu dış modele bağlamda olmayan hiçbir somut
veriyi (telefon, oran, tutar, tarih) icat etmemesini söylüyor ve kapalı
programları "başvurabilirsiniz" diye sunmamasını emrediyor. Kullanıcı bu
çıktıya göre kuruma gidiyor; uydurma bir oran ya da kapanmış bir program
gerçek zaman ve para kaybı demek.

Testler ağ çağrısı yapmaz: dış model katmanı taklit edilir (dis_model fixture'ı), böylece
hem API anahtarı olmadan çalışır hem de "dış model çökerse ne olur" yolu gerçekten
sınanır - bu yol üretimde sessizce devreye giriyor.
"""

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

# ------------------------------------------------ answer() akışı ve yedeğe düşme

def test_eslesme_yoksa_yonlendirme_metni_doner(monkeypatch):
    """Sonuç yoksa uydurma bir program değil, kurumlara yönlendirme dönmeli."""
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [])
    cevap = rag.answer("bu sorguyla hiçbir şey eşleşmeyecek xyzzy")
    assert "bulamadım" in cevap
    assert "KOSGEB" in cevap


def _kayit():
    return _tesvik("Dijital Dönüşüm Desteği", ozet="Yazılım ve makine desteği.", kaynak_url="https://kosgeb.gov.tr/dd",
                   tesvil_tutari="300.000 TL'ye kadar, %60 destek", aktif_mi=True,
                   uygunluk_kriterleri={"sektorler": ["genel"]})


def test_dis_model_yaniti_denetimden_gecerse_kullanilir(monkeypatch, dis_model):
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [_kayit()])
    dis_model.metin = "### 1. Özet\nDijital Dönüşüm Desteği 300.000 TL'ye kadar, %60. Kaynak: https://kosgeb.gov.tr/dd"
    cevap = rag.answer("dijital dönüşüm")
    assert "300.000 TL" in cevap and "yerel danışman" not in cevap


def test_dis_model_yoksa_yerel_danisman_yanitlar(monkeypatch):
    """Varsayılan: dış servis yok; yanıt kayıtlardan kuralla, beş başlıkla gelir, dışarı veri çıkmaz."""
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [_kayit()])
    cevap = rag.answer("dijital dönüşüm", llm_kullan=True)
    assert "Dijital Dönüşüm Desteği" in cevap and "300.000 TL'ye kadar, %60 destek" in cevap
    assert "### 1. Şirket & Proje Uygunluk Özeti" in cevap and "yerel danışmanı" in cevap


def test_dis_model_patlarsa_coksmez_gunluge_yazilir_yerele_duser(monkeypatch, dis_model, caplog):
    """Hata yutulur ama İZ BIRAKIR; kullanıcı yerel danışmanın yanıtını alır."""
    import logging
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [_kayit()])
    dis_model.hata = RuntimeError("kota bitti")
    with caplog.at_level(logging.WARNING):
        cevap = rag.answer("dijital dönüşüm")
    assert "Dijital Dönüşüm Desteği" in cevap and "yerel danışmanı" in cevap
    assert any("RuntimeError" in k.getMessage() for k in caplog.records), [k.getMessage() for k in caplog.records]


def test_uydurma_bilgi_iceren_dis_yanit_kullaniciya_gitmez(monkeypatch, dis_model, caplog):
    """Dayanak denetimi: bağlamda olmayan tutar/URL içeren model yanıtı atılır."""
    import logging
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [_kayit()])
    dis_model.metin = "Bu programdan 750.000 TL hibe alırsınız: https://uydurma.example/basvuru"
    with caplog.at_level(logging.WARNING):
        cevap = rag.answer("dijital dönüşüm")
    assert "750.000" not in cevap and "uydurma.example" not in cevap and "yerel danışmanı" in cevap
    assert any("dayanak denetiminden geçmedi" in k.getMessage() for k in caplog.records)


def test_kesik_dis_yanit_kullanilmaz(monkeypatch, dis_model):
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [_kayit()])
    dis_model.durma = "length"
    assert "yerel danışmanı" in rag.answer("dijital dönüşüm")


def test_yapilandirma_yoksa_dis_cagri_yok():
    assert rag._llm_cevap("soru", [_kayit()], None) is None


def test_dis_model_istegi_sistem_promptu_ve_genis_butce(monkeypatch, dis_model):
    """Düşünen modellerde düşünme de bütçeden düşer; bütçe dar tutulamaz. Sistem promptu aynen gider."""
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [_kayit()])
    rag.answer("dijital dönüşüm")
    istek = dis_model.cagrilar[0]
    assert istek["max_tokens"] >= 16000 and istek["model"] == "test-model"
    assert istek["messages"][0] == {"role": "system", "content": rag.SISTEM_PROMPTU}
    assert "BAĞLAM:" in istek["messages"][1]["content"] and "BUGÜN:" in istek["messages"][1]["content"]


def test_sistem_promptu_danisman_formati_ve_durust_eleme():
    """5 başlıklı danışman formatı, net eleme ve risk analizi kuralları."""
    p = rag.SISTEM_PROMPTU
    for baslik in ["### 1. Şirket & Proje Uygunluk Özeti", "### 2. Eşleşen Teşvik ve Hibe Programları",
                   "### 3. Darboğazlar ve Kritik Şartlar", "### 4. Adım Adım Yol Haritası",
                   "### 5. Bilgi Eksikliği / Netleştirme"]:
        assert baslik in p, baslik
    assert "NET VE DÜRÜST ELEME" in p and "ÇİFT YÖNLÜ ANALİZ" in p
    assert "SADECE bağlamda geçiyorsa" in p, "oran/limit yalnızca bağlamdan gelmeli"
