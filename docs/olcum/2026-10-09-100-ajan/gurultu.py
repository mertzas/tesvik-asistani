"""İlk 10 öneride ilgisiz/şüpheli öneri ölçümü (eşleştirme kodundan bağımsız danışman kuralları), 2026-10-09.

Kurallar (her biri bir öneriyi bu PROFİL için ilgisiz sayar; uygunluk değil, ilgi değerlendirmesi):
  N1 Yapay Zekâ Kredi (2): profil sektörü/hedefi Ar-Ge değil ve NACE yazılım/Ar-Ge (62, 63, 72) değil.
  N2 SGK istihdam teşvikleri (185, 186): hedeflerde istihdam yok.
  N3 KOSGEB YÖNDE (5): tarım profili (birincil üretim).
  N4 TÜBİTAK sanayi Ar-Ge (34, 44, 75, 152): hedef/sektör Ar-Ge değil ve sektör imalat değil.
  N5 9903 Stratejik Hamle (179) / Öncelikli (181) / Teknoloji Hamlesi (177): mikro ya da küçük ölçek.
Şüpheli (raporlanır, puanlanmaz): S1 Organik (77) organik beyanı yokken; S2 statü/USD şartlı 195/196 USD bilinmezken.

    python docs/olcum/2026-10-09-100-ajan/gurultu.py   (sonuc.json'u okur; önce simulasyon.py)
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(DIZIN.parents[2]))
from app.kobi import kobi_sinifi  # noqa: E402


def ilgisiz(tid: int, p: dict) -> str | None:
    hedef = set(p.get("hedefler") or [])
    arge = p["sektor"] == "arge" or "arge" in hedef or str(p.get("nace_kodu", "")).split(".")[0] in ("62", "63", "72")
    olcek = kobi_sinifi(p.get("calisan_sayisi"), p.get("yillik_ciro")).sinif
    if tid == 2 and not arge:
        return "N1 Yapay Zekâ Kredi"
    if tid in (185, 186) and "istihdam" not in hedef:
        return "N2 SGK istihdam teşviki"
    if tid == 5 and p["sektor"] == "tarim":
        return "N3 YÖNDE tarıma"
    if tid in (34, 44, 75, 152) and not arge and p["sektor"] != "imalat":
        return "N4 Ar-Ge programı"
    if tid in (177, 179, 181) and olcek in ("mikro", "kucuk"):
        return "N5 büyük ölçekli 9903"
    return None


def olc(dosya: str = "sonuc.json") -> dict:
    r = json.loads((DIZIN / dosya).read_text(encoding="utf-8"))
    sayi, kural, ark = Counter(), Counter(), defaultdict(list)
    for a in r:
        ids = [int(x.split()[0]) for x in a["ilk10"]]
        n = [ilgisiz(i, a["profil"]) for i in ids]
        n = [x for x in n if x]
        kural.update(n)
        ark[a["arketip"]].append(len(n) / max(len(ids), 1))
        sayi["oneri"] += len(ids)
        sayi["ilgisiz"] += len(n)
        sayi["ajan_temiz"] += not n
    return {"oneri": sayi["oneri"], "ilgisiz": sayi["ilgisiz"], "oran": sayi["ilgisiz"] / sayi["oneri"],
            "temiz_ajan": sayi["ajan_temiz"], "kural": dict(kural.most_common()),
            "arketip": {k: round(100 * sum(v) / len(v)) for k, v in ark.items()}}


if __name__ == "__main__":
    d = olc(sys.argv[1] if len(sys.argv) > 1 else "sonuc.json")
    print(f"İlk 10'larda ilgisiz öneri: {d['ilgisiz']}/{d['oneri']} (%{100 * d['oran']:.1f}); hiç ilgisiz önerisi olmayan ajan: {d['temiz_ajan']}/100")
    print("Kural başına:", d["kural"])
    print("Arketip başına ilgisiz oranı (%):")
    for k, v in sorted(d["arketip"].items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
