#!/usr/bin/env python3
"""
Tarım Bakanlığı bitkisel üretim kayıtlarına 2026 resmî birim fiyatlarını yazar.

NEDEN
-----
Ölçüm (2026-09-26): 176 kaydın 162'sinde yapısal tutar yoktu; Tarım Bakanlığı
kayıtlarında tutar yalnızca serbest metin olarak duruyordu ve çiftçinin arazi
büyüklüğüyle ölçeklenmiyordu. Sonuç: tarım profillerinde "toplam tahmini
destek" gerçeğin çok altında ya da 0 çıkıyordu.

app/matching.py'daki altyapı hazır: tutari_min/tutari_max BİRİM fiyat (TL/dekar)
olarak saklanır, tutari_hesaplama_kriteri="dekar" ise profildeki
arazi_buyuklugu_dekar ile çarpılır.

KAPSAM SINIRI - ÖNEMLİ
----------------------
2026 BUGEM tablosu yalnızca BİTKİSEL ÜRETİM desteklerini kapsıyor. Bu yüzden
sadece şu kayıtlar dolduruluyor:
    Hububat ve Baklagil Üretim Destekleri
    Meyve-Sebze Üretim Destekleri
    Sera/Örtüaltı Tarım Destekleri
    Organik Tarım Destekleri

Şu kayıtlara DOKUNULMUYOR, çünkü tutarları bu tabloda YOK ve uydurmak
çiftçiye yanlış rakam göstermek olurdu:
    Hayvancılık Destekleri      -> hayvancılık destekleri ayrı kararda,
                                   hayvan başına ödenir
    Sulama Yatırımı Destekleri  -> KKYDP/bireysel sulama, proje bazlı hibe
    Tarımsal Makineleştirme     -> makine-ekipman hibesi, alım bedeli üzerinden

KAYNAK
------
T.C. Tarım ve Orman Bakanlığı BUGEM, "2026 Üretim Yılı Bitkisel Üretim
Destekleme Birim Fiyatları". Katsayılar app/tarim_destek_2026.py içinde.

Kullanım:
    python -m scripts.backfill_tarim_tutar_2026            # rapor
    python -m scripts.backfill_tarim_tutar_2026 --uygula
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
from app.tarim_destek_2026 import (  # noqa: E402
    IYI_TARIM,
    KATSAYI_BIRIM_TL,
    KAYNAK,
    KAYNAK_URL,
    ORGANIK_ORGUT_ILAVE_ORANI,
    ORGANIK_TARIM,
    TEMEL_DESTEK_KATEGORILERI,
)

K = KATSAYI_BIRIM_TL

# Her kayıt için: (alt sınır TL/dekar, üst sınır TL/dekar, formül açıklaması)
# Alt sınır = en az alınabilecek, üst sınır = tüm ilave şartlar sağlanırsa.
# Aralık vermek şart: aynı kayıt altında farklı ürün kategorileri ve
# sertifika durumları farklı tutar üretiyor; tek sayı vermek yanıltıcı olur.

_temel_1 = TEMEL_DESTEK_KATEGORILERI[1][0] * K          # 310,00
_temel_2 = TEMEL_DESTEK_KATEGORILERI[2][0] * K          # 403,00
_organik_en_az = ORGANIK_TARIM[3][1] * K                # 3. grup, grup sert. = 62,00
_organik_en_cok = ORGANIK_TARIM[1][0] * K * (1 + ORGANIK_ORGUT_ILAVE_ORANI)  # 465,00
_iyi_tarim_ortualti = IYI_TARIM["1_ortualti"][0] * K    # 527,00

HEDEFLER: dict[str, tuple[float, float, str]] = {
    "Hububat ve Baklagil Üretim Destekleri": (
        _temel_1 * 2, _temel_2 * 2,
        f"Temel destek + planlı üretim desteği. Kategori katsayısı ürüne göre "
        f"değişir: mercimek/nohut 1,0 ({_temel_1:.2f} TL/da), buğday/arpa/mısır "
        f"1,3 ({_temel_2:.2f} TL/da). İki kalem ayrı ayrı ödendiği için alt "
        f"sınır {_temel_1*2:.2f}, üst sınır {_temel_2*2:.2f} TL/dekar. "
        f"Sertifikalı tohum kullanılırsa ilave ödenir. Birim değer "
        f"{K:.2f} TL/da (katsayı 1)."
    ),
    "Meyve-Sebze Üretim Destekleri": (
        _temel_1, _temel_1,
        f"Sebze ve meyve, tabloda 1. kategori \"Diğer ürünler\" kapsamında: "
        f"temel destek {_temel_1:.2f} TL/dekar. Planlı üretim desteği "
        f"kategorilerinde yer almadığı için o kalem eklenmez. Fidan kullanım "
        f"desteği (standart 620,00 / sertifikalı 1.550,00 TL/da) ayrıca "
        f"alınabilir."
    ),
    "Sera/Örtüaltı Tarım Destekleri": (
        _temel_1, _temel_1 + _iyi_tarim_ortualti,
        f"Temel destek {_temel_1:.2f} TL/dekar. İyi tarım uygulamaları "
        f"sertifikası varsa örtüaltı üretim için bireysel sertifikada "
        f"{_iyi_tarim_ortualti:.2f} TL/dekar ilave; üst sınır bu iki kalemin "
        f"toplamı. Grup sertifikasında ilave yarıya iner."
    ),
    "Organik Tarım Destekleri": (
        _organik_en_az, _organik_en_cok,
        f"Ürün grubuna ve sertifika türüne göre: 3. grup grup sertifikası "
        f"{_organik_en_az:.2f} TL/dekar (en az), 1. grup bireysel sertifika "
        f"{ORGANIK_TARIM[1][0]*K:.2f} TL/dekar. 1. derece tarımsal amaçlı "
        f"örgüt üyesi çiftçilere katsayının %25'i kadar ilave ödenir; üst "
        f"sınır {_organik_en_cok:.2f} TL/dekar bunu içerir. Temel destek "
        f"buna ek olarak alınır."
    ),
}

# Bilerek dokunulmayan kayıtlar ve sebebi.
DOKUNULMAYANLAR = {
    "Hayvancılık Destekleri":
        "Hayvancılık destekleri ayrı bir kararda ve hayvan başına ödenir; "
        "2026 bitkisel üretim birim fiyat tablosunda yok.",
    "Sulama Yatırımı Destekleri":
        "Bireysel sulama/KKYDP kapsamında proje bazlı hibe; dekar başına "
        "birim fiyatı yok.",
    "Tarımsal Makineleştirme Destekleri":
        "Makine-ekipman hibesi alım bedeli üzerinden hesaplanır; dekar başına "
        "birim fiyatı yok.",
}

DURUM_NOTU_EKI = (
    f"Tutarlar {KAYNAK} tablosundan hesaplandı (birim değer {K:.2f} TL/dekar). "
    "Ödeme ÇKS kaydınızın uygunluğuna bağlıdır; nihai tutar için il/ilçe tarım "
    "müdürlüğünden teyit alın."
)


def calistir(uygula: bool) -> int:
    db = SessionLocal()
    try:
        simdi = datetime.now(timezone.utc)
        etiket = "yazilacak" if uygula else "RAPOR"
        yazilan = 0

        print("== DOLDURULACAK KAYITLAR ==")
        for parca, (alt, ust, formul) in HEDEFLER.items():
            t = db.query(Tesvik).filter(Tesvik.baslik.like(f"{parca}%")).first()
            if t is None:
                print(f"  [ATLANDI] '{parca}' ile baslayan kayit bulunamadi")
                continue
            print(f"  [{etiket}] {t.baslik}")
            print(f"      onceki: min={t.tutari_min} max={t.tutari_max} "
                  f"kriter={t.tutari_hesaplama_kriteri!r}")
            print(f"      yeni  : {alt:.2f} - {ust:.2f} TL/dekar")
            if uygula:
                t.tutari_min = round(alt, 2)
                t.tutari_max = round(ust, 2)
                t.tutari_hesaplama_kriteri = "dekar"
                t.tutari_hesaplama_formulu = formul
                mevcut_not = (t.durum_notu or "").strip()
                if DURUM_NOTU_EKI not in mevcut_not:
                    t.durum_notu = (mevcut_not + " " + DURUM_NOTU_EKI).strip()
                if not t.kaynak_url:
                    t.kaynak_url = KAYNAK_URL
                t.guncelleme_tarihi = simdi
            yazilan += 1

        print("\n== BILEREK DOKUNULMAYANLAR ==")
        for parca, sebep in DOKUNULMAYANLAR.items():
            t = db.query(Tesvik).filter(Tesvik.baslik.like(f"{parca}%")).first()
            durum = "kayit yok" if t is None else f"min={t.tutari_min}"
            print(f"  {parca} ({durum})")
            print(f"      {sebep}")

        # Proje bazlı kayıtları İŞARETLE: tutar metinleri programın üst
        # sınırını içeriyor ve kullanıcının ölçeğiyle ilişkili değil. İşaret
        # olmadan bu tavanlar "toplam tahmini destek"e giriyor ve 50 dekarlık
        # bir çiftçinin toplamını 1,6 milyon TL'ye çıkarıyordu
        # (bkz. app/matching._proje_bazli_tavan_mi).
        print("\n== PROJE BAZLI OLARAK ISARETLENECEKLER ==")
        isaretlenen = 0
        for parca in DOKUNULMAYANLAR:
            t = db.query(Tesvik).filter(Tesvik.baslik.like(f"{parca}%")).first()
            if t is None:
                continue
            k = dict(t.uygunluk_kriterleri or {})
            if k.get("tutar_niteligi") == "proje_bazli_tavan":
                print(f"  [zaten isaretli] {t.baslik}")
                continue
            print(f"  [{etiket}] {t.baslik}")
            if uygula:
                k["tutar_niteligi"] = "proje_bazli_tavan"
                t.uygunluk_kriterleri = k
                t.guncelleme_tarihi = simdi
            isaretlenen += 1

        if uygula:
            db.commit()
            print(f"\nYAZILDI: {yazilan} kayit guncellendi, "
                  f"{isaretlenen} kayit proje bazli olarak isaretlendi.")
        else:
            print(f"\nRAPOR: {yazilan} kayit guncellenecek, "
                  f"{isaretlenen} kayit isaretlenecek.")
            print("Uygulamak icin --uygula ile tekrar calistirin.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="2026 tarim birim fiyat backfill.")
    a.add_argument("--uygula", action="store_true")
    sys.exit(calistir(a.parse_args().uygula))
