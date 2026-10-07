"""Denetim 2 / Aşama H — tur 7 veri düzeltmesinin eşleştirme ve aramaya etkisi (ücretsiz, LLM yok, DB'ye yazmaz).

G_persona_esles.py'deki 12 persona ve 6 soruyu kullanır; hangi veritabanına bakacağını DATABASE_URL belirler.
Asıl veritabanına dokunmamak için tur 7 önce bir KOPYAYA uygulanır, sonra iki ölçüm karşılaştırılır:

  DATABASE_URL=sqlite:///<asıl>  python H_etki.py once
  DATABASE_URL=sqlite:///<kopya> python H_etki.py sonra    -> H_fark.md
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import G_persona_esles as G  # noqa: E402

DEGISEN = {57, 66, 76, 30, 31, 33, 35, 38, 78, 80, 37, 73, 27, 58, 11, 20, 24, 45, 69, 29, 22, 41, 43, 60, 64, 65,
           68, 71, 75, 175, 176, 77, 79, 160, 161, 185, 186}


def fark(once, sonra) -> str:
    s = ["# Aşama H — tur 7 etkisi (eşleştirme + arama)\n",
         "Yalnızca tur 7'de değişen kayıtları ilgilendiren farklar listelenir.\n",
         "## Eşleştirme\n", "| Persona | Listeden çıkan | Listeye giren | Sırası değişen (önce→sonra) |", "|---|---|---|---|"]
    for ad in sonra["esles"]:
        o = {x["id"]: x["sira"] for x in once["esles"].get(ad, [])}
        n = {x["id"]: x["sira"] for x in sonra["esles"][ad]}
        cikan = sorted(i for i in o if i not in n)
        giren = sorted(i for i in n if i not in o)
        oynayan = [f"{i}: {o[i]}→{n[i]}" for i in sorted(DEGISEN) if i in o and i in n and o[i] != n[i]]
        s.append(f"| {ad} | {', '.join(map(str, cikan)) or '-'} | {', '.join(map(str, giren)) or '-'} | "
                 f"{'; '.join(oynayan) or '-'} |")
    s.append("\n## Arama ilk 8\n")
    for a_o, a_n in zip(once["arama"], sonra["arama"]):
        if a_o["ilk8"] == a_n["ilk8"]:
            s.append(f"- **{a_n['persona']}:** değişmedi")
        else:
            s.append(f"- **{a_n['persona']}:** {' / '.join(x.split(' ')[0] for x in a_o['ilk8'])} → "
                     f"{' / '.join(x.split(' ')[0] for x in a_n['ilk8'])}")
    return "\n".join(s) + "\n"


if __name__ == "__main__":
    mod = sys.argv[1] if len(sys.argv) > 1 else "once"
    if mod not in ("once", "sonra"):
        raise SystemExit("kullanım: python H_etki.py once|sonra")
    sonuc = G.calistir()
    json.dump(sonuc, open(os.path.join(HERE, f"H_{mod}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if mod == "sonra":
        once = json.load(open(os.path.join(HERE, "H_once.json"), encoding="utf-8"))
        metin = fark(once, sonuc)
        open(os.path.join(HERE, "H_fark.md"), "w", encoding="utf-8").write(metin)
        print(metin)
    else:
        print(f"once: {len(sonuc['esles'])} persona, {len(sonuc['arama'])} soru ölçüldü")
