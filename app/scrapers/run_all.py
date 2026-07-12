"""Tum kurumlarin scraper'larini sirayla calistirir. Her scraperda hata
olursa loglayip devam eder (sunucuyu cokturmez)."""
from app.scrapers import kosgeb, tubitak, kgf, hazine_tesvik

if __name__ == "__main__":
    for scraper_name, scraper_mod in [
        ("KOSGEB", kosgeb),
        ("TUBITAK", tubitak),
        ("KGF", kgf),
        ("Hazine/Ticaret Bakanligi (Yatirim Tesvik Sistemi)", hazine_tesvik),
    ]:
        try:
            print(f"--- {scraper_name} ---")
            scraper_mod.run()
        except Exception as e:
            print(f"HATA [{scraper_name}]: {e}")
