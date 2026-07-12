"""
T.C. Ticaret Bakanligi Hal Kayit Sistemi (HKS) - gunluk cilek fiyat bulteni.

https://www.hal.gov.tr/Sayfalar/FiyatDetaylari.aspx sayfasi urunleri
alfabetik olarak ~10 sayfaya bolunmus bir ASP.NET GridView (SharePoint
web part) uzerinden gosterir. Sayfalama __doPostBack ile calisir; bu
modul gercek bir tarayici gibi once sayfayi GET edip __VIEWSTATE /
__EVENTVALIDATION degerlerini okuyor, sonra Page$N postback'lerini
sirayla tekrar oynatarak "ÇİLEK" satirlarina ulasiyor.

Not: Bu projede daha once (bkz. app/tmo_fiyatlar.py docstring) bu sitenin
otomatik scraping'e karsi WAF ile korundugu belgelenmisti; bu yalnizca
Excel-disa-aktarma postback'i icin gecerli gibi gorunuyor - sayfa
navigasyonu (Page$N) duz bir requests.Session ile calisiyor (dogrulandi,
2026-07-10). Yine de site tarafi degisirse fetch_all_cilek_rows() bos
liste dondurur, run() hicbir exception firlatmadan "0 kayit" ile biter.

Cikti PazarFiyati tablosuna yazilir (kaynak=HAL). HKS'nin "Urun Turu"
ekseni (Geleneksel/Iyi Tarim/Organik Tarim - yetistirme sertifikasyonu)
bizim KaliteSinifi eksenimizle (sofralik/sanayilik - perakende kalite
sinifi) birebir ortusmuyor; asagidaki KALITE_ESLEME ile en yakin karsiliga
eslenir. HKS bu veride sanayilik/recellik ayrimi yayinlamiyor, o yuzden
KaliteSinifi.SANAYILIK_RECELLIK bu kaynaktan hic doldurulmaz.
"""
import re
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup

from app.models import SessionLocal, init_db
from app.models_cilek import PazarFiyati, PazarKaynagi, KaliteSinifi

BASE_URL = "https://www.hal.gov.tr/Sayfalar/FiyatDetaylari.aspx"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
GRIDVIEW_EVENTTARGET = "ctl00$ctl37$g_7e86b8d6_3aea_47cf_b1c1_939799a091e0$gvFiyatlar"
MAX_SAYFA = 15
ISTEK_TIMEOUT_SANIYE = 20
BEKLENEN_URUN_ADI = "ÇİLEK"

# NOT: Turkce "I/İ/ı/i" harfleri Python'un varsayilan .lower()/.upper()
# fonksiyonlarinda locale-farkindaliksiz calisir (ornegin "İyi".lower()
# "iyi" degil "i̇yi" - noktali bileşik karakter - verir). Bu yuzden burada
# case-fold YAPMADAN, siteden gelen TAM literal metinlerle eslestiriyoruz.
KALITE_ESLEME = {
    "Geleneksel(Konvansiyonel)": KaliteSinifi.SOFRALIK_STANDART,
    "İyi Tarım": KaliteSinifi.SOFRALIK_PREMIUM,
    "Organik Tarım": KaliteSinifi.SOFRALIK_PREMIUM,
}


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
        # Baslik satiri ve sayfalama satiri da <td> icerir; gercek veri
        # satirlari her zaman 6 sutunludur (Urun Adi..Birim Adi).
        if len(hucreler) == 6:
            satirlar.append(hucreler)
    return satirlar


def _bulten_veri_tarihi(html: str) -> date:
    """'Bülten Tarihi : DD.MM.YYYY (DD.MM.YYYY Tarihli Veriler Kullanılmıştır.)' -
    parantez icindeki tarih gercek islem tarihidir, ilki sadece sorgu/yayin tarihidir."""
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


def fetch_all_cilek_rows() -> tuple[list[list[str]], date]:
    """
    Tum sayfalari sirayla dolasip 'ÇİLEK' satirlarini toplar. Urunler
    alfabetik siralandigi icin, en az bir ÇİLEK satiri bulunduktan SONRA
    bir sayfada hic ÇİLEK satiri kalmazsa taramayi durdurur (Ç bolumunu
    gectik demektir) - gereksiz yere tum ~10 sayfayi taramaya gerek kalmaz.

    Ag hatasi / site yapisi degisikligi durumunda BOS LISTE doner, exception
    firlatmaz - cagiran taraf (run()) bunu "bugun veri alinamadi" olarak ele alir.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        yanit = session.get(BASE_URL, timeout=ISTEK_TIMEOUT_SANIYE)
        yanit.raise_for_status()
        yanit.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"HKS sayfasina erisilemedi: {e}")
        return [], date.today()

    veri_tarihi = _bulten_veri_tarihi(yanit.text)
    soup = BeautifulSoup(yanit.text, "html.parser")

    tum_cilek_satirlari: list[list[str]] = []
    cilek_bulundu_mu = False

    for sayfa_no in range(1, MAX_SAYFA + 1):
        if sayfa_no > 1:
            try:
                soup = _sonraki_sayfa(session, soup, sayfa_no)
            except requests.RequestException as e:
                print(f"HKS sayfa {sayfa_no} alinamadi: {e}")
                break

        satirlar = _tablo_satirlari(soup)
        if not satirlar:
            break  # son sayfayi gectik

        bu_sayfada_cilek = [s for s in satirlar if s[0].strip() == BEKLENEN_URUN_ADI]
        if bu_sayfada_cilek:
            cilek_bulundu_mu = True
            tum_cilek_satirlari.extend(bu_sayfada_cilek)
        elif cilek_bulundu_mu:
            break  # ÇİLEK bolumu bitti, alfabetik olarak sonraki harfe gecildi

    return tum_cilek_satirlari, veri_tarihi


def _fiyat_to_float(deger: str) -> float | None:
    try:
        return float(deger.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def run() -> int:
    """HKS'den gunun cilek fiyatlarini cekip PazarFiyati tablosuna yazar.
    Ayni gun icin ayni kayit zaten varsa tekrar eklemez (idempotent)."""
    init_db()
    db = SessionLocal()

    satirlar, veri_tarihi = fetch_all_cilek_rows()
    if not satirlar:
        print("HKS'den çilek verisi alınamadı (site erişilemedi veya çilek satırı bulunamadı).")
        db.close()
        return 0

    # HKS'nin "İyi Tarım" ve "Organik Tarım" kategorileri ikisi de bizim
    # SOFRALIK_PREMIUM sinifimiza eslenir (bkz. KALITE_ESLEME). Bu iki
    # kategori CAKISTIGINDA (ayni gun, ayni kalite_sinifi), hacmi (islem
    # hacmi) daha buyuk olani tercih ederiz: "Organik Tarım" cogu zaman
    # sadece birkac kg gibi ihmal edilebilir hacimde satilir ve fiyati
    # (orn. 400 TL/kg) istatistiksel bir aykiri deger olabilir - bu,
    # ciftcinin finansal_saglik_hesapla projeksiyonunu ciddi sekilde
    # carpitabilir. Once her hedef kalite_sinifi icin en yuksek hacimli
    # satiri seciyoruz, sonra veritabanina yaziyoruz.
    en_iyi_satir_kalite_bazinda: dict[KaliteSinifi, tuple] = {}
    for urun_adi, urun_cinsi, urun_turu, ortalama_fiyat, islem_hacmi, birim_adi in satirlar:
        kalite = KALITE_ESLEME.get(urun_turu.strip())
        if kalite is None:
            print(f"Bilinmeyen ürün türü, atlanıyor: {urun_turu}")
            continue

        fiyat = _fiyat_to_float(ortalama_fiyat)
        if fiyat is None:
            continue
        hacim = _fiyat_to_float(islem_hacmi) or 0.0

        mevcut = en_iyi_satir_kalite_bazinda.get(kalite)
        if mevcut is None or hacim > mevcut[1]:
            en_iyi_satir_kalite_bazinda[kalite] = (fiyat, hacim, urun_turu)

    eklenen = 0
    for kalite, (fiyat, hacim, urun_turu) in en_iyi_satir_kalite_bazinda.items():
        zaten_var = (
            db.query(PazarFiyati)
            .filter(
                PazarFiyati.tarih == veri_tarihi,
                PazarFiyati.kaynak == PazarKaynagi.HAL,
                PazarFiyati.kalite_sinifi == kalite,
            )
            .first()
        )
        if zaten_var is not None:
            continue

        db.add(PazarFiyati(
            tarih=veri_tarihi,
            kaynak=PazarKaynagi.HAL,
            kalite_sinifi=kalite,
            bolge=f"Ulusal Ortalama (T.C. Ticaret Bakanlığı HKS - tüm haller, {urun_turu})",
            fiyat_kg=fiyat,
            hacim_kg=hacim,
        ))
        eklenen += 1

    db.commit()
    db.close()
    print(f"HKS çilek fiyatı: {eklenen} yeni kayıt eklendi (veri tarihi: {veri_tarihi}).")
    return eklenen


if __name__ == "__main__":
    run()
