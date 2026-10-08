"""100 sentetik kullanıcı ajanıyla uçtan uca deneme (2026-10-09). Ücretsiz, ağ yok, veritabanına yazmaz.

"Ajan" = kurallı simüle kullanıcı (LLM yok; API bakiyesi yok ve sonuç tekrarlanabilir olsun diye). 20 arketip × 5 varyasyon,
sabit tohum. Her ajan uygulamanın kullanıcı adımlarını, API'nin çağırdığı fonksiyonlarla yürür:
  1 eşleşme (matching.esles)  2 kontrol listesi + çağrılar (basvuru_listesi._yanit)  3 hazırlık (hazirlik.yol_haritasi)
  4 e-ihracat hesabı (e-ticaret/ihracat arketiplerinde)  5 cevapsız taslak  6 sihirbaz cevaplı taslak (sentetik cevaplar)
Denetim: değişmez kurallar (D*) + arketip başına danışman beklentisi (B*). Beklentiler ÇALIŞTIRMADAN ÖNCE yazıldı.

    python docs/olcum/2026-10-09-100-ajan/simulasyon.py
Çıktı: sonuc.json (ajan başına ayrıntı) ve ozet.md (oranlar, başarısız örnekler).
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "docs/olcum/2026-10-08-taslak"))
sys.path.insert(0, str(KOK / "docs/olcum/2026-10-07-denetim2"))
sys.stdout.reconfigure(encoding="utf-8")

import taslak_olcum as TO  # noqa: E402
from app import sablon_taslak  # noqa: E402
from app.basvuru_listesi import _yanit  # noqa: E402
from app.basvuru_taslagi import baglam  # noqa: E402
from app.cagrilar import program_cagrilari  # noqa: E402
from app.eticaret_destek_hesaplayici import EihracatDurumu, EihracatGirdisi, hesapla  # noqa: E402
from app.hazirlik import yol_haritasi  # noqa: E402
from app.kobi import kobi_sinifi  # noqa: E402
from app.matching import esles, isletmeye_yonelik_mi  # noqa: E402
from app.models import FinancialProfile, SessionLocal  # noqa: E402
from app.ozet import il_listesi  # noqa: E402
from app.rag import profil_sozlugu  # noqa: E402

DIZIN = Path(__file__).resolve().parent
R = random.Random(20261009)
BUGUN = date.today()
IKAS_YASAK = {187, 188, 189, 190, 191, 192, 193, 194, 195, 196}   # 5973/5986 madde kayıtları: şirket şartı
SAHIS_URUNU = {87}
KOSGEB_BUYUGE_ACIK = {7}

# arketip: profil üreteci, beklenen (id kümesi, en kötü sıra; kümeden biri yeterli), yasak id'ler
ARKETIPLER = {
    "e-ticaret şahıs ihracat": dict(sektor="e-ticaret", nace=["47.91"], tur=["sahis"], calisan=(1, 4), ciro=(1e6, 8e6),
                                     yas=(0, 4), hedef=[["ihracat"], ["ihracat", "e-ticaret"]], beklenen=({162, 1, 87, 159}, 10),
                                     yasak=IKAS_YASAK, eihracat=True),
    "e-ticaret Ltd ihracat": dict(sektor="e-ticaret", nace=["47.91"], tur=["limited"], calisan=(5, 30), ciro=(8e6, 60e6),
                                  yas=(2, 12), hedef=[["ihracat"]], beklenen=({192, 193, 194}, 10), eihracat=True),
    "imalat mikro Ltd genç": dict(sektor="imalat", nace=["25.62", "10.71", "22.29"], tur=["limited"], calisan=(2, 9),
                                  ciro=(1e6, 9e6), yas=(0, 2), hedef=[["yatirim"], ["makine"]], beklenen=({1, 8, 3, 81, 170}, 10)),
    "imalat küçük Ltd yatırım": dict(sektor="imalat", nace=["25.62", "28.29", "13.20", "22.29"], tur=["limited", "anonim"],
                                     calisan=(12, 45), ciro=(15e6, 90e6), yas=(5, 25), hedef=[["yatirim", "makine"], ["yatirim", "ihracat"]],
                                     beklenen=({8, 81, 180}, 6)),
    "imalat orta A.Ş. ihracat": dict(sektor="imalat", nace=["27.11", "29.32", "20.59"], tur=["anonim"], calisan=(60, 220),
                                     ciro=(150e6, 900e6), yas=(10, 35), hedef=[["ihracat", "yatirim"]], beklenen=({8, 9, 159, 180, 81}, 10)),
    "imalat büyük A.Ş. yatırım": dict(sektor="imalat", nace=["10.82", "24.10", "29.10"], tur=["anonim"], calisan=(300, 1500),
                                      ciro=(1.5e9, 9e9), yas=(15, 40), hedef=[["yatirim"]], beklenen=({180, 179, 181}, 5),
                                      yasak_kosgeb=True),
    "tarım buğday şahıs": dict(sektor="tarim", nace=["01.11"], tur=["sahis"], calisan=(0, 3), ciro=(5e5, 5e6), yas=(3, 30),
                               tarim="tahil_baklagil", urun="buğday", hedef=[["makine"], []], beklenen=({160}, 3), yasak={34, 44}),
    "tarım sebze şahıs": dict(sektor="tarim", nace=["01.13"], tur=["sahis"], calisan=(0, 4), ciro=(4e5, 4e6), yas=(3, 30),
                              tarim="sebze_meyve", urun="domates", hedef=[[], ["sulama"]], beklenen=({161}, 3)),
    "tarım hayvancı şahıs": dict(sektor="tarim", nace=["01.41", "01.45"], tur=["sahis"], calisan=(0, 5), ciro=(8e5, 8e6),
                                 yas=(3, 30), tarim="hayvancilik", urun="süt sığırı", hedef=[["hayvan"]], beklenen=({76}, 3),
                                 yasak={160, 161}),
    "tarım organik": dict(sektor="tarim", nace=["01.24"], tur=["sahis"], calisan=(0, 3), ciro=(3e5, 3e6), yas=(3, 20),
                          tarim="organik", urun="kayısı", hedef=[["organik"]], beklenen=({77}, 3)),
    "tarım sera": dict(sektor="tarim", nace=["01.13"], tur=["sahis", "limited"], calisan=(1, 8), ciro=(1e6, 12e6), yas=(2, 20),
                       tarim="sera", urun="domates", hedef=[[]], beklenen=({79}, 3)),
    "tarım kooperatifi": dict(sektor="tarim", nace=["01.11", "01.50"], tur=["kooperatif"], calisan=(3, 15), ciro=(5e6, 40e6),
                              yas=(5, 30), tarim="genel", etiket=["kooperatif"], hedef=[["makine"]], beklenen=({116}, 10),
                              yasak={87}),
    "şirketsiz teknoloji girişimi": dict(sektor="arge", nace=["62.01", "72.19"], tur=["yok"], calisan=(0, 0), ciro=(0, 0),
                                         yas=None, trl=(2, 5), etiket=[[], ["genc_girisimci"]], hedef=[["arge"]],
                                         beklenen=({174, 49}, 3), yasak={34, 44, 177, 178, 179, 180, 181, 1}),
    "yazılım Ltd ihracat": dict(sektor="hizmet", nace=["62.01", "62.02"], tur=["limited"], calisan=(5, 60), ciro=(5e6, 80e6),
                                yas=(2, 15), hedef=[["ihracat", "arge"]], beklenen=({182}, 5)),
    "Ar-Ge küçük Ltd": dict(sektor="arge", nace=["26.51", "72.19", "21.20"], tur=["limited"], calisan=(5, 40),
                            ciro=(3e6, 50e6), yas=(2, 10), trl=(3, 7), hedef=[["arge"]], beklenen=({34, 44, 2}, 10)),
    "kadın girişimci hizmet şahıs": dict(sektor="hizmet", nace=["96.02", "56.10", "47.71"], tur=["sahis"], calisan=(0, 4),
                                         ciro=(3e5, 3e6), yas=(0, 3), etiket=["kadin_girisimci"], hedef=[["istihdam"], []],
                                         beklenen=({169, 1, 185}, 10), yasak={133, 93}),
    "genç girişimci şahıs": dict(sektor="hizmet", nace=["74.10", "73.11", "47.91"], tur=["sahis"], calisan=(0, 2),
                                 ciro=(1e5, 2e6), yas=(0, 2), etiket=["genc_girisimci"], hedef=[[]],
                                 beklenen=({112, 138, 169, 1}, 10)),
    "savunma tedarikçisi Ltd": dict(sektor="imalat", nace=["25.62", "30.30"], tur=["limited", "anonim"], calisan=(20, 150),
                                    ciro=(30e6, 400e6), yas=(5, 25), etiket=["savunma_sanayii"], hedef=[["yatirim"]],
                                    beklenen=({133}, 10)),
    "turizm/hizmet Ltd yatırım": dict(sektor="hizmet", nace=["55.10", "86.10"], tur=["limited", "anonim"], calisan=(10, 120),
                                      ciro=(10e6, 200e6), yas=(3, 25), hedef=[["yatirim"]], beklenen=({180, 178, 90}, 10)),
    "deprem bölgesi imalat istihdam": dict(sektor="imalat", nace=["13.20", "25.62", "10.71"], tur=["limited", "sahis"],
                                           calisan=(8, 60), ciro=(5e6, 80e6), yas=(3, 20), il=["Hatay", "Kahramanmaraş", "Adıyaman", "Malatya"],
                                           hedef=[["istihdam"]], beklenen=({7, 126, 185}, 10)),
}


def _sec(x):
    return R.choice(x) if isinstance(x, list) else x


def profil_uret(ad: str, a: dict, n: int) -> dict:
    lo, hi = a["calisan"]
    lo_c, hi_c = a["ciro"]
    p = dict(sektor=a["sektor"], bolge=_sec(a.get("il") or il_listesi()), nace_kodu=_sec(a["nace"]), sirket_turu=_sec(a["tur"]),
             calisan_sayisi=R.randint(lo, hi), yillik_ciro=round(R.uniform(lo_c, hi_c), -3) if hi_c else 0.0,
             hedefler=list(_sec(a["hedef"])))
    if a.get("yas") is not None:
        y = R.uniform(*a["yas"])
        p["kurulus_tarihi"] = date.fromordinal(BUGUN.toordinal() - int(y * 365) - 10)
    if a.get("tarim"):
        p["tarim_kategori"] = a["tarim"]
    if a.get("urun"):
        p["urun_turu"] = a["urun"]
    if a.get("trl"):
        p["trl"] = R.randint(*a["trl"])
    et = a.get("etiket")
    if et:
        p["ozellikler"] = list(_sec(et)) if isinstance(et[0], list) else list(et)
    return p


def sentetik_cevap(s: dict) -> dict:
    kalemler = s["gider_kalemleri"] or ["Makine ve ekipman", "Danışmanlık", "Personel"]
    butce = [{"kalem": k, "tutar": float(R.randrange(100_000, 3_000_000, 50_000))} for k in R.sample(kalemler, min(3, len(kalemler)))]
    return {"proje_adi": "Sentetik proje", "proje_ozeti": "Sentetik ajan cevabı.",
            "gerekce": {q["anahtar"]: "Sentetik gerekçe." for q in s["gerekce"][:2]},
            "faaliyetler": [{"ad": x, "baslangic": "2027-01", "bitis": "2027-06"} for x in s["faaliyet_onerileri"][:2]],
            "butce": butce, "destek_orani": s["oran_secenekleri"][0] if s["oran_secenekleri"] else None,
            "ciktilar": {q["anahtar"]: "Sentetik çıktı." for q in s["cikti"]}}


def ajan(db, ad: str, a: dict, n: int) -> dict:
    p_al = profil_uret(ad, a, n)
    p = FinancialProfile(**p_al)
    es = esles(p, db, limit=30)
    sira = {e.tesvik.id: i + 1 for i, e in enumerate(es)}
    k = {}  # denetim adı -> (geçti mi, açıklama)
    k["D1 en az 1 öneri"] = (len(es) > 0, f"{len(es)} öneri")
    k["D2 akademik çağrı önerilmez"] = (all(isletmeye_yonelik_mi(e.tesvik) for e in es), "")
    olcek = kobi_sinifi(p.calisan_sayisi, p.yillik_ciro)
    kos = [e.tesvik.id for e in es if e.tesvik.kurum == "KOSGEB" and e.tesvik.id not in KOSGEB_BUYUGE_ACIK]
    k["D3 büyük işletmeye KOSGEB yok"] = (not (olcek.kesin and olcek.sinif == "buyuk" and kos), f"KOSGEB {kos}" if kos else "")
    k["D4 şahıs ürünü yalnız şahısa"] = (not (p.sirket_turu != "sahis" and SAHIS_URUNU & set(sira)), "")
    k["D5 şirketsize 9903 yok"] = (not (p.sirket_turu == "yok" and any(e.tesvik.kurum == "Sanayi ve Teknoloji Bakanlığı" for e in es)), "")
    izinsiz = [e.tesvik.id for e in es if (e.tesvik.uygunluk_kriterleri or {}).get("sirket_turleri")
               and p.sirket_turu not in e.tesvik.uygunluk_kriterleri["sirket_turleri"]]
    k["D6 şirket türü listesine uyulur"] = (not izinsiz, f"{izinsiz}" if izinsiz else "")
    tarim_ust = [e.tesvik for e in es[:10] if e.tesvik.kurum == "Tarım Bakanlığı"]
    k["D7 tarım dışına Tarım Bakanlığı yok"] = (p.sektor == "tarim" or not tarim_ust, f"{[t.id for t in tarim_ust]}")
    k["D8 skor>0 ve gerekçe var"] = (all(e.skor > 0 and e.gerekce for e in es), "")
    # 2 kontrol listesi + çağrı tarihi tutarlılığı + yol bilgisi
    yol, tarih_hata = [], []
    for e in es[:5]:
        y = _yanit(e.tesvik, None)
        yol.append(sum(map(bool, (y["tesvik"]["basvuru_yeri"], y["tesvik"]["basvuru_suresi"], y["maddeler"]))))
        for c in y["cagrilar"]:
            sg = c.get("son_gun")
            if c["durum"] == "acik" and sg and date.fromisoformat(sg) < BUGUN:
                tarih_hata.append(f"{e.tesvik.id}:{c['ad']}")
    k["D9 çağrı durumu tarihle tutarlı"] = (not tarih_hata, f"{tarih_hata}")
    k["D10 ilk 5'te yol bilgisi (yer/süre/madde)"] = (all(v == 3 for v in yol), f"{yol}")
    # 3 hazırlık
    yh = yol_haritasi(p, db)["adimlar"]
    if p.sektor == "tarim" and p.sirket_turu == "sahis" and any(x["kod"] == "cks" for x in yh):
        k["D11 tarımda ilk adım ÇKS"] = (yh[0]["kod"] == "cks", yh[0]["kod"])
    # 4 e-ihracat
    if a.get("eihracat"):
        s_e = hesapla(EihracatGirdisi(giderler={"pazaryeri_reklam": 240_000, "pazaryeri_komisyon": 120_000,
                                                 "siparis_karsilama": 60_000}, hedef_ulke_payi=0.8, yurt_disi_satis_tl=1_500_000),
                      EihracatDurumu(sirket_turu=p.sirket_turu, birlik_uyesi=True, madrid_marka=True))
        toplam = s_e.simdi_tl + s_e.hazirlikla_tl + s_e.teyitle_tl
        k["D12 e-ihracat ≤ %75 gider, şahısta 'şimdi' 0"] = (toplam <= 0.75 * 420_000 + 1 and
                                                             (p.sirket_turu != "sahis" or s_e.simdi_tl == 0), f"{toplam:.0f}")
    # 5-6 taslak (ilk öneri)
    if es:
        t = es[0].tesvik
        prof = profil_sozlugu(p)
        cag = program_cagrilari(t)
        mad = _yanit(t, None)["maddeler"]
        bos = sablon_taslak.uret(t, prof, mad, cag)
        bag = baglam(t, prof) + json.dumps(cag, ensure_ascii=False, default=str)
        d = TO.denetle(re.sub(r"^## 6\..*", "", bos, flags=re.S | re.M), bag)
        k["D13 cevapsız taslak: başlık sırası, boş tablo yok"] = (d["baslik_sirasi_dogru"] and "| [DOLDURUN" not in bos, "")
        k["D14 cevapsız taslak: uydurma rakam yok"] = (not d["baglamda_olmayan_sayilar"], f"{d['baglamda_olmayan_sayilar']}")
        s = sablon_taslak.sorular(t)
        cev = sentetik_cevap(s)
        dolu = sablon_taslak.uret(t, prof, mad, cag, cev)
        top = sum(b["tutar"] for b in cev["butce"])
        beklenen_destek = None
        if cev["destek_orani"]:
            beklenen_destek = top * cev["destek_orani"] / 100
            if s["ust_limit"]:
                beklenen_destek = min(beklenen_destek, s["ust_limit"])
        hesap_ok = sablon_taslak._tl(top) in dolu and (beklenen_destek is None or sablon_taslak._tl(beklenen_destek) in dolu)
        k["D15 sihirbaz: cevaplar ve bütçe hesabı doğru"] = (hesap_ok and "Sentetik proje" in dolu, f"toplam {top:.0f}, destek {beklenen_destek}")
    # B beklenen / yasak
    hedef_ids, esik = a["beklenen"]
    en_iyi = min((sira[i] for i in hedef_ids if i in sira), default=None)
    k["B1 beklenen program eşikte"] = (en_iyi is not None and en_iyi <= esik, f"en iyi sıra {en_iyi} (≤{esik}), beklenen {sorted(hedef_ids)}")
    yasak_gelen = sorted(i for i in a.get("yasak", set()) if i in sira)
    k["B2 yasak program gelmez"] = (not yasak_gelen, f"{yasak_gelen}")
    if a.get("yasak_kosgeb"):
        k["B3 büyük firmaya KOSGEB yok"] = (not kos, f"{kos}")
    return {"ajan": n, "arketip": ad, "profil": {k_: (v.isoformat() if isinstance(v, date) else v) for k_, v in p_al.items()},
            "ilk10": [f"{e.tesvik.id} {e.tesvik.baslik[:45]} ({e.skor:.2f})" for e in es[:10]],
            "denetim": {ad_: {"gecti": bool(g), "not": n_} for ad_, (g, n_) in k.items()}}


def main():
    db = SessionLocal()
    sonuc = []
    n = 0
    for ad, a in ARKETIPLER.items():
        for _ in range(5):
            n += 1
            sonuc.append(ajan(db, ad, a, n))
    db.close()
    (DIZIN / "sonuc.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    toplam, gecen = Counter(), Counter()
    arketip = defaultdict(lambda: [0, 0])
    basarisiz = defaultdict(list)
    for r in sonuc:
        tum = True
        for ad, d in r["denetim"].items():
            toplam[ad] += 1
            gecen[ad] += d["gecti"]
            if not d["gecti"]:
                tum = False
                basarisiz[ad].append(f"#{r['ajan']} {r['arketip']} ({r['profil']['bolge']}, {r['profil']['sirket_turu']}, "
                                     f"{r['profil']['calisan_sayisi']} kişi): {d['not']}")
        arketip[r["arketip"]][0] += 1
        arketip[r["arketip"]][1] += tum
    s = ["# 100 sentetik ajan — ham özet\n", "| Denetim | Geçen / toplam | Oran |", "|---|---|---|"]
    for ad in sorted(toplam):
        s.append(f"| {ad} | {gecen[ad]}/{toplam[ad]} | %{100 * gecen[ad] / toplam[ad]:.0f} |")
    s += ["", "| Arketip | Tüm denetimleri geçen ajan |", "|---|---|"]
    s += [f"| {a} | {v[1]}/{v[0]} |" for a, v in arketip.items()]
    s += ["", "## Başarısız örnekler (denetim başına en çok 6)"]
    for ad in sorted(basarisiz):
        s.append(f"\n**{ad}** ({len(basarisiz[ad])})")
        s += [f"- {x}" for x in basarisiz[ad][:6]]
    (DIZIN / "ozet.md").write_text("\n".join(s), encoding="utf-8")
    print("\n".join(s))


if __name__ == "__main__":
    main()
