#!/usr/bin/env python3
"""
7 ölü linki elle araştırılmış sonuçlarla düzeltir (2026-09-29).

NEDEN ELLE
----------
Bu 7 kayıt scripts/check_kaynak_linkleri.py tarafından ölü olarak
işaretlenmişti. Her biri için doğru çözüm farklı ve otomatikleştirmeye
uygun değil - her biri ayrı bir araştırma (KGF sitesinin güncel menüsünü
tarama, TÜBİTAK duyurularını arama) gerektirdi:

KGF - 3 kayıt: URL YAPISI DEĞİŞMİŞ, yeni adres bulundu ve HTTP 200 ile
doğrulandı.
  - "ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ(GREENDEKS)":
    yeni yol sonunda çift "i" var ("paketii") - KGF'nin kendi sitesindeki
    yazım hatası, ama link BÖYLE çalışıyor.
  - "ZİRAAT BANKASI KADIN VE GENÇ GİRİŞİMCİ DESTEK PROGRAMI": başlık da
    değişmiş ("Destek Programı" -> "Destek Paketi").
  - "İSTİHDAM KORUMA DESTEK PROGRAMI": kategori değişmiş - "Özkaynak
    Kefaletlerimiz > KGF Tematik Destek Programları"ndan
    "KOSGEB Destekli Kefaletler" altına taşınmış.

KGF - 2 kayıt: MÜKERRER. Aynı ürün, KGF'nin güncel sitesinde banka adı
eklenmiş farklı bir başlıkla ZATEN veritabanımızda kayıtlı:
  - "BASIN İLAN KURUMU DESTEK PROGRAMI" ==
    "Vakıfbank Basın İlan Kurumu Destek Paketi" (linki sağlam)
  - "KATILIM FİNANS KEFALET DESTEK PROGRAMI" ==
    "Ziraat Katılım Bankası Katılım Finans Destek Paketi" (linki sağlam)
  Silinmiyor (URL geçmişi ve arama geçmişiyle uyum için), ama aktif_mi=False
  yapılıp hangi kayda bakılması gerektiği not olarak yazılıyor - iki kez
  aynı programı göstermek kullanıcıyı yanıltır.

TÜBİTAK - 1 kayıt: PROGRAM BÖLÜNMÜŞ. "3005 - Sosyal ve Beşeri Bilimlerde
Yenilikçi Çözümler Araştırma Projeleri Destek Programı" TÜBİTAK'ın kendi
duyurusuna göre ("3005-Sosyal ve Beşeri Bilimlerde Yenilikçi Çözümler
Araştırma Projeleri Destek Programı İki Ayrı Modül Olarak Güncellendi",
tubitak.gov.tr) iki ayrı modüle bölünmüş; bu modüller ZATEN veritabanımızda
kayıtlı ve linkleri sağlam:
  - "3005 - A Politika Geliştirme Modülü"
  - "3005 - B Teknolojik İlerlemelerin Toplumsal Etkileri Modülü"

TÜBİTAK - 1 kayıt: ÇÖZÜLEMEDİ (URL muhtemelen doğru). "1512 - Girişimcilik
Destek Programı (BiGG)" - hem doğrudan istek hem tarayıcı ile denendi,
ikisi de "Erişim engellendi" (403) aldı; aynı oturumda TÜBİTAK'ın başka
sayfaları (1501) sorunsuz açıldı, yani bu genel bir IP/bot engeli değil,
SPESİFİK bu URL'e (ya da "1512" içeren yollara) uygulanan bir kural
olabilir. Arama motoru sonuçlarında da aynı adres geçiyor, yani URL'in
kendisi muhtemelen doğru. Link SİLİNMİYOR, yalnızca not güncelleniyor;
gelecekte tekrar denenmeli.

Kullanım:
    python -m scripts.fix_olu_linkler_2026_09              # rapor
    python -m scripts.fix_olu_linkler_2026_09 --uygula
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from app.models import SessionLocal, Tesvik  # noqa: E402

# baslik -> yeni_url (HTTP 200 ile dogrulandi, 2026-09-29)
# DIKKAT: kaynak_url sutununda UNIQUE kisiti var. Once ilk denemede
# "ZİRAAT BANKASI YEŞİL İHRACAT..." ve "ZİRAAT BANKASI KADIN VE GENÇ
# GİRİŞİMCİ..." icin bulunan "yeni" adresler aslinda veritabaninda
# ZATEN, BASKA (guncel adli) bir kayitta kayitliydi - yani bunlar da
# MUKERRER'miş, IntegrityError ile yakalandi. Asagida sadece GERCEKTEN
# URL guncellemesi gereken (cakismayan) kayit kaldi.
YENI_URL = {
    "İSTİHDAM KORUMA DESTEK PROGRAMI":
        "https://www.kgf.com.tr/index.php/tr/urunlerimiz/"
        "kosgeb-destekli-kefaletler/istihdam-koruma-destek-programi",
}

# baslik -> (mukerrer_oldugu_kaydin_baslik_parcasi, not)
MUKERRER = {
    "BASIN İLAN KURUMU DESTEK PROGRAMI": (
        "Vakıfbank Basın İlan Kurumu Destek Paketi",
        "⚠️ MÜKERRER KAYIT. KGF'nin güncel sitesinde bu ürün "
        "'Vakıfbank Basın İlan Kurumu Destek Paketi' adıyla ve o kaydın "
        "linkinde yer alıyor; bu kayıt eski/genel adı taşıyor ve linki "
        "artık çalışmıyor. Güncel bilgi için diğer kayda bakın.",
    ),
    "KATILIM FİNANS KEFALET DESTEK PROGRAMI": (
        "Ziraat Katılım Bankası Katılım Finans Destek Paketi",
        "⚠️ MÜKERRER KAYIT. KGF'nin güncel sitesinde bu ürün "
        "'Ziraat Katılım Bankası Katılım Finans Destek Paketi' adıyla ve "
        "o kaydın linkinde yer alıyor; bu kayıt eski/genel adı taşıyor ve "
        "linki artık çalışmıyor. Güncel bilgi için diğer kayda bakın.",
    ),
    # Ilk denemede "yeni URL" sanilan iki kayit, aslinda veritabaninda
    # GUNCEL adiyla ZATEN kayitli (linkleri saglam) - IntegrityError ile
    # tespit edildi (bkz. modul basindaki not).
    "ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ(GREENDEKS)": (
        "ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ",
        "⚠️ MÜKERRER KAYIT. Bu ürün 'ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ "
        "DESTEK PAKETİ' (parantezsiz) adıyla ve sağlam bir linkle zaten "
        "kayıtlı; bu kayıt eski adı ve artık çalışmayan bir link taşıyor. "
        "Güncel bilgi için diğer kayda bakın.",
    ),
    "ZİRAAT BANKASI KADIN VE GENÇ GİRİŞİMCİ DESTEK PROGRAMI": (
        "ZİRAAT BANKASI KADIN VE GENÇ GİRİŞİMCİ DESTEK PAKETİ",
        "⚠️ MÜKERRER KAYIT. Bu ürün 'ZİRAAT BANKASI KADIN VE GENÇ "
        "GİRİŞİMCİ DESTEK PAKETİ' ('Programı' değil 'Paketi') adıyla ve "
        "sağlam bir linkle zaten kayıtlı; bu kayıt eski adı ve artık "
        "çalışmayan bir link taşıyor. Güncel bilgi için diğer kayda bakın.",
    ),
}

# baslik -> (parcalandigi_kayitlarin_baslik_parcalari, not)
BOLUNMUS = {
    "3005 - Sosyal ve Beşeri Bilimlerde Yenilikçi Çözümler Araştırma "
    "Projeleri Destek Programı": (
        ["3005 - A Politika Geliştirme Modülü",
         "3005 - B Teknolojik İlerlemelerin Toplumsal Etkileri Modülü"],
        "⚠️ PROGRAM İKİYE BÖLÜNDÜ. TÜBİTAK'ın kendi duyurusuna göre "
        "('3005-Sosyal ve Beşeri Bilimlerde Yenilikçi Çözümler Araştırma "
        "Projeleri Destek Programı İki Ayrı Modül Olarak Güncellendi', "
        "tubitak.gov.tr) bu program '3005-A Politika Geliştirme Modülü' "
        "ve '3005-B Teknolojik İlerlemelerin Toplumsal Etkileri Modülü' "
        "olarak ikiye ayrıldı; bu kayıt artık geçerli değil. Güncel bilgi "
        "için o iki kayda bakın.",
    ),
}

# baslik -> yeni_not (link SİLİNMİYOR, sadece not güncelleniyor)
ERISIM_ENGELI = {
    "1512 - Girişimcilik Destek Programı (BiGG - Bireysel Genç Girişim)": (
        "⚠️ SAYFAYA ŞU AN ERİŞİLEMİYOR (HTTP 403 'Erişim engellendi'). "
        "Hem doğrudan istek hem tarayıcı ile denendi; aynı oturumda "
        "TÜBİTAK'ın başka sayfaları (1501) sorunsuz açıldığı için bu genel "
        "bir engel değil, bu adrese özel görünüyor. Arama motoru "
        "sonuçlarında da aynı adres geçtiği için URL'in kendisi muhtemelen "
        "doğru - link silinmedi. Kontrol: 2026-09-29, tekrar denenmeli."
    ),
}


def calistir(uygula: bool) -> int:
    db = SessionLocal()
    try:
        simdi = datetime.now(timezone.utc)
        etiket = "yazilacak" if uygula else "RAPOR"
        n = 0

        print("== YENI URL (KGF, tasinmis) ==")
        for baslik, url in YENI_URL.items():
            t = db.query(Tesvik).filter(Tesvik.baslik == baslik).first()
            if t is None:
                print(f"  [ATLANDI] kayit yok: {baslik}"); continue
            print(f"  [{etiket}] {baslik}")
            print(f"      eski: {t.kaynak_url}")
            print(f"      yeni: {url}")
            if uygula:
                t.kaynak_url = url
                mevcut = (t.durum_notu or "")
                temiz = mevcut.split("⚠️ KAYNAK LİNKİ ÇALIŞMIYOR")[0].strip()
                t.durum_notu = (
                    (temiz + " " if temiz else "") +
                    f"Kaynak linki {simde_str(simde=simdi)} tarihinde "
                    "güncellendi (KGF sitesi URL yapısını değiştirmiş)."
                ).strip()
                t.guncelleme_tarihi = simdi
            n += 1

        print("\n== MUKERRER (baska kayitta guncel hali var) ==")
        for baslik, (diger, not_) in MUKERRER.items():
            t = db.query(Tesvik).filter(Tesvik.baslik == baslik).first()
            if t is None:
                print(f"  [ATLANDI] kayit yok: {baslik}"); continue
            print(f"  [{etiket}] {baslik}  ->  bkz. '{diger}'")
            if uygula:
                t.aktif_mi = False
                t.durum_notu = not_
                t.guncelleme_tarihi = simdi
            n += 1

        print("\n== BOLUNMUS PROGRAM (yerine gecen kayitlar var) ==")
        for baslik, (digerleri, not_) in BOLUNMUS.items():
            t = db.query(Tesvik).filter(Tesvik.baslik == baslik).first()
            if t is None:
                print(f"  [ATLANDI] kayit yok: {baslik}"); continue
            print(f"  [{etiket}] {baslik}  ->  {', '.join(digerleri)}")
            if uygula:
                t.aktif_mi = False
                t.durum_notu = not_
                t.guncelleme_tarihi = simdi
            n += 1

        print("\n== ERISIM ENGELI (link silinmedi, not guncellendi) ==")
        for baslik, not_ in ERISIM_ENGELI.items():
            t = db.query(Tesvik).filter(Tesvik.baslik == baslik).first()
            if t is None:
                print(f"  [ATLANDI] kayit yok: {baslik}"); continue
            print(f"  [{etiket}] {baslik}")
            if uygula:
                t.durum_notu = not_
                t.guncelleme_tarihi = simdi
            n += 1

        if uygula:
            db.commit()
            print(f"\nYAZILDI: {n} kayit guncellendi.")
        else:
            print(f"\nRAPOR: {n} kayit guncellenecek.")
            print("Uygulamak icin --uygula ile tekrar calistirin.")
        return 0
    finally:
        db.close()


def simde_str(simde: datetime) -> str:
    return simde.date().isoformat()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="7 ozel olu link duzeltmesi.")
    a.add_argument("--uygula", action="store_true")
    sys.exit(calistir(a.parse_args().uygula))
