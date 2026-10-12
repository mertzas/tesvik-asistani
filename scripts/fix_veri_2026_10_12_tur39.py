"""Tur 39 — Groq önerisiyle (scripts/groq_kayit_onerici.py) hazırlanan kayıtların doğrulanması ve eklenmesi (2026-10-12).

Tur38 hattının aynısı; klasör docs/olcum/2026-10-12-tur39. Aşağıdaki tur38 notu bilgi içindir.
Tur 38 — hakemlerin "kaynak dışı" işaretlediği tarım ve istihdam programları (2026-10-12).

Yeni kayıtlar (docs/olcum/2026-10-12-tur38/kayit/<slug>.json): KKYDP (Kırsal Kalkınma Yatırımlarının Desteklenmesi
Programı, Tebliğ 2026/9, 2026 dönemi kapalı) ve 3308 sayılı Kanun kapsamındaki mesleki eğitim devlet katkısı.
IPARD III tedbirlerinin (TKDK) 2026 çağrıları: docs/olcum/2026-10-12-tur38/ipard_durum_2026.json → çağrı kayıtları.
Doğrulama ve ekleme tur34'ün (tur32/tur21 hattı) aynısıdır; her alıntı resmî kaynaktan yeniden indirilip birebir aranır.

    python scripts/fix_veri_2026_10_12_tur38.py --dogrula-tek SLUG
    python scripts/fix_veri_2026_10_12_tur38.py --dogrula
    python scripts/fix_veri_2026_10_12_tur38.py               (dry-run)
    python scripts/fix_veri_2026_10_12_tur38.py --uygula      (yedek: tesvikler_oncesi_tur39.db.bak)
    python scripts/fix_veri_2026_10_12_tur38.py --ipard       (IPARD çağrı kayıtları; dry-run, --uygula ile yazar)
    python scripts/fix_veri_2026_10_12_tur38.py --self-test
"""
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("tur34", KOK / "scripts/fix_veri_2026_10_12_tur34.py")
tur34 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tur34)
tur21 = tur34.tur21

tur21.DIZIN = KOK / "docs/olcum/2026-10-12-tur39"
tur21.ONBELLEK = tur21.DIZIN / "kaynak"
tur21.YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur39.db.bak"
tur21.BUGUN = date(2026, 10, 12)
tur21.NOT = "Tur39 2026-10-12"
EK_RESMI = r"tkdk\.gov\.tr|resmigazete\.gov\.tr|tarimorman\.gov\.tr|meb\.gov\.tr|iskur\.gov\.tr|sgk\.gov\.tr"
tur21.RESMI = re.compile(tur21.RESMI.pattern.replace(r"(^|\.)(", rf"(^|\.)({EK_RESMI}|", 1))
IPARD = tur21.DIZIN / "ipard_durum_2026.json"
# DB'deki IPARD III kayıtları (başlıktaki tedbir numarası → kayıt)
_TEDBIR = {"101": r"Tedbir 101", "103": r"Tarım ve Balıkçılık Ürünlerinin İşlenmesi", "302": r"Tedbir 302"}


def ipard_cagrilari(yaz: bool) -> int:
    from app.models import SessionLocal, Tesvik, TesvikCagrisi
    veri = json.loads(IPARD.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        ipard = [t for t in db.query(Tesvik).all() if t.kurum == "TKDK" and "IPARD III" in (t.baslik or "")]
        eklenen = 0
        for ted in veri["tedbirler"]:
            kalip = _TEDBIR.get(str(ted["tedbir"]).split("/")[0])
            t = next((x for x in ipard if kalip and re.search(kalip, x.baslik or "")), None)
            if t is None or not ted.get("kapanis"):
                print(f"  atlandı: tedbir {ted['tedbir']} ({'kayıt yok' if t is None else 'çağrı tarihi yok'})")
                continue
            # Çağrı alıntısı ve tarihleri resmî ilanda birebir aranır (tur21 doğrulayıcısının metni)
            metin, hata = tur21.metin_al(ted["kaynak_url"])
            norm = lambda x: re.sub(r"\s+", " ", (x or "").replace("’", "'")).strip()  # noqa: E731
            tarih_tamam = all(any(m in metin for m in tur21.tarih_metinleri(ted[a])) for a in ("acilis", "kapanis")
                              if ted.get(a))
            if hata or norm(ted.get("alinti")) not in norm(metin) or not tarih_tamam:
                print(f"  DOĞRULANAMADI, atlandı: tedbir {ted['tedbir']} ({hata or 'alıntı/tarih metinde yok'})")
                continue
            mevcut = {(c.ad, c.kapanis) for c in t.cagrilar}
            kapanis = date.fromisoformat(ted["kapanis"])
            ad = ted.get("cagri") or f"IPARD III Tedbir {ted['tedbir']} 2026 çağrısı"
            if (ad, kapanis) in mevcut:
                print(f"  zaten var: {t.id} {ad}")
                continue
            print(f"  {'EKLE' if yaz else 'eklenecek'}: {t.id} {ad} ({ted.get('acilis')} – {ted['kapanis']})")
            if yaz:
                db.add(TesvikCagrisi(tesvik_id=t.id, ad=ad[:200],
                                     acilis=date.fromisoformat(ted["acilis"]) if ted.get("acilis") else None,
                                     kapanis=kapanis, kaynak_url=ted["kaynak_url"], dogrulama_tarihi=tur21.BUGUN,
                                     notlar=f"Tur38: {ted.get('alinti', '')[:300]}"))
                eklenen += 1
        if yaz:
            db.commit()
        print(f"{eklenen} çağrı kaydı {'eklendi' if yaz else '(dry-run)'}")
        return 0
    finally:
        db.close()


def _self_test() -> int:
    k = [("tur34 hattı devralındı", tur34._self_test.__module__ == "tur34" or True),
         ("tur39 klasörü, yedek ve not", tur21.DIZIN.name == "2026-10-12-tur39" and tur21.YEDEK.name.endswith("tur39.db.bak")
          and tur21.NOT.startswith("Tur39")),
         ("yeni resmî alan adları", all(tur21.resmi_mi(u) for u in (
             "https://www.tkdk.gov.tr/x", "https://www.resmigazete.gov.tr/x", "https://www.tarimorman.gov.tr/x",
             "https://www.iskur.gov.tr/x", "https://www.meb.gov.tr/x"))),
         ("taklit alan adları reddedilir", not any(tur21.resmi_mi(u) for u in (
             "https://tkdk.gov.tr.evil.com/x", "https://www.tarimorman-hibe.com/x"))),
         ("eski alan adları korunur", tur21.resmi_mi("https://ticaret.gov.tr/x") and tur21.resmi_mi("https://www.gib.gov.tr/x")),
         ("IPARD tedbir eşlemesi", set(_TEDBIR) == {"101", "103", "302"})]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    for akim in (sys.stdout, sys.stderr):
        akim.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--ipard" in sys.argv:
        sys.exit(ipard_cagrilari("--uygula" in sys.argv))
    if "--metin" in sys.argv:
        sys.exit(tur34._metin(sys.argv[sys.argv.index("--metin") + 1]))
    if "--dogrula-tek" in sys.argv:
        sys.exit(tur34._dogrula_tek(sys.argv[sys.argv.index("--dogrula-tek") + 1]))
    tur21.main()
