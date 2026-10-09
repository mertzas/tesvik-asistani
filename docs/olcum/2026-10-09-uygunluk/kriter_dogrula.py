"""Ajanların çıkardığı kriter dosyalarını (kriter/<id>.json) şemaya ve kaynağa karşı doğrular.

  python docs/olcum/2026-10-09-uygunluk/kriter_dogrula.py          -> kriter/dogrulama.json + özet
  python docs/olcum/2026-10-09-uygunluk/kriter_dogrula.py --self-test

Bir kriter geçerli = alanı ve kural biçimi KRITER_SEMASI.md'deki listede + alıntısı kaynak/<id>.txt içinde birebir
(boşluk ve büyük/küçük harf normalize) geçiyor. Geçersiz kriter ölçümde kullanılmaz ve raporlanır.
"""
from __future__ import annotations

import json
import os
import re
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
BICIM = {"proje", "kredi", "faiz_destegi", "kefalet", "bildirim_prim", "uretim_odeme", "belge_etuys", "gider_on_onay",
         "hisse_fon", "gotuyu_hibe", "diger"}
ENUM = {
    "sirket_turu": {"sahis", "limited", "anonim", "kooperatif", "yok", "diger_tuzel"},
    "olcek": {"mikro", "kucuk", "orta", "buyuk"},
    "faaliyet": {"imalat", "yazilim_bilisim", "tarim", "hayvancilik", "turizm", "ticaret", "hizmet", "insaat", "enerji",
                 "saglik", "egitim", "lojistik", "savunma"},
    "hedef_grup": {"kadin", "genc", "engelli", "gazi_sehit_yakini", "ogrenci", "yeni_mezun", "ciftci", "kooperatif_ortagi",
                   "ihracatci"},
    "calisan_niteligi": {"kadin", "genc_18_29", "mesleki_belgeli", "engelli", "issiz_iskur"},
    "belge": {"uygulamali_girisimcilik_sertifikasi", "teknogirisim_rozeti", "ihracatci_birligi_uyeligi", "cks_kaydi",
              "kosgeb_kaydi", "dys_kaydi", "iskur_kaydi", "mesleki_yeterlilik_belgesi", "organik_sertifika", "marka_tescili",
              "ar_ge_merkezi_veya_teknopark", "teminat_mektubu", "dijital_olgunluk_raporu", "e_imza", "tobb_uyeligi",
              "banka_kredisi"},
}
SAYISAL = {"calisan_sayisi", "yillik_ciro_tl", "isletme_yasi_yil", "kurucu_yasi", "yatirim_tutari_tl", "onceki_yil_ihracat_usd",
           "arazi_dekar", "trl"}
ESIT = {"vergi_sgk_borcu_yok", "onceki_destek_yok", "baska_sirkette_ortak_degil", "ilave_istihdam"}
LISTE_SERBEST = {"il", "urun", "bolge_9903"}


def _norm(s: str) -> str:
    s = s.replace("i̇", "i").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s.replace("İ", "i").replace("I", "ı").lower()).strip()


def kural_gecerli(alan: str, kural: dict) -> str | None:
    if not isinstance(kural, dict) or not kural:
        return "kural boş"
    if alan in ENUM and alan != "belge":
        return None if set(kural) == {"in"} and set(kural["in"]) <= ENUM[alan] and kural["in"] else f"{alan}: in ⊆ izinli değerler"
    if alan == "belge":
        return None if set(kural) == {"gerekli"} and kural["gerekli"] in ENUM["belge"] else "belge: gerekli ∈ izinli belgeler"
    if alan in SAYISAL:
        return None if set(kural) <= {"min", "max"} and all(isinstance(v, (int, float)) for v in kural.values()) else f"{alan}: min/max sayı"
    if alan in ESIT:
        return None if kural == {"esit": True} else f"{alan}: esit true"
    if alan == "nace":
        return None if len(kural) == 1 and next(iter(kural)) in ("in_prefix", "not_in_prefix") and next(iter(kural.values())) else "nace: in_prefix/not_in_prefix"
    if alan in LISTE_SERBEST:
        return None if len(kural) == 1 and next(iter(kural)) in ("in", "not_in") and next(iter(kural.values())) else f"{alan}: in/not_in"
    if alan == "diger":
        return None if set(kural) == {"aciklama"} else "diger: aciklama"
    return f"bilinmeyen alan {alan}"


def dogrula_dosya(d: dict, kaynak: str) -> dict:
    kn = _norm(kaynak)
    sorun, gecerli = [], []
    if d.get("basvuru_bicimi") not in BICIM:
        sorun.append(f"basvuru_bicimi geçersiz: {d.get('basvuru_bicimi')}")
    bilesenler = set(d.get("bilesenler") or [])
    for i, k in enumerate(d.get("kriterler") or []):
        h = kural_gecerli(k.get("alan"), k.get("kural"))
        al = (k.get("alinti") or "").strip()
        if not h and not al:
            h = "alıntı yok"
        elif not h and _norm(al) not in kn:
            h = "alıntı kaynakta yok"
        if not h and k.get("bilesen") not in (None, *bilesenler):
            h = f"bileşen listede yok: {k.get('bilesen')}"
        if not h and not isinstance(k.get("zorunlu"), bool):
            h = "zorunlu bool değil"
        (sorun.append(f"#{i} {k.get('alan')}: {h}") if h else gecerli.append(i))
    return {"gecerli": gecerli, "sorunlar": sorun, "toplam": len(d.get("kriterler") or [])}


def main():
    sonuc = {}
    for ad in sorted(os.listdir(os.path.join(OUT, "kriter"))):
        if not re.fullmatch(r"\d+\.json", ad):
            continue
        tid = ad[:-5]
        try:
            d = json.load(open(os.path.join(OUT, "kriter", ad), encoding="utf-8"))
        except json.JSONDecodeError as e:
            sonuc[tid] = {"gecerli": [], "sorunlar": [f"JSON: {e}"], "toplam": 0}
            continue
        sonuc[tid] = dogrula_dosya(d, open(os.path.join(OUT, "kaynak", f"{tid}.txt"), encoding="utf-8").read())
    json.dump(sonuc, open(os.path.join(OUT, "kriter", "dogrulama.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    top = sum(v["toplam"] for v in sonuc.values())
    gec = sum(len(v["gecerli"]) for v in sonuc.values())
    print(f"program {len(sonuc)} · kriter {top} · geçerli {gec} ({gec / max(1, top):.0%})")
    for tid, v in sonuc.items():
        for s in v["sorunlar"]:
            print(f"  [{tid}] {s}")


def _self_test() -> int:
    kay = "Başvuru sahibi KOBİ statüsündeki işletmeler olmalıdır. Vadesi geçmiş SGK borcu bulunmamalıdır."
    d = {"basvuru_bicimi": "proje", "bilesenler": [], "kriterler": [
        {"alan": "olcek", "kural": {"in": ["mikro", "kucuk", "orta"]}, "zorunlu": True, "bilesen": None,
         "alinti": "KOBİ   statüsündeki işletmeler"},
        {"alan": "vergi_sgk_borcu_yok", "kural": {"esit": True}, "zorunlu": True, "bilesen": None, "alinti": "uydurma cümle"},
        {"alan": "olcek", "kural": {"in": ["dev"]}, "zorunlu": True, "bilesen": None, "alinti": "KOBİ"},
        {"alan": "nace", "kural": {"in_prefix": ["62"]}, "zorunlu": True, "bilesen": "Yok", "alinti": "KOBİ"}]}
    r = dogrula_dosya(d, kay)
    k = [("Türkçe büyük harf + boşluk normalize alıntı bulunur", r["gecerli"] == [0]),
         ("kaynakta olmayan alıntı reddedilir", any("#1" in s and "kaynakta yok" in s for s in r["sorunlar"])),
         ("izinsiz değer reddedilir", any("#2" in s for s in r["sorunlar"])),
         ("listede olmayan bileşen reddedilir", any("#3" in s and "bileşen" in s for s in r["sorunlar"])),
         ("sayısal kural", kural_gecerli("calisan_sayisi", {"max": 250}) is None and bool(kural_gecerli("calisan_sayisi", {"max": "x"})))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(_self_test() if "--self-test" in sys.argv else main())
