"""Katı eleme kriterlerini (hedef kitle, çalışan sınırı, il kısıtı)
uygunluk_kriterleri'ne yazar. Bkz. app/match_scoring.py, app/match_adapter.py.

DİKKAT - kaynak: bu etiketler program BAŞLIKLARINDAN çıkarıldı (resmî şart
metni okunmadı). Başlığın açıkça söylediği dikeyleri işaretliyor; emin
olunmayanlar bilerek dışarıda bırakıldı. Yanlış bir "zorunlu hedef kitle"
etiketi hak eden kullanıcıdan programı GİZLER, bu yüzden liste kısa tutuldu.

Varsayılan kuru çalıştırma; yazmak için --uygula. Idempotent.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, init_db  # noqa: E402

# 6 Şubat depremi bölgesi (mevcut backfill_bolge_kisiti.py ile aynı liste)
DEPREM_ILLERI = [
    "kahramanmaraş", "gaziantep", "şanlıurfa", "diyarbakır", "adana",
    "adıyaman", "malatya", "osmaniye", "hatay", "elazığ", "kilis", "sivas",
]

# başlıkta geçen ifade (BÜYÜK HARF) -> eklenecek kriterler
KURALLAR: list[tuple[str, dict]] = [
    ("SAVUNMA SANAYİİ", {"exclusive_target_group": True, "target_group_tags": ["savunma_sanayii"]}),
    ("MESLEKİ EĞİTİM KREDİSİ", {"exclusive_target_group": True, "target_group_tags": ["mesleki_egitim"]}),
    ("HUKUK BÜROSU", {"exclusive_target_group": True, "target_group_tags": ["hukuk_burosu"]}),
    ("BASIN İLAN KURUMU", {"exclusive_target_group": True, "target_group_tags": ["basin_ilan"]}),
    ("KADIN VE GENÇ GİRİŞİMCİ", {"exclusive_target_group": True,
                                  "target_group_tags": ["kadin_girisimci", "genc_girisimci"]}),
    ("KADIN GİRİŞİMCİ DESTEK PAKETİ", {"exclusive_target_group": True, "target_group_tags": ["kadin_girisimci"]}),
    ("GENÇ İŞİ KREDİSİ", {"exclusive_target_group": True, "target_group_tags": ["genc_girisimci"]}),
    ("GENÇİZ KREDİSİ", {"exclusive_target_group": True, "target_group_tags": ["genc_girisimci"]}),
    ("ÇAY ALIMI", {"exclusive_target_group": True, "target_group_tags": ["cay_ureticisi"]}),
    ("KOOPERATİF DESTEK PAKETİ", {"exclusive_target_group": True, "target_group_tags": ["kooperatif"]}),
    # 5174 sayılı/AB tanımı: mikro < 10, küçük < 50 çalışan
    ("MİKRO İŞLETMELER DESTEK PAKETİ", {"max_employees": 9}),
    ("KÜÇÜK İŞLETME CAN SUYU", {"max_employees": 49}),
    ("6 ŞUBAT DEPREMLERİ", {"bolge_kisitli": DEPREM_ILLERI}),
]


def _kucuk_harf_degil_buyuk(metin: str) -> str:
    # str.upper() Türkçe i/ı'yı bozar; karşılaştırmanın iki tarafı da aynı
    # fonksiyondan geçtiği için tutarlı.
    return metin.replace("i", "İ").replace("ı", "I").upper()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    degisen = 0
    try:
        for t in db.query(Tesvik).order_by(Tesvik.id):
            baslik = _kucuk_harf_degil_buyuk(t.baslik or "")
            eklenecek: dict = {}
            for ifade, kriter in KURALLAR:
                if _kucuk_harf_degil_buyuk(ifade) in baslik:
                    eklenecek.update(kriter)
            if not eklenecek:
                continue
            mevcut = dict(t.uygunluk_kriterleri or {})
            if all(mevcut.get(k) == v for k, v in eklenecek.items()):
                continue
            degisen += 1
            print(f"[{t.id}] {t.baslik}: {eklenecek}")
            if args.uygula:
                mevcut.update(eklenecek)
                t.uygunluk_kriterleri = mevcut
        if args.uygula:
            db.commit()
    finally:
        db.close()
    print(f"\n{degisen} kayıt {'güncellendi' if args.uygula else 'güncellenecek (kuru çalıştırma)'}.")


if __name__ == "__main__":
    main()
