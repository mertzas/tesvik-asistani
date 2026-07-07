"""
KOSGEB destek programlari icin basit scraper.

Not: KOSGEB sitesinde resmi bir API yok, bu yuzden HTML uzerinden veri
cekiyoruz. Site yapisi degisirse asagidaki CSS secicilerinin
guncellenmesi gerekir (bkz. https://www.kosgeb.gov.tr/site/tr/genel/destekler).
Detay sayfalari /site/tr/genel/destekdetay/[ID]/[slug] formatinda.
"""
import time
import requests
from bs4 import BeautifulSoup

from app.models import SessionLocal, Tesvik, init_db, seen_keys, normalize_title

BASE_URL = "https://www.kosgeb.gov.tr"
LIST_URL = f"{BASE_URL}/site/tr/genel/destekler"
HEADERS = {"User-Agent": "Mozilla/5.0 (tesvik-asistani/1.0)"}


def fetch_list_page(page: int = 1):
    resp = requests.get(LIST_URL, params={"sayfa": page}, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


# Listeleme sayfasi hem gercek destek programlarini hem de bu programlar
# hakkinda cikan gazete haberlerini ayni URL desenini kullanarak listeliyor.
# Haber linkleri genelde bilinen gazete adlarini icerdigi icin bunlari eliyoruz.
HABER_KAYNAKLARI = {
    "gazetesi", "hurriyet", "milliyet", "sabah", "takvim", "dunya",
    "haberturk", "sozcu", "aa-", "cnn-turk", "ntv",
}


def extract_detail_links(soup: BeautifulSoup) -> list[str]:
    links = set()
    for a in soup.find_all("a", href=True):
        if "/site/tr/genel/destekdetay/" in a["href"]:
            href = a["href"]
            if href.startswith("/"):
                href = BASE_URL + href
            slug = href.rsplit("/", 1)[-1].lower()
            if any(kaynak in slug for kaynak in HABER_KAYNAKLARI):
                continue
            links.add(href)
    return list(links)


def fetch_detail(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.find("h1") or soup.find("h2") or soup.find("h3")
    baslik = " ".join(title_el.get_text(strip=True).split()) if title_el else url

    # Ozel bir icerik container'i yok; body metninde nav/menu her zaman
    # basligin ONCESINDE gelir, bu yuzden basligin ilk gectigi noktadan
    # itibaren metni alarak menu gurultusunu atiyoruz.
    body = soup.find("body")
    full_text = body.get_text("\n", strip=True) if body else soup.get_text("\n", strip=True)
    idx = full_text.find(baslik)
    detay = full_text[idx:] if idx != -1 else full_text
    ozet = detay[:300]

    return {
        "kurum": "KOSGEB",
        "baslik": baslik,
        "ozet": ozet,
        "detay": detay,
        "hedef_kitle": "KOBI/girisimci",
        "kaynak_url": url,
    }


def run(max_pages: int = 5, delay_sec: float = 1.0):
    init_db()
    db = SessionLocal()
    seen_urls, seen_titles = seen_keys(db, "KOSGEB")

    all_links: set[str] = set()
    for page in range(1, max_pages + 1):
        soup = fetch_list_page(page)
        links = extract_detail_links(soup)
        if not links:
            break
        all_links.update(links)
        time.sleep(delay_sec)

    new_count = 0
    for url in all_links:
        if url in seen_urls:
            continue
        try:
            data = fetch_detail(url)
        except requests.RequestException as e:
            print(f"Hata ({url}): {e}")
            continue

        # Ayni URL deseni altinda destek programi disinda finansal
        # gosterge/sozluk gibi ilgisiz sayfalar da bulunuyor; baslikta
        # "destek" veya "program" gecmeyenleri eliyoruz.
        baslik_lower = data["baslik"].lower()
        if "destek" not in baslik_lower and "program" not in baslik_lower:
            continue

        # Ayni program farkli il/donem slug'i altinda tekrar listelenebiliyor;
        # ayni kurum icinde ayni baslik zaten varsa atla.
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
