"""Sunum test hesaplarının arayüzde gördüğü verinin özeti (API'den; slayt notları için, 2026-10-12).

    python docs/olcum/2026-10-12-sunum/veri_dokumu.py --self-test
    python docs/olcum/2026-10-12-sunum/veri_dokumu.py          → data/sunum_ekran/veri.json
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parents[3]
URL = "http://127.0.0.1:8000"
HESAPLAR = KOK / "data/sunum_test_hesaplari.json"
CIKTI = KOK / "data/sunum_ekran/veri.json"


def istek(yol, govde=None, belirtec=""):
    b = {"Content-Type": "application/json"}
    if belirtec:
        b["Authorization"] = f"Bearer {belirtec}"
    r = urllib.request.Request(f"{URL}{yol}", data=json.dumps(govde).encode() if govde else None, headers=b,
                               method="POST" if govde else "GET")
    for _ in range(10):
        try:
            with urllib.request.urlopen(r) as y:
                return json.loads(y.read())
        except urllib.error.HTTPError as h:
            if h.code != 429:
                raise
            time.sleep(int(h.headers.get("Retry-After") or 15) + 1)   # IP hız sınırı: bekle, yeniden dene
    raise RuntimeError(f"hız sınırı aşılamadı: {yol}")


def kisalt(d: dict) -> dict:
    """Slayt için gereken alanlar: ilk 5 eşleşme, hazırlık adımları, açılan kontrol listesi, özet kartları."""
    e = d["eslesme"]
    sonuc = e.get("sonuclar") or e.get("eslesmeler") or []
    return {
        "eslesme_sayisi": e.get("toplam") or len(sonuc),
        "ilk5": [{"baslik": (s.get("tesvik") or s).get("baslik"), "kurum": (s.get("tesvik") or s).get("kurum"),
                  "skor": s.get("skor")} for s in sonuc[:5]],
        "hazirlik": [{"baslik": a.get("baslik"), "durum": a.get("durum")}
                     for a in (d["hazirlik"].get("adimlar") or [])][:6],
        "eihracat": d["hazirlik"].get("hazirlik", {}).get("sonuc") if isinstance(d["hazirlik"].get("hazirlik"), dict)
        else None,
        "basvurular": [{"baslik": b.get("baslik"), "ilerleme": b.get("ilerleme") or b.get("hazirlik")}
                       for b in (d["ozet"].get("basvurular") or [])],
        "ozet_anahtarlar": sorted(d["ozet"].keys()),
    }


def _self_test() -> int:
    ornek = {"eslesme": {"sonuclar": [{"tesvik": {"baslik": "A", "kurum": "K"}, "skor": 0.7}], "toplam": 1},
             "hazirlik": {"adimlar": [{"baslik": "ÇKS", "durum": "hazirlik"}]},
             "ozet": {"basvurular": [{"baslik": "A", "ilerleme": "1/6"}]}}
    k = kisalt(ornek)
    testler = [("ilk eşleşme", k["ilk5"][0] == {"baslik": "A", "kurum": "K", "skor": 0.7}),
               ("hazırlık adımı", k["hazirlik"][0]["baslik"] == "ÇKS"),
               ("başvuru", k["basvurular"][0]["ilerleme"] == "1/6")]
    for ad, ok in testler:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in testler)
    print(f"\nself-test: {g}/{len(testler)} geçti")
    return 0 if g == len(testler) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    tum = {}
    for eposta, parola in json.loads(HESAPLAR.read_text(encoding="utf-8")).items():
        t = istek("/api/auth/login", {"email": eposta, "password": parola})["access_token"]
        ham = {"eslesme": istek("/api/eslesme", belirtec=t), "hazirlik": istek("/api/hazirlik", belirtec=t),
               "ozet": istek("/api/ozet", belirtec=t), "liste": istek("/api/basvuru-listesi", belirtec=t)}
        tum[eposta] = {"ozet_kisa": kisalt(ham), "ham": ham}
    CIKTI.write_text(json.dumps(tum, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"{len(tum)} hesap → {CIKTI}")
