"""
T.C. Ticaret Bakanligi Hal Kayit Sistemi (HKS) - gunluk "Fiyat Detaylari"
bulteni (https://www.hal.gov.tr/Sayfalar/FiyatDetaylari.aspx).

app/scrapers/hal_cilek_fiyat.py'nin GENELLESTIRILMIS hali: cilek disinda
hedeflenen HERHANGI bir urunu (su an sadece MUZ, HEDEF_URUNLER'e yenisi
eklenebilir) ayni sayfa+postback deseniyle ceker ve genel amacli
HalFiyati tablosuna yazar (bkz. app/models.py). Cilek icin ozel panel
(cilek_engine.py) hala hal_cilek_fiyat.py + PazarFiyati/KaliteSinifi
uzerinden calismaya devam ediyor - bu modul ona dokunmuyor.

Urunler alfabetik siralandigi icin, hedef urun kumesindeki TUM urunler
bulunduktan sonra bir sayfada hicbiri kalmazsa (alfabetik bolumleri
gectik demektir) tarama durur.
"""
import re
import time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from app.models import SessionLocal, HalFiyati, init_db

BASE_URL = "https://www.hal.gov.tr/Sayfalar/FiyatDetaylari.aspx"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
GRIDVIEW_EVENTTARGET = "ctl00$ctl37$g_7e86b8d6_3aea_47cf_b1c1_939799a091e0$gvFiyatlar"
MAX_SAYFA = 40
ISTEK_TIMEOUT_SANIYE = 20
# Sayfalar arasi bekleme - hal.gov.tr'yi ardisik isteklerle yormamak icin.
SAYFA_ARASI_BEKLEME_SANIYE = 0.6

# Belirli urunlerle sinirlamak icin kullanilabilir (orn. {"MUZ"}). None/bos
# birakilirsa bultendeki TUM urunler cekilir - bu betik canli uygulamadan
# BAGIMSIZ, offline/zamanlanmis bir is olarak calistirilir (bkz. run()),
# yani "tüm ürünler" modu bile uygulamayi/istekleri bloklamaz.
HEDEF_URUNLER: set[str] | None = None


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


def fetch_hedef_urun_rows(hedef_urunler: set[str] | None = HEDEF_URUNLER) -> tuple[list[list[str]], date]:
    """Bultendeki satirlari toplar.

    hedef_urunler verilmisse (orn. {"MUZ"}) sadece o urun(ler)in alfabetik
    bolumunu tarar ve biter biter durur. None/bos ise (varsayilan) TUM
    urunleri ceker; sayfalar arasinda kisa bir bekleme (bkz.
    SAYFA_ARASI_BEKLEME_SANIYE) birakarak hal.gov.tr'ye asiri yuk
    bindirmemeye calisir. Ag hatasi / site yapisi degisikligi durumunda
    o ana kadar toplanan satirlari doner (bos olabilir)."""
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        yanit = session.get(BASE_URL, timeout=ISTEK_TIMEOUT_SANIYE)
        yanit.raise_for_status()
        yanit.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"HKS fiyat detaylari sayfasina erisilemedi: {e}")
        return [], date.today()

    veri_tarihi = _bulten_veri_tarihi(yanit.text)
    soup = BeautifulSoup(yanit.text, "html.parser")

    tum_satirlar: list[list[str]] = []
    herhangi_bulundu_mu = False
    tum_urunler_modu = not hedef_urunler

    for sayfa_no in range(1, MAX_SAYFA + 1):
        if sayfa_no > 1:
            time.sleep(SAYFA_ARASI_BEKLEME_SANIYE)
            try:
                soup = _sonraki_sayfa(session, soup, sayfa_no)
            except requests.RequestException as e:
                print(f"HKS fiyat detaylari sayfa {sayfa_no} alinamadi: {e}")
                break

        satirlar = _tablo_satirlari(soup)
        if not satirlar:
            break

        if tum_urunler_modu:
            tum_satirlar.extend(satirlar)
            continue

        bu_sayfada_hedef = [s for s in satirlar if s[0].strip().upper() in hedef_urunler]
        if bu_sayfada_hedef:
            herhangi_bulundu_mu = True
            tum_satirlar.extend(bu_sayfada_hedef)
        elif herhangi_bulundu_mu:
            break  # hedef urunlerin alfabetik bolumu bitti

    return tum_satirlar, veri_tarihi


def _fiyat_to_float(deger: str) -> float | None:
    try:
        return float(deger.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def run() -> int:
    """HKS'den hedef urunlerin gunun fiyatlarini cekip HalFiyati tablosuna
    yazar. Ayni gun+urun+cins+tur kaydi zaten varsa tekrar eklemez."""
    init_db()
    db = SessionLocal()

    satirlar, veri_tarihi = fetch_hedef_urun_rows()
    if not satirlar:
        print("HKS'den hedef urun verisi alınamadı (site erişilemedi veya satır bulunamadı).")
        db.close()
        return 0

    eklenen = 0
    for urun_adi, urun_cinsi, urun_turu, ortalama_fiyat, islem_hacmi, _birim_adi in satirlar:
        fiyat = _fiyat_to_float(ortalama_fiyat)
        if fiyat is None:
            continue
        hacim = _fiyat_to_float(islem_hacmi)

        zaten_var = (
            db.query(HalFiyati)
            .filter(
                HalFiyati.tarih == veri_tarihi,
                HalFiyati.urun_adi == urun_adi.strip(),
                HalFiyati.urun_cinsi == urun_cinsi.strip(),
                HalFiyati.urun_turu == urun_turu.strip(),
            )
            .first()
        )
        if zaten_var is not None:
            continue

        db.add(HalFiyati(
            tarih=veri_tarihi,
            urun_adi=urun_adi.strip(),
            urun_cinsi=urun_cinsi.strip(),
            urun_turu=urun_turu.strip(),
            fiyat_kg=fiyat,
            hacim_kg=hacim,
        ))
        eklenen += 1

    db.commit()
    db.close()
    print(f"HKS hal fiyatı (genel): {eklenen} yeni kayıt eklendi (veri tarihi: {veri_tarihi}).")
    return eklenen


if __name__ == "__main__":
    run()
