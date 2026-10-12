"""Tur 35 — persona denemesinin (docs/olcum/2026-10-12-persona) ortaya çıkardığı veri hataları (2026-10-12).

A. Ticaret Bakanlığı Karar destekleri (5973, 5986, 10962) "şirket"i TTK md.124 şirketleri ve kooperatifler diye tanımlar;
   şahıs işletmesi ve şirketi olmayan girişimci yararlanamaz (5986'da şahıs yalnız E-İhracat Konsorsiyumu üzerinden).
   187-196 kayıtlarında yapılandırılmış şirket türü kısıtı vardı; sonradan eklenen kayıtlarda (tur32-34) yoktu ve
   şahıs e-ticaret mağazasına fuar, heyet, pazara giriş desteği "engel yok" diye sunuluyordu (hakem D, senaryo 29/32).
   -> uygunluk_kriterleri.sirket_turleri = limited, anonim, kooperatif; kontrol listesinde şirket şartı yoksa aynı
      Kararın doğrulanmış tanım maddesi (alıntılı) eklenir.
B. 2026 bitkisel üretim destekleri (kanıt: docs/olcum/2026-10-12-tur34/TARIM_2026_KANIT.md):
   - tutari_min alanları 310 TL'den kalmaydı (77: 62, 79: 310, 160: 620, 161: 310) -> 367 TL ile.
   - 161 Meyve-Sebze kaydı fındığı 1. kategori 367 TL/da gibi gösteriyordu; fındık Tablo 1'de 3. kategori (1,5 ->
     550,50 TL/da) ve yalnız fındık üretimine izin verilen ilçelerdeki parsellere ödenir (8859 m.6/4, 11781 m.4).
   - 160 Hububat kaydı (tur20) 8859'un 2024 ilk hâlinin tablolarıyla yazılmıştı. 10394 sayılı Karar (RG 14.09.2025,
     1/1/2026'dan geçerli) tabloları değiştirdi: mısır (dane) 2. kategori (1,3), yulaf/çavdar/tritikale birinci grup
     yem bitkisi (1,0), sertifikalı arpa/buğday tohumu 0,56. Bakanlığın 2026 birim fiyat tablosu da böyle.
C. Hedef kitle ve başvuran türü: TİM Wings yalnız kadın ihracatçılara (başlık); KOSGEB girişim sermayesi fonu
   programına portföy yönetim şirketleri başvurur (kayıttaki şart); 10962 m.38-41 ("Destek Programlarının Yürütülmesi
   ile Hizmet Sektörlerinin Geliştirilmesi ve Tanıtılması") TİM ve ihracatçı birliklerine verilir — işletme
   profillerine önerilmez (araci_kurulus), şirket şartı maddesi bu kayıtlara eklenmez.

    python scripts/fix_veri_2026_10_12_persona_tur35.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_12_persona_tur35.py --uygula     (önce yedek alır; tekrar çalıştırılırsa değişiklik yok)
    python scripts/fix_veri_2026_10_12_persona_tur35.py --self-test
"""
import argparse
import copy
import re
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur35 2026-10-12"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur35.db.bak"
SIRKET = ["limited", "anonim", "kooperatif"]
KARAR = re.compile(r"\b(5973|5986|10962) sayılı Karar", re.I)   # "5986 Sayılı Karar" (162) da
RG11781 = "https://www.resmigazete.gov.tr/eskiler/2026/09/20260908-7.pdf"
DEGER = 367.0

# Kararın "şirket/yararlanıcı" tanımı — aynı Kararın daha önce doğrulanmış kayıtlarındaki maddeler (187, 192, 298).
TANIM = {
    "5973": {"tur": "sart", "metin": "Şirket olmak: 6102 sayılı TTK md.124'teki şirketler (kollektif, komandit, anonim, "
             "limited) ya da ticari/sınai faaliyette bulunan kooperatif (Karar m.2); şahıs işletmesi kapsam dışı",
             "alinti": "maddesinde belirtilen şirketler ile 24/4/1969 tarihli ve 1163 sayılı Kooperatifler Kanunu ile",
             "kaynak_url": "https://ticaret.gov.tr/data/69afdacb269de120c032b73a/5973%20Say%C4%B1l%C4%B1%20Karar.pdf#madde-3",
             "kaynak_tarihi": "2026-10-09", "dogrulandi": True},
    "5986": {"tur": "sart", "metin": "Şirket olmak: 6102 sayılı TTK md.124'teki şirketler ya da ticari/sınai faaliyette "
             "bulunan kooperatif (5986 sayılı Karar m.2); şahıs işletmesi doğrudan yararlanamaz",
             "alinti": "belirtilen şirketler ile 24/4/1969 tarihli ve 1163 sayılı Kooperatifler Kanunu ile 1/6/2000 tarihli ve",
             "kaynak_url": "https://ticaret.gov.tr/data/632b13e013b8767974670b91/E-ihracat%20Karar.pdf#madde-4",
             "kaynak_tarihi": "2026-10-09", "dogrulandi": True},
    "10962": {"tur": "sart", "metin": "Şirket ya da kooperatif olmak: Türkiye'de yerleşik, Türk Ticaret Kanunu hükümlerine "
              "göre kurulmuş şirket ya da Kooperatifler Kanunu çerçevesinde faaliyette bulunan kooperatif (10962 sayılı "
              "Karar m.2 yararlanıcı tanımı); şahıs işletmesi yararlanıcı tanımına girmez",
              "alinti": "Kanunu hükümlerine göre kurulmuş şirket i, 24/4/1969 tarihli ve 1163 sayılı Kooperatifler Kanunu "
                        "hükümleri çerçevesinde faaliyette bulunan kooperatifi,",
              "kaynak_url": "https://ticaret.gov.tr/data/69a9d756269de18b843851b7/%C3%87er%C3%A7eve%20Karar.pdf",
              "kaynak_tarihi": "2026-10-12", "dogrulandi": True},
}
ARACI_BASLIK = re.compile(r"^Destek Programlarının Yürütülmesi ile Hizmet Sektörlerinin")
_SIRKET_SARTI = re.compile(r"^\s*Şirket (?:olmak|ya da kooperatif)|şahıs işletme", re.I)


def tl(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


FINDIK = (f"Fındık Tablo 1'de 3. kategoridedir: katsayı 1,5 → {tl(1.5 * DEGER)} TL/da; fındıkta temel destek yalnız "
          "fındık üretimine izin verilen ilçelerdeki parsellere ödenir.")
TARIM = {
    77: dict(tutari_min=round(0.2 * DEGER, 2)),
    79: dict(tutari_min=DEGER),
    160: dict(tutari_min=round(2 * DEGER, 2), tutari_max=round(2 * 1.3 * DEGER, 2),
              tesvil_tutari=(f"Dekar başına {tl(2 * DEGER)}–{tl(2 * 1.3 * DEGER)} TL (2026): temel destek + planlı üretim "
                             f"desteği; mercimek, nohut ile birinci grup yem bitkisi sayılan yulaf, çavdar, tritikale katsayı "
                             f"1,0 → {tl(2 * DEGER)} TL/da; arpa, buğday, mısır (dane) 1,3 → {tl(2 * 1.3 * DEGER)} TL/da. "
                             "Sertifikalı tohum desteği ayrıca."),
              tutari_hesaplama_formulu=(
                  f"Temel destek (Tablo 1) + planlı üretim desteği (Tablo 2, planlama kapsamındaki ürünü havzasında "
                  f"üretene), her biri katsayı × {tl(DEGER)} TL: 1. kategori (mercimek, nohut; yulaf, çavdar, tritikale "
                  f"birinci grup yem bitkisi olarak) 1,0 → {tl(DEGER)} + {tl(DEGER)}; 2. kategori (arpa, buğday, mısır dane) "
                  f"1,3 → {tl(1.3 * DEGER)} + {tl(1.3 * DEGER)}. Sertifikalı tohum (Tablo 4): arpa, buğday, çavdar, "
                  f"tritikale, yulaf 0,56 → {tl(0.56 * DEGER)}; mercimek, nohut 0,4 → {tl(0.4 * DEGER)} TL/da. "
                  "Mercimek/nohutta havza ilavesi 2027'den geçerlidir. Dayanak: 8859 sayılı CB Kararı, 10394 sayılı "
                  "Kararla değişik tablolar (RG 14.09.2025, 1/1/2026'dan geçerli); destek katsayı değeri 2026 için "
                  f"{tl(DEGER)} TL/da (11781 sayılı CB Kararı, RG 08.09.2026, m.1/a, 1.1.2026'dan geçerli).")),
    161: dict(tutari_min=DEGER,
              # Fındık cümlesi yalnız formülde: tutar metni her meyve-sebze üreticisine gösterilir (çilek
              # üreticisine fındık notu gürültüydü); fındığın kendi kaydı var (Fındık Temel Desteği, tur34).
              tesvil_tutari=(f"Dekar başına {tl(DEGER)} TL temel destek (2026, 1. kategori 'diğer ürünler'); fidan "
                             f"kullanım desteği ayrıca {tl(2 * DEGER)} TL/da (standart) veya {tl(5 * DEGER)} TL/da "
                             "(sertifikalı)."),
              _formul_ek=(f" {FINDIK} Dayanak: 8859 sayılı Karar Tablo 1 ve m.6/4 (11781 sayılı Kararın 4 üncü maddesiyle "
                          "değişik, 1/1/2025'ten geçerli).")),
}
FINDIK_MADDE = {"tur": "sart", "metin": "Fındık üreticisiyseniz: parseliniz fındık üretimine izin verilen bir ilçede "
                "olmalı; izin verilen ilçeler dışında fındık üretilen parsellere temel destek ödenmez (8859 sayılı Karar "
                "m.6/4, 11781 sayılı Kararla değişik)", "alinti": None, "kaynak_url": RG11781,
                "kaynak_tarihi": "2026-10-12", "dogrulandi": False}


KRITER = {
    # (kayıt id, beklenen başlık parçası) -> eklenecek uygunluk kriterleri
    (288, "TİM Wings"): {"exclusive_target_group": True, "target_group_tags": ["kadin_girisimci"]},
    (264, "Girişim Sermayesi Yatırım Fonları"): {"araci_kurulus": True},
    # GVK 20/B: işletmesi olmayan gerçek kişi geliştirici de yararlanır (istisna tam da bunun içindir).
    (327, "mükerrer madde 20/B"): {"sirket_turleri": ["sahis", "yok"]},
    # TURWIB: "kadın yönetici bulunan işletmelere destek" (kayıt özeti, EBRD kaynağı); şart olarak yazılmadığı için
    # zorunlu değil, öncelik etiketi.
    (146, "TURWIB"): {"target_group_tags": ["kadin_girisimci"]},
    # Meyve-sebze temel desteği 1. kategori "diğer ürünler" içindir; Tablo 1'de başka kategorideki ürünler (fındık 3.
    # kategori vb.) kendi kaydındadır (persona denemesi: fındık üreticisine iki farklı dekar tutarı gösteriliyordu).
    (161, "Meyve-Sebze Üretim Destekleri"): {"urun_haric": [
        "fındık", "çay", "ayçiçeği", "kolza", "kanola", "fasulye", "soya", "çeltik", "pamuk", "arpa", "buğday",
        "mısır"]},
    # Lisanslı depo kira desteği yalnız 8859 Tablo 10 ürünlerine (kayıt başlığı "fındık dahil"; çilek listede yok).
    (364, "Lisanslı Depoda Muhafaza Edilen Ürünler"): {"urun_listesi": [
        "buğday", "arpa", "yulaf", "çavdar", "mısır", "çeltik", "pirinç", "mercimek", "nohut", "fasulye", "soya",
        "ayçiçeği", "pamuk", "fındık", "antepfıstığı", "kayısı", "üzüm", "zeytin"]},
    # Fidan desteği yalnız 8859 Tablo 6 türlerine (kaydın tutar metninde sayılı; app/tarim_destek_2026.FIDAN_URUNLERI)
    (365, "Sertifikalı/Standart Fidan Kullanım Desteği"): {"urun_listesi": [
        "altıntop", "armut", "asma", "ayva", "badem", "ceviz", "dut", "elma", "erik", "fındık", "incir", "kayısı",
        "kestane", "kiraz", "kivi", "limon", "mandarin", "mandalina", "nektarin", "pikan cevizi", "portakal",
        "şeftali", "trabzon hurması", "vişne", "zeytin"]},
}


def _not(t, metin: str) -> None:
    ek = f"{NOT}: {metin}"
    if ek not in (t.durum_notu or ""):
        t.durum_notu = (t.durum_notu + " | " if t.durum_notu else "") + ek


def plan(tum: list) -> list[tuple]:
    """(kayıt, alan, eski, yeni) değişiklik listesi; uygulanmış kayıtlar listeye girmez (idempotent)."""
    p = []
    for t in tum:
        if t.kurum != "Ticaret Bakanlığı" or t.aktif_mi is False:
            continue
        m = KARAR.search(t.baslik or "")
        if not m:
            continue
        if ARACI_BASLIK.search(t.baslik or ""):
            k = {a: v for a, v in (t.uygunluk_kriterleri or {}).items() if a != "sirket_turleri"}
            k["araci_kurulus"] = True
            if k != (t.uygunluk_kriterleri or {}):
                p.append((t, "uygunluk_kriterleri", t.uygunluk_kriterleri, k))
            kl = [x for x in (t.kontrol_listesi or []) if x not in TANIM.values()]
            if kl != list(t.kontrol_listesi or []):
                p.append((t, "kontrol_listesi", t.kontrol_listesi, kl))
            continue
        k = dict(t.uygunluk_kriterleri or {})
        if not k.get("sirket_turleri"):
            k["sirket_turleri"] = SIRKET
            p.append((t, "uygunluk_kriterleri", t.uygunluk_kriterleri, k))
        kl = list(t.kontrol_listesi or [])
        if not any(_SIRKET_SARTI.search(x.get("metin") or "") for x in kl if x.get("tur") == "sart"):
            p.append((t, "kontrol_listesi", t.kontrol_listesi, [copy.deepcopy(TANIM[m.group(1)])] + kl))
    for t in tum:
        for (i, parca), ek in KRITER.items():
            if t.id == i and parca in (t.baslik or ""):
                k = dict(t.uygunluk_kriterleri or {})
                if any(k.get(a) != v for a, v in ek.items()):
                    p.append((t, "uygunluk_kriterleri", t.uygunluk_kriterleri, {**k, **ek}))
    for t in tum:
        if t.id not in TARIM:
            continue
        for alan, yeni in TARIM[t.id].items():
            if alan == "_formul_ek":
                if yeni.strip() not in (t.tutari_hesaplama_formulu or ""):
                    p.append((t, "tutari_hesaplama_formulu", t.tutari_hesaplama_formulu,
                              (t.tutari_hesaplama_formulu or "") + yeni))
            elif getattr(t, alan) != yeni:
                p.append((t, alan, getattr(t, alan), yeni))
        if t.id == 161 and not any("fındık" in (x.get("metin") or "") for x in t.kontrol_listesi or []):
            p.append((t, "kontrol_listesi", t.kontrol_listesi, list(t.kontrol_listesi or []) + [dict(FINDIK_MADDE)]))
    return p


def uygula(db, dry_run: bool = True) -> int:
    from app.models import Tesvik
    from sqlalchemy.orm.attributes import flag_modified
    p = plan(db.query(Tesvik).all())
    for t, alan, eski, yeni in p:
        print(f"[{t.id:3}] {alan:26} {str(eski)[:60]!r} -> {str(yeni)[:90]!r}")
        if not dry_run:
            setattr(t, alan, yeni)
            flag_modified(t, alan)
            _not(t, f"{alan} güncellendi (şirket türü kısıtı / 2026 tarım tutarları; kanıt docs/olcum/2026-10-12-tur34/"
                    "TARIM_2026_KANIT.md ve aynı Kararın tanım maddesi)")
    if not dry_run:
        db.commit()
    print(f"\n{len(p)} değişiklik ({'dry-run' if dry_run else 'uygulandı'}), {len({t.id for t, *_ in p})} kayıt")
    return len(p)


def _self_test() -> int:
    from types import SimpleNamespace as N
    tb = lambda i, b, **kw: N(id=i, kurum="Ticaret Bakanlığı", baslik=b, aktif_mi=True,  # noqa: E731
                              uygunluk_kriterleri=kw.get("k"), kontrol_listesi=kw.get("kl", []), durum_notu=None,
                              tesvil_tutari=None, tutari_min=None, tutari_hesaplama_formulu=None)
    fuar = tb(316, "Yurt İçi Fuar Desteği (5973 sayılı Karar m.8)")
    hazir = tb(187, "Pazara Giriş Belgesi Desteği (5973 sayılı Karar m.3)", k={"sirket_turleri": SIRKET},
               kl=[TANIM["5973"]])
    hizmet = tb(298, "Hizmet Sektörleri Atılım Programı — Dijital Ürün (10962 sayılı Karar m.17)")
    baska = tb(1, "Kadın Kooperatifleri Programı")
    tim = tb(355, "Destek Programlarının Yürütülmesi ile Hizmet Sektörlerinin Geliştirilmesi ve Tanıtılması — X "
                  "(10962 sayılı Karar m.38)", k={"sirket_turleri": SIRKET}, kl=[dict(TANIM["10962"])])
    p = plan([fuar, hazir, hizmet, baska, tim])
    meyve = N(id=161, kurum="Tarım Bakanlığı", baslik="Meyve-Sebze", aktif_mi=True, uygunluk_kriterleri={},
              kontrol_listesi=[], durum_notu=None, tesvil_tutari="eski", tutari_min=310.0,
              tutari_hesaplama_formulu="Sebze ve meyve 367,00 TL/da.")
    pm = plan([meyve])
    k = [("5973 kaydına şirket türü ve tanım maddesi", {(t.id, a) for t, a, *_ in p} >= {
             (316, "uygunluk_kriterleri"), (316, "kontrol_listesi")}),
         ("10962 tanımı alıntılı", any(t.id == 298 and a == "kontrol_listesi" and y[0]["alinti"] for t, a, _, y in p)),
         ("hazır kayıt ve Karar dışı kayıt değişmez", not any(t.id in (187, 1) for t, *_ in p)),
         ("m.38-41: aracı kuruluş, şirket şartı kalkar", any(t.id == 355 and a == "uygunluk_kriterleri"
                                                             and y.get("araci_kurulus") and "sirket_turleri" not in y
                                                             for t, a, _, y in p)
          and any(t.id == 355 and a == "kontrol_listesi" and y == [] for t, a, _, y in p)),
         ("fındık: 550,50 TL/da ve ilçe şartı formülde", any(a == "tutari_hesaplama_formulu" and "550,50" in y
                                                             and "ilçe" in y for _, a, _, y in pm)),
         ("alt sınır 367", any(a == "tutari_min" and y == 367.0 for _, a, _, y in pm)),
         ("hububat 2026: mısır 1,3 ve tohum 0,56", "mısır (dane) 1,3" in TARIM[160]["tesvil_tutari"]
          and "205,52" in TARIM[160]["tutari_hesaplama_formulu"] and TARIM[160]["tutari_min"] == 734.0),
         ("TİM Wings kadın hedef kitlesi", KRITER[(288, "TİM Wings")]["target_group_tags"] == ["kadin_girisimci"]),
         ("TANIM alıntıları kısa", all(len(v["alinti"]) <= 300 for v in TANIM.values()))]
    # idempotent: plan uygulanınca ikinci plan boş
    for t, a, _, y in p + pm:
        setattr(t, a, y)
    k.append(("ikinci çalıştırmada değişiklik yok", not plan([fuar, hazir, hizmet, baska, meyve, tim])))
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
    if a.uygula and not YEDEK.exists():
        shutil.copy2(Path(settings.DATABASE_URL.replace("sqlite:///", "")), YEDEK)
        print(f"yedek: {YEDEK}")
    db = SessionLocal()
    uygula(db, dry_run=not a.uygula)
    db.close()


if __name__ == "__main__":
    main()
