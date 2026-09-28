#!/usr/bin/env python3
"""
Veritabanındaki mevcut AÇIK METİN İKAS token'larını yerinde şifreler.

NEDEN
-----
`ikas_baglanti.access_token` / `.refresh_token` sütunları artık SifreliMetin
tipinde (bkz. app/sifreleme.py) ve yeni yazılan değerler şifreli saklanıyor.
Ama sürüm geçişinden ÖNCE yazılmış kayıtlar hâlâ açık metin.

app.sifreleme.coz() ön eki olmayan değerleri olduğu gibi döndürür - yani eski
kayıtlar çalışmaya devam eder, sessizce kırılmaz. Bu script o kayıtları
yerinde şifreler ki diskte açık metin token kalmasın.

Şifreleme anahtarı SECRET_KEY'den türetildiği (ya da IKAS_TOKEN_KEY'den
alındığı) için, bu script çalıştırıldıktan SONRA anahtar değişirse token'lar
çözülemez ve İKAS bağlantısının yeniden kurulması gerekir. Token'lar zaten
süreli olduğu için bu kabul edilebilir bir maliyet.

Kullanım:
    python -m scripts.sifrele_mevcut_tokenlar             # rapor
    python -m scripts.sifrele_mevcut_tokenlar --uygula
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import text  # noqa: E402

from app.models import SessionLocal  # noqa: E402
from app.sifreleme import ONEK, sifrele  # noqa: E402

ALANLAR = ("access_token", "refresh_token")


def calistir(uygula: bool) -> int:
    db = SessionLocal()
    try:
        # HAM SQL kullaniyoruz: ORM okursa SifreliMetin zaten cozmeye calisir
        # ve diskteki gercek degeri goremeyiz.
        satirlar = db.execute(text(
            "SELECT id, store_name, access_token, refresh_token "
            "FROM ikas_baglanti")).fetchall()

        if not satirlar:
            print("ikas_baglanti tablosunda kayit yok - yapilacak bir sey yok.")
            return 0

        print(f"{len(satirlar)} baglanti kaydi inceleniyor\n")
        sifrelenecek = []
        for satir in satirlar:
            kayit_id, magaza = satir[0], satir[1]
            for i, alan in enumerate(ALANLAR, start=2):
                deger = satir[i]
                if deger is None:
                    continue
                if str(deger).startswith(ONEK):
                    print(f"  [zaten şifreli] {magaza}.{alan}")
                    continue
                print(f"  [AÇIK METİN]    {magaza}.{alan}  "
                      f"({str(deger)[:14]}...)")
                sifrelenecek.append((kayit_id, alan, deger))

        if not sifrelenecek:
            print("\nAcik metin token bulunamadi - hepsi zaten sifreli.")
            return 0

        if uygula:
            simdi = datetime.now(timezone.utc)
            for kayit_id, alan, deger in sifrelenecek:
                db.execute(
                    text(f"UPDATE ikas_baglanti SET {alan} = :d, "
                         "updated_at = :u WHERE id = :i"),
                    {"d": sifrele(str(deger)), "u": simdi, "i": kayit_id})
            db.commit()
            print(f"\nYAZILDI: {len(sifrelenecek)} deger sifrelendi.")
        else:
            print(f"\nRAPOR: {len(sifrelenecek)} deger sifrelenecek.")
            print("Uygulamak icin --uygula ile tekrar calistirin.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Mevcut tokenlari sifrele.")
    a.add_argument("--uygula", action="store_true")
    sys.exit(calistir(a.parse_args().uygula))
