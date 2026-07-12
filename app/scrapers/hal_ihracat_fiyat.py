"""
T.C. Ticaret Bakanligi Hal Kayit Sistemi (HKS) - gunluk "Ihracat Fiyat
Bulteni" (gumruk/ihracat beyani icin resmi referans fiyat).

https://www.hal.gov.tr/Sayfalar/IhracatFiyatBulten.aspx - app/scrapers/
hal_cilek_fiyat.py ile ayni GridView + Page$N postback deseni (dogrulandi,
2026-07-11), farkli bir urun katalogu: bu bulten CILEK icermiyor, ~40
baska urun (domates, elma, biber, kayisi, karpuz vb.) icin veri sagliyor.

Bu yuzden hal_cilek_fiyat.py'nin aksine "tek urun ara, bulunca dur" degil,
"tum sayfalari gez, TUM satirlari topla" mantigi kullanilir - hangi
urunlerin kullaniciya sorulacagini onceden bilemeyiz (bkz. app/
ihracat_fiyatlari.py).

Ag hatasi / site yapisi degisikligi durumunda BOS LISTE doner, exception
firlatmaz - run() bunu "bugun veri alinamadi" olarak ele alir.
"""
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from app.models import SessionLocal, IhracatFiyati, init_db

BASE_URL = "https://www.hal.gov.tr/Sayfalar/IhracatFiyatBulten.aspx"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
GRIDVIEW_EVENTTARGET = "ctl00$ctl37$g_c63c2760_eb32_413b_957c_df76d47b9297$gvFiyatlar"
MAX_SAYFA = 15
ISTEK_TIMEOUT_SANIYE = 20


def _form_deger(soup: BeautifulSoup, ad: str) -> str:
    el = soup.find("input", {"name": ad})
    return el["value"] if el and el.has_attr("value") else ""


def _tablo_satirlari(soup: BeautifulSoup) -> list[list[str]]:
    tablo = soup.find("table", id=lambda x: x and "gvFiyatlar" in x)
    if tablo is None:
        return []
    satirlar = []
    for tr in tablo.find_all("tr"):
        hucreler = [td.get_text(strip=True) for td in tr.find_all("td")]
        # Ihracat bultenindeki veri satirlari 6 sutunludur:
        # Urun Adi, Urun Cinsi, Urun Turu, Fiyat, Miktar, Birim.
        if len(hucreler) == 6:
            satirlar.append(hucreler)
    return satirlar


def _bulten_veri_tarihi(html: str) -> date:
    eslesme = re.search(r"\((\d{1,2}\.\d{1,2}\.\d{4})\s*Tarihli", html)
    if eslesme:
        return datetime.strptime(eslesme.group(1), "%d.%m.%Y").date()
    return date.today()


def _sonraki_sayfa(session: requests.Session, soup: BeautifulSoup, sayfa_no: int) -> BeautifulSoup:
    payload = {
        "__EVENTTARGET": GRIDVIEW_EVENTTARGET,
        "__EVENTARGUMENT": f"Page${sayfa_no}",
        "__VIEWSTATE": _form_deger(soup, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": _form_deger(soup, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": _form_deger(soup, "__EVENTVALIDATION"),
    }
    yanit = session.post(BASE_URL, data=payload, timeout=ISTEK_TIMEOUT_SANIYE)
    yanit.raise_for_status()
    yanit.encoding = "utf-8"
    return BeautifulSoup(yanit.text, "html.parser")


def fetch_all_ihracat_rows() -> tuple[list[list[str]], date]:
    """Tum sayfalari gezip bulteindeki TUM urun satirlarini toplar (~40 urun,
    77 satir civari - urun basina birden fazla urun_turu/cinsi olabilir)."""
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        yanit = session.get(BASE_URL, timeout=ISTEK_TIMEOUT_SANIYE)
        yanit.raise_for_status()
        yanit.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"HKS ihracat bulteni sayfasina erisilemedi: {e}")
        return [], date.today()

    veri_tarihi = _bulten_veri_tarihi(yanit.text)
    soup = BeautifulSoup(yanit.text, "html.parser")

    tum_satirlar: list[list[str]] = []
    for sayfa_no in range(1, MAX_SAYFA + 1):
        if sayfa_no > 1:
            try:
                soup = _sonraki_sayfa(session, soup, sayfa_no)
            except requests.RequestException as e:
                print(f"HKS ihracat bulteni sayfa {sayfa_no} alinamadi: {e}")
                break

        satirlar = _tablo_satirlari(soup)
        if not satirlar:
            break  # son sayfayi gectik

        tum_satirlar.extend(satirlar)

    return tum_satirlar, veri_tarihi


def _fiyat_to_float(deger: str) -> float | None:
    try:
        return float(deger.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def run() -> int:
    """HKS'den gunun ihracat fiyat bultenini cekip IhracatFiyati tablosuna
    yazar. Ayni gun icin ayni urun+cins+tur kaydi zaten varsa tekrar
    eklemez (idempotent)."""
    init_db()
    db = SessionLocal()

    satirlar, veri_tarihi = fetch_all_ihracat_rows()
    if not satirlar:
        print("HKS'den ihracat fiyat bulteni alınamadı (site erişilemedi veya veri bulunamadı).")
        db.close()
        return 0

    eklenen = 0
    for urun_adi, urun_cinsi, urun_turu, fiyat_str, miktar_str, _birim in satirlar:
        fiyat = _fiyat_to_float(fiyat_str)
        if fiyat is None:
            continue
        miktar = _fiyat_to_float(miktar_str)

        zaten_var = (
            db.query(IhracatFiyati)
            .filter(
                IhracatFiyati.tarih == veri_tarihi,
                IhracatFiyati.urun_adi == urun_adi.strip(),
                IhracatFiyati.urun_cinsi == urun_cinsi.strip(),
                IhracatFiyati.urun_turu == urun_turu.strip(),
            )
            .first()
        )
        if zaten_var is not None:
            continue

        db.add(IhracatFiyati(
            tarih=veri_tarihi,
            urun_adi=urun_adi.strip(),
            urun_cinsi=urun_cinsi.strip(),
            urun_turu=urun_turu.strip(),
            fiyat_kg=fiyat,
            miktar_kg=miktar,
        ))
        eklenen += 1

    db.commit()
    db.close()
    print(f"HKS ihracat fiyat bülteni: {eklenen} yeni kayıt eklendi (veri tarihi: {veri_tarihi}).")
    return eklenen


if __name__ == "__main__":
    run()
