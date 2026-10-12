"""Bağımsız uzman değerlendirmesi turlarını karşılaştırır (degerlendirme_*.json = tur 1, degerlendirme2_*.json = tur 2,
degerlendirme3_*.json = tur 3 ...). Çıktı: karsilastirma.md (ortalama puanlar, ciddiyete göre bulgu sayısı,
senaryo bazında toplam puan farkı).

    python docs/olcum/2026-10-11-yerel-danisman/karsilastir.py
    python docs/olcum/2026-10-11-yerel-danisman/karsilastir.py --self-test
"""
import glob
import json
import os
import re
import sys
from collections import Counter

OUT = os.path.dirname(os.path.abspath(__file__))
ALAN = ["dogruluk", "soruya_odak", "eksiksizlik", "anlasilirlik"]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def turlar() -> dict[int, list[dict]]:
    sonuc: dict[int, list[dict]] = {}
    for yol in sorted(glob.glob(os.path.join(OUT, "degerlendirme*_*.json"))):
        m = re.search(r"degerlendirme(\d*)_[A-Z]\.json$", yol)
        if not m:
            continue
        sonuc.setdefault(int(m.group(1) or 1), []).extend(json.load(open(yol, encoding="utf-8")))
    return sonuc


def ozet(kayitlar: list[dict]) -> dict:
    n = len(kayitlar)
    ort = {a: round(sum(k["puan"][a] for k in kayitlar) / n, 2) for a in ALAN}
    cid = Counter(b["ciddiyet"] for k in kayitlar for b in k["bulgular"] if not b.get("kaynak_disi"))
    return {"n": n, "ortalama": ort, "genel": round(sum(ort.values()) / len(ALAN), 2), "ciddiyet": dict(cid),
            "toplam": {k["n"]: sum(k["puan"][a] for a in ALAN) for k in kayitlar}}


def rapor() -> str:
    t = {no: ozet(k) for no, k in sorted(turlar().items())}
    sat = ["| Tur | Senaryo | Doğruluk | Soruya odak | Eksiksizlik | Anlaşılırlık | Genel | Kritik | Orta | Düşük |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for no, o in t.items():
        sat.append(f"| {no} | {o['n']} | " + " | ".join(str(o["ortalama"][a]) for a in ALAN)
                   + f" | **{o['genel']}** | {o['ciddiyet'].get('kritik', 0)} | {o['ciddiyet'].get('orta', 0)} | "
                     f"{o['ciddiyet'].get('dusuk', 0)} |")
    if len(t) >= 2:
        ilk, son = t[min(t)], t[max(t)]
        sat += ["", f"Senaryo bazında toplam puan (4-20), tur {min(t)} → tur {max(t)}:", ""]
        for n in sorted(set(ilk["toplam"]) & set(son["toplam"])):
            fark = son["toplam"][n] - ilk["toplam"][n]
            sat.append(f"- {n:02}: {ilk['toplam'][n]} → {son['toplam'][n]} ({'+' if fark >= 0 else ''}{fark})")
    metin = "\n".join(sat) + "\n\n(Kritik/orta/düşük: değerlendiricinin kaynak dışı işaretlediği bulgular hariç.)\n"
    open(os.path.join(OUT, "karsilastirma.md"), "w", encoding="utf-8").write(metin)
    return metin


def _self_test() -> int:
    ornek = [{"n": 1, "puan": dict.fromkeys(ALAN, 4), "bulgular": [{"ciddiyet": "kritik"}, {"ciddiyet": "orta",
                                                                                          "kaynak_disi": True}]},
             {"n": 2, "puan": dict.fromkeys(ALAN, 2), "bulgular": []}]
    o = ozet(ornek)
    k = [("ortalama", o["ortalama"]["dogruluk"] == 3.0 and o["genel"] == 3.0),
         ("kaynak dışı bulgu sayılmaz", o["ciddiyet"] == {"kritik": 1}),
         ("senaryo toplamı", o["toplam"] == {1: 16, 2: 8})]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.exit(_self_test() if "--self-test" in sys.argv else (print(rapor()) or 0))
