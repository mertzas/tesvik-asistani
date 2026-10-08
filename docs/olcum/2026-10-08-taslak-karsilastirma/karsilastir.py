"""Şablon taslak (yapay zekâsız) ile yapay zekâ taslağının karşılaştırması (2026-10-08). Ücretsiz, ağ yok.

Yapay zekâ tarafı: docs/olcum/2026-10-08-taslak/taslak_elle_<n>.md — üretim istemiyle (app.basvuru_taslagi.SISTEM +
birebir kullanıcı istemi, istem_<n>.md) oturum modelinin yazdığı 3 taslak (API bakiyesi yokken, Aşama C yöntemi).
Şablon tarafı: aynı 3 vaka (persona + program) için app.sablon_taslak.uret, bugünkü veritabanıyla.

Ölçütler (ikisine aynı denetim, taslak_olcum.denetle):
  başlık sırası, [DOLDURUN] sayısı, kelime, bağlamda olmayan sayılar (uydurma rakam adayı; yapay zekâ için o günkü
  istemin bağlamı, şablon için bugünkü bağlam), profil olgusu kapsaması (il, NACE, çalışan, ciro), program olgusu
  kapsaması (tutar/oran, başvuru yeri, başvuru dönemi/süresi).

    python docs/olcum/2026-10-08-taslak-karsilastirma/karsilastir.py
Çıktı: bu klasöre sablon_<n>.md ve sonuc.json, RAPOR.md tablosu stdout'a.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ESKI = os.path.join(KOK, "docs", "olcum", "2026-10-08-taslak")
sys.path.insert(0, KOK)
sys.path.insert(0, ESKI)
sys.path.insert(0, os.path.join(KOK, "docs", "olcum", "2026-10-07-denetim2"))

import taslak_olcum as TO  # noqa: E402
from app import sablon_taslak  # noqa: E402
from app.basvuru_listesi import maddeler  # noqa: E402
from app.cagrilar import program_cagrilari  # noqa: E402
from app.models import SessionLocal  # noqa: E402


def _govde(md: str) -> str:
    """Belgeler bölümü (iki yolda da aynı, listeden) ve uyarı notu hariç model/şablon gövdesi."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    md = md.split("## 6. Hazırlanacak belgeler")[0]
    return "\n".join(s for s in md.splitlines() if not s.startswith(">")).strip()


def _kapsam(metin: str, profil: dict, baglam: str) -> dict:
    """Olgu kapsaması; program olguları HER YOLUN KENDİ bağlamından (yapay zekâ: o günkü istem, şablon: bugünkü kayıt)
    ve ifade biçiminden bağımsız denetlenir (ilk sürüm şablonun kalıbını aradığı için yapay zekâya karşı taraflıydı)."""
    sayilar = TO._degerler(metin)
    satir = lambda etiket: (re.search(rf"^{etiket}: (.*)$", baglam, re.M) or [None, ""])[1]  # noqa: E731
    tutar_bag, yer_bag = satir("Tutar/oran"), satir("Başvuru yeri")
    tutar_say = {v for v in TO._degerler(tutar_bag) if v >= 1}
    profil_olgu = {
        "il": bool(profil.get("bölge")) and profil["bölge"] in metin,
        "NACE": bool(profil.get("NACE kodu")) and str(profil["NACE kodu"]) in metin,
        "çalışan": profil.get("çalışan sayısı") is not None and float(profil["çalışan sayısı"]) in sayilar,
        "ciro": bool(profil.get("yıllık ciro")) and (round(float(profil["yıllık ciro"]), 4) in sayilar),
    }
    program_olgu = {
        "tutar/oran": bool(tutar_say & sayilar) or bool(re.findall(r"%\s?\d+", tutar_bag)) and any(
            x in metin for x in re.findall(r"%\s?\d+", tutar_bag)),
        "başvuru yeri": bool(yer_bag) and any(k in metin for k in re.findall(r"[\w.-]+\.gov\.tr|KBS|PRODİS|e-Hizmet\w*|DYS",
                                                                          yer_bag) or [yer_bag[:20]]),
        "dönem/süre": bool(re.search(r"(başvuru|çağrı)[^.\n]{0,80}(dönem|tarih|son gün|açık|kapan|sürekli)", metin,
                                     re.IGNORECASE)),
    }
    return {"profil": profil_olgu, "program": program_olgu}


def main():
    db = SessionLocal()
    sonuc = []
    for n, (persona, tid) in enumerate(TO.VAKALAR, 1):
        t, liste, baglam_bugun, _ = TO._vaka(db, persona, tid)
        profil = TO.profil_sozlugu(TO.FinancialProfile(**TO.G.PERSONA[persona]))
        sab = sablon_taslak.uret(t, profil, maddeler(t), program_cagrilari(t))
        with open(os.path.join(HERE, f"sablon_{n}.md"), "w", encoding="utf-8") as f:
            f.write(f"<!-- {persona} | {t.kurum} — {t.baslik} | üretici: {sablon_taslak.MODEL_ADI} -->\n\n{sab}")
        yz_yol = os.path.join(ESKI, f"taslak_elle_{n}.md")
        yz = open(yz_yol, encoding="utf-8").read() if os.path.exists(yz_yol) else None
        istem = open(os.path.join(ESKI, f"istem_{n}.md"), encoding="utf-8").read() if yz else ""
        baglam_o_gun = istem.split("BAĞLAM:", 1)[-1] if istem else ""
        satir = {"vaka": n, "persona": persona, "program": t.baslik,
                 "sablon": {**TO.denetle(_govde(sab), baglam_bugun), **_kapsam(_govde(sab), profil, baglam_bugun)}}
        if yz:
            satir["yapay_zeka"] = {**TO.denetle(_govde(yz), baglam_o_gun), **_kapsam(_govde(yz), profil, baglam_o_gun)}
        sonuc.append(satir)
    db.close()
    json.dump(sonuc, open(os.path.join(HERE, "sonuc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("| Vaka | Yol | Başlık sırası | [DOLDURUN] | Kelime | Bağlamda olmayan sayı | Profil olgusu | Program olgusu |")
    print("|---|---|---|---|---|---|---|---|")
    for s in sonuc:
        for yol in ("sablon", "yapay_zeka"):
            d = s.get(yol)
            if not d:
                continue
            p, g = d["profil"], d["program"]
            print(f"| {s['vaka']} {s['program'][:28]} | {yol} | {'✓' if d['baslik_sirasi_dogru'] else '✗'} | "
                  f"{d['doldurun_sayisi']} | {d['kelime']} | {d['baglamda_olmayan_sayilar'] or '—'} | "
                  f"{sum(p.values())}/{len(p)} | {sum(g.values())}/{len(g)} |")


if __name__ == "__main__":
    main()
