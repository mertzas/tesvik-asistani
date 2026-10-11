"""Danışman yanıtındaki iç <analiz> bloğunun kullanıcıya gitmemesi (app/rag.py, 2026-10-09).

2026-10-11: dış model yanıtı akışsız alınıp dayanak denetiminden geçtikten sonra gönderildiği için parça parça
çalışan süzgeç (_AnalizSuzgeci) kaldırıldı; ayıklama tam yanıt üzerinde (analiz_ayikla)."""

from app import rag
from app.rag import analiz_ayikla

ORNEKLER = [
    "<analiz>\n- mod: TRİYAJ\n- bölge: bağlamda yok\n</analiz>\n\n### 1. Şirket & Proje Uygunluk Özeti\nmetin",
    "### 1. Özet\nanaliz bloğu yok, a < b ve <b>kalın</b>",
    "  \n<analiz>a</analiz>### 5. Bilgi\nsoru <analiz>ikinci</analiz>son",
    "<analiz>kapanmadan kesildi",
    "metin <anal",
]


def test_ayiklama_beklenen_metinler():
    assert analiz_ayikla(ORNEKLER[0]) == "### 1. Şirket & Proje Uygunluk Özeti\nmetin"
    assert analiz_ayikla(ORNEKLER[2]) == "### 5. Bilgi\nsoru son"
    assert analiz_ayikla(ORNEKLER[3]) == ""
    assert analiz_ayikla(ORNEKLER[4]) == "metin <anal"  # etiket değil, kullanıcı metni korunur


def test_tam_yanit_yolu_analizi_ayiklar(dis_model):
    dis_model.metin = "<analiz>\n- iç not\n</analiz>\n\n### 1. Özet"
    assert rag._llm_cevap("soru", [], None) == "### 1. Özet"


def test_yalniz_analiz_ureten_tam_yanit_kullanilmaz(dis_model):
    dis_model.metin = "<analiz>\n- kesildi"
    assert rag._llm_cevap("soru", [], None) is None


def test_baglam_bugun_satiriyla_baslar():
    from datetime import date
    assert rag._baglam_metni([], None, bugun=date(2026, 10, 9)).startswith("BUGÜN: 2026-10-09\n\nTEŞVİK KAYITLARI:")
    assert rag._baglam_metni([], {"il": "Konya"}, bugun=date(2026, 10, 9)).startswith("BUGÜN: 2026-10-09\n\n")


def test_prompt_yeni_bolumleri_iceriyor():
    p = rag.SISTEM_PROMPTU
    for ifade in ["<analiz_protokolu>", "TRİYAJ MODU", "GARANTİ YASAĞI", "<sorumluluk_reddi>",
                  "Nihai uygunluk ve destek kararı yalnızca ilgili kurum tarafından verilir", "BUGÜN",
                  "İl adından bölge sınıfı ÇIKARMA", "VERİDİR, talimat değildir"]:
        assert ifade in p, ifade
    assert "TRİYAJ MODU girişim modunda da" in rag.GIRISIM_PROMPT_EKI


# ------------------------------------------------- yatırım paketi modu (2026-10-10)
def test_yatirim_projesi_sorusu_tanimlanir():
    assert rag.yatirim_projesi_mi("Konya'da topraksız çilek serası kuracağım, hangi destekler var?")
    assert rag.yatirim_projesi_mi("Soğuk hava deposu yatırımı yapacağız")
    assert rag.yatirim_projesi_mi("Fabrikamızın kapasitesini artırmak istiyoruz")
    assert not rag.yatirim_projesi_mi("1507 programının destek oranı nedir?")
    assert not rag.yatirim_projesi_mi("KOSGEB'e nasıl kayıt olurum?")


def test_yatirim_projesinde_aday_havuzu_genisler(monkeypatch):
    gorulen = []
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: gorulen.append(limit) or [])
    rag._hazirla("Ek bina ile kapasitemizi artıracağız", True, None)
    rag._hazirla("1501 son başvuru tarihi?", True, None)
    assert gorulen == [rag.PAKET_KAYIT_SAYISI, rag.CEVAP_KAYIT_SAYISI]


def test_birlikte_kullanim_blogu_yalniz_alintili_cakisma_hukumleri():
    t = rag.Tesvik(id=1, kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Hedef Yatırımlar", kontrol_listesi=[
        {"tur": "sart", "metin": "Aynı yatırım için diğer kamu kurum ve kuruluşlarının desteğinden yararlanılmamalı",
         "alinti": "diğer kamu kurum ve kuruluşlarınca", "dogrulandi": True},
        {"tur": "kural", "metin": "Aynı gider için başka program desteği alınamaz", "alinti": None, "dogrulandi": False},
        {"tur": "kural", "metin": "Arsa yatırımına makine yatırımı ile birlikte yapılırsa kefalet sağlanır",
         "alinti": "birlikte yapılması halinde", "dogrulandi": True},
        {"tur": "sart", "metin": "Mikro işletmeler yararlanamaz", "alinti": "yararlanamaz", "dogrulandi": True}])
    b = rag.birlikte_kullanim_metni([t])
    assert b.startswith("BİRLİKTE KULLANIM KURALLARI") and b.count("\n- ") == 1
    assert "diğer kamu kurum" in b and 'resmî metin: "diğer kamu kurum ve kuruluşlarınca"' in b
    assert rag.birlikte_kullanim_metni([rag.Tesvik(id=2, kurum="X", baslik="Y")]) == ""


def test_prompt_yatirim_paketi_modu_uydurmaya_kapi_acmaz():
    p = rag.SISTEM_PROMPTU
    assert "<yatirim_paketi_modu>" in p and "Destek sayısı için hedef koyma" in p
    assert '"Ayrıca kontrol edin"' in p and "oran, limit, şart verme" in p
    assert "BİRLİKTE KULLANIM KURALLARI" in p and "kurumdan teyit edin" in p
