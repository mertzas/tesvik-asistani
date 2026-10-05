"""NACE çıkarım JSONL logunu (özellikle --dry-run logunu) özetler ve toplu
çalıştırma öncesi bir KAPI (gate) kontrolü yapar.

  python scripts/nace_log_ozet.py                              # dry-run logunu özetle
  python scripts/nace_log_ozet.py data/nace_extraction_log.jsonl
  python scripts/nace_log_ozet.py --json                       # makine okunur çıktı
  python scripts/nace_log_ozet.py --kapi                       # eşik aşılırsa çıkış kodu 2

Önerilen akış (maliyet düşük, güvenli):
  1) python scripts/backfill_nace_llm.py --dry-run --limit 20      # tek API ödemesi
  2) python scripts/nace_log_ozet.py --kapi                        # özet + kapı
  3) python scripts/backfill_nace_llm.py --log-dan-uygula data/nace_extraction_log.dry-run.jsonl
     # API'ye GİTMEDEN aynı kararları yazar

Aynı kayıt logda birden çok kez varsa en son satır geçerlidir.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

VARSAYILAN_LOG = Path("data/nace_extraction_log.dry-run.jsonl")

# Elle bakılmadan toplu uygulanmaması gereken çakışma türleri: kilidin yönünü
# değiştirirler (A->C) ya da karışık sonuç üretirler.
RISKLI_CAKISMALAR = ("sektor_degisimi", "karisik_degisim")

VARSAYILAN_ESIKLER = {
    "maks_riskli_cakisma": 0,        # sayı
    "maks_inceleme_orani": 0.20,     # manuel inceleme / kayıt
    "maks_belirsiz_orani": 0.50,
    "maks_dusuk_guven_orani": 0.30,  # kapsam_guven < dusuk_guven
}
DUSUK_GUVEN = 0.8


def log_oku(yol: Path) -> list[dict]:
    """JSONL'i okur; aynı tesvik_id için son satırı tutar. Bozuk satırı atlar."""
    son: dict[int, dict] = {}
    for no, satir in enumerate(yol.read_text(encoding="utf-8").splitlines(), 1):
        if not satir.strip():
            continue
        try:
            kayit = json.loads(satir)
            son[int(kayit["tesvik_id"])] = kayit
        except (ValueError, KeyError) as e:
            print(f"UYARI: {yol.name}:{no} okunamadı ({e})", file=sys.stderr)
    return list(son.values())


def ozetle(kayitlar: list[dict]) -> dict:
    n = len(kayitlar)
    kapsam = Counter(k["kapsam"]["kapsam_turu"] for k in kayitlar)
    tip = Counter(k["kapsam"]["yararlanici_tipi"] for k in kayitlar)
    cakisma_turu = Counter()
    cakisma_aksiyon = Counter()
    riskli: list[dict] = []
    for k in kayitlar:
        c = k.get("cakisma")
        if c:
            cakisma_turu[c["tur"]] += 1
            cakisma_aksiyon[c["aksiyon"]] += 1
            if c["tur"] in RISKLI_CAKISMALAR:
                riskli.append({"tesvik_id": k["tesvik_id"], "baslik": k["baslik"],
                               "tur": c["tur"], "eski": c["eski"], "yeni": c["yeni"]})
    reddedilen = Counter()
    for k in kayitlar:
        for _, sebep in k.get("reddedilen", []):
            reddedilen[sebep.split(" (")[0].split(" <")[0]] += 1
    inceleme = [{"tesvik_id": k["tesvik_id"], "baslik": k["baslik"], "nedenler": k["inceleme_nedenleri"]}
                for k in kayitlar if k.get("manuel_inceleme_gerekli")]
    guvenler = [k["kapsam"].get("kapsam_guven", 0.0) for k in kayitlar]
    dusuk = [{"tesvik_id": k["tesvik_id"], "baslik": k["baslik"],
              "kapsam_turu": k["kapsam"]["kapsam_turu"], "guven": k["kapsam"].get("kapsam_guven", 0.0)}
             for k in kayitlar if k["kapsam"].get("kapsam_guven", 0.0) < DUSUK_GUVEN]
    kod_sayac = Counter()
    for k in kayitlar:
        for h in k["kapsam"].get("hedef_nace_kodlari", []):
            kod_sayac[h["nace_prefix"]] += 1
    haric_sayac = Counter()
    for k in kayitlar:
        for h in k.get("haric", []):
            haric_sayac[h] += 1
    return {
        "kayit_sayisi": n,
        "kapsam_turu": dict(kapsam), "yararlanici_tipi": dict(tip),
        "cakisma_turu": dict(cakisma_turu.most_common()),
        "cakisma_aksiyon": dict(cakisma_aksiyon),
        "cakisma_toplam": sum(cakisma_turu.values()),
        "riskli_cakismalar": riskli,
        "reddedilen_sebepleri": dict(reddedilen.most_common()),
        "manuel_inceleme": inceleme,
        "dusuk_guvenli": dusuk,
        "guven_ortalama": round(sum(guvenler) / n, 3) if n else None,
        "guven_min": min(guvenler) if guvenler else None,
        "en_sik_hedef_kodlar": dict(kod_sayac.most_common(10)),
        "haric_kodlar": dict(haric_sayac.most_common()),
    }


def kapi_kontrol(ozet: dict, esikler: dict | None = None) -> list[str]:
    """Eşik ihlallerini döndürür; boş liste = toplu uygulamaya geçilebilir."""
    e = {**VARSAYILAN_ESIKLER, **(esikler or {})}
    n = ozet["kayit_sayisi"]
    ihlal: list[str] = []
    if n == 0:
        return ["log boş: doğrulanacak karar yok"]
    if len(ozet["riskli_cakismalar"]) > e["maks_riskli_cakisma"]:
        ihlal.append(f"{len(ozet['riskli_cakismalar'])} riskli çakışma (sektör değişimi/karışık) elle onaylanmalı")
    if len(ozet["manuel_inceleme"]) / n > e["maks_inceleme_orani"]:
        ihlal.append(f"manuel inceleme oranı %{100 * len(ozet['manuel_inceleme']) / n:.0f} > "
                     f"%{100 * e['maks_inceleme_orani']:.0f}")
    belirsiz = ozet["kapsam_turu"].get("BELIRSIZ", 0)
    if belirsiz / n > e["maks_belirsiz_orani"]:
        ihlal.append(f"BELIRSIZ oranı %{100 * belirsiz / n:.0f} > %{100 * e['maks_belirsiz_orani']:.0f} "
                     "(metin kalitesi/prompt sorunu olabilir)")
    if len(ozet["dusuk_guvenli"]) / n > e["maks_dusuk_guven_orani"]:
        ihlal.append(f"düşük güvenli karar oranı %{100 * len(ozet['dusuk_guvenli']) / n:.0f} > "
                     f"%{100 * e['maks_dusuk_guven_orani']:.0f}")
    return ihlal


def _tablo(baslik: str, sozluk: dict, toplam: int | None = None) -> list[str]:
    if not sozluk:
        return [f"{baslik}: -"]
    genislik = max(len(str(k)) for k in sozluk)
    satirlar = [baslik]
    for k, v in sozluk.items():
        yuzde = f"  %{100 * v / toplam:.0f}" if toplam else ""
        satirlar.append(f"  {str(k):<{genislik}}  {v:>4}{yuzde}")
    return satirlar


def bicimle(ozet: dict) -> str:
    n = ozet["kayit_sayisi"]
    cikti = [f"NACE çıkarım özeti: {n} kayıt, ortalama güven {ozet['guven_ortalama']}, "
             f"en düşük {ozet['guven_min']}", ""]
    cikti += _tablo("Kapsam türü", ozet["kapsam_turu"], n) + [""]
    cikti += _tablo("Çakışma türü (frekans)", ozet["cakisma_turu"], ozet["cakisma_toplam"] or None) + [""]
    cikti += _tablo("Çakışma aksiyonu", ozet["cakisma_aksiyon"]) + [""]
    cikti += _tablo("Yararlanıcı tipi", ozet["yararlanici_tipi"], n) + [""]
    cikti += _tablo("Reddedilen kod sebepleri", ozet["reddedilen_sebepleri"]) + [""]
    cikti += _tablo("En sık hedef kodlar", ozet["en_sik_hedef_kodlar"]) + [""]
    cikti += _tablo("Hariç tutulan kodlar", ozet["haric_kodlar"]) + [""]
    if ozet["riskli_cakismalar"]:
        cikti.append("ELLE BAKILACAK çakışmalar:")
        cikti += [f"  [{r['tesvik_id']}] {r['baslik']}: {r['eski']} -> {r['yeni']} ({r['tur']})"
                  for r in ozet["riskli_cakismalar"]]
        cikti.append("")
    if ozet["manuel_inceleme"]:
        cikti.append("MANUEL İNCELEME:")
        cikti += [f"  [{m['tesvik_id']}] {m['baslik']}: {m['nedenler']}" for m in ozet["manuel_inceleme"]]
        cikti.append("")
    if ozet["dusuk_guvenli"]:
        cikti.append(f"Düşük güvenli (<{DUSUK_GUVEN}) kararlar:")
        cikti += [f"  [{d['tesvik_id']}] {d['baslik']}: {d['kapsam_turu']} ({d['guven']})"
                  for d in ozet["dusuk_guvenli"]]
    return "\n".join(cikti).rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("log", nargs="?", type=Path, default=VARSAYILAN_LOG)
    ap.add_argument("--json", action="store_true", help="Özeti JSON olarak yaz")
    ap.add_argument("--kapi", action="store_true", help="Eşik aşılırsa çıkış kodu 2 ver")
    ap.add_argument("--maks-riskli-cakisma", type=int)
    ap.add_argument("--maks-inceleme-orani", type=float)
    ap.add_argument("--maks-belirsiz-orani", type=float)
    ap.add_argument("--maks-dusuk-guven-orani", type=float)
    a = ap.parse_args(argv)

    if not a.log.exists():
        print(f"Log bulunamadı: {a.log}", file=sys.stderr)
        return 1
    ozet = ozetle(log_oku(a.log))
    esikler = {k: v for k, v in {
        "maks_riskli_cakisma": a.maks_riskli_cakisma, "maks_inceleme_orani": a.maks_inceleme_orani,
        "maks_belirsiz_orani": a.maks_belirsiz_orani,
        "maks_dusuk_guven_orani": a.maks_dusuk_guven_orani}.items() if v is not None}
    ihlaller = kapi_kontrol(ozet, esikler)
    if a.json:
        print(json.dumps({**ozet, "kapi_ihlalleri": ihlaller}, ensure_ascii=False, indent=2))
    else:
        print(bicimle(ozet))
        if a.kapi:
            print("\nKAPI: " + ("GEÇTİ" if not ihlaller else "GEÇMEDİ"))
            for i in ihlaller:
                print(f"  - {i}")
    return 2 if (a.kapi and ihlaller) else 0


if __name__ == "__main__":
    sys.exit(main())
