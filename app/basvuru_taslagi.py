"""Başvuru ön taslağı (2026-10-08): seçilen teşvik için kullanıcının profilinden, dış dil modeliyle düzenlenebilir
bir başvuru metni taslağı üretir (2026-10-11'den beri kendi sunucumuzdaki model, app/llm_saglayici; üçüncü taraf
yapay zekâ servisi kullanılmaz). Evrak hazırlama desteğinin ikinci adımı (ilki: app/basvuru_listesi.py).

Sınırlar (bilerek):
  - Resmi başvuru formu DEĞİLDİR; kurumun güncel formuna aktarılacak metin taslağıdır. Bu, metnin başında yazar.
  - Model yalnızca verilen bilgiyi kullanır; bilinmeyen her şey "[DOLDURUN: ...]" olarak bırakılır, rakam uydurulmaz.
  - "Hazırlanacak belgeler ve şartlar" bölümü modelden DEĞİL, kontrol listesinden (kaydın kendi alanlarından) eklenir.
  - Profil yalnız kendi sunucumuzdaki modele (iç ağ) gider; kuruluş vazgeçtiyse çağrılmaz
    (llm_saglayici.riza_gecerli_mi); çağıran uç nokta denetler.
  - Modelin metni app/dayanak.py ile denetlenir: bağlamda olmayan tutar/oran/tarih/URL varsa taslak verilmez.

Maliyet: tek çağrı; girdi ~2-3 bin, çıktı en çok TASLAK_MAX_TOKENS token. Kuruluş başına günlük sınır uç noktada.

    python -m app.basvuru_taslagi --self-test      (ağ yok, ücretsiz)
"""
from __future__ import annotations

import logging
import sys

from app import dayanak, llm_saglayici
from app.models import Tesvik

logger = logging.getLogger(__name__)

TASLAK_MAX_TOKENS = 12000   # düşünen modellerde düşünme de bütçeden düşer
BASLIK_NOTU = ("> **Ön taslak — resmi başvuru formu değildir.** Bu metni kurumun güncel başvuru formuna aktarın; "
               "[DOLDURUN: …] ile işaretli yerleri kendi bilgilerinizle tamamlayın ve tüm rakamları kontrol edin.")
BOLUMLER = ("1. İşletme tanıtımı", "2. Projenin amacı ve gerekçesi", "3. Yapılacak faaliyetler ve takvim",
            "4. Tahmini bütçe kalemleri", "5. Beklenen çıktılar ve etkiler")

SISTEM = f"""Sen Türk devlet teşviklerine başvuru hazırlayan KOBİ'lere yardım eden bir başvuru yazımı asistanısın.
Görevin: verilen teşvik programı ve işletme profili için Türkçe, düzenlenebilir bir başvuru metni ÖN TASLAĞI yazmak.

Kurallar:
- Yalnızca BAĞLAM'daki bilgileri kullan. Bağlamda olmayan rakam, tarih, unvan, kişi adı, ürün, müşteri, ciro
  büyümesi, istihdam sayısı UYDURMA. Bilinmeyen her şeyi "[DOLDURUN: ne yazılmalı]" olarak bırak.
- Programın uygunluğunu garanti etme; "uygundur" yerine "şartları karşıladığını belirtin/teyit edin" gibi yaz.
- Resmi form alan adlarını bilmiyorsun; genel başlıklar kullan.
- Çıktı yalnızca Markdown olsun ve tam olarak şu başlıkları bu sırayla içersin (## ile):
{chr(10).join('  ## ' + b for b in BOLUMLER)}
- Bütçe bölümünde tutar varsa yalnızca bağlamdaki program tavanı/oranı ile sınırla; kalem tutarlarını [DOLDURUN] bırak.
- Profilde İKAS mağaza verisi (sipariş sayısı, ciro, yurt dışı teslimat) varsa işletme tanıtımında ve ihracat
  göstergelerinde kullan; kaynağını "e-ticaret mağaza kayıtlarına göre" diye belirt ve resmi belgeyle (fatura,
  gümrük beyannamesi/ETGB) teyit edilmesi gerektiğini yaz. Döviz tutarlarını TL'ye çevirme.
- Toplam uzunluk 500-900 kelime. Giriş/kapanış cümlesi, kendinden söz etme yok."""


def _liste(deger) -> list[str]:
    if not deger:
        return []
    return [deger] if isinstance(deger, str) else [str(x) for x in deger if str(x).strip()]


def _cumle_mi(satir: str) -> bool:
    """Menü/başlık satırı değil, cümle mi: en az 6 kelime VE kelimelerin çoğu küçük harfle başlıyor (menüdeki program
    adları "YÖNDE - Yönderlik ve Değerlendirme Destek Programı" gibi başlık düzenindedir)."""
    kelimeler = [k for k in satir.split() if k[:1].isalpha()]
    if len(satir.split()) < 6 or not kelimeler:
        return False
    buyuk = sum(k[:1].isupper() for k in kelimeler)
    return buyuk / len(kelimeler) < 0.6


def _temiz_ozet(ozet: str | None) -> str:
    """Kazınmış özetlerde site menüsü (program adları listesi, "+ - 0" düğmeleri) var (ölçüm 2026-10-08: kayıt 8, 9,
    49). Yalnızca cümle satırları alınır; kalan yoksa özet bağlama girmez."""
    return " ".join(s.strip() for s in (ozet or "").splitlines() if _cumle_mi(s))


def _kisalt(metin: str, sinir: int) -> str:
    """Sınırı aşan metni son cümle sonunda keser (ortadan kesik "1812 k" gibi parçalar modele gitmesin)."""
    if len(metin) <= sinir:
        return metin
    kesik = metin[:sinir]
    nokta = max(kesik.rfind(". "), kesik.rfind("; "))
    return (kesik[:nokta + 1] if nokta > sinir // 2 else kesik.rsplit(" ", 1)[0]) + " […]"


def kart_ozeti(ozet: str | None, sinir: int = 320) -> str:
    """Eşleşme ve arama kartındaki özet: menü satırları atılmış, cümle sonunda kısaltılmış metin. Cümle kalmazsa boş
    döner ve kart özetsiz gösterilir; başka alana (detay, hedef kitle) geri düşülmez, çünkü onların ilk cümlesi çoğu
    kayıtta başka programın ya da kurumun genel metnidir (ölçüm 2026-10-08)."""
    return _kisalt(_temiz_ozet(ozet), sinir)


def baglam(t: Tesvik, profil: dict) -> str:
    satirlar = [f"PROGRAM: {t.baslik} ({t.kurum})"]
    for etiket, deger in (("Özet", _temiz_ozet(t.ozet)), ("Tutar/oran", t.tesvil_tutari),
                          ("Hesaplama", t.tutari_hesaplama_formulu), ("Başvuru yeri", t.basvuru_yeri),
                          ("Başvuru dönemi", t.basvuru_suresi), ("Destek süresi", t.destek_verilme_suresi)):
        if deger:
            satirlar.append(f"{etiket}: {_kisalt(str(deger), 600)}")
    for etiket, deger in (("Şartlar", t.basvuru_sartlari), ("Gerekli belgeler", t.gerekli_belgeler)):
        if _liste(deger):
            satirlar.append(f"{etiket}: " + _kisalt("; ".join(_liste(deger)), 1200))
    profil_satirlari = [f"- {k}: {v}" for k, v in profil.items() if v not in (None, "", [], {})]
    satirlar.append("İŞLETME PROFİLİ:\n" + ("\n".join(profil_satirlari) or "(profil alanları boş)"))
    return "\n".join(satirlar)


def belgeler_bolumu(maddeler: list[dict]) -> str:
    """Kontrol listesinden deterministik bölüm (modelden değil)."""
    if not maddeler:
        return ("## 6. Hazırlanacak belgeler ve şartlar\n\nBu program için şart/belge bilgisi sistemimizde yok; "
                "kurumun resmi sayfasından kontrol edin.")
    satir = ["## 6. Hazırlanacak belgeler ve şartlar", "", "Kontrol listenizden; kurumun güncel listesiyle teyit edin.", ""]
    satir += [f"- [{'x' if m.get('isaretli') else ' '}] {m['metin']}" for m in maddeler]
    return "\n".join(satir)


def birlestir(model_metni: str, maddeler: list[dict]) -> str:
    return f"{BASLIK_NOTU}\n\n{model_metni.strip()}\n\n{belgeler_bolumu(maddeler)}\n"


class TaslakHatasi(Exception):
    """Kullanıcıya gösterilebilir hata (anahtar yok, çağrı başarısız, boş yanıt)."""


def _llm_istek(sistem: str, kullanici: str) -> tuple[str, dict]:
    """Tek dış model çağrısı. Testler bu fonksiyonu yamar (ağ yok)."""
    return llm_saglayici.tamamla(sistem, kullanici, max_tokens=TASLAK_MAX_TOKENS)


def uret(t: Tesvik, profil: dict, maddeler: list[dict]) -> tuple[str, dict]:
    if not llm_saglayici.etkin_mi():
        raise TaslakHatasi("Yapay zekâ servisi bu sunucuda yapılandırılmamış; şablon taslağını kullanın.")
    kullanici = f"BAĞLAM:\n{baglam(t, profil)}\n\nBu program için başvuru ön taslağını yaz."
    try:
        metin, kullanim = _llm_istek(SISTEM, kullanici)
    except Exception as e:  # ağ, kota, anahtar, zaman aşımı, kesik yanıt
        logger.warning("Taslak üretilemedi (tesvik=%s): %s: %s", t.id, type(e).__name__, e)
        raise TaslakHatasi("Taslak şu anda üretilemedi; birkaç dakika sonra tekrar deneyin.") from e
    if not metin:
        raise TaslakHatasi("Yapay zekâ boş yanıt döndürdü; tekrar deneyin.")
    sorunlar = dayanak.denetle(metin, kullanici + "\n" + SISTEM)
    if sorunlar:
        logger.warning("Taslak dayanak denetiminden geçmedi (tesvik=%s): %s", t.id, "; ".join(sorunlar[:5]))
        raise TaslakHatasi("Yapay zekâ taslağı kayıtlarda olmayan bilgi içerdiği için gösterilmedi; şablon taslağını "
                           "kullanın ya da tekrar deneyin.")
    logger.info("Taslak üretildi (tesvik=%s, giriş=%s, çıkış=%s token)", t.id, kullanim.get("giris"),
                kullanim.get("cikis"))
    return birlestir(metin, maddeler), kullanim


def _self_test() -> int:
    t = Tesvik(id=9, kurum="KOSGEB", baslik="Küresel Rekabetçilik", ozet="İhracat odaklı büyüme",
               tesvil_tutari="5 milyon TL'ye kadar", basvuru_sartlari=["KOBİ olmak"], gerekli_belgeler=["Başvuru Formu"])
    b = baglam(t, {"sektör": "imalat", "çalışan sayısı": 18, "NACE kodu": None})
    maddeler = [{"tur": "sart", "metin": "KOBİ olmak", "isaretli": True},
                {"tur": "belge", "metin": "Başvuru Formu", "isaretli": False}]
    tam = birlestir("## 1. İşletme tanıtımı\nmetin", maddeler)
    kontroller = [
        ("bağlam programı ve profili içerir", "Küresel Rekabetçilik" in b and "çalışan sayısı: 18" in b),
        ("boş profil alanı bağlama girmez", "NACE kodu" not in b),
        ("sistem istemi beş başlığı sayar", all(x in SISTEM for x in BOLUMLER)),
        ("taslak uyarı notuyla başlar", tam.startswith("> **Ön taslak")),
        ("belgeler bölümü listeden, işaretleriyle", "- [x] KOBİ olmak" in tam and "- [ ] Başvuru Formu" in tam),
        ("listesiz programda uyarı", "resmi sayfasından" in belgeler_bolumu([])),
        ("menü satırları özetten atılır",
         _temiz_ozet("Kapasite Geliştirme Destek Programı\nYÖNDE - Yönderlik ve Değerlendirme Destek Programı\n+\n0\n"
                     "1812 ile girişimcilerin iş fikirlerini teşebbüse dönüştürmesi amaçlanır") ==
         "1812 ile girişimcilerin iş fikirlerini teşebbüse dönüştürmesi amaçlanır"),
        ("uzun metin cümle sonunda kesilir", _kisalt("Birinci cümle burada. İkinci cümle uzun " * 3, 70)
         .endswith("burada. […]")),
        ("yalnız menü olan özet kartta boş", kart_ozeti("Girişimci Destek Programı\nKapasite Geliştirme Destek Programı") == ""),
        ("kart özeti sınırı aşmaz", len(kart_ozeti("Bu program işletmelerin ihracat kapasitesini artırır. " * 20)) <= 324),
    ]
    for ad, ok in kontroller:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in kontroller)
    print(f"\nself-test: {gecen}/{len(kontroller)} geçti")
    return 0 if gecen == len(kontroller) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
