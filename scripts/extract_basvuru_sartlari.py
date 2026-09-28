#!/usr/bin/env python3
"""
Başvuru şartlarını kurumun kendi sayfasından çıkarır.

NEDEN
-----
Ölçüm (2026-09-28): 181 kaydın 162'sinde `basvuru_sartlari` boş. Kullanıcı
"bu teşvike başvurabilir miyim" sorusunun cevabını kayıttan alamıyor;
eşleştirme puanı yüksek çıksa bile şartı tutmuyor olabilir.

Kurum sayfalarında bu bilgi yapılandırılmış bir başlık altında duruyor:
    KOSGEB   -> "Başvuru Şartları"
    TÜBİTAK  -> "Kimler Başvurabilir?"

MUHAFAZAKÂR TASARIM
-------------------
Yanlış bir şart, kullanıcıyı hak ettiği bir teşvikten vazgeçirebilir ya da
boşuna başvurmaya gönderebilir. Bu yüzden:

  - Yalnızca BOŞ olan kayıtlar doldurulur; elle girilmiş şartların üzerine
    YAZILMAZ.
  - Bölüm başlığı bulunamazsa hiçbir şey yazılmaz.
  - Çıkarılan metin uzunluk ve biçim kontrolünden geçer; çok kısa (anlamsız)
    ya da çok uzun (yanlış bölüm yakalanmış) metinler reddedilir.
  - Her kayda kaynak ve çıkarma tarihi not olarak eklenir.
  - --uygula verilmeden hiçbir şey yazılmaz; önce rapor okunmalı.

Maddeleme: Türkçe şart listeleri "-ması/-mesi," gerund ekiyle biter
("... güncel olması, ... faaliyet göstermesi, ... sağlaması gerekmektedir").
Bu ek sınırından bölmek, virgülden bölmekten çok daha doğru sonuç veriyor -
düz virgül "kayıtlı, aktif durumda ve ... olması" ifadesini de parçalardı.

Kullanım:
    python -m scripts.extract_basvuru_sartlari --kurum KOSGEB
    python -m scripts.extract_basvuru_sartlari --kurum TUBITAK --uygula
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from app.logging_setup import kur as gunluklemeyi_kur  # noqa: E402
from app.models import SessionLocal, Tesvik  # noqa: E402
from scripts.verify_aktiflik import BEKLEME_SN, _sayfa_metni  # noqa: E402

logger = logging.getLogger("sartlar")

# Bolum basliklari, oncelik sirasiyla. Basliktan sonraki metin alinir.
BASLIKLAR = (
    "Başvuru Şartları",
    "Kimler Başvurabilir",
    "Başvuru Koşulları",
    "Kimler Yararlanabilir",
)

# Bolumun BITTIGI yer: bir sonraki basligin geldigi nokta. Bunu bilmezsek
# sayfanin geri kalanini sart sanip yaziyoruz.
BITIS_ISARETLERI = (
    "Başvuru Formları", "Başvuru Süreci", "Destek Oranı", "Destek Unsurları",
    "Programın Amacı", "Sıkça Sorulan", "Mevzuat", "Duyurular", "İletişim",
    "Başvuru Tarihleri", "Değerlendirme", "Destek Miktarı", "Proje Süresi",
)

# Turkce sart listeleri KAPANIS IFADESIYLE biter: "... gerekmektedir.",
# "... gerekir.", "... sarti aranir.". Bolumu burada kesmek, baslik bazli
# kesmekten cok daha dogru: KOSGEB Istihdami Koruma sayfasinda sartlar 250
# karakterde bitiyor ama "Basvuru Sartlari" basligindan sonraki metin 3836
# karakter suruyor (kredi limitleri, kefalet kuruluslari vb.) - hepsini
# "sart" diye yazmak kullaniciya yanlis bilgi vermek olurdu.
KAPANIS_IFADELERI = re.compile(
    r"(gerekmektedir|gerekir|şart[ıi]\s+aran[ıi]r|aranmaktad[ıi]r)\s*\.")

# Yalnizca kapanis/baglac icerip anlam tasimayan parcalar.
ANLAMSIZ_PARCALAR = re.compile(
    r"^(ve|veya|ile|ayr[ıi]ca|gerekmektedir|gerekir|aranmaktad[ıi]r|"
    r"şart[ıi]\s+aran[ıi]r)[\s.,;:]*$", re.I)

# ILERI ISARET EDEN ifadeler: asil sart listesi BUNLARDAN SONRA geliyor.
# Kapanis ifadesinde kor korune kesince, ornegin "Basvuruda bulunabilecek
# kuruluslarin asagidaki tanimlara uymasi gerekmektedir." cumlesi tek basina
# "sart" olarak yaziliyordu - kullaniciya hicbir sey soylemeyen, kendini
# isaret eden bir cumle (dogrulandi 2026-09-28, TUBITAK 1709 ve 2544).
ILERI_ISARET = re.compile(
    r"(aşağ[ıi]da(?:ki)?|şunlard[ıi]r|aşağ[ıi]da\s+yer\s+alan|"
    r"t[ıi]klay[ıi]n[ıi]z|belirtilen\s+koşullar)", re.I)

EN_AZ_MADDE_UZUNLUGU = 20   # bundan kisa parca anlamli bir sart degil
EN_AZ_UZUNLUK = 60      # bundan kisa metin anlamli bir sart listesi degil
EN_COK_UZUNLUK = 1800   # bundan uzunsa yanlis bolum yakalanmis demektir
EN_COK_MADDE = 12

# Turkce sart listelerinde madde siniri: "-ması/-mesi" gerund eki + virgul.
_MADDE_SINIRI = re.compile(r"(?<=m[ae]s[ıi])\s*,\s*")


@dataclass
class Cikarim:
    baslik: str
    kurum: str
    url: str
    durum: str           # "bulundu" | "bulunamadi" | "reddedildi" | "hata"
    maddeler: list[str]
    ayrinti: str = ""


def _bolum_bul(metin: str) -> tuple[str, str] | None:
    """(baslik, bolum_metni) doner; bulunamazsa None."""
    for baslik in BASLIKLAR:
        m = re.search(re.escape(baslik) + r"\s*\??\s*", metin)
        if not m:
            continue
        kalan = metin[m.end():]
        # Bir sonraki bolum basligina kadar kes.
        en_yakin = len(kalan)
        for bitis in BITIS_ISARETLERI:
            b = kalan.find(bitis)
            if 0 <= b < en_yakin:
                en_yakin = b
        kalan = kalan[:en_yakin]
        # ONCELIKLI sinir: kapanis ifadesi. Ama ILERI ISARET eden bir
        # kapanista kesmek asil listeyi disarida birakir; o durumda bir
        # sonraki kapanisa gidiyoruz.
        arama_baslangici = 0
        while True:
            kapanis = KAPANIS_IFADELERI.search(kalan, arama_baslangici)
            if not kapanis:
                break
            parca = kalan[:kapanis.end()]
            # Kapanistan onceki ~120 karakterde ileri isaret var mi?
            kuyruk = parca[-120:]
            if ILERI_ISARET.search(kuyruk):
                arama_baslangici = kapanis.end()
                continue
            kalan = parca
            break
        return baslik, kalan.strip()
    return None


def _maddelere_ayir(bolum: str) -> list[str]:
    ham = _MADDE_SINIRI.split(bolum)
    maddeler = []
    for p in ham:
        p = " ".join(p.split()).strip(" ;,-–")
        if len(p) < EN_AZ_MADDE_UZUNLUGU:
            continue
        # "gerekmektedir." gibi kapanis parcalari madde degildir; boyle bir
        # parca listeye girdiginde kullanici sart sanip okuyor.
        if ANLAMSIZ_PARCALAR.match(p):
            continue
        maddeler.append(p)
    return maddeler[:EN_COK_MADDE]


def _kontrol_et(bolum: str, maddeler: list[str]) -> str | None:
    """Kabul edilemezse sebebini doner, kabul edilebilirse None."""
    if len(bolum) < EN_AZ_UZUNLUK:
        return f"bölüm çok kısa ({len(bolum)} karakter) - anlamlı şart değil"
    if len(bolum) > EN_COK_UZUNLUK:
        return (f"bölüm çok uzun ({len(bolum)} karakter) - büyük ihtimalle "
                "yanlış bölüm yakalandı")
    if not maddeler:
        return "madde çıkarılamadı"
    # Tek maddelik ve ileri isaret eden sonuc, icermedigi bir icerigi vaat
    # ediyor demektir - kullaniciya yazmak yerine reddetmek dogru.
    if len(maddeler) == 1 and ILERI_ISARET.search(maddeler[0]):
        return ("tek madde ve ileri işaret ediyor - asıl liste "
                "çıkarılamadı, yazmak yanıltıcı olur")
    return None


OTOMATIK_IMZA = "otomatik çıkarıldı"


def calistir(kurum: str | None, limit: int | None, uygula: bool,
             uzerine_yaz: bool, sadece_otomatik: bool = False) -> int:
    gunluklemeyi_kur("INFO")
    db = SessionLocal()
    try:
        q = db.query(Tesvik)
        if kurum:
            q = q.filter(Tesvik.kurum == kurum)
        kayitlar = [t for t in q.all() if (t.kaynak_url or "").startswith("http")]
        if sadece_otomatik:
            # Yalnizca daha once BU SCRIPT tarafindan yazilmis kayitlar.
            # Elle kurulmus sartlarin uzerine yazmak, insan emegini sessizce
            # silmek olur.
            kayitlar = [t for t in kayitlar
                        if OTOMATIK_IMZA in (t.durum_notu or "")]
        elif not uzerine_yaz:
            kayitlar = [t for t in kayitlar if not t.basvuru_sartlari]
        if limit:
            kayitlar = kayitlar[:limit]

        if not kayitlar:
            print("Islenecek kayit yok.")
            return 0
        print(f"{len(kayitlar)} kayit islenecek "
              f"({'MEVCUT SARTLARIN UZERINE YAZILACAK' if uzerine_yaz else 'yalnizca bos olanlar'})")

        simdi = datetime.now(timezone.utc)
        sonuclar: list[Cikarim] = []
        for i, t in enumerate(kayitlar, 1):
            try:
                metin = _sayfa_metni(t.kaynak_url)
            except Exception as e:
                sonuclar.append(Cikarim(t.baslik or "", t.kurum or "", t.kaynak_url,
                                        "hata", [], f"{type(e).__name__}: {e}"[:90]))
                time.sleep(BEKLEME_SN)
                continue

            bulgu = _bolum_bul(metin)
            if bulgu is None:
                sonuclar.append(Cikarim(t.baslik or "", t.kurum or "", t.kaynak_url,
                                        "bulunamadi", [], "bölüm başlığı yok"))
                time.sleep(BEKLEME_SN)
                continue

            bolum_basligi, bolum = bulgu
            maddeler = _maddelere_ayir(bolum)
            sebep = _kontrol_et(bolum, maddeler)
            if sebep:
                sonuclar.append(Cikarim(t.baslik or "", t.kurum or "", t.kaynak_url,
                                        "reddedildi", [], sebep))
                # Daha once otomatik yazilmis ama artik kontrolden gecmeyen
                # sarti TEMIZLE: elemis oldugumuz bir metni kayitta birakmak,
                # kullaniciya yanlis bilgi gostermeye devam etmek olur.
                if uygula and OTOMATIK_IMZA in (t.durum_notu or ""):
                    t.basvuru_sartlari = None
                    t.guncelleme_tarihi = simdi
                time.sleep(BEKLEME_SN)
                continue

            sonuclar.append(Cikarim(t.baslik or "", t.kurum or "", t.kaynak_url,
                                    "bulundu", maddeler, f"'{bolum_basligi}' bölümü"))
            print(f"[{i}/{len(kayitlar)}] {(t.baslik or '')[:46]:48} "
                  f"{len(maddeler)} madde")
            for md in maddeler[:3]:
                print(f"        - {md[:88]}")

            if uygula:
                t.basvuru_sartlari = maddeler
                not_ = (f"Başvuru şartları {simdi.date().isoformat()} tarihinde "
                        f"kurumun kendi sayfasından ('{bolum_basligi}' bölümü) "
                        f"otomatik çıkarıldı: {t.kaynak_url}")
                mevcut = (t.durum_notu or "").strip()
                if "Başvuru şartları" not in mevcut:
                    t.durum_notu = (mevcut + " " + not_).strip()
                t.guncelleme_tarihi = simdi
            time.sleep(BEKLEME_SN)

        if uygula:
            db.commit()

        from collections import Counter
        ozet = Counter(s.durum for s in sonuclar)
        print("\n" + "=" * 62)
        print("OZET:", dict(ozet))
        for durum, etiket in [("bulunamadi", "BOLUM BASLIGI YOK"),
                              ("reddedildi", "KONTROLDEN GECMEDI"),
                              ("hata", "SAYFAYA ULASILAMADI")]:
            liste = [s for s in sonuclar if s.durum == durum]
            if liste:
                print(f"\n{etiket} ({len(liste)}):")
                for s in liste[:12]:
                    print(f"  {s.baslik[:46]:48} {s.ayrinti[:44]}")
                if len(liste) > 12:
                    print(f"  ... ve {len(liste)-12} kayit daha")
        print(f"\n{'YAZILDI' if uygula else 'RAPOR (yazilmadi)'}: "
              f"{ozet.get('bulundu',0)} kayda sart "
              f"{'yazildi' if uygula else 'yazilacak'}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Basvuru sarti cikarici.")
    a.add_argument("--kurum")
    a.add_argument("--limit", type=int)
    a.add_argument("--uygula", action="store_true")
    a.add_argument("--uzerine-yaz", action="store_true",
                   help="Elle girilmis sartlarin da uzerine yaz (dikkatli kullanin)")
    a.add_argument("--sadece-otomatik", action="store_true",
                   help="Yalnizca daha once bu script tarafindan yazilmis "
                        "kayitlari yeniden isle (elle girilenlere dokunmaz)")
    args = a.parse_args()
    sys.exit(calistir(args.kurum, args.limit, args.uygula, args.uzerine_yaz,
                      args.sadece_otomatik))
