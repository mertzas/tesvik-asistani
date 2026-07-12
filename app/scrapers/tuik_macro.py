"""
TUIK/TCMB makro-ekonomik gostergeler ve sektor bazli maliyet/reklam
benchmark'lari icin veri kaynagi.

Makro gostergeler (yillik TUFE, TCMB politika faizi) artik TCMB'nin EVDS
Web Servisi'nden (https://evds3.tcmb.gov.tr) canli cekiliyor. EVDS API
2025'te evds2 -> evds3 tasindi; eski "evds2.tcmb.gov.tr/service/evds/..."
adresi artik calismiyor (evds3 anasayfasina yonlendiriyor). Guncel servis:

    Base URL : https://evds3.tcmb.gov.tr/igmevdsms-dis/
    Auth     : HTTP header olarak  {"key": EVDS_API_KEY}  (query param DEGIL)
    Istek    : {base}/series=<KOD>&startDate=DD-MM-YYYY&endDate=DD-MM-YYYY&type=json
               (resmi API '?' kullanmiyor, parametreler '&' ile path'e ekleniyor)

Kullanilan seriler:
    TP.FG.J0            -> TUFE (2003=100) endeks degeri (TUIK kaynakli), aylik
    TP.BISPOLFAIZ.TUR   -> TCMB politika faiz orani (%), aylik

Tarim sektorune ozel, girdi bazinda fiyat endeksleri (TUIK Tarimsal Girdi
Fiyat Endeksi / Tarim-GFE, EVDS uzerinden), aylik, TUFE ile ayni yontemle
(12 aylik degisim) hesaplaniyor:
    TP.TARIMGFE.GK378650488 -> Gubre ve Toprak Gelistiriciler
    TP.TARIMGFE.GK378650491 -> Tarimsal Ilaclar
    TP.TARIMGFE.GK378650497 -> Hayvan Yemi
    TP.TARIMGFE.GK378650505 -> Binalar (sera/ahir gibi yapim/yatirim kalemi)
    TP.TARIMGFE.GK378650500 -> Makine Bakim Masraflari
Bunlar sadece FIYAT ENDEKSI/enflasyon bilgisidir (gubre ne kadar zamlandi
gibi); "hangi gubreyi/ne kadar kullanmali" gibi agronomik bir tavsiye
DEGILDIR - bu, toprak tahlili ve bolgeye gore degisir, TUIK/TCMB'de boyle
bir veri yoktur (bkz. app/budget.py'daki ilgili not).

Sektor bazli stok maliyeti / reklam harcamasi oranlari artik TCMB'nin
"Sektor Bilancolari" veri setinden (NACE bolumlerine gore yillik karlilik
oranlari) turetiliyor:

    TP.SEKBILD02B.<NACE>  -> Brut Satis Kari / Net Satislar Orani (%)
    TP.SEKBILD02E.<NACE>  -> Faaliyet Giderleri / Net Satislar Orani (%)
    TP.SEKBILD02C.<NACE>  -> Net Kar (Zarar) / Net Satislar Orani (%) - "sektorun kar orani"

Bu iki oran gercek, TCMB'ye bildirilen sirket bilancolarindan hesaplaniyor
(yillik, tek nokta - aylik degil). Buradan turetilen degerler:

    stok_maliyeti_orani = 1 - (Brut Satis Kari Orani)
        yani "Satilan Malin/Hizmetin Maliyeti / Net Satislar" orani.
    reklam_orani = (Faaliyet Giderleri Orani) * REKLAM_PAYI_VARSAYIMI
        EVDS'te sektor bazinda ayri bir "reklam harcamasi" serisi YOK;
        faaliyet giderleri kirasi/personeli/reklami vb. hepsini kapsayan
        genis bir kalem. REKLAM_PAYI_VARSAYIMI (bkz. asagida), bu genis
        kalemin ne kadarinin pazarlama/reklama gittigine dair belgelenmis
        bir varsayimdir, olculmus bir deger degildir.

Tek yillik nokta etrafinda bir "aralik" ifade edebilmek icin degerin
%15 alt/ustu bir bant (BANT_ORANI) uygulanir; bu istatistiksel bir
guven araligi degil, sadece UX'teki min/max alanlarini doldurmak icindir.

EVDS'e erisilemezse (anahtar yok, ag hatasi) curated seed'e dusulur
(bkz. YEDEK_SEKTOR_BENCHMARKLARI).

Kaynaklar:
- https://evds3.tcmb.gov.tr/dokumanlar (EVDS Web Servisi kullanim kilavuzu)
"""
import os
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

from app.models import SessionLocal, MacroIndicator, SectorBenchmark, init_db

load_dotenv()

EVDS_BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"

# EVDS seri kodu -> (macro_indicators.anahtar, birim, aciklama)
EVDS_SERILERI = {
    "TP.FG.J0": {"anahtar": "tufe_endeksi", "birim": "endeks", "kaynak": "TUIK/EVDS TP.FG.J0"},
    "TP.BISPOLFAIZ.TUR": {"anahtar": "tcmb_politika_faizi", "birim": "%", "kaynak": "TCMB/EVDS TP.BISPOLFAIZ.TUR"},
}

# Tarim girdi fiyat endeksi seri kodu -> (macro_indicators.anahtar, alan adi, etiket)
TARIM_GIRDI_SERILERI = {
    "TP.TARIMGFE.GK378650488": {"anahtar": "tarim_gubre_yillik_degisim", "alan": "TP_TARIMGFE_GK378650488", "etiket": "Gubre ve Toprak Gelistiriciler"},
    "TP.TARIMGFE.GK378650491": {"anahtar": "tarim_ilac_yillik_degisim", "alan": "TP_TARIMGFE_GK378650491", "etiket": "Tarimsal Ilaclar"},
    "TP.TARIMGFE.GK378650497": {"anahtar": "tarim_yem_yillik_degisim", "alan": "TP_TARIMGFE_GK378650497", "etiket": "Hayvan Yemi"},
    "TP.TARIMGFE.GK378650505": {"anahtar": "tarim_bina_yillik_degisim", "alan": "TP_TARIMGFE_GK378650505", "etiket": "Bina/Sera Yapim-Yatirim"},
    "TP.TARIMGFE.GK378650500": {"anahtar": "tarim_makine_bakim_yillik_degisim", "alan": "TP_TARIMGFE_GK378650500", "etiket": "Makine Bakim"},
}

# Bizim sektor etiketimiz -> TCMB Sektor Bilancolari NACE bolum kodu.
# NACE tek harfli boluma (A, C, G ...) karsilik gelmeyen sektorlerimiz
# (e-ticaret, ihracat, arge) en yakin/temsili NACE bolumune eslendi;
# bu bir yaklastirmadir, ayri bir resmi seri yoktur.
SEKTOR_NACE_ESLEMESI = {
    "tarim": ["A"],               # A - Tarim, Ormancilik ve Balikcilik
    "imalat": ["C"],              # C - Imalat
    "perakende": ["G"],           # G - Toptan ve Perakende Ticaret
    "e-ticaret": ["G"],           # NACE'de ayri kod yok; perakende ile ayni bolum kullanilir
    "hizmet": ["I", "M", "N", "S"],  # Konaklama/Yiyecek, Mesleki-Bilimsel-Teknik, Idari Destek, Diger Hizmetler ortalamasi
    "ihracat": ["C"],             # Turkiye ihracatinin buyuk kismi imalat sanayii kaynakli
    "arge": ["M"],                # M - Mesleki, Bilimsel ve Teknik Faaliyetler (Ar-Ge bu bolumde)
    "genel": ["GENEL"],           # TCMB'nin tum sektorler agirlikli ortalamasi
}

# Faaliyet giderlerinin ne kadarinin reklam/pazarlamaya gittigine dair
# belgelenmis bir varsayim (ölçülmüş bir deger degil) - bkz. modul dokumani.
REKLAM_PAYI_VARSAYIMI = 0.20

# Tek yillik nokta etrafinda min/max alanlarini doldurmak icin uygulanan bant.
BANT_ORANI = 0.15

KAYNAK_ETIKETI_EVDS = "TCMB Sektor Bilancolari/EVDS (TP.SEKBILD02B / TP.SEKBILD02E)"
KAYNAK_ETIKETI_SEED = "TUIK sektor anketi (curated seed, EVDS erisilemedi)"

# EVDS'e erisilemezse kullanilacak eski curated degerler.
YEDEK_SEKTOR_BENCHMARKLARI = [
    {"sektor": "tarim", "stok_min": 0.25, "stok_max": 0.40, "reklam_min": 0.01, "reklam_max": 0.03, "net_kar_orani": None},
    {"sektor": "imalat", "stok_min": 0.20, "stok_max": 0.35, "reklam_min": 0.02, "reklam_max": 0.05, "net_kar_orani": None},
    {"sektor": "perakende", "stok_min": 0.30, "stok_max": 0.45, "reklam_min": 0.03, "reklam_max": 0.07, "net_kar_orani": None},
    {"sektor": "e-ticaret", "stok_min": 0.20, "stok_max": 0.35, "reklam_min": 0.06, "reklam_max": 0.15, "net_kar_orani": None},
    {"sektor": "hizmet", "stok_min": 0.02, "stok_max": 0.08, "reklam_min": 0.03, "reklam_max": 0.08, "net_kar_orani": None},
    {"sektor": "ihracat", "stok_min": 0.20, "stok_max": 0.35, "reklam_min": 0.02, "reklam_max": 0.05, "net_kar_orani": None},
    {"sektor": "arge", "stok_min": 0.05, "stok_max": 0.15, "reklam_min": 0.01, "reklam_max": 0.03, "net_kar_orani": None},
    {"sektor": "genel", "stok_min": 0.15, "stok_max": 0.30, "reklam_min": 0.02, "reklam_max": 0.05, "net_kar_orani": None},
]


def _evds_fetch(series: str, api_key: str, ay_sayisi: int = 26) -> list[dict]:
    """Verilen EVDS serisi icin son `ay_sayisi` aya ait kayitlari ceker.

    Yayin gecikmesi olabilecegi icin (TUFE genelde 1 ay geriden yayinlanir)
    yillik degisim hesaplayabilmek amaciyla 26 aylik genis bir pencere
    cekilir; asil eslestirme tarihe gore yapilir (bkz. _son_iki_deger)."""
    bugun = date.today()
    baslangic = bugun - timedelta(days=30 * ay_sayisi)

    url = (
        f"{EVDS_BASE_URL}/series={series}"
        f"&startDate={baslangic.strftime('%d-%m-%Y')}"
        f"&endDate={bugun.strftime('%d-%m-%Y')}"
        f"&type=json"
    )
    resp = requests.get(url, headers={"key": api_key}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", [])


def _son_iki_deger(items: list[dict], seri_alan_adi: str) -> tuple[float | None, float | None]:
    """En guncel deger ile ayni ayin bir onceki yildaki degerini dondurur.

    Tarih alani EVDS'te "YYYY-A" (ay, bastaki sifirsiz) formatinda gelir;
    eslestirme item sayisina degil bu tarihe gore yapilir, cunku yayin
    gecikmesi yuzunden pencere icindeki kayit sayisi degisebilir."""
    temiz = {
        it["Tarih"]: float(it[seri_alan_adi])
        for it in items
        if it.get(seri_alan_adi) not in (None, "")
    }
    if not temiz:
        return None, None

    son_tarih = max(temiz, key=lambda t: tuple(map(int, t.split("-"))))
    son_deger = temiz[son_tarih]

    yil, ay = map(int, son_tarih.split("-"))
    onceki_yil_tarih = f"{yil - 1}-{ay}"
    onceki_yil_deger = temiz.get(onceki_yil_tarih)

    return son_deger, onceki_yil_deger


def _son_deger_yil_bazinda(items: list[dict], seri_alan_adi: str) -> float | None:
    """Yillik (tek nokta/yil) serilerde en guncel yilin degerini dondurur.

    TP.SEKBILD02B/E gibi Sektor Bilancolari serileri aylik degil yillik
    yayinlanir; Tarih alani burada dogrudan yil (int) olarak gelir."""
    temiz = {
        int(it["Tarih"]): float(it[seri_alan_adi])
        for it in items
        if it.get(seri_alan_adi) not in (None, "")
    }
    if not temiz:
        return None
    return temiz[max(temiz)]


def fetch_sector_benchmarks_from_evds(api_key: str) -> list[dict]:
    """TCMB Sektor Bilancolari'ndan (NACE bazli) gercek maliyet/gider
    oranlarini ceker ve bizim sektor etiketlerimize donusturur."""
    nace_kodlari = sorted({kod for kodlar in SEKTOR_NACE_ESLEMESI.values() for kod in kodlar})

    brut_kar_serisi = "-".join(f"TP.SEKBILD02B.{k}" for k in nace_kodlari)
    faaliyet_gideri_serisi = "-".join(f"TP.SEKBILD02E.{k}" for k in nace_kodlari)
    net_kar_serisi = "-".join(f"TP.SEKBILD02C.{k}" for k in nace_kodlari)

    bugun = date.today()
    baslangic = bugun - timedelta(days=365 * 6)  # yillik veri, birkac yil geriye bak

    def _cek(seri_str: str) -> list[dict]:
        url = (
            f"{EVDS_BASE_URL}/series={seri_str}"
            f"&startDate={baslangic.strftime('%d-%m-%Y')}"
            f"&endDate={bugun.strftime('%d-%m-%Y')}"
            f"&type=json"
        )
        resp = requests.get(url, headers={"key": api_key}, timeout=30)
        resp.raise_for_status()
        return resp.json().get("items", [])

    brut_kar_items = _cek(brut_kar_serisi)
    faaliyet_gideri_items = _cek(faaliyet_gideri_serisi)
    net_kar_items = _cek(net_kar_serisi)

    brut_kar_by_nace: dict[str, float] = {}
    faaliyet_gideri_by_nace: dict[str, float] = {}
    net_kar_by_nace: dict[str, float] = {}
    for kod in nace_kodlari:
        alan_b = f"TP_SEKBILD02B_{kod}"
        alan_e = f"TP_SEKBILD02E_{kod}"
        alan_c = f"TP_SEKBILD02C_{kod}"
        v_b = _son_deger_yil_bazinda(brut_kar_items, alan_b)
        v_e = _son_deger_yil_bazinda(faaliyet_gideri_items, alan_e)
        v_c = _son_deger_yil_bazinda(net_kar_items, alan_c)
        if v_b is not None:
            brut_kar_by_nace[kod] = v_b
        if v_e is not None:
            faaliyet_gideri_by_nace[kod] = v_e
        if v_c is not None:
            net_kar_by_nace[kod] = v_c

    sonuclar = []
    for sektor, nace_kodlari_sektor in SEKTOR_NACE_ESLEMESI.items():
        brut_kar_degerleri = [brut_kar_by_nace[k] for k in nace_kodlari_sektor if k in brut_kar_by_nace]
        faaliyet_gideri_degerleri = [faaliyet_gideri_by_nace[k] for k in nace_kodlari_sektor if k in faaliyet_gideri_by_nace]
        net_kar_degerleri = [net_kar_by_nace[k] for k in nace_kodlari_sektor if k in net_kar_by_nace]

        if not brut_kar_degerleri or not faaliyet_gideri_degerleri:
            continue  # bu sektor icin veri gelmediyse, run() seed'e dusecek

        ortalama_brut_kar = sum(brut_kar_degerleri) / len(brut_kar_degerleri)
        ortalama_faaliyet_gideri = sum(faaliyet_gideri_degerleri) / len(faaliyet_gideri_degerleri)
        ortalama_net_kar = sum(net_kar_degerleri) / len(net_kar_degerleri) if net_kar_degerleri else None

        stok_orani = (100 - ortalama_brut_kar) / 100
        reklam_orani = (ortalama_faaliyet_gideri / 100) * REKLAM_PAYI_VARSAYIMI

        sonuclar.append({
            "sektor": sektor,
            "stok_min": round(stok_orani * (1 - BANT_ORANI), 4),
            "stok_max": round(stok_orani * (1 + BANT_ORANI), 4),
            "reklam_min": round(reklam_orani * (1 - BANT_ORANI), 4),
            "reklam_max": round(reklam_orani * (1 + BANT_ORANI), 4),
            "net_kar_orani": round(ortalama_net_kar / 100, 4) if ortalama_net_kar is not None else None,
        })

    return sonuclar


def fetch_macro_from_evds(api_key: str) -> dict[str, dict]:
    """EVDS'ten yillik TUFE degisimini ve guncel politika faizini ceker."""
    sonuclar: dict[str, dict] = {}

    tufe_items = _evds_fetch("TP.FG.J0", api_key)
    son_tufe, yil_once_tufe = _son_iki_deger(tufe_items, "TP_FG_J0")
    if son_tufe is not None and yil_once_tufe:
        yillik_degisim = (son_tufe / yil_once_tufe - 1) * 100
        sonuclar["yillik_tufe"] = {
            "deger": round(yillik_degisim, 2),
            "birim": "%",
            "kaynak": "TUIK/EVDS TP.FG.J0 (12 aylik degisim)",
        }

    faiz_items = _evds_fetch("TP.BISPOLFAIZ.TUR", api_key)
    son_faiz, _ = _son_iki_deger(faiz_items, "TP_BISPOLFAIZ_TUR")
    if son_faiz is not None:
        sonuclar["tcmb_politika_faizi"] = {
            "deger": son_faiz,
            "birim": "%",
            "kaynak": "TCMB/EVDS TP.BISPOLFAIZ.TUR",
        }

    for seri_kodu, bilgi in TARIM_GIRDI_SERILERI.items():
        items = _evds_fetch(seri_kodu, api_key)
        son_deger, yil_once_deger = _son_iki_deger(items, bilgi["alan"])
        if son_deger is not None and yil_once_deger:
            yillik_degisim = (son_deger / yil_once_deger - 1) * 100
            sonuclar[bilgi["anahtar"]] = {
                "deger": round(yillik_degisim, 2),
                "birim": "%",
                "kaynak": f"TUIK/EVDS Tarim-GFE {bilgi['etiket']} (12 aylik degisim)",
            }

    ihracat_items = _evds_fetch("TP.IHRISICREV4.01", api_key)
    son_ihracat, _ = _son_iki_deger(ihracat_items, "TP_IHRISICREV4_01")
    if son_ihracat is not None:
        sonuclar["tarim_aylik_ihracat_milyon_usd"] = {
            "deger": round(son_ihracat / 1000, 1),  # bin USD -> milyon USD
            "birim": "milyon USD",
            "kaynak": "TUIK/EVDS TP.IHRISICREV4.01 (Tarim, Ormancilik ve Balikcilik - aylik ihracat)",
        }

    ithalat_items = _evds_fetch("TP.ITHISICREV4.01", api_key)
    son_ithalat, _ = _son_iki_deger(ithalat_items, "TP_ITHISICREV4_01")
    if son_ithalat is not None:
        sonuclar["tarim_aylik_ithalat_milyon_usd"] = {
            "deger": round(son_ithalat / 1000, 1),
            "birim": "milyon USD",
            "kaynak": "TUIK/EVDS TP.ITHISICREV4.01 (Tarim, Ormancilik ve Balikcilik - aylik ithalat)",
        }

    return sonuclar


# EVDS baglantisi kurulamazsa (anahtar yok, ag hatasi vb.) kullanilacak
# curated seed degerler; canli veri ile guncellenene kadar makul bir varsayilan
# sunar.
YEDEK_MACRO_GOSTERGELERI = {
    "yillik_tufe": {"deger": 38.5, "birim": "%", "kaynak": "TUIK TUFE (curated seed, EVDS erisilemedi)"},
    "tcmb_politika_faizi": {"deger": 40.0, "birim": "%", "kaynak": "TCMB (curated seed, EVDS erisilemedi)"},
}


def run():
    init_db()
    db = SessionLocal()
    try:
        guncellenen = 0

        api_key = os.getenv("EVDS_API_KEY", "").strip()
        gostergeler = None
        if api_key:
            try:
                gostergeler = fetch_macro_from_evds(api_key)
            except (requests.RequestException, ValueError, KeyError) as e:
                print(f"EVDS'ten veri cekilemedi, seed degerlere donuluyor: {e}")

        if not gostergeler:
            gostergeler = YEDEK_MACRO_GOSTERGELERI

        for anahtar, gosterge in gostergeler.items():
            row = db.query(MacroIndicator).filter(MacroIndicator.anahtar == anahtar).first()
            if row is None:
                row = MacroIndicator(anahtar=anahtar)
                db.add(row)
            row.deger = gosterge["deger"]
            row.birim = gosterge["birim"]
            row.kaynak = gosterge["kaynak"]
            guncellenen += 1

        sektor_benchmarklari = None
        sektor_kaynagi = KAYNAK_ETIKETI_EVDS
        if api_key:
            try:
                sektor_benchmarklari = fetch_sector_benchmarks_from_evds(api_key)
            except (requests.RequestException, ValueError, KeyError) as e:
                print(f"EVDS'ten sektor benchmark verisi cekilemedi, seed'e donuluyor: {e}")

        if not sektor_benchmarklari:
            sektor_benchmarklari = YEDEK_SEKTOR_BENCHMARKLARI
            sektor_kaynagi = KAYNAK_ETIKETI_SEED

        bulunan_sektorler = {b["sektor"] for b in sektor_benchmarklari}
        for yedek in YEDEK_SEKTOR_BENCHMARKLARI:
            if yedek["sektor"] not in bulunan_sektorler:
                sektor_benchmarklari.append(yedek)  # EVDS'ten veri gelmeyen sektor icin seed'e dus

        for b in sektor_benchmarklari:
            row = db.query(SectorBenchmark).filter(SectorBenchmark.sektor == b["sektor"]).first()
            if row is None:
                row = SectorBenchmark(sektor=b["sektor"])
                db.add(row)
            row.stok_maliyeti_oran_min = b["stok_min"]
            row.stok_maliyeti_oran_max = b["stok_max"]
            row.reklam_oran_min = b["reklam_min"]
            row.reklam_oran_max = b["reklam_max"]
            row.net_kar_orani = b.get("net_kar_orani")
            row.kaynak = sektor_kaynagi if b["sektor"] in bulunan_sektorler else KAYNAK_ETIKETI_SEED
            guncellenen += 1

        db.commit()
    finally:
        db.close()

    print(f"{guncellenen} makro gosterge/benchmark kaydi guncellendi.")


if __name__ == "__main__":
    run()
