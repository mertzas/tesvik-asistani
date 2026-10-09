"""Uygunluk ölçümü 3. adım: sistemin önerileri, resmî kriterlere göre gerçekten başvurulabilir mi?

  python docs/olcum/2026-10-09-uygunluk/uygunluk_olc.py            -> sonuc.json + ozet.md
  python docs/olcum/2026-10-09-uygunluk/uygunluk_olc.py --self-test

Girdi: kriter/<id>.json (alıntısı doğrulanmış kriterler; kriter_dogrula.py), 12 gerçek profil (aşağıda).
Her profilin iki görünümü var:
  - GERÇEK: işletmenin tüm nitelikleri (borç, önceki destek, belgeler, kurucu, yatırım tutarı ...): hakikat.
  - SİSTEM: yalnız uygulamanın profil formunda bulunan alanlar (FinancialProfile).
Karar (yalnız zorunlu kriterlerle, bileşenlerden en iyisi):
  UYGUN_DEGIL  bir zorunlu kriter sağlanmıyor ve sonradan giderilemez
  HAZIRLIKLA   yalnız edinilebilir kayıt/belge eksik (KOSGEB/DYS kaydı, e-imza, sertifika eğitimi ...)
  BILINMIYOR   karar için veri yok ya da şart makine okunur değil ("diger")
  UYGUN        bütün zorunlu kriterler sağlanıyor
Sistemin önerisi: app.matching.esles(profil, limit=30); ilk 10 "öneri" sayılır.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date

KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, KOK)
OUT = os.path.dirname(os.path.abspath(__file__))
BUGUN = date(2026, 10, 9)

# Sonradan edinilebilir kayıt/belge: eksikliği "uygun değil" değil "hazırlıkla" sayılır.
GIDERILEBILIR = {"kosgeb_kaydi", "dys_kaydi", "e_imza", "iskur_kaydi", "cks_kaydi", "ihracatci_birligi_uyeligi",
                 "tobb_uyeligi", "banka_kredisi", "teminat_mektubu", "dijital_olgunluk_raporu", "teknogirisim_rozeti",
                 "uygulamali_girisimcilik_sertifikasi", "marka_tescili"}
SISTEM_ALANLARI = {"sirket_turu", "olcek", "calisan_sayisi", "yillik_ciro_tl", "isletme_yasi_yil", "nace", "faaliyet", "il",
                   "bolge_9903", "trl", "arazi_dekar", "urun"}
KISIM = [("A", 1, 3), ("B", 5, 9), ("C", 10, 33), ("D", 35, 35), ("E", 36, 39), ("F", 41, 43), ("G", 45, 47), ("H", 49, 53),
         ("I", 55, 56), ("J", 58, 63), ("K", 64, 66), ("L", 68, 68), ("M", 69, 75), ("N", 77, 82), ("P", 85, 85),
         ("Q", 86, 88), ("R", 90, 93), ("S", 94, 96)]

# sistem: FinancialProfile alanları; gercek: KRITER_SEMASI alanları (+ sistem alanlarından türetilenler otomatik)
PROFILLER = [
    dict(ad="Denizli şahıs e-ticaret (kadın)", sistem=dict(sektor="e-ticaret", bolge="Denizli", calisan_sayisi=2, yillik_ciro=3.2e6,
         nace_kodu="47.91", sirket_turu="sahis", kurulus_tarihi=date(2023, 5, 1), hedefler=["ihracat", "finansman"]),
         gercek=dict(faaliyet={"ticaret"}, hedef_grup={"kadin", "ihracatci"}, kurucu_yasi=31, belge={"e_imza"},
                     vergi_sgk_borcu_yok=True, onceki_destek_yok=True, baska_sirkette_ortak_degil=True, onceki_yil_ihracat_usd=40_000)),
    dict(ad="İzmir Ltd örme tekstil Ar-Ge", sistem=dict(sektor="imalat", bolge="İzmir", calisan_sayisi=12, yillik_ciro=60e6,
         nace_kodu="13.91", sirket_turu="limited", kurulus_tarihi=date(2017, 3, 1), hedefler=["arge", "ihracat"]),
         gercek=dict(faaliyet={"imalat"}, hedef_grup={"ihracatci"}, kurucu_yasi=48, belge={"kosgeb_kaydi", "dys_kaydi",
                     "ihracatci_birligi_uyeligi", "e_imza", "tobb_uyeligi"}, vergi_sgk_borcu_yok=True, onceki_destek_yok=False,
                     baska_sirkette_ortak_degil=True, onceki_yil_ihracat_usd=1_200_000, trl=4)),
    dict(ad="Konya Ltd metal, SGK borcu var", sistem=dict(sektor="imalat", bolge="Konya", calisan_sayisi=28, yillik_ciro=85e6,
         nace_kodu="28.30", sirket_turu="limited", kurulus_tarihi=date(2011, 6, 1), hedefler=["yatirim", "ihracat"]),
         gercek=dict(faaliyet={"imalat"}, hedef_grup={"ihracatci"}, kurucu_yasi=55, belge={"kosgeb_kaydi", "e_imza", "tobb_uyeligi"},
                     vergi_sgk_borcu_yok=False, onceki_destek_yok=True, baska_sirkette_ortak_degil=True,
                     yatirim_tutari_tl=10_050_000, onceki_yil_ihracat_usd=600_000)),
    dict(ad="Ankara şirketsiz öğrenci girişimci", sistem=dict(sektor="arge", bolge="Ankara", calisan_sayisi=0, yillik_ciro=0,
         nace_kodu="62.01", sirket_turu="yok", trl=4, hedefler=["arge"]),
         gercek=dict(faaliyet={"yazilim_bilisim"}, hedef_grup={"genc", "ogrenci"}, kurucu_yasi=24, belge={"e_imza"},
                     vergi_sgk_borcu_yok=True, onceki_destek_yok=True, baska_sirkette_ortak_degil=True)),
    dict(ad="Ankara şirketsiz, başka şirkette ortak", sistem=dict(sektor="arge", bolge="Ankara", calisan_sayisi=0, yillik_ciro=0,
         nace_kodu="62.01", sirket_turu="yok", trl=4, hedefler=["arge"]),
         gercek=dict(faaliyet={"yazilim_bilisim"}, hedef_grup=set(), kurucu_yasi=41, belge={"e_imza"},
                     vergi_sgk_borcu_yok=True, onceki_destek_yok=True, baska_sirkette_ortak_degil=False)),
    dict(ad="Van A.Ş. otel yatırımı", sistem=dict(sektor="hizmet", bolge="Van", calisan_sayisi=25, yillik_ciro=30e6,
         nace_kodu="55.10", sirket_turu="anonim", kurulus_tarihi=date(2014, 4, 1), hedefler=["yatirim", "istihdam"]),
         gercek=dict(faaliyet={"turizm"}, hedef_grup=set(), kurucu_yasi=50, belge={"kosgeb_kaydi", "e_imza", "tobb_uyeligi"},
                     vergi_sgk_borcu_yok=True, onceki_destek_yok=True, baska_sirkette_ortak_degil=True,
                     yatirim_tutari_tl=85_000_000, ilave_istihdam=True)),
    dict(ad="Bursa büyük A.Ş. otomotiv", sistem=dict(sektor="imalat", bolge="Bursa", calisan_sayisi=400, yillik_ciro=2e9,
         nace_kodu="29.10", sirket_turu="anonim", kurulus_tarihi=date(1998, 1, 1), hedefler=["yatirim", "istihdam", "ihracat"]),
         gercek=dict(faaliyet={"imalat"}, hedef_grup={"ihracatci"}, kurucu_yasi=60, belge={"e_imza", "dys_kaydi",
                     "ihracatci_birligi_uyeligi", "tobb_uyeligi", "ar_ge_merkezi_veya_teknopark"}, vergi_sgk_borcu_yok=True,
                     onceki_destek_yok=False, baska_sirkette_ortak_degil=True, yatirim_tutari_tl=300_000_000,
                     onceki_yil_ihracat_usd=50_000_000, ilave_istihdam=True)),
    dict(ad="Hatay şahıs lokanta, 3 ilave işçi", sistem=dict(sektor="hizmet", bolge="Hatay", calisan_sayisi=4, yillik_ciro=3e6,
         nace_kodu="56.10", sirket_turu="sahis", kurulus_tarihi=date(2019, 9, 1), hedefler=["istihdam"]),
         gercek=dict(faaliyet={"hizmet", "turizm"}, hedef_grup=set(), kurucu_yasi=45, belge={"e_imza", "iskur_kaydi", "tobb_uyeligi"},
                     vergi_sgk_borcu_yok=True, onceki_destek_yok=True, baska_sirkette_ortak_degil=True, ilave_istihdam=True,
                     calisan_niteligi={"genc_18_29", "kadin", "issiz_iskur"})),
    dict(ad="Konya buğday çiftçisi", sistem=dict(sektor="tarim", bolge="Konya", calisan_sayisi=1, yillik_ciro=2.5e6,
         sirket_turu="sahis", arazi_buyuklugu_dekar=180, urun_turu="buğday", tarim_kategori="tahil_baklagil", hedefler=["makine"]),
         gercek=dict(faaliyet={"tarim"}, hedef_grup={"ciftci"}, kurucu_yasi=52, belge={"cks_kaydi", "e_imza"},
                     vergi_sgk_borcu_yok=True, onceki_destek_yok=True, baska_sirkette_ortak_degil=True, urun={"buğday"})),
    dict(ad="Afyon genç besici (büyükbaş)", sistem=dict(sektor="tarim", bolge="Afyonkarahisar", calisan_sayisi=1, yillik_ciro=1.8e6,
         sirket_turu="sahis", urun_turu="sığır", tarim_kategori="hayvancilik", hedefler=["hayvan"]),
         gercek=dict(faaliyet={"hayvancilik"}, hedef_grup={"ciftci", "genc"}, kurucu_yasi=27, belge={"cks_kaydi", "e_imza"},
                     vergi_sgk_borcu_yok=True, onceki_destek_yok=True, baska_sirkette_ortak_degil=True, urun={"sığır", "buzağı"})),
    dict(ad="İstanbul Ltd yazılım ihracatçısı", sistem=dict(sektor="arge", bolge="İstanbul", calisan_sayisi=12, yillik_ciro=20e6,
         nace_kodu="62.01", sirket_turu="limited", kurulus_tarihi=date(2022, 2, 1), trl=8, hedefler=["ihracat", "arge", "finansman"]),
         gercek=dict(faaliyet={"yazilim_bilisim"}, hedef_grup={"ihracatci"}, kurucu_yasi=35, belge={"kosgeb_kaydi", "e_imza",
                     "ar_ge_merkezi_veya_teknopark", "dys_kaydi"}, vergi_sgk_borcu_yok=True, onceki_destek_yok=True,
                     baska_sirkette_ortak_degil=True, onceki_yil_ihracat_usd=300_000)),
    dict(ad="Eskişehir kadın, şirketsiz, sertifikalı", sistem=dict(sektor="hizmet", bolge="Eskişehir", calisan_sayisi=0,
         yillik_ciro=0, nace_kodu="10.71", sirket_turu="yok", hedefler=["finansman", "istihdam"]),
         gercek=dict(faaliyet={"imalat", "hizmet"}, hedef_grup={"kadin"}, kurucu_yasi=34, belge={"uygulamali_girisimcilik_sertifikasi",
                     "e_imza"}, vergi_sgk_borcu_yok=True, onceki_destek_yok=True, baska_sirkette_ortak_degil=True)),
]


def _katla(x) -> str:
    """Türkçe harf katlama: ajanlar ürün adlarını ASCII yazdı ('bugday'), profil 'buğday' diyor."""
    return str(x).translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")).lower()


def _yas(kurulus) -> float | None:
    return round((BUGUN - kurulus).days / 365.25, 2) if kurulus else None


def gercek_profil(p: dict, yalniz_sistem: bool = False) -> dict:
    """Kriter alanlarına göre profil. yalniz_sistem: uygulamanın bildiği alanlar dışındakiler bilinmiyor (None)."""
    from app.kobi import kobi_sinifi
    from app.nace_9903 import il_bolgesi
    s = p["sistem"]
    g = {"sirket_turu": s.get("sirket_turu"), "olcek": kobi_sinifi(s.get("calisan_sayisi"), s.get("yillik_ciro")).sinif,
         "calisan_sayisi": s.get("calisan_sayisi"), "yillik_ciro_tl": s.get("yillik_ciro"),
         "isletme_yasi_yil": _yas(s.get("kurulus_tarihi")) if s.get("sirket_turu") != "yok" else None,
         "nace": s.get("nace_kodu"), "il": s.get("bolge"), "bolge_9903": il_bolgesi(s.get("bolge")), "trl": s.get("trl"),
         "arazi_dekar": s.get("arazi_buyuklugu_dekar"), "urun": {s["urun_turu"]} if s.get("urun_turu") else None}
    g.update(p["gercek"])
    if yalniz_sistem:
        g = {k: (v if k in SISTEM_ALANLARI else None) for k, v in g.items()}
        g["faaliyet"] = None  # sistemde sektör etiketi var ama şemadaki faaliyet alanı yok; NACE ile karar verilir
    return g


def _kisim(nace: str) -> str | None:
    m = re.match(r"(\d{2})", nace or "")
    if not m:
        return None
    n = int(m.group(1))
    return next((k for k, a, b in KISIM if a <= n <= b), None)


def kriter_sonucu(k: dict, g: dict) -> str:
    """'saglar' | 'saglamaz' | 'giderilebilir' | 'bilinmiyor' | 'elle'"""
    alan, kural = k["alan"], k["kural"]
    if alan == "diger":
        return "elle"
    if alan == "belge":
        b = g.get("belge")
        if b is None:
            return "bilinmiyor"
        if kural["gerekli"] in b:
            return "saglar"
        return "giderilebilir" if kural["gerekli"] in GIDERILEBILIR else "saglamaz"
    v = g.get(alan)
    if v is None:
        return "bilinmiyor"
    if alan == "nace":
        on = next(iter(kural.values()))
        eslesir = any(v.startswith(x) or (len(x) == 1 and x.isalpha() and _kisim(v) == x.upper()) for x in on)
        return "saglar" if eslesir == ("in_prefix" in kural) else "saglamaz"
    if alan == "onceki_destek_yok" and v is False:
        return "elle"  # yasak belirli programlarla çakışmayı kastediyor; "daha önce destek aldı" tek başına hüküm vermez
    if "esit" in kural:
        return "saglar" if v is True else "saglamaz"
    if "in" in kural or "not_in" in kural:
        liste = {_katla(x) for x in kural.get("in", kural.get("not_in"))}
        degerler = {_katla(x) for x in (v if isinstance(v, (set, list)) else [v])}
        if alan == "faaliyet" and "hayvancilik" in degerler:
            degerler.add("tarim")  # hayvancılık NACE 01.4, tarım kısmının (A) alt dalı
        kesisir = bool(degerler & liste)
        return "saglar" if kesisir == ("in" in kural) else "saglamaz"
    if "min" in kural and v < kural["min"]:
        return "saglamaz"
    if "max" in kural and v > kural["max"]:
        return "saglamaz"
    return "saglar"


def program_karari(kd: dict, gecerli: list[int], g: dict) -> dict:
    kriterler = [k for i, k in enumerate(kd.get("kriterler") or []) if i in gecerli and k.get("zorunlu")]
    bilesenler = kd.get("bilesenler") or [None]
    en_iyi = None
    sira = {"UYGUN": 0, "HAZIRLIKLA": 1, "BILINMIYOR": 2, "UYGUN_DEGIL": 3}
    for b in bilesenler:
        ilgili = [k for k in kriterler if k.get("bilesen") in (None, b)]
        sonuc = [(k, kriter_sonucu(k, g)) for k in ilgili]
        if any(s == "saglamaz" for _, s in sonuc):
            karar = "UYGUN_DEGIL"
        elif any(s in ("bilinmiyor", "elle") for _, s in sonuc):
            karar = "BILINMIYOR"
        elif any(s == "giderilebilir" for _, s in sonuc):
            karar = "HAZIRLIKLA"
        else:
            karar = "UYGUN"
        aday = dict(karar=karar, bilesen=b,
                    saglamayan=[f"{k['alan']}: {k['metin']}"[:120] for k, s in sonuc if s == "saglamaz"],
                    eksik_belge=[k["kural"]["gerekli"] for k, s in sonuc if s == "giderilebilir"],
                    bilinmeyen=[k["alan"] for k, s in sonuc if s == "bilinmiyor"],
                    elle=[k["metin"][:100] for k, s in sonuc if s == "elle"], zorunlu_kriter=len(ilgili))
        if en_iyi is None or sira[karar] < sira[en_iyi["karar"]]:
            en_iyi = aday
    return en_iyi


def olc():
    from app.matching import esles
    from app.models import FinancialProfile, SessionLocal, Tesvik
    db = SessionLocal()
    dog = json.load(open(os.path.join(OUT, "kriter", "dogrulama.json"), encoding="utf-8"))
    kd = {int(t): json.load(open(os.path.join(OUT, "kriter", f"{t}.json"), encoding="utf-8")) for t in dog}
    baslik = {t.id: t.baslik for t in db.query(Tesvik).all()}
    sonuc = []
    for p in PROFILLER:
        fp = FinancialProfile(**p["sistem"])
        es = esles(fp, db, limit=30)
        oneri = [e.tesvik.id for e in es]
        g, gs = gercek_profil(p), gercek_profil(p, yalniz_sistem=True)
        kararlar = {}
        for tid, d in kd.items():
            kg = program_karari(d, dog[str(tid)]["gecerli"], g)
            ks = program_karari(d, dog[str(tid)]["gecerli"], gs)
            kararlar[tid] = dict(gercek=kg, sistem_verisiyle=ks["karar"], sira=oneri.index(tid) + 1 if tid in oneri else None,
                                 baslik=baslik.get(tid, "?")[:70], bicim=d.get("basvuru_bicimi"))
        sonuc.append(dict(profil=p["ad"], ilk10=oneri[:10], kararlar=kararlar))
    json.dump(sonuc, open(os.path.join(OUT, "sonuc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=list)
    ozet_yaz(sonuc)


def ozet_yaz(sonuc):
    from collections import Counter
    sat = ["| Profil | İlk 10'da: uygun / hazırlıkla / bilinmiyor / **uygun değil** | Uygun değil örnekleri (sıra · program · şart) | "
           "Gerçekte uygun/hazırlıkla ama ilk 10'da yok |", "|---|---|---|---|"]
    top = Counter()
    sistem_karar = Counter()
    for s in sonuc:
        on = [(tid, s["kararlar"].get(tid)) for tid in s["ilk10"]]
        c = Counter(k["gercek"]["karar"] for _, k in on if k)
        top.update(c)
        sistem_karar.update(k["sistem_verisiyle"] for _, k in on if k)
        ud = [f"{k['sira']}·{k['baslik'][:32]}·{(k['gercek']['saglamayan'] or ['?'])[0][:55]}" for _, k in on if k and k["gercek"]["karar"] == "UYGUN_DEGIL"]
        kac = [f"{k['baslik'][:35]}{' (sıra ' + str(k['sira']) + ')' if k['sira'] else ''}" for tid, k in s["kararlar"].items()
               if k["gercek"]["karar"] in ("UYGUN", "HAZIRLIKLA") and (k["sira"] is None or k["sira"] > 10)]
        sat.append(f"| {s['profil']} | {c['UYGUN']} / {c['HAZIRLIKLA']} / {c['BILINMIYOR']} / **{c['UYGUN_DEGIL']}** | "
                   f"{'<br>'.join(ud) or '-'} | {len(kac)}: {'; '.join(kac[:4])}{' …' if len(kac) > 4 else ''} |")
    n = sum(top.values())
    sat += ["", f"Toplam ilk-10 önerisi {n}: UYGUN {top['UYGUN']} · HAZIRLIKLA {top['HAZIRLIKLA']} · BİLİNMİYOR {top['BILINMIYOR']} · "
            f"**UYGUN DEĞİL {top['UYGUN_DEGIL']} ({top['UYGUN_DEGIL'] / max(1, n):.0%})**",
            f"Aynı öneriler yalnız sistemin bildiği alanlarla değerlendirilseydi: {dict(sistem_karar)}"]
    neden, elle_say, yalniz_elle = Counter(), 0, 0
    for s in sonuc:
        for tid in s["ilk10"]:
            k = s["kararlar"].get(tid)
            if k and k["gercek"]["karar"] == "BILINMIYOR":
                neden.update(set(k["gercek"]["bilinmeyen"]))
                elle_say += bool(k["gercek"]["elle"])
                yalniz_elle += bool(k["gercek"]["elle"]) and not k["gercek"]["bilinmeyen"]
    sat += [f"BİLİNMİYOR nedenleri: makine okunur olmayan ('diğer') zorunlu şart içeren {elle_say} öneri "
            f"({yalniz_elle}'inde tek neden bu); gerçek profilde de bilinmeyen alanlar: {dict(neden.most_common())}"]
    open(os.path.join(OUT, "ozet.md"), "w", encoding="utf-8").write("\n".join(sat) + "\n")
    print("\n".join(sat))


def _self_test() -> int:
    g = gercek_profil(PROFILLER[2])
    kd = {"bilesenler": ["A", "B"], "kriterler": [
        {"alan": "olcek", "kural": {"in": ["mikro", "kucuk", "orta"]}, "zorunlu": True, "bilesen": None, "metin": "KOBİ"},
        {"alan": "vergi_sgk_borcu_yok", "kural": {"esit": True}, "zorunlu": True, "bilesen": "A", "metin": "borç yok"},
        {"alan": "belge", "kural": {"gerekli": "dys_kaydi"}, "zorunlu": True, "bilesen": "B", "metin": "DYS"},
        {"alan": "nace", "kural": {"in_prefix": ["C"]}, "zorunlu": True, "bilesen": None, "metin": "imalat"}]}
    r = program_karari(kd, [0, 1, 2, 3], g)
    k = [("12 profil", len(PROFILLER) == 12),
         ("KOBİ ölçeği türetilir (28 kişi, 85M)", g["olcek"] == "kucuk"),
         ("bileşenlerden en iyisi: A borç yüzünden düşer, B'de yalnız DYS eksik → HAZIRLIKLA", r["karar"] == "HAZIRLIKLA" and r["bilesen"] == "B"),
         ("NACE kısım harfi (28.30 → C)", kriter_sonucu(kd["kriterler"][3], g) == "saglar"),
         ("sistem görünümünde borç bilinmiyor", kriter_sonucu(kd["kriterler"][1], gercek_profil(PROFILLER[2], True)) == "bilinmiyor"),
         ("max kuralı", kriter_sonucu({"alan": "calisan_sayisi", "kural": {"max": 9}}, g) == "saglamaz"),
         ("diger → elle", kriter_sonucu({"alan": "diger", "kural": {"aciklama": "x"}}, g) == "elle")]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gec = sum(ok for _, ok in k)
    print(f"\nself-test: {gec}/{len(k)} geçti")
    return 0 if gec == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(_self_test() if "--self-test" in sys.argv else olc())
