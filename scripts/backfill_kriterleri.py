"""
Mevcut tesvikler tablosundaki kayitlara, kurum/baslik/hedef_kitle metnine
dayanarak sektor etiketi (kategori) ve esleme motorunun kullanacagi
uygunluk_kriterleri JSON alanini geriye donuk (backfill) doldurur.

Bu bir kesin/otoriter kaynak degil, mevcut curated veriden cikarilan
best-effort bir etiketleme. Yeni scraper'lar eklendikce KURUM_SEKTOR_HARITASI
genisletilmeli.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, init_db

KURUM_SEKTOR_HARITASI = {
    "tkdk": ["tarim"],
    "tarım bakanlığı": ["tarim"],
    "tarim bakanligi": ["tarim"],
    "kosgeb": ["kobi", "genel"],
    "tubitak": ["arge", "teknoloji"],
    "tübi̇tak": ["arge", "teknoloji"],
    "kgf": ["finansman", "genel"],
    "ticaret bakanlığı": ["ihracat"],
    "ticaret bakanligi": ["ihracat"],
    "işkur": ["istihdam"],
    "iskur": ["istihdam"],
    "çalışma bakanlığı": ["istihdam"],
    "calisma bakanligi": ["istihdam"],
    "enerji bakanlığı": ["enerji"],
    "enerji bakanligi": ["enerji"],
    "çevre bakanlığı": ["cevre"],
    "cevre bakanligi": ["cevre"],
    "hazine": ["yatirim", "sanayi"],
    "invest in turkey": ["yatirim", "yabanci_sermaye"],
    "kalkınma ajansları": ["bolgesel", "genel"],
    "kalkinma ajanslari": ["bolgesel", "genel"],
    "kültür bakanlığı": ["kultur"],
    "kultur bakanligi": ["kultur"],
    "spor bakanlığı": ["spor"],
    "spor bakanligi": ["spor"],
}

HEDEF_ANAHTAR_KELIME = {
    "kobi": ["kobi", "girisimci"],
    "sanayi": ["sanayi", "imalat"],
    "arastirmaci": ["arge"],
    "yatirimci": ["yatirim"],
    "ihracatci": ["ihracat"],
    "ciftci": ["tarim"],
    "üretici": ["tarim", "imalat"],
}


def sektor_etiketle(kurum: str, hedef_kitle: str | None) -> list[str]:
    kurum_l = (kurum or "").lower()
    sektorler: set[str] = set()

    for anahtar, etiketler in KURUM_SEKTOR_HARITASI.items():
        if anahtar in kurum_l:
            sektorler.update(etiketler)

    hedef_l = (hedef_kitle or "").lower()
    for anahtar, etiketler in HEDEF_ANAHTAR_KELIME.items():
        if anahtar in hedef_l:
            sektorler.update(etiketler)

    if not sektorler:
        sektorler.add("genel")

    return sorted(sektorler)


def run():
    init_db()
    db = SessionLocal()
    guncellenen = 0
    try:
        for t in db.query(Tesvik).all():
            sektorler = sektor_etiketle(t.kurum, t.hedef_kitle)

            if not t.kategori:
                t.kategori = sektorler[0]

            if not t.uygunluk_kriterleri:
                t.uygunluk_kriterleri = {
                    "sektorler": sektorler,
                    "hedef_kitle_ham": t.hedef_kitle,
                }
                guncellenen += 1

        db.commit()
    finally:
        db.close()

    print(f"{guncellenen} kayit icin uygunluk_kriterleri dolduruldu.")


if __name__ == "__main__":
    run()
