"""
9903 sayili "Yatirimlarda Devlet Yardimlari Hakkinda Karar" - NACE bazli
uygunluk kontrolu.

NEDEN BU MODUL VAR
------------------
Esleştirme motoru (app/matching.py) sektorleri 7 kaba etikete gore ayiriyor
("genel", "arge", "tarim", "ihracat", "hizmet", "imalat", "e-ticaret") ve
176 kaydin 138'i "genel" etiketli. Olcum (2026-09-26): Istanbul'da yazilim
yapan bir kullaniciya en ustte "BASIN ILAN KURUMU DESTEK PROGRAMI" ve
"Vakifbank Hukuk Burosu Destek Paketi" cikiyordu - ucu de "hizmet" etiketli
oldugu icin ayirt edilemiyordu.

Devletin kendi sistemi bu sorunu NACE kodlariyla cozuyor: 9903 sayili Karar
(Resmi Gazete, 30/05/2025) yatirim konularini NACE Rev. 2.1 kodlariyla
tanimliyor ve basvurulari EK-3 listesiyle bu kodlar uzerinden eslestiriyor.
Bu modul o resmi listeyi uygulamaya tasiyor.

ONEMLI KAPSAM SINIRI
--------------------
Buradaki esikler YATIRIM TESVIK BELGESI icindir (vergi indirimi, KDV
istisnasi, sigorta primi destegi vb.). KOSGEB hibeleri, TUBITAK proje
destekleri ve Tarim Bakanligi'nin dekar/hayvan basi odemeleri AYRI
enstrumanlardir ve bu esiklere tabi DEGILDIR. Kullaniciya "sera icin asgari
20 dekar" derken hangi destegin kastedildigi mutlaka belirtilmelidir -
aksi halde 5 dekar serasi olan bir uretici, hak kazandigi mazot-gubre
destegini de alamayacagini sanir.

9903, 2012/3305 sayili Karar'i ve 2018/11201 sayili Cazibe Merkezleri
Karari'ni YURURLUKTEN KALDIRDI. Bu yuzden veritabanindaki "Bolgesel Tesvik
Uygulamalari", "Genel Tesvik Uygulamalari", "Buyuk Olcekli Yatirimlarin
Tesviki" ve "Stratejik Yatirimlarin Tesviki" kayitlari artik gecerli degil
(bkz. scripts/mark_9903_yururlukten_kalkanlar.py).

KAYNAK
------
Karar metni: https://www.yatirimadestek.gov.tr/pdf/assets/upload/dosyalar/karar-yatirim_tesvik_uygulamalari.pdf
Resmi Gazete: https://www.resmigazete.gov.tr/eskiler/2025/05/20250530-2.pdf
Asagidaki EK-2 ve EK-3/A verileri bu metinden birebir alinmistir
(dogrulama tarihi: 2026-09-26).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from app.urun_sektor_anahtarlari import kucult

# ---------------------------------------------------------------------------
# EK-2: YATIRIM TESVIK UYGULAMALARINDA BOLGELER
# ---------------------------------------------------------------------------
# Karar metninden birebir. 81 ilin tamami kapsanir; eksik il bir hata
# belirtisidir (bkz. tests/test_nace_9903.py).
BOLGE_ILLERI: dict[int, tuple[str, ...]] = {
    1: ("Ankara", "Antalya", "Bursa", "Eskişehir", "İstanbul", "İzmir",
        "Kocaeli", "Muğla"),
    2: ("Aydın", "Balıkesir", "Bolu", "Çanakkale", "Denizli", "Edirne",
        "Kayseri", "Konya", "Manisa", "Mersin", "Sakarya", "Tekirdağ",
        "Yalova"),
    3: ("Adana", "Bilecik", "Burdur", "Düzce", "Gaziantep", "Isparta",
        "Karabük", "Karaman", "Kırıkkale", "Kırklareli", "Kütahya",
        "Nevşehir", "Rize", "Samsun", "Trabzon", "Uşak", "Zonguldak"),
    4: ("Afyonkarahisar", "Aksaray", "Amasya", "Artvin", "Çorum", "Elâzığ",
        "Erzincan", "Kastamonu", "Kırşehir", "Malatya", "Sivas"),
    5: ("Bartın", "Bayburt", "Çankırı", "Erzurum", "Giresun", "Hatay",
        "Kahramanmaraş", "Kilis", "Niğde", "Ordu", "Osmaniye", "Sinop",
        "Tokat", "Tunceli", "Yozgat"),
    6: ("Adıyaman", "Ağrı", "Ardahan", "Batman", "Bingöl", "Bitlis",
        "Diyarbakır", "Gümüşhane", "Hakkâri", "Iğdır", "Kars", "Mardin",
        "Muş", "Siirt", "Şanlıurfa", "Şırnak", "Van"),
}

# Aksanli/aksansiz yazim, buyuk-kucuk harf ve yaygin varyantlar icin arama
# indeksi. Kullanici "elazig", "ELAZIĞ", "Elâzığ" yazabilir.
_IL_VARYANTLARI: dict[str, str] = {
    "elazig": "Elâzığ", "elaziğ": "Elâzığ", "elâzig": "Elâzığ",
    "hakkari": "Hakkâri", "hakkarı": "Hakkâri",
    "afyon": "Afyonkarahisar",
    "k.maras": "Kahramanmaraş", "kmaras": "Kahramanmaraş",
    "urfa": "Şanlıurfa", "sanliurfa": "Şanlıurfa",
    "istanbul": "İstanbul", "izmir": "İzmir", "icel": "Mersin",
}


def _il_anahtari(il: str) -> str:
    """Il adini karsilastirilabilir bir anahtara cevirir.

    kucult() kullaniliyor: Python'un str.lower()'i "İSTANBUL"u "i̇stanbul"
    (i + birlesik nokta) yapiyor ve karsilastirma sessizce basarisiz oluyor
    (bkz. app/urun_sektor_anahtarlari.kucult).
    """
    anahtar = kucult(il).strip()
    # Aksanlari sadelestir - kullanici klavyesinde Turkce karakter olmayabilir.
    for a, b in (("â", "a"), ("î", "i"), ("û", "u"), ("ğ", "g"), ("ş", "s"),
                 ("ç", "c"), ("ö", "o"), ("ü", "u"), ("ı", "i")):
        anahtar = anahtar.replace(a, b)
    return anahtar


_IL_BOLGE_INDEKSI: dict[str, int] = {}
for _bolge, _iller in BOLGE_ILLERI.items():
    for _il in _iller:
        _IL_BOLGE_INDEKSI[_il_anahtari(_il)] = _bolge
for _varyant, _asil in _IL_VARYANTLARI.items():
    for _bolge, _iller in BOLGE_ILLERI.items():
        if _asil in _iller:
            _IL_BOLGE_INDEKSI[_il_anahtari(_varyant)] = _bolge


def il_bolgesi(il: str | None) -> int | None:
    """Ilin 9903 sayili Karar'daki tesvik bolgesini (1-6) dondurur."""
    if not il:
        return None
    return _IL_BOLGE_INDEKSI.get(_il_anahtari(il))


def bolge_illeri(bolge: int) -> tuple[str, ...]:
    return BOLGE_ILLERI.get(bolge, ())


# ---------------------------------------------------------------------------
# EK-3/A: TARIM, ORMANCILIK VE BALIKCILIK - yapilandirilmis asgari esikler
# ---------------------------------------------------------------------------
# Yalnizca BOLUM A yapilandirildi. Sebebi: kullanici profilinde bu esikleri
# karsilastirabilecegimiz alanlar var (arazi_buyuklugu_dekar, hayvan sayisi).
# Diger bolumlerin (imalat, madencilik, ulastirma...) sartlari asgari sabit
# yatirim tutari ve teknoloji siniflandirmasi gibi profilde bulunmayan
# verilere dayaniyor; onlari yapilandirmis gibi gostermek yanlis bir
# "uygunsunuz/degilsiniz" hukmu uretirdi. O kayitlar icin yalnizca resmi
# sart METNI gosteriliyor (bkz. ek3_kaydi()).


@dataclass(frozen=True)
class AsgariEsik:
    """Bir yatirim konusu icin bolge bazli asgari olcek sarti."""
    nace_kodu: str
    yatirim_konusu: str
    birim: str                       # "dekar", "adet/dönem", "m2"
    # bolge -> asgari deger. Karar metninde bir bolge icin esik verilmemisse
    # o bolge burada YER ALMAZ ve "esik tanimli degil" olarak raporlanir -
    # 0 yazmak "hicbir sart yok" anlamina gelir ki bu yanlis olurdu.
    bolge_esikleri: dict[int, float] = field(default_factory=dict)
    ek_not: str = ""


# Asagidaki degerler Karar metninin EK-3 bolumunden birebir alinmistir.
EK3_A_ESIKLERI: tuple[AsgariEsik, ...] = (
    AsgariEsik(
        nace_kodu="01.19.99",
        yatirim_konusu="Sera yatirimi (ortualti bitkisel uretim)",
        birim="dekar",
        bolge_esikleri={1: 20, 2: 20, 3: 15, 4: 10, 5: 10, 6: 5},
        ek_not="Yapay isikla fotosentez saglanan kontrollu bitkisel uretim "
               "yatirimlarinda katmanlarin toplam alaninin asgari 1.000 m2 "
               "olmasi sarti aranir. Diger yatirimlar desteklenmez.",
    ),
    AsgariEsik(
        nace_kodu="01.41.31",
        yatirim_konusu="Sutu sagilan buyukbas hayvan yetistiriciligi",
        birim="adet/dönem",
        bolge_esikleri={1: 500, 2: 500, 3: 500, 4: 300, 5: 300, 6: 150},
        ek_not="Damizlik veya sut yonlu olmasi gerekir. Tevsi ve komple yeni "
               "yatirimlar yem bitkileri yetistiriciligi ve/veya yem tesisi "
               "ve/veya sut isleme yatirimlari ile entegre edilebilir.",
    ),
    AsgariEsik(
        nace_kodu="01.42.09",
        yatirim_konusu="Diger sigir ve manda yetistiriciligi (et yonlu)",
        birim="adet/dönem",
        bolge_esikleri={1: 500, 2: 500, 3: 500, 4: 500, 5: 500, 6: 150},
        ek_not="Tevsi ve komple yeni yatirimlar; yem bitkileri yetistiriciligi "
               "ve/veya yem tesisi ve/veya kesimhane yatirimlari ile entegre "
               "edilebilir.",
    ),
    AsgariEsik(
        nace_kodu="01.45.01",
        yatirim_konusu="Koyun ve keci (davar) yetistiriciligi",
        birim="adet/dönem",
        bolge_esikleri={1: 2500, 2: 2500, 3: 2500, 4: 1500, 5: 1500, 6: 1000},
        ek_not="Damizlik veya et yonlu veya sut yonlu olmasi gerekir.",
    ),
    AsgariEsik(
        nace_kodu="01.47.01",
        yatirim_konusu="Kumes hayvanlari yetistiriciligi (et yonlu)",
        birim="adet/dönem",
        bolge_esikleri={1: 200_000, 2: 200_000, 3: 200_000, 4: 200_000,
                        5: 200_000, 6: 100_000},
        ek_not="Et yonlu kumes hayvanlari yetistiriciliginin KESIMHANE ile "
               "entegre olmasi sarti aranir. Damizlik kumes hayvanlari "
               "yetistiriciliginde kulucka hane ile entegre olma sarti vardir.",
    ),
    AsgariEsik(
        nace_kodu="01.47.03",
        yatirim_konusu="Kumes hayvanlarindan yumurta uretilmesi",
        birim="adet/dönem",
        bolge_esikleri={1: 200_000, 2: 200_000, 3: 200_000, 4: 200_000,
                        5: 200_000, 6: 100_000},
        ek_not="Tevsi ve komple yeni yatirimlar soguk hava deposu ve/veya "
               "yumurta tasnif-paketleme yatirimlari ile entegre edilebilir.",
    ),
    AsgariEsik(
        nace_kodu="03.2",
        yatirim_konusu="Su urunleri yetistiriciligi",
        birim="",
        bolge_esikleri={},
        ek_not="Karar metninde bolge bazli asgari olcek sarti belirtilmemistir. "
               "Tevsi ve komple yeni yatirimlar balik yemi tesisi ile entegre "
               "edilebilir.",
    ),
)

_ESIK_INDEKSI = {e.nace_kodu: e for e in EK3_A_ESIKLERI}

# Profildeki tarim kategorisi -> ilgili NACE kodlari. Kullanici NACE kodunu
# bilmek zorunda kalmasin.
TARIM_KATEGORI_NACE: dict[str, tuple[str, ...]] = {
    "sera": ("01.19.99",),
    "hayvancilik": ("01.41.31", "01.42.09", "01.45.01", "01.47.01", "01.47.03"),
}


# ---------------------------------------------------------------------------
# EK-3 tam referans metni (tum bolumler)
# ---------------------------------------------------------------------------
_VERI_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "ek3_9903.json")
_EK3_ONBELLEK: dict | None = None


def _ek3_paketi() -> dict:
    global _EK3_ONBELLEK
    if _EK3_ONBELLEK is None:
        try:
            with open(_VERI_YOLU, encoding="utf-8") as f:
                _EK3_ONBELLEK = json.load(f)
        except (OSError, json.JSONDecodeError):
            _EK3_ONBELLEK = {"kayitlar": [], "bolum_sartlari": {}}
    return _EK3_ONBELLEK


def ek3_kayitlari() -> list[dict]:
    """EK-3 listesinin tamami: {kod, bolum, bolum_ad, tanim, sartlar}.

    Sartlar SERBEST METIN olarak saklanir; yapilandirilmis esik yalnizca
    BOLUM A icin vardir (bkz. EK3_A_ESIKLERI). Metni oldugu gibi gostermek,
    yapilandirmadigimiz bir sarti yorumlamaya calismaktan daha guvenlidir.

    Bolum harfleri KARAR'IN KENDI harflendirmesidir (K = telekomunikasyon/
    bilisim, N = mesleki-bilimsel, O = idari destek, Q = egitim, R = saglik);
    standart NACE bolum harflerinden farkli olabilir.
    """
    return _ek3_paketi().get("kayitlar", [])


def bolum_sarti(bolum: str) -> str | None:
    """Bazi bolumlerde (B MADENCILIK, D ELEKTRIK) NACE satiri yerine bolum
    duzeyinde metin sart var; onlari kaybetmemek icin ayri tutuluyor."""
    return _ek3_paketi().get("bolum_sartlari", {}).get(bolum)


def kaynak_bilgisi() -> dict:
    p = _ek3_paketi()
    return {k: p.get(k) for k in
            ("kaynak", "kaynak_url", "resmi_gazete", "cikarma_tarihi")}


def ek3_kaydi(nace_kodu: str) -> dict | None:
    kod = (nace_kodu or "").strip()
    for k in ek3_kayitlari():
        if k.get("kod") == kod:
            return k
    return None


def nace_destekleniyor_mu(nace_kodu: str) -> bool:
    """Kod EK-3 listesinde var mi? Yok ise yatirim tesvik belgesi kapsaminda
    DESTEKLENMEYEN bir konu demektir."""
    return ek3_kaydi(nace_kodu) is not None


# ---------------------------------------------------------------------------
# Uygunluk degerlendirmesi
# ---------------------------------------------------------------------------
@dataclass
class UygunlukSonucu:
    nace_kodu: str
    yatirim_konusu: str
    il: str | None
    bolge: int | None
    asgari: float | None
    birim: str
    kullanici_olcegi: float | None
    # "uygun" | "yetersiz" | "esik_yok" | "olcek_bilinmiyor" | "bolge_bilinmiyor"
    durum: str
    aciklama: str
    ek_not: str = ""

    @property
    def uygun_mu(self) -> bool:
        return self.durum == "uygun"


def olcek_uygunlugu(nace_kodu: str, il: str | None,
                    olcek: float | None) -> UygunlukSonucu | None:
    """Kullanicinin olcegi, 9903 EK-3'teki asgari sarti karsiliyor mu?

    Yalnizca BOLUM A (tarim) kodlari icin calisir; diger kodlar icin None
    doner cunku o sartlar profilde bulunmayan verilere (asgari sabit yatirim
    tutari vb.) dayaniyor ve hukum vermek yaniltici olur.
    """
    esik = _ESIK_INDEKSI.get((nace_kodu or "").strip())
    if esik is None:
        return None

    bolge = il_bolgesi(il)
    if bolge is None:
        return UygunlukSonucu(
            nace_kodu=esik.nace_kodu, yatirim_konusu=esik.yatirim_konusu,
            il=il, bolge=None, asgari=None, birim=esik.birim,
            kullanici_olcegi=olcek, durum="bolge_bilinmiyor",
            aciklama="Iliniz taninmadigi icin bolge belirlenemedi; asgari sart "
                     "bolgeye gore degistigi icin karsilastirma yapilamadi.",
            ek_not=esik.ek_not,
        )

    if not esik.bolge_esikleri:
        return UygunlukSonucu(
            nace_kodu=esik.nace_kodu, yatirim_konusu=esik.yatirim_konusu,
            il=il, bolge=bolge, asgari=None, birim=esik.birim,
            kullanici_olcegi=olcek, durum="esik_yok",
            aciklama="Karar metninde bu yatirim konusu icin bolge bazli asgari "
                     "olcek sarti belirtilmemistir.",
            ek_not=esik.ek_not,
        )

    asgari = esik.bolge_esikleri.get(bolge)
    if asgari is None:
        return UygunlukSonucu(
            nace_kodu=esik.nace_kodu, yatirim_konusu=esik.yatirim_konusu,
            il=il, bolge=bolge, asgari=None, birim=esik.birim,
            kullanici_olcegi=olcek, durum="esik_yok",
            aciklama=f"{bolge}. bolge icin Karar metninde asgari olcek sarti "
                     "tanimlanmamistir.",
            ek_not=esik.ek_not,
        )

    if olcek is None or olcek <= 0:
        return UygunlukSonucu(
            nace_kodu=esik.nace_kodu, yatirim_konusu=esik.yatirim_konusu,
            il=il, bolge=bolge, asgari=asgari, birim=esik.birim,
            kullanici_olcegi=None, durum="olcek_bilinmiyor",
            aciklama=f"{il} {bolge}. bolgede; bu yatirim konusu icin asgari "
                     f"{asgari:,.0f} {esik.birim} sarti var. Olceginizi "
                     "girerseniz karsilayip karsilamadiginizi soyleyebilirim."
                     .replace(",", "."),
            ek_not=esik.ek_not,
        )

    if olcek >= asgari:
        return UygunlukSonucu(
            nace_kodu=esik.nace_kodu, yatirim_konusu=esik.yatirim_konusu,
            il=il, bolge=bolge, asgari=asgari, birim=esik.birim,
            kullanici_olcegi=olcek, durum="uygun",
            aciklama=f"{il} {bolge}. bolgede asgari sart {asgari:,.0f} "
                     f"{esik.birim}; sizin olceginiz {olcek:,.0f} "
                     f"{esik.birim} - sarti karsiliyorsunuz."
                     .replace(",", "."),
            ek_not=esik.ek_not,
        )

    eksik = asgari - olcek
    return UygunlukSonucu(
        nace_kodu=esik.nace_kodu, yatirim_konusu=esik.yatirim_konusu,
        il=il, bolge=bolge, asgari=asgari, birim=esik.birim,
        kullanici_olcegi=olcek, durum="yetersiz",
        aciklama=f"{il} {bolge}. bolgede asgari sart {asgari:,.0f} "
                 f"{esik.birim}; sizin olceginiz {olcek:,.0f} {esik.birim}. "
                 f"Yatirim tesvik belgesi icin {eksik:,.0f} {esik.birim} daha "
                 "gerekiyor.".replace(",", "."),
        ek_not=esik.ek_not,
    )


def kategoriden_uygunluk(tarim_kategori: str | None, il: str | None,
                         olcek: float | None) -> list[UygunlukSonucu]:
    """Profil kategorisinden ilgili NACE kodlarini bulup degerlendirir."""
    kategori = (tarim_kategori or "").strip().lower()
    kodlar = TARIM_KATEGORI_NACE.get(kategori, ())
    sonuclar = []
    for kod in kodlar:
        s = olcek_uygunlugu(kod, il, olcek)
        if s is not None:
            sonuclar.append(s)
    return sonuclar
