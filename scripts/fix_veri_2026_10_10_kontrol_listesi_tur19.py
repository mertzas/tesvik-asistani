"""Tur 19 — denetlenmiş kontrol listesi ve başvuru biçimi (2026-10-10).

Kaynak: docs/olcum/2026-10-10-kontrol-listesi/denetim/<id>.json (507 maddenin hükmü + türü + resmî sayfadan alıntı,
alıntıların hepsi denetim_ozet.py ile canlı sayfada doğrulandı; 177 eksik madde) ve
docs/olcum/2026-10-09-uygunluk/kriter/<id>.json (basvuru_bicimi). Kurallar:
  dogru                    -> mevcut metin, denetimdeki türle, alıntılı
  yanlis/eskimis/belirsiz  -> önerilen metin (alıntılı); önerilen "listeden çıkar" diyorsa madde düşer ("Yerine: ..."
                              varsa o metin girer)
  desteksiz                -> mevcut metin korunur, dogrulandi=false ("kurumdan teyit edin" diye gösterilir)
  eksik madde              -> eklenir, alıntılı
  başvuru maddesi          -> yalnız "Başvuruyu yap: <başvuru yeri>"; dönem bilgisi çağrı kayıtlarından gösterilir
                              (eski basvuru_suresi metni maddeye yapıştırıldığı için çağrıyla çelişiyordu)
Eski alanlar (basvuru_sartlari, gerekli_belgeler) değiştirilmez; kontrol_listesi doluysa uygulama onu kullanır.

    python scripts/fix_veri_2026_10_10_kontrol_listesi_tur19.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_10_kontrol_listesi_tur19.py --uygula     (önce yedek alır)
    python scripts/fix_veri_2026_10_10_kontrol_listesi_tur19.py --self-test
"""
import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DENETIM = KOK / "docs/olcum/2026-10-10-kontrol-listesi"
KRITER = KOK / "docs/olcum/2026-10-09-uygunluk/kriter"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur19.db.bak"
KAYNAK_TARIHI = "2026-10-09"
SIRA = {"sart": 0, "belge": 1, "adim": 2, "kural": 3, "bilgi": 4}
CIKAR = re.compile(r"listeden çıkar|çıkarılmalı|başvuru listesinden çıkar", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


# Belge ve adım listesi isim olarak okunur: denetimin önerdiği "…'ü hazırladım", "…onayladım" sonları atılır.
_FIIL = re.compile(r"(['’]\w+)?\s+(hazırladım|onayladım|aldım|yaptım|yükledim|sundum|imzaladım)\.?$", re.IGNORECASE)


def isim_bicimi(tur: str, metin: str) -> str:
    return _FIIL.sub("", metin).strip() if tur in ("belge", "adim") else metin


def _kelimeler(metin: str, haric: set[str]) -> set[str]:
    return {k for k in re.findall(r"\w+", metin.lower()) if len(k) > 2 and k not in haric}


def tekrar_mi(yeni: dict, liste: list[dict], haric: set[str]) -> bool:
    """Aynı türde, program adı dışındaki kelimeleri tamamen başka bir maddenin içinde kalan madde tekrardır
    ("Proje Başvuru Formu II. Bölüm" ⊂ "Başvuru Formu ve Proje Başvuru Formu II. Bölüm")."""
    k = _kelimeler(yeni["metin"], haric)
    if len(k) < 2:
        return False
    return any(x["tur"] == yeni["tur"] and (k <= (o := _kelimeler(x["metin"], haric)) or (len(o) >= 2 and o <= k))
               for x in liste)


def onerilen(metin: str) -> str | None:
    """Önerilen metin: 'çıkar' diyorsa None (madde düşer), 'Yerine: X' varsa X."""
    m = re.search(r"Yerine:\s*(.+)", metin)
    if m:
        return m.group(1).strip()
    return None if CIKAR.search(metin) else metin.strip()


def kur(mevcut: dict, denetim: dict) -> list[dict]:
    hukum = {m["anahtar"]: m for m in denetim["maddeler"]}
    url = mevcut["kaynak_url"]
    haric = _kelimeler(mevcut.get("baslik") or "", set())
    liste, gorulen = [], set()

    def ekle(tur, metin, alinti, dogrulandi):
        metin = isim_bicimi(tur, " ".join(metin.split()))
        if not metin or _norm(metin) in gorulen:
            return
        yeni = {"tur": tur, "metin": metin, "alinti": (alinti or "").strip() or None, "kaynak_url": url,
                "kaynak_tarihi": KAYNAK_TARIHI, "dogrulandi": dogrulandi}
        # Önce gelen (mevcut, düzeltilmiş) madde korunur; onu tekrar eden sonraki madde (çoğunlukla eksik madde) düşer.
        if tur != "adim" and tekrar_mi(yeni, liste, haric):
            return
        gorulen.add(_norm(metin))
        liste.append(yeni)

    basvuru_eklendi = False
    for m in mevcut["maddeler"]:
        h = hukum[m["anahtar"]]
        if m["tur"] == "basvuru":
            if mevcut.get("basvuru_yeri"):
                ekle("adim", f"Başvuruyu yap: {mevcut['basvuru_yeri'].strip()}", h.get("alinti"), h["hukum"] != "desteksiz")
                basvuru_eklendi = True
            continue
        if h["hukum"] == "dogru":
            ekle(h["dogru_tur"], m["metin"], h.get("alinti"), True)
        elif h["hukum"] == "desteksiz":
            ekle(h["dogru_tur"], m["metin"], None, False)
        else:
            yeni = onerilen(h.get("onerilen_metin") or "")
            if yeni:
                ekle(h["dogru_tur"], yeni, h.get("alinti"), h["hukum"] != "belirsiz" or bool(h.get("alinti")))
    for e in denetim.get("eksik_maddeler") or []:
        ekle(e["tur"], e["metin"], e["alinti"], True)
    if not basvuru_eklendi and mevcut.get("basvuru_yeri"):
        ekle("adim", f"Başvuruyu yap: {mevcut['basvuru_yeri'].strip()}", None, False)
    # Başvuru adımı adımların sonunda; diğerleri tür sırasıyla, kendi içinde mevcut sırayla.
    son = [x for x in liste if x["tur"] == "adim" and x["metin"].startswith("Başvuruyu yap:")]
    digerleri = [x for x in liste if x not in son]
    digerleri.sort(key=lambda x: SIRA[x["tur"]])
    adim_sonu = max((i for i, x in enumerate(digerleri) if x["tur"] in ("sart", "belge", "adim")), default=-1) + 1
    return digerleri[:adim_sonu] + son + digerleri[adim_sonu:]


def yukle():
    mevcut = {m["id"]: m for m in json.load(open(DENETIM / "mevcut.json", encoding="utf-8"))}
    sonuc = {}
    for tid, m in mevcut.items():
        d = json.load(open(DENETIM / "denetim" / f"{tid}.json", encoding="utf-8"))
        k = json.load(open(KRITER / f"{tid}.json", encoding="utf-8"))
        sonuc[tid] = (kur(m, d), k.get("basvuru_bicimi"))
    return sonuc


def uygula(db, veri: dict, dry_run: bool = True) -> int:
    from app.models import Tesvik
    degisen = 0
    say = Counter()
    for tid, (liste, bicim) in sorted(veri.items()):
        t = db.get(Tesvik, tid)
        if t is None or not t.aktif_mi:
            print(f"[{tid}] kayıt yok/aktif değil; atlandı")
            continue
        # Maddelerin kaynağı programın GÜNCEL resmî kaynağıdır: tur20 genel sayfaları değiştirdi; denetim anındaki adrese
        # dönmek tekrar çalıştırmada tur20'yi geri alırdı.
        liste = [{**x, "kaynak_url": t.kaynak_url} for x in liste]
        # Sonraki turların eklediği maddeler ("ekleyen" işaretli, ör. tur23 profil şartları) kendi kaynaklarıyla korunur.
        sonraki = [x for x in (t.kontrol_listesi or []) if x.get("ekleyen")]
        liste = [x for x in sonraki if x["tur"] == "sart"] + liste + [x for x in sonraki if x["tur"] != "sart"]
        if t.kontrol_listesi == liste and t.basvuru_bicimi == bicim:
            continue
        c = Counter(x["tur"] for x in liste)
        say.update(c)
        say["dogrulanmamis"] += sum(not x["dogrulandi"] for x in liste)
        print(f"[{tid:3}] {t.baslik[:48]:48} bicim={bicim:13} " + " ".join(f"{k}={c[k]}" for k in SIRA)
              + f" teyitsiz={sum(not x['dogrulandi'] for x in liste)}")
        if not dry_run:
            t.kontrol_listesi, t.basvuru_bicimi = liste, bicim
        degisen += 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {degisen} program · toplam {dict(say)}")
    return degisen


def _self_test() -> int:
    mev = {"kaynak_url": "https://k", "basvuru_yeri": "PRODİS", "maddeler": [
        {"anahtar": "s1", "tur": "sart", "metin": "KOBİ olmak"}, {"anahtar": "s2", "tur": "sart", "metin": "Harcama önce yapılmaz"},
        {"anahtar": "b1", "tur": "belge", "metin": "Ödeme formu"}, {"anahtar": "b2", "tur": "belge", "metin": "Eski form"},
        {"anahtar": "b3", "tur": "belge", "metin": "Kanıtsız belge"},
        {"anahtar": "x1", "tur": "basvuru", "metin": "Başvuruyu yap: PRODİS — genellikle Ocak"}]}
    den = {"maddeler": [
        {"anahtar": "s1", "hukum": "yanlis", "dogru_tur": "sart", "alinti": "küçük ve orta", "onerilen_metin": "Küçük veya orta işletme olmak"},
        {"anahtar": "s2", "hukum": "dogru", "dogru_tur": "kural", "alinti": "önce yapılan"},
        {"anahtar": "b1", "hukum": "yanlis", "dogru_tur": "belge", "alinti": "a", "onerilen_metin": "Başvuruda istenmez (listeden çıkar)"},
        {"anahtar": "b2", "hukum": "yanlis", "dogru_tur": "belge", "alinti": "a", "onerilen_metin": "Bu madde çıkarılmalı. Yerine: Uluslararası başvuru formu"},
        {"anahtar": "b3", "hukum": "desteksiz", "dogru_tur": "belge"},
        {"anahtar": "x1", "hukum": "eskimis", "dogru_tur": "adim", "alinti": "PRODİS", "onerilen_metin": "x"}],
        "eksik_maddeler": [{"tur": "sart", "metin": "Sermaye şirketi olmak", "alinti": "sermaye şirketi"}]}
    l = kur(mev, den)
    metin = [x["metin"] for x in l]
    k = [("yanlış madde önerilenle değişir", "Küçük veya orta işletme olmak" in metin and "KOBİ olmak" not in metin),
         ("'listeden çıkar' düşer", "Ödeme formu" not in metin and not any("çıkar" in m for m in metin)),
         ("'Yerine:' metni girer", "Uluslararası başvuru formu" in metin),
         ("desteksiz korunur, teyitsiz", any(x["metin"] == "Kanıtsız belge" and not x["dogrulandi"] for x in l)),
         ("eksik eklenir", "Sermaye şirketi olmak" in metin),
         ("başvuru adımı yalnız yer, dönem yok", "Başvuruyu yap: PRODİS" in metin and not any("Ocak" in m for m in metin)),
         ("sıra: şartlar, belgeler, adımlar, kurallar", [x["tur"] for x in l] == ["sart", "sart", "belge", "belge", "adim", "kural"]),
         ("onerilen() saf", onerilen("Metin") == "Metin" and onerilen("çıkarılmalı") is None),
         ("belge isim biçiminde", isim_bicimi("belge", "Proje Başvuru Formu II. Bölüm'ü hazırladım") == "Proje Başvuru Formu II. Bölüm"
          and isim_bicimi("sart", "İmalatçıyım, onayladım") == "İmalatçıyım, onayladım"),
         ("tekrar: içerilen madde düşer, program adı karışmaz",
          tekrar_mi({"tur": "belge", "metin": "Proje Başvuru Formu II. Bölüm"},
                    [{"tur": "belge", "metin": "Başvuru Formu ve Proje Başvuru Formu II. Bölüm"}], set())
          and not tekrar_mi({"tur": "belge", "metin": "Kapasite Geliştirme Destek Programı Taahhütnamesi"},
                            [{"tur": "belge", "metin": "Kapasite Geliştirme Destek Programı Başvuru Formu"}],
                            _kelimeler("Kapasite Geliştirme Destek Programı", set())))]
    gerçek = yukle()
    k.append(("77 program kurulur, her birinde başvuru adımı", len(gerçek) == 77 and all(
        any(x["metin"].startswith("Başvuruyu yap:") for x in li) for li, _ in gerçek.values())))
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    from app.models import SessionLocal, settings
    veri = yukle()
    if a.uygula:
        db_yolu = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
        if not YEDEK.exists():
            shutil.copy2(db_yolu, YEDEK)
            print(f"yedek: {YEDEK}")
    db = SessionLocal()
    uygula(db, veri, dry_run=not a.uygula)


if __name__ == "__main__":
    main()
