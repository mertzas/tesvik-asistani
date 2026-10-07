"""9903 sayılı Karar programları için NACE/il/ölçek bazlı ön uygunluk (saf fonksiyonlar).

Kaynak: 9903 sayılı Yatırımlarda Devlet Yardımları Hakkında Karar (R.G. 30/05/2025),
metinden okunan hükümler (doğrulama 2026-10-07):

  MADDE 5/1  Desteklerden yararlanacak yatırımlar EK-3'teki ("Desteklerden
             faydalanabilecek sektörler ve şartlar") konulara yönelik olmalı. Türkiye
             Yüzyılı Kalkınma Hamlesi (Teknoloji, Yerel Kalkınma, Stratejik Hamle),
             Dijital/Yeşil Dönüşüm Programı ve 9/1-(v) için bu şart ARANMAZ.
  MADDE 2    (ı) orta-yüksek teknoloji (EK-1): 20, 25.3, 27, 28, 29, 30 (30.1 ve 30.3
             hariç), 32.5; (u) yüksek teknoloji (EK-1): 21, 26, 30.3. (i) Öncelikli ürün
             listesi orta-yüksek/yüksek teknoloji ve kritik ürünlerden oluşur (tebliğ).
  MADDE 6    Teknoloji Hamlesi: öncelikli ürün listesindeki ürün/teknolojiler; komite.
  MADDE 7    Yerel Kalkınma Hamlesi: il bazlı yerel yatırım konuları listesi (tebliğ).
  MADDE 8    Stratejik Hamle: stratejik konu listesi; asgari 100M TL (yüksek teknoloji)
             / 200M TL; ön değerlendirmede 5 kriterden 3'ü (ithalat karşılama ≤%70,
             katma değer ≥%30, %20 öz kaynak, ithalat ≥50M USD...).
  MADDE 9    Öncelikli Yatırımlar: bentler (a)-(y); ör. (b) yüksek teknoloji (liste veya
             ≥500M TL), (c) orta-yüksek teknoloji (İstanbul hariç; liste veya ≥1 milyar
             TL), (ç) 6. bölge yatırımları (müteharrik hariç), (i) Ar-Ge yatırımları...
  MADDE 10   Hedef Yatırımlar: EK-3'teki konular, belirtilen şartlarla.

Bu bir ÖN DEĞERLENDİRMEDİR: yalnızca "uygun_degil" kesin bir hukuki sonuçtur (EK-3 şartı
aranan programda konu listede yok). Diğer durumlar kullanıcıya "teyit edin" ile sunulur.
Öncelikli ürün listesi, stratejik konu listesi ve yerel yatırım konuları listesi
tebliğlerle yayımlanır ve sistemde yoktur.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.nace_9903 import bolum_sarti, ek3_kaydi, ek3_kayitlari, ek3_yuklendi_mi, il_bolgesi
from app.nace_hiyerarsi import normalize_nace
from app.urun_sektor_anahtarlari import kucult

YUKSEK_TEKNOLOJI = ("21", "26", "30.3")                               # MADDE 2/u
ORTA_YUKSEK_TEKNOLOJI = ("20", "25.3", "27", "28", "29", "30", "32.5")  # MADDE 2/ı
ORTA_YUKSEK_HARIC = ("30.1", "30.3")

DURUMLAR = ("uygun", "sartli", "bilinmiyor", "dusuk", "uygun_degil")
# "dusuk", iki ihtiyaca birden eşleşen (yatırım + Ar-Ge = 6 puan) bir programı da tek
# ihtiyaçlı uygun programların altına indirecek büyüklükte olmalı (ölçüm 2026-10-07:
# -1.5 iken ekmek üreticisine Teknoloji Hamlesi 2. sırada geliyordu).
SIRALAMA_ETKISI = {"uygun": 2.0, "sartli": 1.0, "bilinmiyor": 0.0, "dusuk": -4.0}

_BASLIK_PROGRAM = (
    ("hedef yatirimlar", "hedef_yatirimlar"),
    ("oncelikli yatirimlar", "oncelikli_yatirimlar"),
    ("teknoloji hamlesi", "teknoloji_hamlesi"),
    ("yerel kalkinma hamlesi", "yerel_kalkinma_hamlesi"),
    ("stratejik hamle", "stratejik_hamle"),
)
_ASCII = str.maketrans("çğıöşü", "cgiosu")


@dataclass(frozen=True)
class Uygunluk9903:
    program: str
    durum: str          # DURUMLAR
    gerekce: str
    madde: str

    def metin(self) -> str:
        ad = {"uygun": "UYGUN GÖRÜNÜYOR", "sartli": "ŞARTLI", "bilinmiyor": "BELİRLENEMEDİ",
              "dusuk": "DÜŞÜK OLASILIK", "uygun_degil": "UYGUN DEĞİL"}[self.durum]
        return f"{ad} — {self.gerekce} ({self.madde})"


def program_turu(baslik: str | None) -> str | None:
    """Teşvik kaydı başlığından 9903 programı. 9903 dışı kayıtlar için None."""
    b = kucult(baslik or "").translate(_ASCII)
    if "9903" not in b:
        return None
    for anahtar, program in _BASLIK_PROGRAM:
        if anahtar in b:
            return program
    return None


def _rakam(kod: str) -> str:
    return kod.replace(".", "")


def teknoloji_sinifi(nace: str | None) -> str | None:
    """EK-1'e göre 'yuksek' | 'orta_yuksek' | None. Kod liste maddesinin altında
    olmalı (ör. 28.93 -> orta_yuksek); daha geniş kod (ör. 'C', '2') None döner."""
    n = normalize_nace(nace)
    if n is None or not n[0].isdigit():
        return None
    r = _rakam(n)
    if any(r.startswith(_rakam(k)) for k in YUKSEK_TEKNOLOJI):
        return "yuksek"
    if any(r.startswith(_rakam(k)) for k in ORTA_YUKSEK_HARIC):
        return None
    if any(r.startswith(_rakam(k)) for k in ORTA_YUKSEK_TEKNOLOJI):
        return "orta_yuksek"
    return None


def _ek3_durumu(nace: str) -> tuple[str, str]:
    """EK-3 şartı aranan programlar için ('uygun'|'sartli'|'uygun_degil'|'bilinmiyor', açıklama)."""
    if not ek3_yuklendi_mi():
        return "bilinmiyor", "EK-3 listesi şu an okunamıyor"
    n = normalize_nace(nace)
    if n is None:
        return "bilinmiyor", f"'{nace}' geçerli bir NACE kodu değil"
    if not n[0].isdigit():
        return "bilinmiyor", f"NACE kodu kısım düzeyinde ({n}); EK-3 eşleşmesi için en az 2 haneli kod gerekir"
    kayit = ek3_kaydi(n)
    if kayit is not None:
        sart = (kayit.get("sartlar") or "").strip()
        bolum = bolum_sarti(kayit.get("bolum", "")) or ""
        ek = " ".join(x for x in (sart, bolum) if x)
        if ek:
            return "sartli", f"NACE {n}, EK-3'te '{kayit['kod']} {kayit['tanim'][:60]}' kalemine giriyor; şart: {ek[:220]}"
        return "uygun", f"NACE {n}, EK-3'te '{kayit['kod']} {kayit['tanim'][:60]}' kalemine giriyor"
    # Kullanıcının kodu listeden daha genişse (ör. "10"), alt kolları listede olabilir.
    alt = [k["kod"] for k in ek3_kayitlari() if _rakam(k["kod"]).startswith(_rakam(n))]
    if alt:
        return "sartli", (f"NACE {n} geniş bir kod; EK-3'te yalnızca alt kolları var "
                          f"({', '.join(alt[:6])}{'...' if len(alt) > 6 else ''}); faaliyetiniz bunlardan biri olmalı")
    # Aynı bölümde (2 hane) EK-3 kalemi varsa kesin "uygun değil" DENMEZ: EK-3 NACE
    # Rev.2.1 kullanır, kullanıcı Rev.2 kodu girmiş olabilir (ölçüm 2026-10-07: Rev.2
    # "62.01" bilgisayar programlama, EK-3'teki Rev.2.1 "62.1" ile eşleşmeyip yazılım
    # firmasını yanlış gerekçeyle eliyordu). Kardeş kodlar gösterilir, karar kullanıcıya
    # ve teyide bırakılır; sıralamada en alta iner ama gizlenmez.
    kardesler = sorted({".".join(k["kod"].split(".")[:2]) for k in ek3_kayitlari()
                        if _rakam(k["kod"])[:2] == _rakam(n)[:2]}, key=lambda x: _rakam(x))
    if kardesler:
        return "dusuk", (f"NACE {n} EK-3'te yok; aynı bölümde listelenen kodlar: "
                         f"{', '.join(kardesler[:12])}{'...' if len(kardesler) > 12 else ''}. EK-3 NACE Rev.2.1 "
                         "kullanır; kodunuz Rev.2 ise Rev.2.1 karşılığını (TÜİK dönüşüm tablosu) teyit edin, "
                         "karşılığı listede yoksa bu programda yatırım konusu desteklenmez")
    return "uygun_degil", (f"NACE {n} EK-3'te ('Desteklerden faydalanabilecek sektörler ve şartlar') "
                           f"yer almıyor; {n[:2]} numaralı bölümden hiçbir kalem listede yok, bu programda "
                           "yatırım konusu desteklenmez")


def degerlendir(program: str, nace: str | None, il: str | None = None,
                olcek: str | None = None) -> Uygunluk9903:
    """Bir 9903 programı için ön uygunluk. olcek: app/kobi.py sınıfı (mikro/kucuk/orta/buyuk)."""
    bolge = il_bolgesi(il) if il else None
    teknoloji = teknoloji_sinifi(nace)

    if program == "hedef_yatirimlar":
        if not nace:
            return Uygunluk9903(program, "bilinmiyor", "NACE kodu girilmemiş; program EK-3 listesine göre "
                                "değerlendirilir", "MADDE 5/1, 10")
        durum, aciklama = _ek3_durumu(nace)
        return Uygunluk9903(program, durum, aciklama, "MADDE 5/1, 10")

    if program == "oncelikli_yatirimlar":
        if not nace:
            return Uygunluk9903(program, "bilinmiyor", "NACE kodu girilmemiş", "MADDE 5/1, 9")
        durum, aciklama = _ek3_durumu(nace)
        if durum == "uygun_degil":
            return Uygunluk9903(program, "uygun_degil", aciklama + " (yalnızca 9/1-v deprem/yangın riski "
                                "yatırımları bu şarttan muaf)", "MADDE 5/1, 9")
        if bolge == 6:
            # EK-3 kalemi şartlıysa (ör. geniş kod, konu bazlı istisna) sonuç "uygun" olamaz.
            if durum == "sartli":
                return Uygunluk9903(program, "sartli", "6. bölge yatırımı (müteharrik hariç); ayrıca EK-3: "
                                    + aciklama, "MADDE 5/1, 9/1-ç")
            return Uygunluk9903(program, "uygun", "6. bölge yatırımı (müteharrik karakterli yatırımlar hariç); "
                                + aciklama, "MADDE 5/1, 9/1-ç")
        if teknoloji == "yuksek":
            return Uygunluk9903(program, "sartli", "yüksek teknoloji (EK-1); ürün öncelikli ürün listesinde "
                                "olmalı ya da yatırım asgari 500 milyon TL olmalı", "MADDE 9/1-b")
        if teknoloji == "orta_yuksek":
            if bolge == 1 and il and kucult(il).translate(_ASCII).strip() == "istanbul":
                return Uygunluk9903(program, "dusuk", "orta-yüksek teknoloji yatırımları İstanbul'da bu bentten "
                                    "yararlanamaz", "MADDE 9/1-c")
            return Uygunluk9903(program, "sartli", "orta-yüksek teknoloji (EK-1); ürün öncelikli ürün "
                                "listesinde olmalı ya da yatırım asgari 1 milyar TL olmalı (İstanbul hariç)",
                                "MADDE 9/1-c")
        return Uygunluk9903(program, "dusuk", "teknoloji sınıfı (EK-1) veya 6. bölge koşulu yok; ancak diğer "
                            "bentlerden biri (ör. Ar-Ge yatırımı, savunma, öz tüketim GES/RES, lisanslı depo, "
                            "eğitim) kapsamına girerse desteklenir", "MADDE 9/1")

    if program == "teknoloji_hamlesi":
        if not nace:
            return Uygunluk9903(program, "bilinmiyor", "NACE kodu girilmemiş", "MADDE 6")
        if teknoloji:
            ad = "yüksek" if teknoloji == "yuksek" else "orta-yüksek"
            return Uygunluk9903(program, "sartli", f"{ad} teknoloji sınıfında (EK-1); ürün/teknoloji öncelikli "
                                "ürün listesinde olmalı, proje komite tarafından değerlendirilir; EK-3 şartı "
                                "aranmaz", "MADDE 5/1, 6")
        return Uygunluk9903(program, "dusuk", "faaliyet EK-1 orta-yüksek/yüksek teknoloji sınıfında değil; "
                            "öncelikli ürün listesi bu sınıflar ve kritik ürünlerden oluşur", "MADDE 2/i, 6")

    if program == "yerel_kalkinma_hamlesi":
        return Uygunluk9903(program, "bilinmiyor", "desteklenecek konular il bazlı 'yerel yatırım konuları "
                            "listesi' ile belirlenir (tebliğ, sistemde yok); EK-3 şartı aranmaz; ilinizin "
                            "listesini kalkınma ajansından teyit edin", "MADDE 5/1, 7")

    if program == "stratejik_hamle":
        if olcek in ("mikro", "kucuk"):
            return Uygunluk9903(program, "dusuk", "asgari sabit yatırım 100 milyon TL (yüksek teknoloji) / 200 "
                                "milyon TL, %20 öz kaynak ve ithalat ölçütleri aranır; mikro/küçük ölçek için "
                                "gerçekçi değildir", "MADDE 8/2-3")
        return Uygunluk9903(program, "sartli", "stratejik hamle yatırım konuları listesinde olmalı; asgari 100M/"
                            "200M TL yatırım ve ön değerlendirmede 5 kriterden 3'ü (ithalat karşılama ≤%70, "
                            "katma değer ≥%30, %20 öz kaynak, ithalat ≥50M USD...) aranır; EK-3 şartı aranmaz",
                            "MADDE 5/1, 8")

    raise ValueError(f"Bilinmeyen 9903 programı: {program!r}")


def kayit_icin(tesvik, nace: str | None, il: str | None, olcek: str | None) -> Uygunluk9903 | None:
    """Teşvik kaydı 9903 programıysa değerlendirme, değilse None."""
    program = program_turu(getattr(tesvik, "baslik", None))
    return degerlendir(program, nace, il, olcek) if program else None
