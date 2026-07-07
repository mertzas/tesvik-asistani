"""
TUBITAK destek programlari icin scraper.

TUBITAK'in da resmi bir API'si yok. Destek programlari
https://www.tubitak.gov.tr/tr/destekler altinda kategorilere ayrilmis
sekilde listeleniyor, her programin detay sayfasi
https://tubitak.gov.tr/tr/destekler/[kategori]/[alt-kategori]/[kod]-[slug]
formatinda (orn. 1501-tubitak-sanayi-ar-ge-projeleri-destekleme-programi).
"""
import time
import requests
from bs4 import BeautifulSoup

from app.models import SessionLocal, Tesvik, init_db, seen_keys, normalize_title

BASE_URL = "https://www.tubitak.gov.tr"
LIST_URL = f"{BASE_URL}/tr/destekler"
HEADERS = {"User-Agent": "Mozilla/5.0 (tesvik-asistani/1.0)"}


def fetch_list_page() -> BeautifulSoup:
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


def extract_detail_links(soup: BeautifulSoup) -> list[str]:
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/tr/destekler/" in href and href.rstrip("/") != "/tr/destekler":
            if href.startswith("/"):
                href = BASE_URL + href
            elif href.startswith("tr/"):
                href = f"{BASE_URL}/{href}"
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
        "kurum": "TUBITAK",
        "baslik": baslik,
        "ozet": ozet,
        "detay": detay,
        "hedef_kitle": "arastirmaci/sanayi/KOBI",
        "kaynak_url": url,
    }


def run(delay_sec: float = 1.0):
    init_db()
    db = SessionLocal()
    seen_urls, seen_titles = seen_keys(db, "TUBITAK")

    soup = fetch_list_page()
    links = extract_detail_links(soup)

    new_count = 0
    for url in links:
        if url in seen_urls:
            continue
        try:
            data = fetch_detail(url)
        except requests.RequestException as e:
            print(f"Hata ({url}): {e}")
            continue

        # Program kodu (1000, 1501 vb.) icermeyen sayfalar genelde
        # kategori/menu sayfalaridir, gercek destek programi degildir.
        slug = url.rsplit("/", 1)[-1]
        if not any(ch.isdigit() for ch in slug.split("-", 1)[0]):
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
    print(f"{new_count} yeni destek programi eklendi.")


if __name__ == "__main__":
    run()
