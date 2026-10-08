"""10 sentetik işletmeyle uçtan uca deneme (2026-10-08): doğru teşvik, doğru tarih, başvuru yolu, hazırlık, başarı.

Ücretsiz: LLM yok, veritabanına yazmaz (profiller oturuma eklenmeyen nesneler). Uygulamanın API'lerinin çağırdığı
fonksiyonlar doğrudan kullanılır: matching.esles, basvuru_listesi._yanit (kontrol listesi + çağrılar),
hazirlik.yol_haritasi, eticaret_destek_hesaplayici.hesapla.

BEKLENTİLER ÇALIŞTIRMADAN ÖNCE yazıldı (danışman gözüyle): "beklenen" = (kayıt id, kabul edilebilir en kötü sıra),
"yasak" = bu profile önerilmemesi gereken kayıtlar ve gerekçesi. Sonuç beklentiye uymuyorsa beklenti değil sistem
sorgulanır; beklentinin yanlış olduğu durumlar RAPOR.md'de ayrıca yazılır.

    DATABASE_URL=sqlite:///<kopya.db> python docs/olcum/2026-10-08-persona/persona_uctan_uca.py
Çıktı: sonuc.json ve RAPOR.md (bu klasörde).
"""
import json
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KOK))
sys.stdout.reconfigure(encoding="utf-8")

from app.basvuru_listesi import _yanit  # noqa: E402
from app.eticaret_destek_hesaplayici import EihracatDurumu, EihracatGirdisi, hesapla  # noqa: E402
from app.hazirlik import yol_haritasi  # noqa: E402
from app.matching import esles  # noqa: E402
from app.models import FinancialProfile, SessionLocal  # noqa: E402

DIZIN = Path(__file__).resolve().parent
RESMI = ("kosgeb.gov.tr", "tubitak.gov.tr", "kgf.com.tr", "ticaret.gov.tr", "tarimorman.gov.tr", "sanayi.gov.tr",
         "sgk.gov.tr", "iskur.gov.tr", "resmigazete.gov.tr", "mevzuat.gov.tr", "yatirimadestek.gov.tr")

PERSONALAR = {
    "P1 İKAS şahıs e-ticaret (Denizli)": dict(
        profil=dict(sektor="e-ticaret", bolge="Denizli", calisan_sayisi=2, yillik_ciro=3e6, sirket_turu="sahis",
                    kurulus_tarihi=date(2024, 5, 1), nace_kodu="47.91", hedefler=["ihracat"]),
        beklenen=[(1, 6), (162, 10), (87, 12)],
        yasak={192: "5986 m.4 şirket şartı", 193: "5986 m.6 şirket şartı", 194: "5986 m.9 şirket şartı",
               188: "5973 şirket şartı", 34: "1501 sermaye şirketi", 44: "1507 sermaye şirketi"},
        hazirlik_ilk="sirket",
        eihracat=dict(giderler={"pazaryeri_reklam": 120_000, "pazaryeri_komisyon": 90_000}, hedef_ulke_payi=0.9,
                      yurt_disi_satis_tl=1_200_000, durum=dict(birlik_uyesi=False, madrid_marka=False))),
    "P2 İKAS Ltd e-ihracatçı (İstanbul kozmetik)": dict(
        profil=dict(sektor="e-ticaret", bolge="İstanbul", calisan_sayisi=9, yillik_ciro=25e6, sirket_turu="limited",
                    kurulus_tarihi=date(2019, 3, 1), nace_kodu="47.91", hedefler=["ihracat"],
                    hazirlik={"eihracat": {"onceki_yil_ihracat_usd": 300_000}}),  # SONRADAN_EKLENEN
        ilk5_yasak={196: "statü için 500 bin USD (beyan 300 bin)", 195: "1 M USD şartı"},  # SONRADAN_EKLENEN
        beklenen=[(192, 10), (193, 12), (194, 12), (188, 15), (9, 15)],
        yasak={76: "hayvancılık", 160: "hububat", 174: "BiGG şirketi olana kapalı", 1: "GDP 0-3 yaş (7 yaşında)"},
        eihracat=dict(giderler={"pazaryeri_reklam": 900_000, "siparis_karsilama": 300_000, "pazaryeri_komisyon": 600_000,
                                "cevrim_ici_magaza": 80_000}, hedef_ulke_payi=1.0, yurt_disi_satis_tl=6_000_000,
                      durum=dict(birlik_uyesi=True, madrid_marka=None, onceki_yil_ihracat_usd=300_000))),
    "P3 Konya buğday çiftçisi (şahıs)": dict(
        profil=dict(sektor="tarim", bolge="Konya", calisan_sayisi=2, yillik_ciro=2.2e6, arazi_buyuklugu_dekar=250,
                    urun_turu="buğday", tarim_kategori="tahil_baklagil", nace_kodu="01.11", sirket_turu="sahis",
                    kurulus_tarihi=date(2010, 1, 1), hedefler=["makine"]),
        beklenen=[(160, 3), (94, 10)],
        yasak={34: "1501", 1: "KOSGEB GDP (2010 kuruluş)", 161: "meyve-sebze", 77: "organik", 79: "sera",
               76: "hayvancılık (beyan yok)"},
        ilk5_yasak={77: "organik beyan yok"}, hazirlik_ilk="cks"),  # SONRADAN_EKLENEN
    "P4 Afyon büyükbaş hayvancı (şahıs)": dict(
        profil=dict(sektor="tarim", bolge="Afyonkarahisar", calisan_sayisi=3, yillik_ciro=4e6,
                    tarim_kategori="hayvancilik", urun_turu="süt sığırı", nace_kodu="01.41", sirket_turu="sahis",
                    kurulus_tarihi=date(2015, 1, 1), hedefler=["hayvan"]),
        beklenen=[(76, 3), (94, 10)],
        yasak={160: "hububat", 161: "meyve-sebze", 34: "1501", 79: "sera"},
        ilk5_yasak={77: "organik beyan yok"}, hazirlik_ilk="cks"),  # SONRADAN_EKLENEN
    "P5 Bursa metal imalat Ltd (45 kişi)": dict(
        profil=dict(sektor="imalat", bolge="Bursa", calisan_sayisi=45, yillik_ciro=120e6, nace_kodu="25.62",
                    sirket_turu="limited", kurulus_tarihi=date(2009, 4, 1), hedefler=["yatirim", "makine", "ihracat"]),
        beklenen=[(8, 6), (180, 6), (81, 12), (7, 15)],
        yasak={1: "GDP 0-3 yaş", 174: "BiGG", 112: "Genç işi kredisi", 76: "hayvancılık", 160: "hububat"}),
    "P6 Ankara şirketsiz yapay zekâ girişimcisi": dict(
        profil=dict(sektor="arge", bolge="Ankara", calisan_sayisi=0, yillik_ciro=0, nace_kodu="62.01", trl=4,
                    sirket_turu="yok", hedefler=["arge"], ozellikler=["genc_girisimci"]),
        beklenen=[(174, 3)],
        yasak={34: "1501 sermaye şirketi", 44: "1507 sermaye şirketi", 180: "9903 yatırım", 87: "şahıs işletmesi kredisi",
               1: "KOSGEB kayıtlı işletme ister"},
        hazirlik_ilk="sirket"),
    "P7 İzmir yazılım hizmet ihracatçısı Ltd": dict(
        profil=dict(sektor="hizmet", bolge="İzmir", calisan_sayisi=15, yillik_ciro=40e6, nace_kodu="62.01",
                    sirket_turu="limited", kurulus_tarihi=date(2018, 9, 1), hedefler=["ihracat", "arge"]),
        beklenen=[(182, 6), (44, 15)],
        yasak={76: "hayvancılık", 160: "hububat", 174: "BiGG", 93: "hukuk bürosu paketi"}),
    "P8 Hatay kadın girişimci kuaför (şahıs)": dict(
        profil=dict(sektor="hizmet", bolge="Hatay", calisan_sayisi=2, yillik_ciro=900_000, nace_kodu="96.02",
                    sirket_turu="sahis", kurulus_tarihi=date(2025, 6, 1), hedefler=["istihdam"],
                    ozellikler=["kadin_girisimci"]),
        beklenen=[(1, 6), (169, 12), (185, 12)],
        yasak={34: "1501", 177: "Teknoloji Hamlesi", 181: "Öncelikli yatırım", 93: "hukuk bürosu", 133: "savunma"},
        ilk5_yasak={178: "2 kişilik kuaföre yatırım teşviki", 180: "yatırım teşviki"}),  # SONRADAN_EKLENEN
    "P9 Gaziantep gıda imalat A.Ş. (320 kişi)": dict(
        profil=dict(sektor="imalat", bolge="Gaziantep", calisan_sayisi=320, yillik_ciro=2.5e9, nace_kodu="10.82",
                    sirket_turu="anonim", kurulus_tarihi=date(2001, 1, 1), hedefler=["yatirim", "ihracat"]),
        beklenen=[(180, 5)],
        yasak={8: "KOSGEB KOBİ şartı (320 çalışan)", 1: "KOSGEB", 3: "KOSGEB", 81: "KGF KOBİ paketi",
               87: "şahıs kredisi", 174: "BiGG"},
        ilk5_yasak={9: "KOSGEB Küresel Rekabetçilik KOBİ programı"}),  # SONRADAN_EKLENEN
    "P10 Karaman tarım kooperatifi": dict(
        profil=dict(sektor="tarim", bolge="Karaman", calisan_sayisi=6, yillik_ciro=15e6, tarim_kategori="genel",
                    sirket_turu="kooperatif", ozellikler=["kooperatif"], kurulus_tarihi=date(2012, 1, 1),
                    hedefler=["makine"]),
        beklenen=[(116, 10), (94, 10)],
        yasak={34: "1501 sermaye şirketi", 174: "BiGG", 87: "şahıs kredisi"},
        ilk5_yasak={77: "organik beyan yok"}, hazirlik_ilk="cks"),  # SONRADAN_EKLENEN
}


def _resmi(url: str | None) -> bool:
    return bool(url) and any(a in url for a in RESMI)


def degerlendir(db, ad: str, v: dict) -> dict:
    p = FinancialProfile(**v["profil"])
    es = esles(p, db, limit=30)
    sira = {e.tesvik.id: i + 1 for i, e in enumerate(es)}
    beklenen = [{"id": i, "esik": esik, "sira": sira.get(i), "tamam": sira.get(i) is not None and sira[i] <= esik}
                for i, esik in v["beklenen"]]
    yasak = [{"id": i, "neden": n, "sira": sira[i]} for i, n in v["yasak"].items() if i in sira]
    ilk5_yasak = [{"id": i, "neden": n, "sira": sira[i]} for i, n in v.get("ilk5_yasak", {}).items()
                  if sira.get(i, 99) <= 5]

    bugun = date.today()
    yollar, tarih_hatalari = [], []
    for e in es[:5]:
        y = _yanit(e.tesvik, None)
        tur = {m["tur"] for m in y["maddeler"]}
        for c in y["cagrilar"]:
            ac = date.fromisoformat(c["acilis"]) if c["acilis"] else None
            kp = date.fromisoformat(c["kapanis"]) if c["kapanis"] else None
            beklenen_durum = ("kapandi" if kp and kp < bugun else "yaklasan" if ac and ac > bugun
                              else "acik" if (ac or kp) else "tarihsiz")
            if c["durum"] != beklenen_durum:
                tarih_hatalari.append(f"{e.tesvik.id} {c['ad']}: {c['durum']} != {beklenen_durum}")
            if not _resmi(c.get("kaynak_url")):
                tarih_hatalari.append(f"{e.tesvik.id} {c['ad']}: çağrı kaynağı resmi değil ({c.get('kaynak_url')})")
        yollar.append({
            "id": e.tesvik.id, "baslik": e.tesvik.baslik[:70], "skor": round(e.skor, 2),
            "yer": bool(y["tesvik"]["basvuru_yeri"]), "sure": bool(y["tesvik"]["basvuru_suresi"]),
            "sart": "sart" in tur, "belge": "belge" in tur, "kaynak_resmi": _resmi(e.tesvik.kaynak_url),
            "cagri": [f"{c['ad']}: {c['durum']} son gün {c['son_gun'] or ''} ({c['kalan_gun']} gün)" for c in y["cagrilar"]
                      if c["durum"] != "kapandi"],
        })
    yh = yol_haritasi(p, db)
    hz = [(a["kod"], a["program_sayisi"]) for a in yh["adimlar"]]
    eh = None
    if v.get("eihracat"):
        x = v["eihracat"]
        s = hesapla(EihracatGirdisi(giderler=x["giderler"], hedef_ulke_payi=x["hedef_ulke_payi"],
                                    yurt_disi_satis_tl=x.get("yurt_disi_satis_tl")),
                    EihracatDurumu(sirket_turu=p.sirket_turu, **x["durum"]))
        eh = {"simdi": s.simdi_tl, "hazirlikla": s.hazirlikla_tl, "teyitle": s.teyitle_tl, "aylik": s.aylik_bekleme_tl,
              "adimlar": s.adimlar, "kalemler": {k.kod: (k.durum, k.tahmini_destek_tl) for k in s.kalemler}}
    return {
        "persona": ad, "eslesme": len(es),
        "ilk10": [f"{i + 1}. {e.tesvik.id} {e.tesvik.kurum[:12]} | {e.tesvik.baslik[:55]} ({e.skor:.2f})"
                  for i, e in enumerate(es[:10])],
        "beklenen": beklenen, "yasak": yasak, "ilk5_yasak": ilk5_yasak, "tarih_hatalari": tarih_hatalari, "yollar": yollar,
        "hazirlik": hz, "hazirlik_ilk_beklenen": v.get("hazirlik_ilk"),
        "hazirlik_ilk_dogru": (not v.get("hazirlik_ilk")) or (bool(hz) and hz[0][0] == v["hazirlik_ilk"]),
        "eihracat": eh,
    }


def rapor(sonuclar: list[dict]) -> str:
    s = ["# 10 sentetik işletmeyle uçtan uca deneme — ham sonuç (2026-10-08)\n",
         "Veritabanı: tur12 + tur13 + göç m0b2d4f6a012 uygulanmış KOPYA. Beklentiler çalıştırmadan önce yazıldı.\n",
         "| Persona | Eşleşme | Beklenen (tuttu/toplam) | Yasak gelen | İlk 5'te yasak (ek) | Tarih hatası | Yol bilgisi (ilk 5) | Hazırlık ilk adım |",
         "|---|---|---|---|---|---|---|---|"]
    for r in sonuclar:
        yol = sum(sum((y["yer"], y["sure"], y["sart"], y["belge"], y["kaynak_resmi"])) for y in r["yollar"])
        s.append(f"| {r['persona']} | {r['eslesme']} | {sum(b['tamam'] for b in r['beklenen'])}/{len(r['beklenen'])} | "
                 f"{len(r['yasak'])} | {len(r['ilk5_yasak'])} | {len(r['tarih_hatalari'])} | {yol}/{5 * len(r['yollar'])} | "
                 f"{'✓' if r['hazirlik_ilk_dogru'] else '✗'} {r['hazirlik'][0][0] if r['hazirlik'] else '-'} |")
    for r in sonuclar:
        s.append(f"\n## {r['persona']}\n")
        s.append("**İlk 10:**\n\n" + "\n".join(f"- {x}" for x in r["ilk10"]))
        s.append("\n**Beklenen:** " + ", ".join(f"{b['id']} sıra {b['sira'] or '—'} (≤{b['esik']}) {'✓' if b['tamam'] else '✗'}"
                                              for b in r["beklenen"]))
        s.append("\n**Yasak gelen:** " + (", ".join(f"{y['id']} sıra {y['sira']} ({y['neden']})" for y in r["yasak"]) or "yok"))
        s.append("\n**Tarih:** " + ("; ".join(r["tarih_hatalari"]) or "tutarlı"))
        s.append("\n**Başvuru yolu (ilk 5):**\n")
        s.append("| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |\n|---|---|---|---|---|---|---|---|")
        for y in r["yollar"]:
            iz = lambda b: "✓" if b else "✗"  # noqa: E731
            s.append(f"| {y['id']} | {y['baslik']} | {iz(y['yer'])} | {iz(y['sure'])} | {iz(y['sart'])} | {iz(y['belge'])} | "
                     f"{iz(y['kaynak_resmi'])} | {'; '.join(y['cagri']) or 'doğrulanmış tarih yok'} |")
        s.append("\n**Hazırlık adımları:** " + (", ".join(f"{k} ({n})" for k, n in r["hazirlik"]) or "yok"))
        if r["eihracat"]:
            e = r["eihracat"]
            s.append(f"\n**E-ihracat:** şimdi {e['simdi']:,.0f} · hazırlıkla {e['hazirlikla']:,.0f} · teyitle "
                     f"{e['teyitle']:,.0f} · aylık bekleme {e['aylik']:,.0f} · adımlar {e['adimlar']} · {e['kalemler']}")
    return "\n".join(s)


if __name__ == "__main__":
    db = SessionLocal()
    sonuclar = [degerlendir(db, ad, v) for ad, v in PERSONALAR.items()]
    db.close()
    (DIZIN / "sonuc.json").write_text(json.dumps(sonuclar, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    metin = rapor(sonuclar)
    (DIZIN / "ham_sonuc.md").write_text(metin, encoding="utf-8")
    print(metin)
