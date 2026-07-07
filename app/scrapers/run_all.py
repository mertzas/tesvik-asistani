"""Tum kurumlarin scraper'larini sirayla calistirir."""
from app.scrapers import kosgeb, tubitak, kgf, hazine_tesvik

if __name__ == "__main__":
    print("--- KOSGEB ---")
    kosgeb.run()
    print("--- TUBITAK ---")
    tubitak.run()
    print("--- KGF ---")
    kgf.run()
    print("--- Hazine/Ticaret Bakanligi (Yatirim Tesvik Sistemi) ---")
    hazine_tesvik.run()
