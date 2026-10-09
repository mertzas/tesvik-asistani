"""Tur 21 — TKDK IPARD III ve kalkınma ajansı programları (2026-10-10).

Girdi: docs/olcum/2026-10-10-tur21/kayit/<slug>.json (şema: YENI_KAYIT_SEMASI.md; araştırma ajanları hazırladı).
Hiçbir kayıt ajan beyanıyla girmez: her kaynak adresi bu betik tarafından indirilir (HTML ya da PDF) ve her alıntı
metinde aranır (boşluk/büyük-küçük harf normalize). Kurallar:
  - alintilar[] ve cagrilar[].alinti ve durum.alinti: biri bile doğrulanamazsa KAYIT REDDEDİLİR
  - tesvil_tutari içindeki her sayı, doğrulanmış bir alıntıda geçmeli; geçmeyen sayı varsa kayıt reddedilir
  - çağrının açılış/kapanış/ön kayıt tarihleri kendi alıntısında (gg.aa.yyyy ya da "g Ay yyyy") geçmeli
  - kontrol_listesi maddesi: alıntısı doğrulanmazsa madde düşer (kayıt girer)
  - kaynak alan adı yalnız resmî: tkdk.gov.tr, *ka.gov.tr / *.ka.gov.tr / kalkinma ajansı alanları, resmigazete.gov.tr,
    sanayi.gov.tr, yatirimadestek.gov.tr, tarimorman.gov.tr
Sonuç: docs/olcum/2026-10-10-tur21/dogrulama.json (kayıt başına kabul/ret ve sebep).

    python scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py --dogrula   (indirir, doğrular, dogrulama.json yazar; DB'ye dokunmaz)
    python scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py             (dry-run: kabul edilenleri gösterir)
    python scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py --uygula    (önce yedek; kabul edilenleri ekler)
    python scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py --self-test
"""
import argparse
import hashlib
import io
import json
import re
import shutil
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DIZIN = KOK / "docs/olcum/2026-10-10-tur21"
ONBELLEK = DIZIN / "kaynak"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur21.db.bak"
BUGUN = date(2026, 10, 10)
NOT = "Tur21 2026-10-10"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
# 26 kalkınma ajansının alan adları (çoğu .org.tr); rastgele .org.tr siteleri kabul edilmez.
AJANSLAR = ("istka|ankaraka|izka|bebka|marka|trakyaka|gmka|zafer|geka|baka|cka|dogaka|mevka|ahika|oran|bakka|kuzka|oka|"
            "doka|kudaka|serka|daka|fka|ika|karacadag|dika")
RESMI = re.compile(r"(^|\.)(tkdk\.gov\.tr|resmigazete\.gov\.tr|sanayi\.gov\.tr|yatirimadestek\.gov\.tr|tarimorman\.gov\.tr|"
                   rf"(?:{AJANSLAR})\.(?:gov|org)\.tr)$")
BICIM = {"proje", "kredi", "faiz_destegi", "kefalet", "bildirim_prim", "uretim_odeme", "belge_etuys", "gider_on_onay",
         "hisse_fon", "gotuyu_hibe", "diger"}
SEKTOR = {"genel", "arge", "ihracat", "imalat", "e-ticaret", "tarim", "hizmet"}
SIRKET = {"sahis", "limited", "anonim", "kooperatif", "yok"}
TUR = {"sart", "belge", "adim", "kural", "bilgi"}
AYLAR = ["ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık"]


def norm(s: str) -> str:
    s = (s or "").replace("i̇", "i").replace("’", "'").replace("“", '"').replace("”", '"').replace(" ", " ")
    return re.sub(r"\s+", " ", s.replace("İ", "i").replace("I", "ı").lower()).strip()


def resmi_mi(url: str) -> bool:
    return bool(RESMI.search((urlparse(url).hostname or "").lower()))


def metin_al(url: str) -> tuple[str, str | None]:
    """URL'nin metni (önbellekli). HTML: görünür metin; PDF: metin katmanı."""
    import requests
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    yol = ONBELLEK / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".txt")
    if yol.exists():
        return yol.read_text(encoding="utf-8"), None
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        r.raise_for_status()
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"[:200]
    try:
        if "pdf" in r.headers.get("Content-Type", "") or r.content[:4] == b"%PDF":
            from pypdf import PdfReader
            metin = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages)
        else:
            from bs4 import BeautifulSoup
            s = BeautifulSoup(r.content.decode(r.encoding or r.apparent_encoding or "utf-8", errors="replace"), "html.parser")
            for x in s(["script", "style", "noscript"]):
                x.decompose()
            metin = s.get_text("\n")
    except Exception as e:
        return "", f"ayrıştırma {type(e).__name__}: {e}"[:200]
    yol.write_text(f"KAYNAK: {url}\nİNDİRME: {BUGUN}\n\n{metin}", encoding="utf-8")
    time.sleep(0.5)
    return metin, None


def tarih_metinleri(g: str) -> list[str]:
    d = date.fromisoformat(g)
    return [d.strftime("%d.%m.%Y"), f"{d.day}.{d.month:02d}.{d.year}", d.strftime("%d/%m/%Y"),
            f"{d.day} {AYLAR[d.month - 1]} {d.year}", f"{d.day:02d} {AYLAR[d.month - 1]} {d.year}"]


def sayilar(metin: str) -> set[str]:
    """'%50', '1.500.000', '2,5' gibi sayılar (yıl ve tek haneli sıra numaraları hariç)."""
    out = set()
    for m in re.finditer(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?", metin or ""):
        x = m.group(0)
        if re.fullmatch(r"20\d\d", x) or (x.isdigit() and len(x) == 1):
            continue
        out.add(x)
    return out


def dogrula_kayit(k: dict, getir=metin_al) -> dict:
    sorun, uyari = [], []
    for alan in ("slug", "kurum", "baslik", "kaynak_url"):
        if not (k.get(alan) or "").strip():
            sorun.append(f"{alan} boş")
    if k.get("basvuru_bicimi") not in BICIM:
        sorun.append(f"basvuru_bicimi geçersiz: {k.get('basvuru_bicimi')}")
    if not set(k.get("sektorler") or []) <= SEKTOR or not k.get("sektorler"):
        sorun.append(f"sektorler geçersiz: {k.get('sektorler')}")
    if not set(k.get("sirket_turleri") or []) <= SIRKET:
        sorun.append(f"sirket_turleri geçersiz: {k.get('sirket_turleri')}")
    urller = {k.get("kaynak_url")} | {a.get("kaynak_url") for a in k.get("alintilar") or []} \
        | {c.get("kaynak_url") for c in k.get("cagrilar") or []} | {(k.get("durum") or {}).get("kaynak_url")} \
        | {m.get("kaynak_url") for m in k.get("kontrol_listesi") or []}
    urller.discard(None)
    metinler = {}
    for u in urller:
        if not resmi_mi(u):
            sorun.append(f"resmî olmayan kaynak: {u}")
            continue
        m, h = getir(u)
        if h or not m.strip():
            sorun.append(f"indirilemedi: {u} ({h or 'boş'})")
        metinler[u] = norm(m)

    def var(alinti, url):
        return bool(alinti) and url in metinler and norm(alinti) in metinler[url]

    dogrulanmis = []
    for a in k.get("alintilar") or []:
        if var(a.get("alinti"), a.get("kaynak_url")):
            dogrulanmis.append(a["alinti"])
        else:
            sorun.append(f"alıntı doğrulanamadı: {a.get('iddia', '')[:50]} — '{(a.get('alinti') or '')[:60]}'")
    d = k.get("durum") or {}
    if d.get("alinti"):
        if var(d["alinti"], d.get("kaynak_url")):
            dogrulanmis.append(d["alinti"])
        else:
            sorun.append("durum alıntısı doğrulanamadı")
    cagrilar = []
    for c in k.get("cagrilar") or []:
        if not var(c.get("alinti"), c.get("kaynak_url")):
            sorun.append(f"çağrı alıntısı doğrulanamadı: {c.get('ad')}")
            continue
        an = norm(c["alinti"])
        for alan in ("acilis", "kapanis", "on_kayit_son"):
            if c.get(alan) and not any(norm(x) in an for x in tarih_metinleri(c[alan])):
                sorun.append(f"çağrı {c.get('ad')}: {alan} {c[alan]} alıntıda yok")
        dogrulanmis.append(c["alinti"])
        cagrilar.append(c)
    kanit_sayi = set().union(*(sayilar(x) for x in dogrulanmis)) if dogrulanmis else set()
    eksik_sayi = sorted(sayilar(k.get("tesvil_tutari") or "") - kanit_sayi)
    if eksik_sayi:
        sorun.append(f"tesvil_tutari'nda alıntısız sayı: {eksik_sayi}")
    liste = []
    for m in k.get("kontrol_listesi") or []:
        if m.get("tur") in TUR and var(m.get("alinti"), m.get("kaynak_url") or k.get("kaynak_url")):
            liste.append(m)
        else:
            uyari.append(f"madde düştü (alıntı doğrulanamadı): {(m.get('metin') or '')[:50]}")
    return {"kabul": not sorun, "sorunlar": sorun, "uyarilar": uyari, "kontrol_listesi": liste, "cagrilar": cagrilar}


def _kucuk(il: str) -> str:
    return il.replace("İ", "i").replace("I", "ı").lower()


def kayitlar() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((DIZIN / "kayit").glob("*.json"))]


def uygula(db, sonuc: dict, dry_run: bool = True) -> int:
    from app.models import Tesvik, TesvikCagrisi
    n = 0
    for k in kayitlar():
        r = sonuc.get(k.get("slug"))
        if not r or not r["kabul"]:
            continue
        if db.query(Tesvik).filter(Tesvik.kaynak_url == k["kaynak_url"]).first():
            print(f"[{k['slug']}] aynı kaynak adresli kayıt var; atlandı")
            continue
        liste = [{"tur": m["tur"], "metin": m["metin"], "alinti": m["alinti"], "kaynak_url": m.get("kaynak_url") or k["kaynak_url"],
                  "kaynak_tarihi": str(BUGUN), "dogrulandi": True} for m in r["kontrol_listesi"]]
        if k.get("basvuru_yeri") and not any(m["tur"] == "adim" and m["metin"].startswith("Başvuruyu yap:") for m in liste):
            liste.append({"tur": "adim", "metin": f"Başvuruyu yap: {k['basvuru_yeri']}", "alinti": None,
                          "kaynak_url": k["kaynak_url"], "kaynak_tarihi": str(BUGUN), "dogrulandi": False})
        kriter = {"sektorler": k["sektorler"]}
        if k.get("bolge_kisitli"):
            kriter["bolge_kisitli"] = [_kucuk(x) for x in k["bolge_kisitli"]]
        if k.get("sirket_turleri"):
            kriter["sirket_turleri"] = k["sirket_turleri"]
        detay = (k.get("ozet") or "") + "\n\nResmî kaynaktan alıntılar:\n" + "\n".join(
            f"- {a['alinti']}" for a in k.get("alintilar") or [])
        print(f"[{k['slug']}] {k['kurum']} — {k['baslik'][:60]} · aktif={k.get('aktif_mi')} · çağrı={len(r['cagrilar'])} "
              f"· madde={len(liste)} · il={len(k.get('bolge_kisitli') or [])}")
        if not dry_run:
            t = Tesvik(kurum=k["kurum"], baslik=k["baslik"], ozet=k.get("ozet") or "", detay=detay, kaynak_url=k["kaynak_url"],
                       aktif_mi=k.get("aktif_mi"), uygunluk_kriterleri=kriter, tesvil_tutari=k.get("tesvil_tutari"),
                       basvuru_yeri=k.get("basvuru_yeri"), basvuru_suresi=k.get("basvuru_suresi"),
                       basvuru_sartlari=[m["metin"] for m in liste if m["tur"] == "sart"],
                       gerekli_belgeler=[m["metin"] for m in liste if m["tur"] == "belge"],
                       kontrol_listesi=liste, basvuru_bicimi=k["basvuru_bicimi"],
                       durum_notu=f"{NOT}: resmî kaynaktan eklendi; durum: {(k.get('durum') or {}).get('metin', '')}; "
                                  f"kanıt docs/olcum/2026-10-10-tur21/kayit/{k['slug']}.json + dogrulama.json")
            db.add(t)
            db.flush()
            for c in r["cagrilar"]:
                db.add(TesvikCagrisi(tesvik_id=t.id, ad=c["ad"], acilis=date.fromisoformat(c["acilis"]) if c.get("acilis") else None,
                                     kapanis=date.fromisoformat(c["kapanis"]) if c.get("kapanis") else None,
                                     on_kayit_son=date.fromisoformat(c["on_kayit_son"]) if c.get("on_kayit_son") else None,
                                     kaynak_url=c["kaynak_url"], dogrulama_tarihi=BUGUN, notlar=c.get("notlar")))
        n += 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} yeni program")
    return n


def _self_test() -> int:
    sayfa = {"https://www.tkdk.gov.tr/a": "Hibe oranı %50 ile %70 arasındadır. Başvurular 01.09.2026 - 30.10.2026 tarihleri arasında.",
             "https://haber.com/x": "uydurma"}
    getir = lambda u: (sayfa.get(u, ""), None if u in sayfa else "404")  # noqa: E731
    temel = {"slug": "t", "kurum": "TKDK", "baslik": "B", "kaynak_url": "https://www.tkdk.gov.tr/a", "basvuru_bicimi": "proje",
             "sektorler": ["tarim"], "tesvil_tutari": "%50-%70 hibe",
             "alintilar": [{"iddia": "oran", "alinti": "Hibe oranı %50 ile %70", "kaynak_url": "https://www.tkdk.gov.tr/a"}],
             "cagrilar": [{"ad": "2026", "acilis": "2026-09-01", "kapanis": "2026-10-30", "kaynak_url": "https://www.tkdk.gov.tr/a",
                           "alinti": "Başvurular 01.09.2026 - 30.10.2026"}],
             "kontrol_listesi": [{"tur": "sart", "metin": "x", "alinti": "uydurma madde", "kaynak_url": "https://www.tkdk.gov.tr/a"}]}
    r = dogrula_kayit(temel, getir)
    k = [("geçerli kayıt kabul, alıntısız madde düşer", r["kabul"] and r["kontrol_listesi"] == [] and len(r["uyarilar"]) == 1),
         ("tutardaki alıntısız sayı reddedilir", not dogrula_kayit({**temel, "tesvil_tutari": "%50-%80"}, getir)["kabul"]),
         ("çağrı tarihi alıntıda yoksa reddedilir", not dogrula_kayit({**temel, "cagrilar": [{**temel["cagrilar"][0], "kapanis": "2026-11-30"}]},
                                                                     getir)["kabul"]),
         ("resmî olmayan kaynak reddedilir", not dogrula_kayit({**temel, "alintilar": [{"iddia": "o", "alinti": "uydurma",
                                                                                         "kaynak_url": "https://haber.com/x"}]}, getir)["kabul"]),
         ("resmî alan adları: ajanslar .org.tr dahil, rastgele site değil",
          resmi_mi("https://www.tkdk.gov.tr/x") and resmi_mi("https://www.mevka.org.tr/x") and resmi_mi("https://ankaraka.org.tr/x")
          and resmi_mi("https://www.geka.gov.tr/x") and not resmi_mi("https://www.danismanlik.org.tr/x")
          and not resmi_mi("https://sahteoka.org.tr/x")),
         ("tarih biçimleri", "1 eylül 2026" in tarih_metinleri("2026-09-01") and "01.09.2026" in tarih_metinleri("2026-09-01")),
         ("sayılar: yıl hariç", sayilar("2026 yılında %50 ve 1.500.000 TL") == {"50", "1.500.000"})]
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
    yol = DIZIN / "dogrulama.json"
    if a.dogrula:
        sonuc = {}
        for k in kayitlar():
            r = dogrula_kayit(k)
            sonuc[k.get("slug")] = r
            print(f"[{'KABUL' if r['kabul'] else 'RET  '}] {k.get('slug')}" + ("" if r["kabul"] else f" — {r['sorunlar'][:3]}"))
        yol.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nkabul {sum(r['kabul'] for r in sonuc.values())}/{len(sonuc)}")
        return
    sonuc = json.loads(yol.read_text(encoding="utf-8"))
    from app.models import SessionLocal, settings
    if a.uygula and not YEDEK.exists():
        shutil.copy2(Path(settings.DATABASE_URL.replace("sqlite:///", "")), YEDEK)
        print(f"yedek: {YEDEK}")
    uygula(SessionLocal(), sonuc, dry_run=not a.uygula)


if __name__ == "__main__":
    main()
