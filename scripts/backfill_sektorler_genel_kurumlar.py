"""
KOSGEB, TUBITAK, KGF ve Hazine kayitlarinin uygunluk_kriterleri alaninda hic
"sektorler" etiketi yoktu (hedef_kitle serbest metin olarak "KOBI/girisimci"
gibi tutuluyordu ama matching.py SADECE uygunluk_kriterleri.sektorler alanina
bakiyor). Sonuc: matching.esles() bu 154 kaydin tumunu (kriterler.get("sektorler")
bos oldugu icin) atliyordu - tarim disi HERHANGI bir profil (e-ticaret, imalat,
hizmet, arge...) icin /api/eslesme SIFIR sonuc donuyordu.

Bu betik geriye donuk olarak sektorler etiketi ekler:
- TUBITAK: arge + genel (R&D odakli ama KOBI/sanayi de basvurabiliyor)
- KOSGEB, KGF, Hazine: genel (sektor bagimsiz, tum KOBI/isletmelere acik)

Calistirma: python scripts/backfill_sektorler_genel_kurumlar.py
"""
import json
from app.models import SessionLocal, Tesvik

KURUM_SEKTOR_ESLEME = {
    "TUBITAK": ["arge", "genel"],
    "TÜBİTAK": ["arge", "genel"],
    "KOSGEB": ["genel"],
    "KGF": ["genel"],
    "Hazine": ["genel"],
    "Hazine/Ticaret Bakanligi": ["genel"],
}


def main() -> None:
    db = SessionLocal()
    guncellenen = 0

    for t in db.query(Tesvik).all():
        kriterler = t.uygunluk_kriterleri or {}
        if kriterler.get("sektorler"):
            continue  # zaten etiketli (orn. Tarim Bakanligi kayitlari)

        sektorler = KURUM_SEKTOR_ESLEME.get(t.kurum)
        if not sektorler:
            print(f"UYARI: '{t.kurum}' icin sektor eslemesi tanimli degil, atlandi (id={t.id}).")
            continue

        kriterler["sektorler"] = sektorler
        t.uygunluk_kriterleri = kriterler
        guncellenen += 1

    db.commit()
    db.close()
    print(f"{guncellenen} kayda sektorler etiketi eklendi.")


if __name__ == "__main__":
    main()
