"""
KGF (Kredi Garanti Fonu) kefalet/destek urunleri icin scraper.

KGF sitesinin de resmi bir API'si yok. Urun listesi ana sayfadan
(https://www.kgf.com.tr/) /index.php/tr/urunlerimiz/... altindaki linkler
uzerinden cikariliyor. Not: /kefalet-urunlerimiz gibi bazi kisayol URL'ler
yonlendirme dongusune giriyor, bu yuzden ana sayfa (/) uzerinden geziyoruz.
"""
import time
import requests
from bs4 import BeautifulSoup

from app.models import SessionLocal, Tesvik, init_db, seen_keys, normalize_title

BASE_URL = "https://www.kgf.com.tr"
HOME_URL = f"{BASE_URL}/"
HEADERS = {"User-Agent": "Mozilla/5.0 (tesvik-asistani/1.0)"}


def fetch_home_page() -> BeautifulSoup:
    resp = requests.get(HOME_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


def extract_product_links(soup: BeautifulSoup) -> list[str]:
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/urunlerimiz/" in href:
            # kategori sayfalari degil, en az 4 seviyeli (gercek urun) linkler
            depth = href.strip("/").count("/")
            if depth < 4:
                continue
            if href.startswith("/"):
                href = BASE_URL + href
            links.add(href)
    return list(links)


def fetch_detail(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.find("h1") or soup.find("h2") or soup.find("h3")
    baslik = " ".join(title_el.get_text(strip=True).split()) if title_el else url

    # Nav/menu basligin oncesinde gelir; basligin ilk gectigi noktadan
    # itibaren metni alarak menu gurultusunu atiyoruz.
    body = soup.find("body")
    full_text = body.get_text("\n", strip=True) if body else soup.get_text("\n", strip=True)
    idx = full_text.find(baslik)
    detay = full_text[idx:] if idx != -1 else full_text
    ozet = detay[:300]

    return {
        "kurum": "KGF",
        "baslik": baslik,
        "ozet": ozet,
        "detay": detay,
        "hedef_kitle": "KOBI/isletme",
        "kaynak_url": url,
    }


def run(delay_sec: float = 1.0):
    init_db()
    db = SessionLocal()
    seen_urls, seen_titles = seen_keys(db, "KGF")

    soup = fetch_home_page()
    links = extract_product_links(soup)

    new_count = 0
    for url in links:
        if url in seen_urls:
            continue
        try:
            data = fetch_detail(url)
        except requests.RequestException as e:
            print(f"Hata ({url}): {e}")
            continue

        norm_title = normalize_title(data["baslik"])
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)

        db.add(Tesvik(**data))
        new_count += 1
        time.sleep(delay_sec)

    db.commit()
    db.close()
    print(f"{new_count} yeni destek/kefalet urunu eklendi.")


if __name__ == "__main__":
    run()
