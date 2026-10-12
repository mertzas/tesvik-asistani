"""Tur 36 — 5973 sayılı Karar desteklerinin 2026 yılı güncellenmiş üst limitleri (2026-10-12).

Hakem bulgusu (persona denemesi, senaryo 16): 5973 kayıtlarının tutarları Karar'ın taban (ilk) tutarlarıydı (ör. yurt dışı
fuar 150/250/750 bin TL); Bakanlık üst limitleri her yıl günceller ve aynı veritabanındaki m.3-6/11/12 kayıtları 2026
tutarlarını kullanıyordu. Kaynak: Ticaret Bakanlığı "5973 sayılı Karar destek üst limitleri" sayfasındaki 2026 tabloları
(docs/olcum/2026-10-12-tur34/limit_2026_5973.json, araştırma ajanı; her alıntı doğrulayıcının önbellek metninde aranır).

    python scripts/fix_veri_2026_10_12_limit2026_tur36.py --dogrula   (alıntıları indirir/önbellekten doğrular)
    python scripts/fix_veri_2026_10_12_limit2026_tur36.py             (dry-run)
    python scripts/fix_veri_2026_10_12_limit2026_tur36.py --uygula    (önce doğrular ve yedek alır; tekrar çalışırsa değişmez)
    python scripts/fix_veri_2026_10_12_limit2026_tur36.py --self-test
"""
import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("tur34", KOK / "scripts/fix_veri_2026_10_12_tur34.py")
tur34 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tur34)
tur21 = tur34.tur21

VERI = KOK / "docs/olcum/2026-10-12-tur34/limit_2026_5973.json"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur36.db.bak"
NOT = "Tur36 2026-10-12"
TABAN_NOTU = " (Karar metnindeki taban tutar; 2026 güncel üst limiti için tutar alanına bakın)"


def dogrula(k: dict, getir=tur21.metin_al) -> list[str]:
    """Kayıt için sorunlar: bulunamayan alıntı, yeni metinde alıntısız rakam. Boş liste = kabul."""
    sorunlar = []
    for a in k.get("alintilar") or []:
        metin, hata = getir(a["kaynak_url"])
        if hata:
            sorunlar.append(f"indirilemedi: {a['kaynak_url']} ({hata})")
        elif tur21.norm(a["alinti"]) not in tur21.norm(metin):
            sorunlar.append(f"alıntı bulunamadı: {a['alinti'][:80]}")
    alinti_sayilari = set().union(*(tur21.sayilar(a["alinti"]) for a in k.get("alintilar") or [])) \
        if k.get("alintilar") else set()
    for s in tur21.sayilar(k.get("yeni_tesvil_tutari") or ""):
        if s not in alinti_sayilari:
            sorunlar.append(f"alıntısız rakam: {s}")
    return sorunlar


def _taban_maddesi(m: dict, eski: str, yeni: str) -> bool:
    """Kontrol listesi maddesi, yeni metinde olmayan eski bir TL tutarı içeriyor mu (Karar tabanı)."""
    tutarlar = re.findall(r"\d{1,3}(?:\.\d{3})+", m.get("metin") or "")
    return any(t in eski and t not in yeni for t in tutarlar) and TABAN_NOTU not in (m.get("metin") or "")


def plan(tum: dict, veri: dict) -> list[tuple]:
    p = []
    tablo = re.compile(r"2026%20|2026 ")
    for k in veri["kayitlar"]:
        t = tum.get(k["id"])
        yeni = k.get("yeni_tesvil_tutari")
        if t is None or not yeni or not (t.baslik or "").startswith(k["baslik"][:30]):
            continue
        if t.tesvil_tutari != yeni:
            p.append((t, "tesvil_tutari", t.tesvil_tutari, yeni))
        kl = [dict(m) for m in t.kontrol_listesi or []]
        degisti = False
        for m in kl:
            if _taban_maddesi(m, k.get("eski_tesvil_tutari") or "", yeni):
                m["metin"] = m["metin"].rstrip(". ") + TABAN_NOTU
                degisti = True
        mevcut = {(m.get("alinti"), m.get("kaynak_url")) for m in kl}
        for a in k.get("alintilar") or []:
            if tablo.search(a["kaynak_url"]) and (a["alinti"], a["kaynak_url"]) not in mevcut:
                kl.append({"tur": "bilgi", "metin": f"2026 üst limit tablosu: {a['iddia']}", "alinti": a["alinti"],
                           "kaynak_url": a["kaynak_url"], "kaynak_tarihi": "2026-10-12", "dogrulandi": True})
                degisti = True
        if degisti:
            p.append((t, "kontrol_listesi", t.kontrol_listesi, kl))
    return p


def uygula(db, veri: dict, dry_run: bool = True) -> int:
    from sqlalchemy.orm.attributes import flag_modified
    from app.models import Tesvik
    tum = {t.id: t for t in db.query(Tesvik).all()}
    p = plan(tum, veri)
    for t, alan, eski, yeni in p:
        print(f"[{t.id:3}] {alan:16} {str(eski)[:70]!r} -> {str(yeni)[:90]!r}")
        if not dry_run:
            setattr(t, alan, yeni)
            flag_modified(t, alan)
            ek = f"{NOT}: {alan} 2026 üst limitleriyle güncellendi (kanıt {VERI.relative_to(KOK).as_posix()})"
            if ek not in (t.durum_notu or ""):
                t.durum_notu = (t.durum_notu + " | " if t.durum_notu else "") + ek
    if not dry_run:
        db.commit()
    print(f"\n{len(p)} değişiklik ({'dry-run' if dry_run else 'uygulandı'}), {len({t.id for t, *_ in p})} kayıt")
    return len(p)


def _self_test() -> int:
    from types import SimpleNamespace as N
    veri = {"kayitlar": [{"id": 278, "baslik": "Yurt Dışı Fuar Desteği (5973 sayılı Karar m.7)",
                          "eski_tesvil_tutari": "genel fuarda 150.000 TL",
                          "yeni_tesvil_tutari": "genel fuarda 739.900 TL (2026 yılı güncellenmiş üst limitler)",
                          "alintilar": [{"iddia": "genel fuar 2026", "alinti": "Genel 739.900",
                                         "kaynak_url": "https://ticaret.gov.tr/data/x/2026%20Destek.pdf"}]}]}
    t = N(id=278, baslik="Yurt Dışı Fuar Desteği (5973 sayılı Karar m.7)", tesvil_tutari="genel fuarda 150.000 TL",
          kontrol_listesi=[{"tur": "kural", "metin": "Genel fuarda en fazla 150.000 TL."}], durum_notu=None)
    p = plan({278: t}, veri)
    getir = lambda url: ("tablo: Genel 739.900 TL", None)  # noqa: E731
    k = [("tutar güncellenir", any(a == "tesvil_tutari" and "739.900" in y for _, a, _, y in p)),
         ("eski taban maddesi işaretlenir", any(a == "kontrol_listesi" and TABAN_NOTU in y[0]["metin"]
                                               for _, a, _, y in p)),
         ("2026 tablo alıntısı bilgi maddesi olur", any(a == "kontrol_listesi" and y[-1]["dogrulandi"]
                                                        and y[-1]["alinti"] == "Genel 739.900" for _, a, _, y in p)),
         ("alıntı doğrulama", dogrula(veri["kayitlar"][0], getir) == []),
         ("alıntısız rakam yakalanır", any("alıntısız" in s for s in dogrula(
             {**veri["kayitlar"][0], "yeni_tesvil_tutari": "999.999 TL"}, getir))),
         ("başlık uyuşmazsa dokunmaz", plan({278: N(**{**t.__dict__, "baslik": "Başka"})}, veri) == [])]
    for _, a, _, y in p:
        setattr(t, a, y)
    k.append(("ikinci çalıştırmada değişiklik yok", plan({278: t}, veri) == []))
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dogrula", action="store_true")
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    veri = json.loads(VERI.read_text(encoding="utf-8"))
    if a.dogrula or a.uygula:
        hata = 0
        for k in veri["kayitlar"]:
            s = dogrula(k) if k.get("yeni_tesvil_tutari") else []
            hata += bool(s)
            print(f"[{'KABUL' if not s else 'RET  '}] {k['id']} {k['baslik'][:60]}" + (f" — {s[:3]}" if s else ""))
        print(f"\nkabul {len(veri['kayitlar']) - hata}/{len(veri['kayitlar'])}")
        if hata:
            sys.exit(1)
        if a.dogrula:
            return
    from app.models import SessionLocal, settings
    if a.uygula and not YEDEK.exists():
        shutil.copy2(Path(settings.DATABASE_URL.replace("sqlite:///", "")), YEDEK)
        print(f"yedek: {YEDEK}")
    db = SessionLocal()
    uygula(db, veri, dry_run=not a.uygula)
    db.close()


if __name__ == "__main__":
    main()
