"""Gerçek işletme personalarıyla uçtan uca deneme (2026-10-12): Rekortiv, fındık ve çilek üreticisi, matbaa, sürücü
kursu, 5 sentetik KOBİ ve İKAS müşteri profiline uyan 10 e-ticaret mağazası. Gerçek veritabanı, dış çağrı YOK.

Hat 2026-10-11-yerel-danisman/yerel_olc.py ile aynıdır (yanit_NN.md, kaynak_NN.md, ozet.json; dayanak denetimi);
ek olarak her persona için eşleştirme listesi (panelde "Size uygun destekler") eslesme_<persona>.md'ye yazılır.

    python docs/olcum/2026-10-12-persona/persona_olc.py --self-test
    python docs/olcum/2026-10-12-persona/persona_olc.py            (üretir + ölçer)
"""
import importlib.util
import os
import sys

KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, KOK)
OUT = os.path.dirname(os.path.abspath(__file__))
for akim in (sys.stdout, sys.stderr):
    if hasattr(akim, "reconfigure"):
        akim.reconfigure(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("yerel_olc", os.path.join(KOK, "docs/olcum/2026-10-11-yerel-danisman/yerel_olc.py"))
yerel_olc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(yerel_olc)

ETICARET = dict(sektor="e-ticaret", nace_kodu="47.91")
P = {
    # Kullanıcının kendi girişimi: şirket yok, mağaza aboneliği geliri GVK 20/B istisnasıyla.
    "rekortiv": dict(sektor="arge", bolge="Ankara", calisan_sayisi=0, yillik_ciro=60_000, nace_kodu="62.01",
                     sirket_turu="yok", kurucu_yasi=21, trl=8, hedefler=["arge", "finansman"],
                     baska_sirkette_ortak=False),
    "findik": dict(sektor="tarim", bolge="Ordu", calisan_sayisi=0, yillik_ciro=250_000, arazi_buyuklugu_dekar=9,
                   urun_turu="fındık", tarim_kategori="sebze_meyve", sirket_turu="sahis", hedefler=["finansman"]),
    "cilek": dict(sektor="tarim", bolge="Aydın", calisan_sayisi=0, yillik_ciro=150_000, arazi_buyuklugu_dekar=1.5,
                  urun_turu="çilek", tarim_kategori="sebze_meyve", sirket_turu="sahis", hedefler=["sulama", "finansman"]),
    "matbaa": dict(sektor="imalat", bolge="Ankara", calisan_sayisi=6, yillik_ciro=9_000_000, nace_kodu="18.12",
                   sirket_turu="limited", hedefler=["makine", "finansman"]),
    "surucu_kursu": dict(sektor="hizmet", bolge="Konya", calisan_sayisi=9, yillik_ciro=7_500_000, nace_kodu="85.53",
                         sirket_turu="limited", hedefler=["finansman", "dijital"]),
    # Sentetik ama gerçekçi KOBİ'ler
    "gaziantep_hali": dict(sektor="imalat", bolge="Gaziantep", calisan_sayisi=45, yillik_ciro=120_000_000,
                           nace_kodu="13.93", sirket_turu="anonim", hedefler=["ihracat", "yatirim"]),
    "kayseri_mobilya": dict(sektor="imalat", bolge="Kayseri", calisan_sayisi=22, yillik_ciro=40_000_000,
                            nace_kodu="31.01", sirket_turu="limited", hedefler=["makine", "dijital"]),
    "izmir_zeytinyagi": dict(sektor="imalat", bolge="İzmir", calisan_sayisi=12, yillik_ciro=25_000_000,
                             nace_kodu="10.41", sirket_turu="limited", hedefler=["ihracat", "finansman"]),
    "antalya_otel": dict(sektor="hizmet", bolge="Antalya", calisan_sayisi=14, yillik_ciro=18_000_000,
                         nace_kodu="55.10", sirket_turu="limited", hedefler=["finansman", "dijital"]),
    "bursa_otomotiv": dict(sektor="imalat", bolge="Bursa", calisan_sayisi=65, yillik_ciro=210_000_000,
                           nace_kodu="29.32", sirket_turu="anonim", hedefler=["arge", "yatirim"], trl=5),
    # İKAS müşteri profili: kendi sitesinden satan D2C e-ticaret KOBİ'leri
    "ikas_giyim": dict(**ETICARET, bolge="İstanbul", calisan_sayisi=5, yillik_ciro=6_000_000, sirket_turu="limited",
                       hedefler=["ihracat", "dijital"], ozellikler=["kadin_girisimci"]),
    "ikas_kozmetik": dict(**ETICARET, bolge="Ankara", calisan_sayisi=3, yillik_ciro=2_500_000, sirket_turu="sahis",
                          hedefler=["finansman"], ozellikler=["kadin_girisimci"]),
    "ikas_evtekstil": dict(**ETICARET, bolge="Denizli", calisan_sayisi=15, yillik_ciro=20_000_000,
                           sirket_turu="limited", hedefler=["ihracat", "makine"]),
    "ikas_taki": dict(**ETICARET, bolge="İstanbul", calisan_sayisi=4, yillik_ciro=8_000_000, sirket_turu="sahis",
                      hedefler=["ihracat"]),
    "ikas_kahve": dict(**ETICARET, bolge="İzmir", calisan_sayisi=6, yillik_ciro=5_000_000, sirket_turu="limited",
                       hedefler=["makine", "finansman"]),
    "ikas_pet": dict(**ETICARET, bolge="İstanbul", calisan_sayisi=8, yillik_ciro=12_000_000, sirket_turu="limited",
                     hedefler=["finansman", "istihdam"]),
    "ikas_bebek": dict(**ETICARET, bolge="Bursa", calisan_sayisi=10, yillik_ciro=15_000_000, sirket_turu="limited",
                       hedefler=["ihracat"]),
    "ikas_spor": dict(**ETICARET, bolge="Konya", calisan_sayisi=7, yillik_ciro=9_000_000, sirket_turu="limited",
                      hedefler=["dijital", "ihracat"]),
    "ikas_seramik": dict(**ETICARET, bolge="Eskişehir", calisan_sayisi=1, yillik_ciro=600_000, sirket_turu="sahis",
                         kurucu_yasi=27, hedefler=["finansman"]),
    "ikas_elektronik": dict(**ETICARET, bolge="İstanbul", calisan_sayisi=12, yillik_ciro=35_000_000,
                            sirket_turu="anonim", hedefler=["ihracat", "finansman"]),
}

S = [
    ("rekortiv", "Rekortiv adında sınav hazırlık mobil uygulamam var; App Store ve Google Play'de abonelikle gelir "
                 "alıyorum ama şirketim yok, 20/B istisnasıyla çalışıyorum. Şirket kurmadan alabileceğim hibe ya da "
                 "destek var mı?"),
    ("rekortiv", "BiGG'ye başvurdum. Şirket kurarsam KOSGEB ve TÜBİTAK'tan hangi destekleri birlikte kullanabilirim?"),
    ("rekortiv", "Uygulamamı yurt dışında tanıtmak için reklam vermek istiyorum; bunun için devlet desteği var mı?"),
    ("findik", "9 dönüm fındık bahçem var. Bu yıl devletten hangi destekleri alabilirim, toplam ne kadar eder?"),
    ("findik", "Fındık alan bazlı gelir desteği hâlâ veriliyor mu, dekar başına ne kadar?"),
    ("findik", "Bahçeyi yenilemek ve damla sulama kurmak için hibe ya da düşük faizli kredi var mı?"),
    ("cilek", "1,5 dönüm açık tarlada çilek yetiştiriyorum. Hangi desteklerden yararlanabilirim?"),
    ("cilek", "Çilek tarlamı alçak tünel ya da sera yapmak istiyorum; hibe veya kredi var mı?"),
    ("cilek", "Dolu ve don riskine karşı sigorta yaptırırsam devlet ne kadarını öder?"),
    ("matbaa", "Matbaamıza yaklaşık 4 milyon TL'lik yeni dijital baskı makinesi almak istiyoruz. Hangi kredi, hibe "
               "ya da teşvik belgesi kullanabiliriz?"),
    ("matbaa", "İki yeni çalışan alacağız; SGK ve İŞKUR teşvikleri neler?"),
    ("matbaa", "KOSGEB'den matbaa için alabileceğimiz destek var mı?"),
    ("surucu_kursu", "Sürücü kursumuz için iki yeni eğitim aracı ve bir sürüş simülatörü almak istiyoruz; uygun kredi "
                     "veya destek var mı?"),
    ("surucu_kursu", "Kursumuzun dijitalleşmesi (online ders, randevu sistemi) için KOSGEB desteği alabilir miyiz?"),
    ("surucu_kursu", "Yeni usta öğretici işe alırsak hangi prim teşvikleri var?"),
    ("gaziantep_hali", "Halı ihracatımızı artırmak için yurt dışı fuar ve tanıtım desteği alabilir miyiz?"),
    ("gaziantep_hali", "Yeni dokuma makineleri için yatırım teşvik belgesi alırsak hangi destekler çıkar?"),
    ("kayseri_mobilya", "CNC ve otomatik kenar bantlama makinesi yatırımı için hangi destekler var?"),
    ("kayseri_mobilya", "Üretimi dijitalleştirmek (ERP, makinelere sensör) için hibe var mı?"),
    ("izmir_zeytinyagi", "Zeytinyağımızı kendi markamızla Almanya'ya ihraç etmek istiyoruz; hangi destekler var?"),
    ("izmir_zeytinyagi", "İhracat için uygun faizli kredi bulabilir miyiz?"),
    ("antalya_otel", "Butik otelimizi yenilemek için kredi ya da hibe var mı?"),
    ("antalya_otel", "Yurt dışı tanıtım ve online satış için destek var mı?"),
    ("bursa_otomotiv", "Yeni bir fren parçası geliştirmek için Ar-Ge projesi yapacağız; TÜBİTAK ve KOSGEB'den ne "
                       "alabiliriz?"),
    ("bursa_otomotiv", "Ar-Ge merkezi kurmanın şartları ve avantajları neler?"),
    ("ikas_giyim", "Kadın giyim e-ticaret mağazam var. Yurt dışına satış için hangi destekler var?"),
    ("ikas_giyim", "Instagram ve Google reklam giderlerim için destek alabilir miyim?"),
    ("ikas_kozmetik", "Doğal kozmetik markamla online satış yapıyorum; kadın girişimciye kredi ya da hibe var mı?"),
    ("ikas_kozmetik", "Şahıs işletmesiyim; e-ihracat desteklerinden yararlanabilir miyim?"),
    ("ikas_evtekstil", "Havlu ve bornoz üretip kendi sitemizden satıyoruz; Amazon Avrupa'da mağaza açmak için destek "
                       "var mı?"),
    ("ikas_evtekstil", "Yurt dışı depo ve sipariş karşılama giderleri destekleniyor mu?"),
    ("ikas_taki", "Gümüş takı satan online mağazam var; Etsy ve kendi sitemden yurt dışı satış için destek var mı?"),
    ("ikas_taki", "Yurt dışına gönderdiğim kargoların masrafı için destek alabilir miyim?"),
    ("ikas_kahve", "Kahve kavurma makinesi almak istiyorum, hangi kredi ya da hibeler var?"),
    ("ikas_kahve", "Online kahve satışımızı büyütmek için dijital pazarlama desteği var mı?"),
    ("ikas_pet", "Evcil hayvan ürünleri satan e-ticaret şirketimiz için işletme sermayesi kredisi bulabilir miyiz?"),
    ("ikas_pet", "Depoya 3 kişi alacağız, istihdam teşviki var mı?"),
    ("ikas_bebek", "Organik bebek tekstili markamızı Körfez ülkelerine satmak istiyoruz; hangi destekler var?"),
    ("ikas_bebek", "Markamızı yurt dışında tescil ettirmenin desteği var mı?"),
    ("ikas_spor", "Spor giyim markamız için yurt dışı pazaryerlerinde reklam desteği var mı?"),
    ("ikas_spor", "KOSGEB dijital dönüşüm desteğinden e-ticaret altyapısı için yararlanabilir miyiz?"),
    ("ikas_seramik", "El yapımı seramik satıyorum, tek kişilik şahıs işletmesiyim; genç girişimciye uygun kredi ya da "
                     "hibe var mı?"),
    ("ikas_seramik", "Seramik fırını almak için KOSGEB'den destek alabilir miyim?"),
    ("ikas_elektronik", "Telefon aksesuarı satıyoruz, e-ihracata başlayacağız; Ticaret Bakanlığı e-ihracat "
                        "desteklerinin şartları neler?"),
    ("ikas_elektronik", "Eximbank'tan e-ihracat kredisi alabilir miyiz?"),
]


def senaryolar():
    return P, [dict(n=i, persona=p, soru=q, beklenen=[], tur="persona") for i, (p, q) in enumerate(S, 1)]


def eslesme_listeleri(limit: int = 20) -> None:
    """Panelin "Size uygun destekler" listesi: her persona için sıralı başlık, skor, gerekçe ve eksikler."""
    from app.matching import esles
    from app.models import FinancialProfile, SessionLocal
    db = SessionLocal()
    for ad, alanlar in P.items():
        sonuc = esles(FinancialProfile(**alanlar), db, limit=limit)
        satirlar = [f"# {ad}", f"profil: {alanlar}", ""]
        for i, r in enumerate(sonuc, 1):
            satirlar.append(f"{i:2}. [{r.skor:.0f}] {r.tesvik.baslik} — {r.tesvik.kurum} (aktif={r.tesvik.aktif_mi})")
            if r.gerekce:
                satirlar.append(f"    gerekçe: {'; '.join(r.gerekce)[:300]}")
            if r.eksik_kriterler:
                satirlar.append(f"    eksik: {'; '.join(r.eksik_kriterler)[:300]}")
        with open(os.path.join(OUT, f"eslesme_{ad}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(satirlar) + "\n")
        print(f"eşleşme {ad:18} {len(sonuc)} program; ilk: {sonuc[0].tesvik.baslik[:70] if sonuc else '-'}")
    db.close()


def _self_test() -> int:
    P_, ss = senaryolar()
    k = [("45 senaryo", len(ss) == 45),
         ("20 persona, hepsinin senaryosu var", len(P_) == 20 and {s["persona"] for s in ss} == set(P_)),
         ("İKAS mağazaları e-ticaret profili", all(v["sektor"] == "e-ticaret" for a, v in P_.items() if a.startswith("ikas_"))
          and sum(a.startswith("ikas_") for a in P_) == 10),
         ("profiller FinancialProfile alanlarıyla kurulur", _profiller_kurulur()),
         ("ortak hat yüklü", callable(yerel_olc.calistir) and "out" in yerel_olc.calistir.__code__.co_varnames)]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


def _profiller_kurulur() -> bool:
    from app.models import FinancialProfile
    try:
        [FinancialProfile(**v) for v in P.values()]
        return True
    except TypeError:
        return False


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--out" in sys.argv:   # ara denemeler hakemlerin okuduğu dosyaların üzerine yazmasın
        OUT = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
        os.makedirs(OUT, exist_ok=True)
    eslesme_listeleri()
    P_, ss = senaryolar()
    yerel_olc.calistir(P_, ss, OUT)
