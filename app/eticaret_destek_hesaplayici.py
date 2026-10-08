"""E-ihracat giderlerinin 5986 sayılı E-İhracat Destekleri Kararı kapsamındaki tahmini geri ödemesi (2026-10-08).

Kaynaklar (ticaret.gov.tr, 2026-10-08'de okundu): Karar metni (son değişiklik RG 17.01.2026), E-İhracat Genelgesi
13.04.2026 ve "2026 Yılına İlişkin E-İhracat Destekleri Üst Limitleri" tablosu (ayrıntı:
scripts/fix_veri_2026_10_08_eihracat_tur12.py). Kuralların karar metnindeki yeri:

  m.4  dijital pazaryeri reklamı   %50; reklamdan dönen satışın %20'sini aşmayan gider; hedef ülkede +20 puan
  m.6  sipariş karşılama            %50; ülkedeki e-ticaret satışının %10'unu aşmayan gider; hedef ülkede +20 puan
  m.8  çevrim içi mağaza            %50; yalnız hedef ülkeler; ilave puan YOK (m.16/3); şirkette önceki yıl
                                    ihracatı 1 milyon USD üstü (Genelge m.18)
  m.9  pazaryeri komisyonu          %50; yalnız hedef ülkeler; ilave puan YOK (m.16/3)
  m.5  e-ihracat tanıtımı (kendi    %50, hedef ülkede +20; yalnız Perakende E-Ticaret Sitesi statüsü (Genelge m.14);
       sitesinin yurt dışı reklamı) statü şartlarından biri önceki yıl ≥ 500.000 USD ihracat (Genelge m.7)
  m.10/1 oran Türk ürünü satış oranı üzerinden uygulanır; m.10/2 bölüm toplamı şirketler için yıllık üst limit;
  m.16/4 ödenen destek giderin %75'ini aşamaz; m.18 limitler her yıl (TÜFE + Yİ-ÜFE)/2 ile güncellenir.

Pazara giriş raporu (m.3) ve pazaryeri entegrasyonu (m.7) yalnız konsorsiyum, perakende e-ticaret sitesi ve
pazaryerlerine açıktır; şirket hesabında yoktur. Yurt dışı depo kirası 5986'da değil, 5973 m.11 Birim Kira
desteğindedir (e-ticaret deposu yalnız statü sahiplerine).

Tahmin İLERİYE dönüktür: destek süresi ön onay tarihini izleyen ayın ilk günü başlar; ön onaydan önceki
harcama desteklenmez. Bu yüzden çıktı "ön onay alınırsa 12 ayda" tutarı ve beklenen her ayın kaybını verir.
Limitler şirketlerin EN YÜKSEK kademesidir (Karar "kademelerine göre"); alt kademede daha düşüktür.

    python -m app.eticaret_destek_hesaplayici --self-test
"""
import sys
from dataclasses import asdict, dataclass, field

TABAN_ORAN = 0.50
HEDEF_ILAVE = 0.20
GIDER_TAVANI = 0.75          # m.16/4
BOLUM_LIMITI_2026 = 73_990_019.0  # m.10/2, şirketler, 2026 (üst limit tablosu)
KARAR = "https://ticaret.gov.tr/data/632b13e013b8767974670b91/E-ihracat%20Karar.pdf"


@dataclass(frozen=True)
class Kalem:
    kod: str
    etiket: str
    madde: int
    limit_2026: float
    hedef_ilavesi: bool          # m.16/1 (+20 puan) uygulanır mı
    yalniz_hedef_ulke: bool      # gider yalnız hedef ülkelerde desteklenir
    satis_tavani: float | None   # desteklenebilir gider ≤ satış × tavan
    madrid: bool                 # ön onay için Madrid Sistemi'ne taraf ülkede marka tescili (Genelge)
    aciklama: str


KALEMLER: dict[str, Kalem] = {k.kod: k for k in (
    Kalem("pazaryeri_reklam", "Yurt dışı pazaryeri reklamı", 4, 36_993_646, True, False, 0.20, True,
          "Tıklama/sipariş başına ödeme, görüntülü reklam ve ürün yorum hizmeti; komisyon ve üyelik ücreti hariç."),
    Kalem("siparis_karsilama", "Sipariş karşılama (fulfillment) ve depolama", 6, 36_993_646, True, False, 0.10, True,
          "Bakanlık listesindeki firmadan ya da pazaryerinden alınan hizmet."),
    Kalem("pazaryeri_komisyon", "Pazaryeri satış komisyonu", 9, 3_698_274, False, True, None, True,
          "Yalnız hedef ülkelerdeki pazaryerleri."),
    Kalem("cevrim_ici_magaza", "Çevrim içi mağaza açılışı, yıllık ödemesi ve paydaş hizmeti", 8, 7_396_548, False, True,
          None, False, "Yalnız hedef ülkelerdeki pazaryerleri; satış komisyonu ve depozito hariç."),
    Kalem("site_tanitim", "Kendi sitenizin yurt dışı tanıtımı", 5, 123_315_792, True, False, None, False,
          "Yalnız Perakende E-Ticaret Sitesi (ya da pazaryeri/B2B/konsorsiyum) statüsüyle."),
)}

SIRKET_TURLERI = ("limited", "anonim", "kooperatif")


@dataclass
class EihracatDurumu:
    """Bilinmeyen alan None kalır; hesap onu engel saymaz, "teyit edin" der."""
    sirket_turu: str | None = None
    birlik_uyesi: bool | None = None
    madrid_marka: bool | None = None
    onceki_yil_ihracat_usd: float | None = None
    perakende_statusu: bool | None = None


@dataclass
class EihracatGirdisi:
    giderler: dict[str, float] = field(default_factory=dict)   # KALEMLER kodu -> yıllık TL
    yurt_disi_satis_tl: float | None = None                    # pazaryeri/ülke satışı (tavanlar için)
    hedef_ulke_payi: float = 0.0                               # giderin hedef ülkelerdeki payı, 0-1
    turk_urun_payi: float = 1.0                                # satışlarda Türk ürünü payı, 0-1 (m.10/1)


@dataclass
class KalemSonucu:
    kod: str
    etiket: str
    madde: int
    yillik_gider_tl: float
    desteklenebilir_gider_tl: float
    oran: float
    tahmini_destek_tl: float
    durum: str                     # uygun | hazirlik | teyit | kapali
    engeller: list[str]
    notlar: list[str]


@dataclass
class EihracatSonucu:
    kalemler: list[KalemSonucu]
    simdi_tl: float                # engeli olmayan kalemler (ön onay alınınca)
    hazirlikla_tl: float           # şirketleşme/üyelik/marka gibi adımlardan sonra
    teyitle_tl: float              # bilinmeyen bilgi teyit edilince
    aylik_bekleme_tl: float        # ön onay her ay gecikince kaybolan (uygun + teyit kalemleri)
    adimlar: list[str]             # hazırlık adım kodları (app/hazirlik.ADIMLAR)
    notlar: list[str]
    kaynak: str = KARAR


def _engeller(k: Kalem, d: EihracatDurumu) -> tuple[str, list[str], list[str]]:
    """(durum, engel metinleri, hazırlık adım kodları). Önce kapatan, sonra hazırlık, sonra teyit."""
    kapali, hazirlik, teyit, adim = [], [], [], []
    if k.kod == "site_tanitim":
        if d.onceki_yil_ihracat_usd is not None and d.onceki_yil_ihracat_usd < 500_000 and not d.perakende_statusu:
            kapali.append("Perakende E-Ticaret Sitesi statüsü için önceki yıl en az 500.000 USD ihracat gerekir "
                          "(Genelge m.7; diğer yol ETBİS net satışı ≥ 1 milyar TL). Statüsüz yol: 5973 m.12 Tanıtım Desteği")
        elif d.perakende_statusu is False:
            hazirlik.append("Perakende E-Ticaret Sitesi statüsü alınmalı (başvuru E-İhracat Sekretaryasına)")
            adim.append("perakende_statusu")
        elif d.perakende_statusu is None:
            teyit.append("Perakende E-Ticaret Sitesi statünüz bilinmiyor")
    if k.kod == "cevrim_ici_magaza" and d.onceki_yil_ihracat_usd is not None and d.onceki_yil_ihracat_usd <= 1_000_000:
        kapali.append("Şirketlerde önceki yıl GB + BGB ihracatı 1.000.000 USD'nin üzerinde olmalı (Genelge m.18)")
    elif k.kod == "cevrim_ici_magaza" and d.onceki_yil_ihracat_usd is None:
        teyit.append("Önceki yıl ihracatınız bilinmiyor (1.000.000 USD üstü şartı)")
    if d.sirket_turu in ("sahis", "yok"):
        hazirlik.append("Şahıs işletmesi doğrudan yararlanamaz: limited/anonim şirket ya da kooperatif olmak gerekir; "
                        "geçici yol E-İhracat Konsorsiyumu (Genelge m.33/7)")
        adim.append("sirket")
    elif d.sirket_turu is None:
        teyit.append("Şirket türünüz bilinmiyor (şahıs işletmesi doğrudan yararlanamaz)")
    if d.birlik_uyesi is False:
        hazirlik.append("İhracatçı birliği üyeliği gerekir (başvurular üyesi olunan birliğe yapılır)")
        adim.append("birlik_uyeligi")
    elif d.birlik_uyesi is None:
        teyit.append("İhracatçı birliği üyeliğiniz bilinmiyor")
    if k.madrid and d.madrid_marka is False:
        hazirlik.append("Ön onay için Madrid Sistemi'ne taraf bir ülkede tescilli marka gerekir")
        adim.append("madrid_marka")
    elif k.madrid and d.madrid_marka is None:
        teyit.append("Yurt dışı (Madrid) marka tesciliniz bilinmiyor")
    if kapali:
        return "kapali", kapali, []
    if hazirlik:
        return "hazirlik", hazirlik + teyit, adim
    if teyit:
        return "teyit", teyit, []
    return "uygun", [], []


def hesapla(girdi: EihracatGirdisi, durum: EihracatDurumu | None = None) -> EihracatSonucu:
    d = durum or EihracatDurumu()
    hedef = min(max(girdi.hedef_ulke_payi or 0.0, 0.0), 1.0)
    turk = min(max(girdi.turk_urun_payi if girdi.turk_urun_payi is not None else 1.0, 0.0), 1.0)
    sonuclar, adimlar = [], []
    for kod, gider in (girdi.giderler or {}).items():
        k = KALEMLER.get(kod)
        if k is None or not gider or gider <= 0:
            continue
        notlar = []
        uygun_gider = float(gider)
        if k.yalniz_hedef_ulke:
            uygun_gider *= hedef
            if hedef < 1:
                notlar.append(f"Yalnız hedef ülkelerdeki gider sayıldı (%{hedef * 100:.0f})")
        if k.satis_tavani is not None and girdi.yurt_disi_satis_tl is not None:
            tavan = girdi.yurt_disi_satis_tl * k.satis_tavani
            if uygun_gider > tavan:
                uygun_gider = tavan
                notlar.append(f"Gider, yurt dışı satışın %{k.satis_tavani * 100:.0f}'si ile sınırlandı (m.{k.madde})")
        elif k.satis_tavani is not None:
            notlar.append(f"Satış girilmedi: gider satışın %{k.satis_tavani * 100:.0f}'sini aşarsa fazlası desteklenmez")
        oran = TABAN_ORAN + (HEDEF_ILAVE * hedef if k.hedef_ilavesi else 0.0)
        oran = min(oran * turk, GIDER_TAVANI)
        destek = uygun_gider * oran
        if destek > k.limit_2026:
            destek = k.limit_2026
            notlar.append(f"2026 yıllık üst limitle sınırlandı ({k.limit_2026:,.0f} TL)".replace(",", "."))
        durum_kodu, engeller, adim = _engeller(k, d)
        if durum_kodu == "kapali":
            destek = 0.0
        adimlar += [a for a in adim if a not in adimlar]
        sonuclar.append(KalemSonucu(k.kod, k.etiket, k.madde, float(gider), round(uygun_gider, 2), round(oran, 4),
                                    round(destek, 2), durum_kodu, engeller, notlar))
    toplam = {s: sum(x.tahmini_destek_tl for x in sonuclar if x.durum == s) for s in ("uygun", "hazirlik", "teyit")}
    notlar = ["Ön onaydan önceki harcama desteklenmez: tutar, ön onay alınırsa izleyen 12 aydaki tahmindir.",
              "Limitler şirketlerin en yüksek kademesidir; kademenize göre daha düşük olabilir (Karar m.4, m.6, m.9).",
              "Oranlar Türk ürünü satış payınızla çarpıldı (Karar m.10/1)."]
    if not sonuclar:
        notlar.append("Hiçbir desteklenen gider kalemi girilmedi; tahmin hesaplanamadı.")
    if sum(toplam.values()) > BOLUM_LIMITI_2026:
        notlar.append("Kalemlerin toplamı şirketlerin 2026 bölüm üst limitini aşıyor (Karar m.10/2).")
    olcek = min(1.0, BOLUM_LIMITI_2026 / sum(toplam.values())) if sum(toplam.values()) else 1.0
    simdi, hazirlikla, teyitle = (round(toplam[s] * olcek, 2) for s in ("uygun", "hazirlik", "teyit"))
    return EihracatSonucu(kalemler=sonuclar, simdi_tl=simdi, hazirlikla_tl=hazirlikla, teyitle_tl=teyitle,
                          aylik_bekleme_tl=round((simdi + teyitle) / 12, 2), adimlar=adimlar, notlar=notlar)


def sozluk(s: EihracatSonucu) -> dict:
    return asdict(s)


def _self_test() -> int:
    tam = EihracatDurumu(sirket_turu="limited", birlik_uyesi=True, madrid_marka=True, onceki_yil_ihracat_usd=200_000,
                         perakende_statusu=False)
    g = EihracatGirdisi(giderler={"pazaryeri_reklam": 100_000, "pazaryeri_komisyon": 100_000}, hedef_ulke_payi=1.0)
    s = hesapla(g, tam)
    r = {k.kod: k for k in s.kalemler}
    sahis = hesapla(g, EihracatDurumu(sirket_turu="sahis", birlik_uyesi=True, madrid_marka=True))
    bos = hesapla(EihracatGirdisi(giderler={"pazaryeri_reklam": 120_000}))
    tavan = hesapla(EihracatGirdisi(giderler={"pazaryeri_reklam": 100_000}, yurt_disi_satis_tl=200_000), tam)
    yarim = hesapla(EihracatGirdisi(giderler={"pazaryeri_reklam": 100_000}, turk_urun_payi=0.5), tam)
    k = [
        ("reklam hedef ülkede %70", r["pazaryeri_reklam"].tahmini_destek_tl == 70_000),
        ("komisyona ilave puan yok (m.16/3)", r["pazaryeri_komisyon"].tahmini_destek_tl == 50_000),
        ("komisyon hedef ülke dışında 0", hesapla(EihracatGirdisi(giderler={"pazaryeri_komisyon": 10_000}), tam)
         .kalemler[0].tahmini_destek_tl == 0),
        ("tam durumda hepsi 'uygun', aylık bekleme 1/12", s.simdi_tl == 120_000 and s.aylik_bekleme_tl == 10_000),
        ("şahıs: hazırlık + şirket adımı", sahis.simdi_tl == 0 and sahis.hazirlikla_tl == 120_000
         and sahis.adimlar == ["sirket"]),
        ("bilinmeyen durum 'teyit'", bos.kalemler[0].durum == "teyit" and bos.teyitle_tl == 60_000),
        ("SRMO: gider satışın %20'si ile sınırlı", tavan.kalemler[0].desteklenebilir_gider_tl == 40_000
         and tavan.simdi_tl == 20_000),
        ("Türk ürünü payı oranı düşürür (m.10/1)", yarim.simdi_tl == 25_000),
        ("1 milyon USD altı şirkete çevrim içi mağaza kapalı", hesapla(
            EihracatGirdisi(giderler={"cevrim_ici_magaza": 50_000}, hedef_ulke_payi=1.0), tam).kalemler[0].durum == "kapali"),
        ("500 bin USD altında site tanıtımı kapalı", hesapla(
            EihracatGirdisi(giderler={"site_tanitim": 50_000}), tam).kalemler[0].tahmini_destek_tl == 0),
        ("tanınmayan kalem yok sayılır", hesapla(EihracatGirdisi(giderler={"pazara_giris_raporu": 1e6}), tam).kalemler == []),
        ("kalem limiti ve bölüm limiti (m.10/2) uygulanır", abs(hesapla(EihracatGirdisi(
            giderler={"pazaryeri_reklam": 2e8, "siparis_karsilama": 2e8, "pazaryeri_komisyon": 1e8}, hedef_ulke_payi=1.0),
            tam).simdi_tl - BOLUM_LIMITI_2026) < 1),
    ]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in k)
    print(f"\nself-test: {gecen}/{len(k)} geçti")
    return 0 if gecen == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
