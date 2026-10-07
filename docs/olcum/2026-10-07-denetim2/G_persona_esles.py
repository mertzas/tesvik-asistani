"""Denetim 2 / Aşama G — eşleştirme ve arama düzeltmeleri için önce/sonra karşılaştırması (ücretsiz, LLM yok, DB'ye yazmaz).

  python G_persona_esles.py once     -> G_once.json
  python G_persona_esles.py sonra    -> G_sonra.json + G_fark.md (once ile karşılaştırma)

Personalar: Aşama 3'ün 10 personası + 2026-10-07 tarayıcı denemesindeki iki sentetik profil.
Her persona için: eşleşme ilk 12 (id, skor, başlık, hedef eşleşti mi) ve elenmesi gereken programların sırası.
Arama: soru başına retrieve ilk 8.
"""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))

from app import rag  # noqa: E402
from app.matching import HEDEF_GEREKCE_ONEKI, esles  # noqa: E402
from app.models import FinancialProfile, SessionLocal  # noqa: E402

A3 = os.path.join(HERE, "..", "2026-10-07-asama3")
# asama3_olcum.py modül düzeyinde DB'ye bağlanıp sorgu çalıştırdığı için import edilmez; PERSONA sözlüğü metinden okunur.
_metin = open(os.path.join(A3, "asama3_olcum.py"), encoding="utf-8").read()
_bas = _metin.index("PERSONA = {")
_son = _metin.index("\n}\n", _bas) + 2
exec(_metin[_bas:_son], {}, _yer := {})
PERSONA = dict(_yer["PERSONA"])
PERSONA["11 Konya bugday sentetik"] = dict(
    sektor="tarim", bolge="Konya", calisan_sayisi=3, yillik_ciro=2.4e6, arazi_buyuklugu_dekar=220, urun_turu="buğday, arpa",
    tarim_kategori="tahil_baklagil", nace_kodu="01.11", sirket_turu="sahis", kurulus_tarihi=date(2014, 3, 1), hedefler=["makine", "hayvan"])
PERSONA["12 Bursa metal sentetik"] = dict(
    sektor="imalat", bolge="Bursa", calisan_sayisi=18, yillik_ciro=32e6, nace_kodu="25.62", sirket_turu="limited",
    kurulus_tarihi=date(2011, 6, 15), hedefler=["yatirim", "ihracat"])

# Elenmesi beklenenler (başlık parçası): profil bu programa uygun değil
ELENMELI = {
    "11 Konya bugday sentetik": ["1501", "Girişimci Destek Programı", "Meyve-Sebze", "Organik", "Sera"],
    "1 Konya ciftci": ["1501", "Girişimci Destek Programı"],
    "8 Hatay mikro": ["1501", "1507"],
    "10 Hatay NACEsiz hizmet": ["1501", "1507"],
    "12 Bursa metal sentetik": ["Girişimci Destek Programı"],
    "2 Izmir tekstil": ["Girişimci Destek Programı"],
    "7 Bursa buyuk imalat": ["Girişimci Destek Programı"],
}
# Üst sıralarda olması beklenenler (başlık parçası, en kötü kabul edilebilir sıra)
UST = {
    "12 Bursa metal sentetik": [("Kapasite Geliştirme", 6), ("Hedef Yatırımlar", 3)],
    "2 Izmir tekstil": [("Hedef Yatırımlar", 3)],
    "11 Konya bugday sentetik": [("Hububat", 2)],
}
SORULAR = [
    ("12 Bursa metal sentetik", "5 eksenli CNC tezgahı almak istiyoruz, yaklaşık 18 milyon TL, hangi destek ve krediler var?"),
    ("9 Ekmek 10.71 Konya", "Yeni ekmek üretim hattı için makine alacağım; yatırım teşvik belgesi alabilir miyim?"),
    ("1 Konya ciftci", "Traktör ve mibzer almak istiyorum, hibe var mı?"),
    ("2 Izmir tekstil", "Almanya'ya ihracata başlayacağız, hangi destekler var?"),
    ("8 Hatay mikro", "3 kişi daha işe alacağım, SGK desteği var mı?"),
    ("10 Hatay NACEsiz hizmet", "İşletme sermayesi için uygun faizli kredi veya kefalet desteği arıyorum."),
]


def calistir():
    db = SessionLocal()
    sonuc = {"esles": {}, "arama": []}
    for ad, alanlar in PERSONA.items():
        p = FinancialProfile(**alanlar)
        es = esles(p, db)
        sonuc["esles"][ad] = [
            dict(sira=i + 1, id=e.tesvik.id, skor=round(e.skor, 3), baslik=e.tesvik.baslik[:70],
                 hedef=any(g.startswith(HEDEF_GEREKCE_ONEKI) for g in (e.gerekce or [])),
                 tahmini=getattr(e, "tahmini_tutar", None))
            for i, e in enumerate(es)]
    for ad, soru in SORULAR:
        p = FinancialProfile(**PERSONA[ad])
        ids = rag.retrieve(soru, limit=8, profil_kaydi=p)
        sonuc["arama"].append(dict(persona=ad, soru=soru, ilk8=[f"{t.id} {t.kurum} | {t.baslik[:55]}" for t in ids]))
    db.close()
    return sonuc


def _sira(liste, parca):
    for s in liste:
        if parca.lower() in s["baslik"].lower():
            return s["sira"]
    return None


def fark(once, sonra):
    satir = ["# Aşama G — önce / sonra (eşleştirme + arama)\n"]
    satir.append("## Hedef eşleşmesi alan kart sayısı (ilk 12)\n\n| Persona | Önce | Sonra |\n|---|---|---|")
    for ad in sonra["esles"]:
        o = sum(1 for s in once["esles"].get(ad, [])[:12] if s["hedef"])
        n = sum(1 for s in sonra["esles"][ad][:12] if s["hedef"])
        satir.append(f"| {ad} | {o} | {n} |")
    satir.append("\n## Elenmesi gerekenler (sıra; '-' = listede yok)\n\n| Persona | Program | Önce | Sonra |\n|---|---|---|---|")
    for ad, parcalar in ELENMELI.items():
        for parca in parcalar:
            satir.append(f"| {ad} | {parca} | {_sira(once['esles'].get(ad, []), parca) or '-'} | {_sira(sonra['esles'][ad], parca) or '-'} |")
    satir.append("\n## Üstte olması gerekenler (sıra / hedef)\n\n| Persona | Program | Hedef ≤ | Önce | Sonra |\n|---|---|---|---|---|")
    for ad, beklenen in UST.items():
        for parca, esik in beklenen:
            satir.append(f"| {ad} | {parca} | {esik} | {_sira(once['esles'].get(ad, []), parca) or '-'} | {_sira(sonra['esles'][ad], parca) or '-'} |")
    satir.append("\n## İlk 5 (önce → sonra)\n")
    for ad in sonra["esles"]:
        o = [f"{s['id']}" for s in once["esles"].get(ad, [])[:5]]
        n = [f"{s['id']}" for s in sonra["esles"][ad][:5]]
        satir.append(f"- **{ad}:** {', '.join(o)} → {', '.join(n)}")
    satir.append("\n## Arama ilk 8 (sonra)\n")
    for a_once, a in zip(once["arama"], sonra["arama"]):
        satir.append(f"**{a['persona']}** — {a['soru']}\n")
        satir.append("| Önce | Sonra |\n|---|---|")
        for x, y in zip(a_once["ilk8"] + [""] * 8, a["ilk8"] + [""] * 8):
            if x or y:
                satir.append(f"| {x} | {y} |")
        satir.append("")
    return "\n".join(satir)


if __name__ == "__main__":
    mod = sys.argv[1] if len(sys.argv) > 1 else "once"
    s = calistir()
    json.dump(s, open(os.path.join(HERE, f"G_{mod}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if mod == "sonra":
        once = json.load(open(os.path.join(HERE, "G_once.json"), encoding="utf-8"))
        open(os.path.join(HERE, "G_fark.md"), "w", encoding="utf-8").write(fark(once, s))
        print(open(os.path.join(HERE, "G_fark.md"), encoding="utf-8").read())
    else:
        for ad, liste in s["esles"].items():
            print(ad, "|", ", ".join(f"{x['sira']}:{x['id']}{'*' if x['hedef'] else ''}" for x in liste[:10]))
