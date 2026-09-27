#!/usr/bin/env python3
"""
Kayıtlara tutar_niteligi işaretini yazar: hibe mi, kredi mi, faiz desteği mi?

NEDEN
-----
"Toplam tahmini destek" hesabı, hangi kaydın toplama gireceğine metin
sezgisiyle karar veriyordu: tesvil_tutari veya formül metninde "kredi"
kelimesi geçen her kayıt tamamen dışarı atılıyordu. Bu sezgi KAYIP VERİYOR.

Ölçüm (2026-09-26): KOSGEB Girişimci Destek Programı'nın içinde GERİ ÖDEMESİZ
10.000 TL kuruluş desteği var, ama formül metninde "%80 geri ödemeli" ve
"Faiz/Kâr Payı Desteği" ifadeleri geçtiği için kayıt komple kredi sayılıp
toplamdan düşüyordu. Yani gerçek bir hibe kullanıcıya hiç gösterilmiyordu.

Çözüm: metinden tahmin etmek yerine veride açıkça işaretlemek.
    "hibe"              -> geri ödemesiz, toplama GİRER
    "kredi_kefalet"     -> kredi ana parası / kefalet limiti, girmez
    "faiz_destegi"      -> kurum faizi karşılıyor, ana parayı değil; girmez
    "proje_bazli_tavan" -> programın üst sınırı, girmez

RESMÎ KAYNAKLAR (doğrulama: 2026-09-26)
---------------------------------------
KOSGEB Girişimci Destek Programı
  https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/1231/girisimci-destek-programi
  İş Kurma Desteği (GERİ ÖDEMESİZ): kuruluş giderleri 10.000 TL (gerçek kişi)
    / 20.000 TL (sermaye şirketi), %100, 36 ay. Girişimci genç/kadın/engelli/
    gazi/şehit yakını ise kuruluş desteğine 10.000 TL ilave.
  İş Geliştirme Desteği (GERİ ÖDEMELİ): üst limit 1.500.000 TL, %80, 36 ay;
    aynı gruplara 150.000 TL ilave.
  İş Geliştirme Faiz/Kâr Payı Desteği (GERİ ÖDEMESİZ): üst limit 1.000.000 TL,
    %50, jüri puanı 50+ olan kadın/genç girişimciler.

KOSGEB KOBİ Dijital Dönüşüm Destek Programı
  https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9144/kobi-dijital-donusum-destek-programi
  Makine-teçhizat ve yazılım-donanım giderleri: alt limit 1.000.000 TL,
    üst limit 20.000.000 TL. KOSGEB, işletmenin anlaşmalı bankalardan
    kullandığı kredinin FAİZİNİ karşılıyor, ana parayı değil. Şart: NACE
    Kısım C (İmalat), KOSGEB veri tabanında aktif, küçük/orta ölçekli
    (mikro değil), yetkili danışmanlardan dijital dönüşüm değerlendirme
    raporu, son mali yılda pozitif özkaynak.

KOSGEB Kapasite Geliştirme Destek Programı
  Kredi üst limiti 20.000.000 TL, alt limit 1.000.000 TL -> kredi ürünü.

Kullanım:
    python -m scripts.backfill_tutar_niteligi            # rapor
    python -m scripts.backfill_tutar_niteligi --uygula
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

GIRISIMCI_URL = ("https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/1231/"
                 "girisimci-destek-programi")
DIJITAL_URL = ("https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9144/"
               "kobi-dijital-donusum-destek-programi")

# baslik -> ayarlar
ELLE_ISARETLENENLER: dict[str, dict] = {
    "Girişimci Destek Programı": {
        "nitelik": "hibe",
        # tutari_min/max artik YALNIZCA geri odemesiz kismi gosteriyor.
        # Eskiden 10.000 - 1.500.000 yaziyordu; ust sinir geri ODEMELI
        # kalemdi, yani kullaniciya "1,5 milyon hibe alabilirsin" izlenimi
        # veriyordu. Simdi: kurulus 10.000 (gercek kisi) - 30.000 (sermaye
        # sirketi + genc/kadin/engelli/gazi/sehit yakini ilavesi).
        "tutari_min": 10_000.0,
        "tutari_max": 30_000.0,
        "kriter": "genel",
        "formul": (
            "GERİ ÖDEMESİZ kuruluş desteği: gerçek kişi 10.000 TL, sermaye "
            "şirketi 20.000 TL; girişimci genç/kadın/engelli/gazi/şehit yakını "
            "ise +10.000 TL (üst sınır 30.000 TL). Buna ek olarak personel "
            "giderleri 36 ay boyunca aylık asgari ücret kadar %100 geri "
            "ödemesiz karşılanır (tutar asgari ücrete bağlı olduğu için bu "
            "aralığa dahil edilmedi). AYRICA geri ÖDEMELİ İş Geliştirme "
            "Desteği 1.500.000 TL'ye kadar (%80) ve jüri puanı 50+ olan "
            "kadın/genç girişimciler için geri ödemesiz Faiz/Kâr Payı Desteği "
            "1.000.000 TL'ye kadar (%50) vardır - bunlar şarta bağlı olduğu "
            "için toplama katılmadı."
        ),
        "durum_notu": (
            "Geri ödemesiz ve geri ödemeli kalemleri ayrı değerlendirin: "
            "1.500.000 TL'lik İş Geliştirme Desteği GERİ ÖDEMELİDİR, hibe "
            f"değildir. Resmî sayfa: {GIRISIMCI_URL}"
        ),
    },
    "KOBİ Dijital Dönüşüm Destek Programı": {
        "nitelik": "faiz_destegi",
        "durum_notu": (
            "DİKKAT: 1.000.000 - 20.000.000 TL rakamı KREDİ limitidir. KOSGEB "
            "anlaşmalı bankalardan kullanılan kredinin FAİZİNİ karşılıyor, ana "
            "parayı değil; eline geçen destek ödenen faiz kadardır. Şart: NACE "
            "Kısım C (İmalat), KOSGEB veri tabanında aktif, küçük/orta ölçekli "
            "(mikro hariç), yetkili danışmandan dijital dönüşüm değerlendirme "
            f"raporu. Resmî sayfa: {DIJITAL_URL}"
        ),
        "basvuru_sartlari": [
            "NACE Kısım C (İmalat) kapsamında faaliyet göstermek",
            "KOSGEB veri tabanında kayıtlı ve aktif olmak",
            "Küçük veya orta ölçekli işletme olmak (mikro işletmeler hariç)",
            "Yetkili danışmanlardan onaylı dijital dönüşüm değerlendirme raporu almak",
            "Son mali yılda özkaynak toplamı pozitif olmak",
            "Son 3 yıldan en az birinde faaliyet kârı pozitif olmak",
        ],
    },
    "Kapasite Geliştirme Destek Programı": {
        "nitelik": "kredi_kefalet",
        "durum_notu": (
            "1.000.000 - 20.000.000 TL rakamı KREDİ üst/alt limitidir, hibe "
            "değildir. Toplam tahmini destek hesabına katılmaz."
        ),
    },
}


def calistir(uygula: bool) -> int:
    db = SessionLocal()
    try:
        simdi = datetime.now(timezone.utc)
        etiket = "yazilacak" if uygula else "RAPOR"

        print("== ELLE DOGRULANMIS KAYITLAR ==")
        elle = 0
        for baslik, ayar in ELLE_ISARETLENENLER.items():
            t = db.query(Tesvik).filter(Tesvik.baslik == baslik).first()
            if t is None:
                print(f"  [ATLANDI] kayit yok: {baslik}")
                continue
            k = dict(t.uygunluk_kriterleri or {})
            print(f"  [{etiket}] {baslik}")
            print(f"      nitelik: {k.get('tutar_niteligi')!r} -> {ayar['nitelik']!r}")
            if "tutari_min" in ayar:
                print(f"      tutar: {t.tutari_min} - {t.tutari_max} -> "
                      f"{ayar['tutari_min']} - {ayar['tutari_max']}")
            if uygula:
                k["tutar_niteligi"] = ayar["nitelik"]
                t.uygunluk_kriterleri = k
                if "tutari_min" in ayar:
                    t.tutari_min = ayar["tutari_min"]
                    t.tutari_max = ayar["tutari_max"]
                    t.tutari_hesaplama_kriteri = ayar["kriter"]
                    t.tutari_hesaplama_formulu = ayar["formul"]
                if ayar.get("basvuru_sartlari") and not t.basvuru_sartlari:
                    t.basvuru_sartlari = ayar["basvuru_sartlari"]
                mevcut = (t.durum_notu or "").strip()
                if ayar["durum_notu"] not in mevcut:
                    t.durum_notu = (mevcut + " " + ayar["durum_notu"]).strip()
                t.guncelleme_tarihi = simdi
            elle += 1

        # Tarim Bakanligi bitkisel uretim destekleri: dekar basina ODENEN,
        # geri odemesiz nakit destekler -> "hibe". Bunlar backfill_tarim_tutar_2026
        # tarafindan yapisal tutarla dolduruldu; isaret koymazsak metin
        # sezgisine dusuyorlar.
        print("\n== TARIM BITKISEL URETIM DESTEKLERI (hibe) ==")
        TARIM_HIBE = (
            "Hububat ve Baklagil Üretim Destekleri",
            "Meyve-Sebze Üretim Destekleri",
            "Sera/Örtüaltı Tarım Destekleri",
            "Organik Tarım Destekleri",
        )
        tarim_yazilan = 0
        for parca in TARIM_HIBE:
            t = db.query(Tesvik).filter(Tesvik.baslik.like(f"{parca}%")).first()
            if t is None:
                print(f"  [ATLANDI] kayit yok: {parca}")
                continue
            k = dict(t.uygunluk_kriterleri or {})
            if k.get("tutar_niteligi") == "hibe":
                print(f"  [zaten isaretli] {t.baslik}")
                continue
            print(f"  [{etiket}] {t.baslik}")
            if uygula:
                k["tutar_niteligi"] = "hibe"
                t.uygunluk_kriterleri = k
                t.guncelleme_tarihi = simdi
            tarim_yazilan += 1

        # KGF kayitlari kurum etiketinden zaten dogru siniflaniyor, ama acik
        # isaret koymak denetlenebilirligi artiriyor: ileride kurum adi
        # degisirse sessizce hibe sayilmaya baslamasin.
        print("\n== KGF KAYITLARI (kredi_kefalet) ==")
        kgf = db.query(Tesvik).filter(Tesvik.kurum == "KGF").all()
        kgf_yazilan = 0
        for t in kgf:
            k = dict(t.uygunluk_kriterleri or {})
            if k.get("tutar_niteligi") == "kredi_kefalet":
                continue
            if uygula:
                k["tutar_niteligi"] = "kredi_kefalet"
                t.uygunluk_kriterleri = k
                t.guncelleme_tarihi = simdi
            kgf_yazilan += 1
        print(f"  {len(kgf)} KGF kaydi, {kgf_yazilan} tanesi isaretlenecek")

        # Kalan isaretsiz kayitlari raporla - gorunmez kalmasinlar.
        print("\n== ISARETSIZ KALAN, TUTARI OLAN KAYITLAR ==")
        isaretsiz = []
        for t in db.query(Tesvik).all():
            k = t.uygunluk_kriterleri or {}
            if k.get("tutar_niteligi"):
                continue
            if t.tutari_min is not None or (t.tesvil_tutari or "").strip():
                isaretsiz.append(t)
        for t in isaretsiz:
            print(f"  {t.kurum[:14]:15} {(t.baslik or '')[:52]}")
        if not isaretsiz:
            print("  (yok)")
        print(f"  -> {len(isaretsiz)} kayit metin sezgisine dusuyor; "
              "elle dogrulanip isaretlenmeli.")

        if uygula:
            db.commit()
            print(f"\nYAZILDI: {elle} elle + {tarim_yazilan} tarim + "
                  f"{kgf_yazilan} KGF kaydi isaretlendi.")
        else:
            print(f"\nRAPOR: {elle} + {tarim_yazilan} + {kgf_yazilan} "
                  "kayit isaretlenecek.")
            print("Uygulamak icin --uygula ile tekrar calistirin.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="tutar_niteligi backfill.")
    a.add_argument("--uygula", action="store_true")
    sys.exit(calistir(a.parse_args().uygula))
