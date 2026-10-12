"""Kapsam matrisi ölçümü (2026-10-11): veritabanı, sektör × ihtiyaç × il hücrelerinde kullanıcıya program sunabiliyor mu?

Her hücre bir persona (sektör + il) ve bir ihtiyaçtır. İki ölçüt:
  kayıt  — ürünün kendi değerlendirmesine göre (app/yerel_danisman.degerlendir: il/bölge, sektör, ölçek, şirket türü,
           hedef kitle, ciro, çağrı dönemi; 9903 için Karar ön değerlendirmesi) kapalı ya da uygun değil OLMAYAN ve
           o ihtiyaca hizmet eden (app/ihtiyac.program_ihtiyaclari) kayıt sayısı; 9903 ön değerlendirmesi "UYGUN DEĞİL"
           ya da "DÜŞÜK" olan program sayılmaz
  ürün   — o profil ve ihtiyaç sorusu için yerel danışmanın gerçek yanıtında bu kayıtlardan en az biri kart olarak
           gösteriliyor mu (arama + sıralama dahil uçtan uca)
Hücre durumu: 0 kayıt = BOŞ, 1 = İNCE, 2+ = VAR. Dış çağrı yok; ücretsiz.

    python docs/olcum/2026-10-11-kapsam/kapsam_olc.py --self-test
    python docs/olcum/2026-10-11-kapsam/kapsam_olc.py            (kapsam.json + KAPSAM.md üretir)
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date

KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, KOK)
OUT = os.path.dirname(os.path.abspath(__file__))
for akim in (sys.stdout, sys.stderr):
    if hasattr(akim, "reconfigure"):
        akim.reconfigure(encoding="utf-8")

# Persona tabanları: profil formundaki alanlar (app/schemas.FinancialProfileCreate).
SEKTORLER = {
    "e-ticaret": dict(sektor="e-ticaret", nace_kodu="47.91", sirket_turu="limited", calisan_sayisi=6,
                      yillik_ciro=8e6, hedefler=["ihracat", "finansman"]),
    "imalat": dict(sektor="imalat", nace_kodu="25.62", sirket_turu="limited", calisan_sayisi=25,
                   yillik_ciro=40e6, hedefler=["yatirim", "makine"]),
    "yazılım": dict(sektor="arge", nace_kodu="62.01", sirket_turu="limited", calisan_sayisi=8,
                    yillik_ciro=6e6, hedefler=["arge"]),
    "tarım": dict(sektor="tarim", sirket_turu="sahis", calisan_sayisi=2, yillik_ciro=1.5e6,
                  urun_turu="buğday", tarim_kategori="tarla", arazi_buyuklugu_dekar=100, hedefler=["makine"]),
    "turizm": dict(sektor="hizmet", nace_kodu="55.10", sirket_turu="limited", calisan_sayisi=15,
                   yillik_ciro=20e6, hedefler=["yatirim"]),
    "hizmet (restoran)": dict(sektor="hizmet", nace_kodu="56.10", sirket_turu="sahis", calisan_sayisi=4,
                              yillik_ciro=3e6, hedefler=["finansman"]),
    "girişimci (şirket yok)": dict(sektor="arge", sirket_turu="yok", trl=3, hedefler=["arge"]),
}
IHTIYACLAR = {
    "yatirim": "Makine ve tesis yatırımı için hangi destekleri alabilirim?",
    "arge": "Ar-Ge ve yeni ürün geliştirme için hangi destekler var?",
    "ihracat": "İhracatımızı artırmak için hangi destekler var?",
    "istihdam": "Yeni personel alırsak hangi teşvikler var?",
    "dijital": "Dijital dönüşüm ve yazılım yatırımı için destek var mı?",
    "finansman": "İşletmemiz için uygun kredi ve kefalet destekleri neler?",
    "girisim": "Şirket kurmak istiyorum, hangi girişim destekleri var?",
}
GIRISIM_IHTIYAC = ("girisim", "finansman", "arge")
# İller: büyük ticaret merkezleri, kayıtlarda ajansı olmayan bölgeler ve kalkınmada öncelikli bölgeler.
ILLER = ["İstanbul", "Ankara", "İzmir", "Bursa", "Konya", "Antalya", "Gaziantep", "Trabzon", "Van", "Diyarbakır",
         "Edirne", "Balıkesir"]


def hucreler():
    for sektor, taban in SEKTORLER.items():
        ihtiyaclar = GIRISIM_IHTIYAC if taban.get("sirket_turu") == "yok" else [
            x for x in IHTIYACLAR if x != "girisim"]
        for il in ILLER:
            for ihtiyac in ihtiyaclar:
                yield sektor, il, ihtiyac


_KARARLAR: dict[tuple, dict[int, tuple[str, str]]] = {}


def persona_kararlari(profil, tum: list, bugun) -> dict[int, tuple[str, str]]:
    """Persona için her etkin kaydın (karar, 9903 notu); persona başına bir kez (ihtiyaçtan bağımsız)."""
    from app import yerel_danisman as y
    from app.rag import profil_9903_degerlendirmesi
    anahtar = (profil.sektor, profil.nace_kodu, profil.sirket_turu, profil.bolge, profil.calisan_sayisi)
    if anahtar not in _KARARLAR:
        etkin = [t for t in tum if t.aktif_mi]
        notlar = {i: u.metin() for i, u in profil_9903_degerlendirmesi(etkin, profil).items()}
        ds = y.degerlendir(etkin, profil, notlar, {}, set(), set(), bugun, y.ust_programlar(etkin, tum), "")
        _KARARLAR[anahtar] = {d.tesvik.id: (d.karar, notlar.get(d.tesvik.id, "")) for d in ds}
    return _KARARLAR[anahtar]


def erisilebilir(t, karar: tuple[str, str] | None, ihtiyac: str) -> bool:
    """Kayıt düzeyi: ürünün değerlendirmesinde kapalı/uygun değil olmayan, 9903 ön değerlendirmesi olumsuz olmayan ve
    ihtiyaca hizmet eden etkin kayıt."""
    from app.ihtiyac import program_ihtiyaclari
    if not t.aktif_mi or karar is None or ihtiyac not in program_ihtiyaclari(t):
        return False
    sonuc, not_9903 = karar
    return sonuc in ("sartli", "belirlenemedi") and not not_9903.startswith(("UYGUN DEĞİL", "DÜŞÜK"))


_KART = re.compile(r"^\*\*(.+) — ([^*—]+)\*\*", re.M)   # başlıkta " — " olabilir: ayraç sondaki


def gosterilen_basliklar(yanit: str, adlar: set[str] = frozenset()) -> set[str]:
    """Yanıtta öne çıkarılan programlar: kart başlıkları ("**Başlık — Kurum**") ve 9903 bölge karşılaştırma bloğunda
    satırı olan programlar (yatırım sorusunda 9903 programları kart değil bu blokta gösterilir)."""
    sonuc = {m.group(1).strip() for m in _KART.finditer(yanit)}
    blok = re.search(r"\*\*9903 programları bölgenize göre.*?(?:\n\n|$)", yanit, re.S)
    if blok:
        sonuc |= {a for a in adlar if f"- {a} (" in blok.group(0)}
    return sonuc


def calistir():
    from app import rag
    from app.models import FinancialProfile, SessionLocal, Tesvik
    bugun = date.today()
    db = SessionLocal()
    tum = db.query(Tesvik).all()
    sonuc = []
    bas = time.perf_counter()
    for sektor, il, ihtiyac in hucreler():
        profil = FinancialProfile(**{**SEKTORLER[sektor], "bolge": il})
        kararlar = persona_kararlari(profil, tum, bugun)
        uygun = [t for t in tum if erisilebilir(t, kararlar.get(t.id), ihtiyac)]
        soru = IHTIYACLAR[ihtiyac]
        h = rag._hazirla(soru, False, profil)
        yanit = rag._yerel(soru, h, profil) if h.matches else rag.BULUNAMADI_METNI
        uygun_ad = {t.baslik for t in uygun}
        gosterilen = gosterilen_basliklar(yanit, uygun_ad)
        sonuc.append(dict(sektor=sektor, il=il, ihtiyac=ihtiyac, kayit=len(uygun),
                          kurumlar=sorted(Counter(t.kurum for t in uygun)), urun=bool(gosterilen & uygun_ad),
                          gosterilen=sorted(gosterilen)[:6], ornek=sorted(uygun_ad)[:5]))
    db.close()
    json.dump(sonuc, open(os.path.join(OUT, "kapsam.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rapor(sonuc, time.perf_counter() - bas)
    return sonuc


def durum(n: int) -> str:
    return "BOŞ" if n == 0 else "İNCE" if n == 1 else "VAR"


def rapor(sonuc: list[dict], sure: float):
    toplam = len(sonuc)
    say = Counter(durum(x["kayit"]) for x in sonuc)
    urun = sum(x["urun"] for x in sonuc)
    satir = [f"# Kapsam matrisi ({date.today().isoformat()})", "",
             f"{toplam} hücre ({len(SEKTORLER)} sektör × {len(ILLER)} il × ihtiyaç). Kayıt düzeyi: VAR {say['VAR']}, "
             f"İNCE {say['İNCE']}, BOŞ {say['BOŞ']}. Ürün düzeyi (yanıtta engelsiz, açık ve ihtiyaca uygun bir program "
             f"kartı): {urun}/{toplam}. Süre {sure:.0f} sn.", "",
             "Hücre: kayıt sayısı (✓ = yanıt bu kayıtlardan birini kart olarak gösteriyor, ✗ = göstermiyor).", ""]
    for sektor in SEKTORLER:
        xs = [x for x in sonuc if x["sektor"] == sektor]
        ihts = list(dict.fromkeys(x["ihtiyac"] for x in xs))
        satir += [f"## {sektor}", "", "| İl | " + " | ".join(ihts) + " |", "|---|" + "---|" * len(ihts)]
        for il in ILLER:
            hs = {x["ihtiyac"]: x for x in xs if x["il"] == il}
            satir.append(f"| {il} | " + " | ".join(
                f"{hs[i]['kayit']} {'✓' if hs[i]['urun'] else '✗'}" for i in ihts) + " |")
        satir.append("")
    # boş hücrelerin özeti: ihtiyaç × sektör (il bağımsız mı, ile özgü mü)
    satir += ["## Boş ve ince hücrelerin özeti", ""]
    grup = defaultdict(list)
    for x in sonuc:
        if x["kayit"] <= 1:
            grup[(x["sektor"], x["ihtiyac"])].append(x["il"])
    for (sektor, ihtiyac), iller in sorted(grup.items(), key=lambda kv: -len(kv[1])):
        satir.append(f"- {sektor} / {ihtiyac}: {len(iller)} ilde boş ya da ince"
                     + (" (tüm illerde)" if len(iller) == len(ILLER) else f" ({', '.join(iller)})"))
    # ulusal programlar her hücreyi doldurduğu için bölgesel boşluk ana tabloda görünmez: il başına ajans programı
    satir += ["", "## İl başına açık kalkınma ajansı programı (herhangi bir sektör/ihtiyaç hücresinde)", ""]
    for il in ILLER:
        ajanslar = sorted({k for x in sonuc if x["il"] == il for k in x["kurumlar"] if "Kalkınma Ajansı" in k})
        satir.append(f"- {il}: {', '.join(ajanslar) if ajanslar else 'YOK'}")
    satir += ["", "## Kayıt var ama yanıt göstermiyor (ürün düzeyi ✗, kayıt ≥ 1)", ""]
    for x in sonuc:
        if x["kayit"] >= 1 and not x["urun"]:
            satir.append(f"- {x['sektor']} / {x['il']} / {x['ihtiyac']}: kayıtta {x['kayit']} "
                         f"(ör. {'; '.join(x['ornek'][:2])}); yanıtta: {'; '.join(x['gosterilen'][:3]) or 'kart yok'}")
    with open(os.path.join(OUT, "KAPSAM.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(satir) + "\n")
    print(satir[2])


def _self_test() -> int:
    k = [("hücre sayısı", sum(1 for _ in hucreler()) == 6 * len(ILLER) * 6 + len(ILLER) * 3),
         ("durum eşikleri", (durum(0), durum(1), durum(2)) == ("BOŞ", "İNCE", "VAR")),
         ("kart başlığı ayrıştırma", gosterilen_basliklar("**KOSGEB Ar-Ge — KOSGEB**\n- x\n**A — B**")
          == {"KOSGEB Ar-Ge", "A"}),
         ("başlığında ayraç olan kart", gosterilen_basliklar("**Atılım Programı — Dijital Destek (m.17) — Ticaret B.**")
          == {"Atılım Programı — Dijital Destek (m.17)"}),
         ("9903 bloğu da gösterilmiş sayılır", gosterilen_basliklar(
             "**9903 programları bölgenize göre (x):**\n- Hedef T (şartlı): katkı\n\nson", {"Hedef T", "Yok T"})
          == {"Hedef T"})]
    from app.models import Tesvik
    t = Tesvik(baslik="Makine Yatırım Kredisi", aktif_mi=True, uygunluk_kriterleri={"sektorler": ["genel"]})
    k += [("kapalı karar erişilebilir sayılmaz", not erisilebilir(t, ("kapali", ""), "yatirim")),
          ("engelsiz karar erişilebilir", erisilebilir(t, ("sartli", ""), "yatirim")),
          ("9903 olumsuz ön değerlendirme sayılmaz", not erisilebilir(t, ("belirlenemedi", "DÜŞÜK OLASILIK — x"),
                                                                     "yatirim")),
          ("ihtiyaca hizmet etmeyen sayılmaz", not erisilebilir(t, ("sartli", ""), "istihdam"))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    import logging
    logging.disable(logging.INFO)
    sys.exit(_self_test() if "--self-test" in sys.argv else (calistir() and 0))
