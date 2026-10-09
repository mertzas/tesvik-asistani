"""Kontrol listesi denetimi: ajan çıktılarını (denetim/<id>.json) doğrular ve özetler.

  python docs/olcum/2026-10-10-kontrol-listesi/denetim_ozet.py           -> denetim/dogrulama.json + ozet.md
  python docs/olcum/2026-10-10-kontrol-listesi/denetim_ozet.py --self-test

Geçerlilik: hüküm ve türler izinli listede; dogru/yanlis/eskimis hükmünde ve eksik maddede alıntı kaynağın
"## CANLI SAYFA" bölümünde birebir (normalize) geçiyor; yanlis/eskimis/belirsiz hükmünde onerilen_metin dolu; her
mevcut madde bir kez denetlenmiş. Alıntısı doğrulanamayan hüküm "doğrulanamadı" sayılır ve özette ayrı gösterilir.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

OUT = os.path.dirname(os.path.abspath(__file__))
KAYNAK = os.path.join(OUT, "..", "2026-10-09-uygunluk", "kaynak")
HUKUM = {"dogru", "yanlis", "eskimis", "desteksiz", "belirsiz"}
TUR = {"sart", "belge", "adim", "kural", "bilgi"}
URL = {"programa_ozel", "genel_sayfa", "yanlis_program", "erisilemedi"}
CAGRI = {"tutarli", "celisik", "cagri_yok", "uygulanmaz"}
ALINTI_GEREKIR = {"dogru", "yanlis", "eskimis"}
METIN_GEREKIR = {"yanlis", "eskimis", "belirsiz"}
ESKI_TUR = {"sart": "sart", "belge": "belge", "basvuru": "adim"}


def _norm(s: str) -> str:
    s = s.replace("i̇", "i").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s.replace("İ", "i").replace("I", "ı").lower()).strip()


def canli(tid: int) -> str:
    metin = open(os.path.join(KAYNAK, f"{tid}.txt"), encoding="utf-8").read()
    return metin.split("## CANLI SAYFA", 1)[1] if "## CANLI SAYFA" in metin else ""


def dogrula(d: dict, mevcut: dict, kaynak: str) -> dict:
    kn = _norm(kaynak)
    sorun, gecerli = [], {}
    anahtarlar = [m["anahtar"] for m in mevcut["maddeler"]]
    gorulen = [m.get("anahtar") for m in d.get("maddeler") or []]
    if sorted(gorulen) != sorted(anahtarlar):
        sorun.append(f"madde kümesi farklı: eksik {sorted(set(anahtarlar) - set(gorulen))}, fazla {sorted(set(gorulen) - set(anahtarlar))}")
    for m in d.get("maddeler") or []:
        h, al = m.get("hukum"), (m.get("alinti") or "").strip()
        s = None
        if h not in HUKUM or m.get("dogru_tur") not in TUR:
            s = "hüküm/tür geçersiz"
        elif h in ALINTI_GEREKIR and (not al or _norm(al) not in kn):
            s = "alıntı canlı sayfada yok"
        elif h in METIN_GEREKIR and not (m.get("onerilen_metin") or "").strip():
            s = "önerilen metin yok"
        if s:
            sorun.append(f"{m.get('anahtar')}: {s}")
        else:
            gecerli[m["anahtar"]] = m
    eksik_gecerli = [e for e in d.get("eksik_maddeler") or []
                     if e.get("tur") in TUR and (e.get("alinti") or "").strip() and _norm(e["alinti"]) in kn]
    if len(eksik_gecerli) != len(d.get("eksik_maddeler") or []):
        sorun.append(f"eksik madde alıntısı doğrulanamadı: {len(d.get('eksik_maddeler') or []) - len(eksik_gecerli)}")
    if (d.get("kaynak_url") or {}).get("hukum") not in URL:
        sorun.append("kaynak_url hükmü geçersiz")
    if (d.get("cagri_tutarliligi") or {}).get("hukum") not in CAGRI:
        sorun.append("çağrı hükmü geçersiz")
    return {"gecerli": gecerli, "eksik": eksik_gecerli, "sorunlar": sorun}


def main():
    mevcut = {m["id"]: m for m in json.load(open(os.path.join(OUT, "mevcut.json"), encoding="utf-8"))}
    sonuc, hukum, tur_degisimi, url, cagri = {}, Counter(), Counter(), Counter(), Counter()
    dogrulanamadi = eksik_say = 0
    satir = []
    for ad in sorted(os.listdir(os.path.join(OUT, "denetim")), key=lambda x: (len(x), x)):
        if not re.fullmatch(r"\d+\.json", ad):
            continue
        tid = int(ad[:-5])
        d = json.load(open(os.path.join(OUT, "denetim", ad), encoding="utf-8"))
        r = dogrula(d, mevcut[tid], canli(tid))
        sonuc[tid] = {"sorunlar": r["sorunlar"], "gecerli_madde": len(r["gecerli"]), "eksik": len(r["eksik"])}
        dogrulanamadi += len(mevcut[tid]["maddeler"]) - len(r["gecerli"])
        eksik_say += len(r["eksik"])
        for m in mevcut[tid]["maddeler"]:
            g = r["gecerli"].get(m["anahtar"])
            if not g:
                continue
            hukum[g["hukum"]] += 1
            eski = "kural" if m.get("kural") else ESKI_TUR[m["tur"]]
            if g["dogru_tur"] != eski:
                tur_degisimi[f"{eski}→{g['dogru_tur']}"] += 1
            if g["hukum"] in ("yanlis", "eskimis"):
                satir.append(f"| {tid} | {mevcut[tid]['baslik'][:40]} | {g['hukum']} | {m['metin'][:90]} | {g['onerilen_metin'][:110]} |")
        url[d["kaynak_url"]["hukum"]] += 1
        cagri[d["cagri_tutarliligi"]["hukum"]] += 1
    json.dump(sonuc, open(os.path.join(OUT, "denetim", "dogrulama.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    toplam = sum(len(mevcut[t]["maddeler"]) for t in sonuc)
    oz = [f"Program {len(sonuc)} · madde {toplam} · alıntısı doğrulanan hüküm {toplam - dogrulanamadi} · doğrulanamayan {dogrulanamadi}",
          f"Hüküm: {dict(hukum.most_common())}",
          f"Tür değişimi (eski→olması gereken): {dict(tur_degisimi.most_common())}",
          f"Eksik madde (alıntılı): {eksik_say}",
          f"Kaynak URL: {dict(url)} · Çağrı tutarlılığı: {dict(cagri)}", "",
          "| id | program | hüküm | mevcut madde | önerilen |", "|---|---|---|---|---|"] + satir
    open(os.path.join(OUT, "ozet.md"), "w", encoding="utf-8").write("\n".join(oz) + "\n")
    print("\n".join(oz[:5]))
    for tid, v in sonuc.items():
        for s in v["sorunlar"]:
            print(f"  [{tid}] {s}")


def _self_test() -> int:
    mev = {"maddeler": [{"anahtar": "s1"}, {"anahtar": "b1"}]}
    kay = "Başvuru sahibi KOBİ olmalıdır. Başvuru Formu sunulur."
    d = {"maddeler": [{"anahtar": "s1", "hukum": "dogru", "dogru_tur": "sart", "alinti": "başvuru sahibi KOBİ   olmalıdır"},
                      {"anahtar": "b1", "hukum": "yanlis", "dogru_tur": "belge", "alinti": "uydurma", "onerilen_metin": "x"}],
         "eksik_maddeler": [{"tur": "belge", "metin": "Form", "alinti": "Başvuru Formu sunulur"}],
         "kaynak_url": {"hukum": "programa_ozel"}, "cagri_tutarliligi": {"hukum": "tutarli"}}
    r = dogrula(d, mev, kay)
    k = [("normalize alıntı geçer", "s1" in r["gecerli"]), ("uydurma alıntı reddedilir", "b1" not in r["gecerli"]),
         ("eksik madde alıntısı doğrulanır", len(r["eksik"]) == 1),
         ("madde kümesi denetlenir", any("madde kümesi" in s for s in dogrula({**d, "maddeler": d["maddeler"][:1]}, mev, kay)["sorunlar"])),
         ("belirsiz hükümde önerilen metin zorunlu", any("önerilen metin" in s for s in dogrula(
             {**d, "maddeler": [{"anahtar": "s1", "hukum": "belirsiz", "dogru_tur": "sart"}, d["maddeler"][1]]}, mev, kay)["sorunlar"]))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(_self_test() if "--self-test" in sys.argv else main())
