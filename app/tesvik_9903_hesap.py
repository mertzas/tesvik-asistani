"""
9903 sayili Karar kapsaminda somut destek tutari hesaplayici.

NEDEN BU MODUL VAR
------------------
Uygulama "butce etkisi" vaat ediyor ama olcum (2026-09-26): 176 kaydin
162'sinde (%92) hicbir tutar bilgisi yoktu ve tarim disi her profilde
"toplam tahmini destek: 0 TL" gorunuyordu. Kullanici somut bir rakam
gormeden karar veremez.

Yatirim tesvik belgesi desteklerinin tutari kayit basina sabit bir TL degeri
DEGIL, yatirimin kendisine bagli bir fonksiyondur:

    vergi indirimi     = sabit yatirim tutari x yatirima katki orani
    sigorta primi      = ilave istihdam x asgari ucret primi x bolge suresi
    faiz destegi       = kredi x (repo orani x program yuzdesi) x yil
    makine destegi     = uygun makine bedeli x %25  (tavanlarla sinirli)

Bu yuzden tutar veritabaninda saklanmiyor, BURADA hesaplaniyor. Boylece
kullanicinin gerçek yatirim buyuklugune gore olceklenir.

TUM ORANLAR VE SURELER KARAR METNINDEN BIREBIR ALINMISTIR
---------------------------------------------------------
Kaynak: 9903 sayili "Yatirimlarda Devlet Yardimlari Hakkinda Karar",
Resmi Gazete 30/05/2025.
  MADDE 12 - vergi indirimi / yatirima katki oranlari
  MADDE 14 - sigorta primi isveren hissesi destegi ve bolge sureleri
  MADDE 15 - faiz veya kar payi destegi
  MADDE 16 - makine destegi
  MADDE 5  - asgari sabit yatirim tutarlari, basvuru son tarihi
Dogrulama: 2026-09-26, PDF metninden cikarildi.

HESAPLARIN NITELIGI
-------------------
Bunlar TAVAN/AZAMI tutarlardir, garanti degildir:
  - Tesvik belgesi duzenlenmesi Bakanligin sektorel/mali/teknik
    degerlendirmesine baglidir (MADDE 5/4).
  - Vergi indirimi ancak KAZANC olustukca kullanilir; zarar eden bir
    isletme hesaplanan tutarin tamamini kullanamaz.
  - Faiz destegi ve makine destegi AYNI yatirimda birlikte alinamaz
    (MADDE 16/3); hesap ikisini ayri ayri gosterir, toplamaz.
Bu uyarilar her sonucta kullaniciya donuyor - tavani kesin gelir gibi
sunmak yaniltici olur.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.nace_9903 import il_bolgesi

# ---------------------------------------------------------------------------
# MADDE 12 - yatirima katki oranlari (vergi indirimi)
# ---------------------------------------------------------------------------
PROGRAMLAR: dict[str, str] = {
    "teknoloji_hamlesi": "Teknoloji Hamlesi Programı",
    "yerel_kalkinma_hamlesi": "Yerel Kalkınma Hamlesi Programı",
    "stratejik_hamle": "Stratejik Hamle Programı",
    "oncelikli_yatirimlar": "Öncelikli Yatırımlar Teşvik Sistemi",
    "hedef_yatirimlar": "Hedef Yatırımlar Teşvik Sistemi",
}

# Turkiye Yuzyili Kalkinma Hamlesi kapsamindaki programlar. Makine destegi
# YALNIZCA bunlara veriliyor (MADDE 16/1) ve sigorta primi suresi farkli.
KALKINMA_HAMLESI = {"teknoloji_hamlesi", "yerel_kalkinma_hamlesi", "stratejik_hamle"}

YATIRIMA_KATKI_ORANI: dict[str, float] = {
    "teknoloji_hamlesi": 0.50,
    "yerel_kalkinma_hamlesi": 0.50,
    "stratejik_hamle": 0.40,
    "oncelikli_yatirimlar": 0.30,
    "hedef_yatirimlar": 0.20,
}

# Vergi, yatirima katki tutarina ulasincaya kadar %60 INDIRIMLI uygulanir
# (MADDE 12/1). Yani devlet verginin tamamini silmiyor; %60'ini siliyor.
VERGI_INDIRIM_ORANI = 0.60

# ---------------------------------------------------------------------------
# MADDE 14 - sigorta primi isveren hissesi destegi
# ---------------------------------------------------------------------------
# 6. bolgede primin TAMAMI, diger bolgelerde %50'si butceden karsilanir.
SIGORTA_PRIMI_KARSILAMA = {1: 0.50, 2: 0.50, 3: 0.50, 4: 0.50, 5: 0.50, 6: 1.00}

# Genel uygulama sureleri (yil)
SIGORTA_PRIMI_SURESI = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 12}

# Turkiye Yuzyili Kalkinma Hamlesi kapsaminda: 6. bolgede 12 yil, diger
# bolgelerde 8 yil (MADDE 14/3) - genel sureden belirgin daha uzun.
SIGORTA_PRIMI_SURESI_HAMLE = {1: 8, 2: 8, 3: 8, 4: 8, 5: 8, 6: 12}

# ---------------------------------------------------------------------------
# MADDE 15 - faiz veya kar payi destegi
# ---------------------------------------------------------------------------
# Kredinin, sabit yatirim tutarinin en fazla %70'ine karsilik gelen kismi
# destekten yararlanir.
FAIZ_DESTEGI_KREDI_ORANI = 0.70
FAIZ_DESTEGI_AZAMI_YIL = 5

# program -> (repo oraninin yuzdesi, azami puan)
FAIZ_DESTEGI: dict[str, tuple[float, float]] = {
    "teknoloji_hamlesi": (0.40, 20.0),
    "yerel_kalkinma_hamlesi": (0.40, 20.0),
    "stratejik_hamle": (0.30, 15.0),
    "oncelikli_yatirimlar": (0.25, 12.5),
    "hedef_yatirimlar": (0.25, 12.5),
}
# Hedef yatirimlarda faiz destegi YALNIZCA 4, 5 ve 6. bolgede verilir
# (MADDE 15/1-c). Bu kisiti atlamak, 1. bolgedeki kullaniciya hak etmedigi
# bir destegi gostermek olurdu.
FAIZ_DESTEGI_BOLGE_KISITI: dict[str, set[int]] = {
    "hedef_yatirimlar": {4, 5, 6},
}

# ---------------------------------------------------------------------------
# MADDE 16 - makine destegi (yalnizca Kalkinma Hamlesi)
# ---------------------------------------------------------------------------
MAKINE_DESTEGI_ORANI = 0.25
# Yalnizca birim fiyati bu tutarin ustundeki makineler icin.
MAKINE_BIRIM_FIYAT_ESIGI = 2_000_000
# program -> (sabit yatirim tutarina gore ust oran, mutlak tavan TL)
MAKINE_DESTEGI_TAVANI: dict[str, tuple[float, float]] = {
    "teknoloji_hamlesi": (0.15, 240_000_000),
    "yerel_kalkinma_hamlesi": (0.15, 240_000_000),
    "stratejik_hamle": (0.15, 180_000_000),
}

# ---------------------------------------------------------------------------
# MADDE 5 - asgari sabit yatirim tutari
# ---------------------------------------------------------------------------
# EK-3'te konu bazinda ayrica belirtilmemisse gecerli genel esik.
ASGARI_SABIT_YATIRIM = {1: 12_000_000, 2: 12_000_000,
                        3: 6_000_000, 4: 6_000_000, 5: 6_000_000, 6: 6_000_000}
BASVURU_SON_TARIHI = "31/12/2030"

KAYNAK = ("9903 sayılı Yatırımlarda Devlet Yardımları Hakkında Karar "
          "(Resmî Gazete, 30/05/2025)")


@dataclass
class DestekKalemi:
    ad: str
    tutar_tl: float | None
    madde: str
    aciklama: str
    # Hesap icin eksik veri varsa burada soylenir; tutar None kalir.
    eksik_bilgi: str | None = None


@dataclass
class DestekHesabi:
    program: str
    program_adi: str
    il: str | None
    bolge: int | None
    sabit_yatirim_tl: float
    asgari_sabit_yatirim_tl: float | None
    asgari_karsilaniyor_mu: bool | None
    kalemler: list[DestekKalemi] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)
    # Faiz ve makine destegi birlikte alinamaz; toplam bu yuzden iki
    # senaryo halinde veriliyor.
    toplam_makine_senaryosu_tl: float = 0.0
    toplam_faiz_senaryosu_tl: float = 0.0

    def sozluk(self) -> dict:
        return {
            "program": self.program,
            "program_adi": self.program_adi,
            "il": self.il,
            "bolge": self.bolge,
            "sabit_yatirim_tl": self.sabit_yatirim_tl,
            "asgari_sabit_yatirim_tl": self.asgari_sabit_yatirim_tl,
            "asgari_karsilaniyor_mu": self.asgari_karsilaniyor_mu,
            "kalemler": [
                {"ad": k.ad, "tutar_tl": k.tutar_tl, "madde": k.madde,
                 "aciklama": k.aciklama, "eksik_bilgi": k.eksik_bilgi}
                for k in self.kalemler
            ],
            "toplam_faiz_senaryosu_tl": self.toplam_faiz_senaryosu_tl,
            "toplam_makine_senaryosu_tl": self.toplam_makine_senaryosu_tl,
            "uyarilar": self.uyarilar,
            "kaynak": KAYNAK,
        }


def _tl(x: float) -> str:
    return f"{x:,.0f} TL".replace(",", ".")


def hesapla(
    program: str,
    il: str | None,
    sabit_yatirim_tl: float,
    *,
    makine_techizat_tl: float | None = None,
    kredi_tl: float | None = None,
    ilave_istihdam: int | None = None,
    aylik_asgari_ucret_isveren_primi_tl: float | None = None,
    repo_faiz_orani: float | None = None,
) -> DestekHesabi:
    """9903 kapsaminda azami destek tutarlarini hesaplar.

    program: PROGRAMLAR anahtarlarindan biri.
    sabit_yatirim_tl: teşvik belgesine kaydedilecek sabit yatirim tutari.
    makine_techizat_tl: birim fiyati 2 milyon TL ustundeki makine bedeli
        (makine destegi icin; Kalkinma Hamlesi programlarinda gecerli).
    kredi_tl: kullanilacak TL yatirim kredisi (faiz destegi icin).
    ilave_istihdam: yatirimla olusacak ilave istihdam sayisi.
    aylik_asgari_ucret_isveren_primi_tl: asgari ucrete tekabul eden aylik
        isveren primi. Verilmezse sigorta primi destegi HESAPLANMAZ ve
        eksik bilgi olarak raporlanir - bu tutar her yil degistigi ve
        SGK tarafindan belirlendigi icin kod icine gomulmez.
    repo_faiz_orani: TCMB bir hafta vadeli repo ihale faiz orani (yuzde).
        Verilmezse faiz destegi hesaplanmaz.
    """
    if program not in PROGRAMLAR:
        raise ValueError(
            f"Bilinmeyen program: {program!r}. Gecerli: {', '.join(PROGRAMLAR)}")
    if sabit_yatirim_tl is None or sabit_yatirim_tl <= 0:
        raise ValueError("sabit_yatirim_tl pozitif olmali")

    bolge = il_bolgesi(il)
    asgari = ASGARI_SABIT_YATIRIM.get(bolge) if bolge else None
    karsiliyor = (sabit_yatirim_tl >= asgari) if asgari else None

    h = DestekHesabi(
        program=program, program_adi=PROGRAMLAR[program], il=il, bolge=bolge,
        sabit_yatirim_tl=sabit_yatirim_tl,
        asgari_sabit_yatirim_tl=asgari, asgari_karsilaniyor_mu=karsiliyor,
    )

    if bolge is None:
        h.uyarilar.append(
            "İliniz tanınmadığı için bölge belirlenemedi. Sigorta primi süresi, "
            "asgari yatırım tutarı ve bazı desteklerin bölge kısıtı hesaba "
            "katılamadı."
        )
    if karsiliyor is False:
        h.uyarilar.append(
            f"Sabit yatırım tutarınız ({_tl(sabit_yatirim_tl)}) {bolge}. bölge "
            f"için geçerli asgari tutarın ({_tl(asgari)}) altında. EK-3'te "
            "yatırım konunuza özel bir asgari tutar belirtilmişse o geçerlidir; "
            "aksi halde bu haliyle teşvik belgesi düzenlenmez."
        )

    # --- Vergi indirimi (MADDE 12) -----------------------------------------
    katki_orani = YATIRIMA_KATKI_ORANI[program]
    katki_tutari = sabit_yatirim_tl * katki_orani
    h.kalemler.append(DestekKalemi(
        ad="Vergi indirimi (yatırıma katkı tutarı)",
        tutar_tl=round(katki_tutari, 2),
        madde="MADDE 12",
        aciklama=(
            f"Sabit yatırımın %{katki_orani*100:.0f}'i kadar yatırıma katkı "
            f"tutarı: {_tl(katki_tutari)}. Bu tutara ulaşılıncaya kadar gelir/"
            f"kurumlar vergisi %{VERGI_INDIRIM_ORANI*100:.0f} indirimli "
            "uygulanır. Yani ödemeyeceğiniz verginin üst sınırı bu tutardır; "
            "kazanç oluştukça kullanılır, zarar eden işletme tamamını kullanamaz."
        ),
    ))

    # --- Sigorta primi isveren hissesi (MADDE 14) --------------------------
    if bolge is None:
        h.kalemler.append(DestekKalemi(
            ad="Sigorta primi işveren hissesi desteği", tutar_tl=None,
            madde="MADDE 14",
            aciklama="Destek süresi ve oranı bölgeye göre değişir.",
            eksik_bilgi="İl bilinmiyor.",
        ))
    else:
        sure = (SIGORTA_PRIMI_SURESI_HAMLE if program in KALKINMA_HAMLESI
                else SIGORTA_PRIMI_SURESI)[bolge]
        karsilama = SIGORTA_PRIMI_KARSILAMA[bolge]
        if ilave_istihdam and aylik_asgari_ucret_isveren_primi_tl:
            tutar = (ilave_istihdam * aylik_asgari_ucret_isveren_primi_tl
                     * 12 * sure * karsilama)
            h.kalemler.append(DestekKalemi(
                ad="Sigorta primi işveren hissesi desteği",
                tutar_tl=round(tutar, 2), madde="MADDE 14",
                aciklama=(
                    f"{ilave_istihdam} ilave istihdam x {sure} yıl x "
                    f"%{karsilama*100:.0f} karşılama = {_tl(tutar)}. "
                    f"{bolge}. bölgede süre {sure} yıl"
                    + (" (Türkiye Yüzyılı Kalkınma Hamlesi kapsamında uzun süre)"
                       if program in KALKINMA_HAMLESI else "")
                    + ". Yalnızca asgari ücrete tekabül eden kısım karşılanır."
                ),
            ))
        else:
            eksikler = []
            if not ilave_istihdam:
                eksikler.append("ilave istihdam sayısı")
            if not aylik_asgari_ucret_isveren_primi_tl:
                eksikler.append("asgari ücret işveren primi (SGK'nın o yıl "
                                "için ilan ettiği tutar)")
            h.kalemler.append(DestekKalemi(
                ad="Sigorta primi işveren hissesi desteği", tutar_tl=None,
                madde="MADDE 14",
                aciklama=(
                    f"{bolge}. bölgede {sure} yıl boyunca, asgari ücrete "
                    f"tekabül eden işveren priminin %{karsilama*100:.0f}'i "
                    "bütçeden karşılanır."
                ),
                eksik_bilgi="Hesap için gerekli: " + ", ".join(eksikler) + ".",
            ))

    # --- Faiz veya kar payi destegi (MADDE 15) -----------------------------
    izinli_bolgeler = FAIZ_DESTEGI_BOLGE_KISITI.get(program)
    if izinli_bolgeler is not None and bolge is not None and bolge not in izinli_bolgeler:
        h.kalemler.append(DestekKalemi(
            ad="Faiz veya kâr payı desteği", tutar_tl=0.0, madde="MADDE 15",
            aciklama=(
                f"{PROGRAMLAR[program]} kapsamında faiz desteği yalnızca "
                f"{', '.join(str(b) for b in sorted(izinli_bolgeler))}. "
                f"bölgelerde verilir; {bolge}. bölgede bu destek yok."
            ),
        ))
    else:
        yuzde, azami_puan = FAIZ_DESTEGI[program]
        if repo_faiz_orani and kredi_tl:
            destekli_kredi = min(kredi_tl, sabit_yatirim_tl * FAIZ_DESTEGI_KREDI_ORANI)
            puan = min(repo_faiz_orani * yuzde, azami_puan)
            tutar = destekli_kredi * (puan / 100) * FAIZ_DESTEGI_AZAMI_YIL
            h.kalemler.append(DestekKalemi(
                ad="Faiz veya kâr payı desteği", tutar_tl=round(tutar, 2),
                madde="MADDE 15",
                aciklama=(
                    f"Kredinin sabit yatırımın %{FAIZ_DESTEGI_KREDI_ORANI*100:.0f}"
                    f"'ine kadarki kısmı destekleniyor: {_tl(destekli_kredi)}. "
                    f"TCMB repo oranı %{repo_faiz_orani:.2f}'nin "
                    f"%{yuzde*100:.0f}'i = {puan:.2f} puan "
                    f"(azami {azami_puan} puan), azami "
                    f"{FAIZ_DESTEGI_AZAMI_YIL} yıl -> {_tl(tutar)}. "
                    "Gerçek ödeme, kredinin kullanım ve vade tarihlerindeki "
                    "repo oranlarına göre yapılır."
                ),
            ))
        else:
            eksikler = []
            if not kredi_tl:
                eksikler.append("kullanılacak yatırım kredisi tutarı")
            if not repo_faiz_orani:
                eksikler.append("TCMB bir hafta vadeli repo faiz oranı")
            h.kalemler.append(DestekKalemi(
                ad="Faiz veya kâr payı desteği", tutar_tl=None, madde="MADDE 15",
                aciklama=(
                    f"Kredinin, sabit yatırımın %"
                    f"{FAIZ_DESTEGI_KREDI_ORANI*100:.0f}'ine kadarki kısmı için "
                    f"TCMB repo oranının %{yuzde*100:.0f}'i "
                    f"(azami {azami_puan} puan), azami "
                    f"{FAIZ_DESTEGI_AZAMI_YIL} yıl karşılanır."
                ),
                eksik_bilgi="Hesap için gerekli: " + ", ".join(eksikler) + ".",
            ))

    # --- Makine destegi (MADDE 16) -----------------------------------------
    if program not in MAKINE_DESTEGI_TAVANI:
        h.kalemler.append(DestekKalemi(
            ad="Makine desteği", tutar_tl=0.0, madde="MADDE 16",
            aciklama=("Makine desteği yalnızca Türkiye Yüzyılı Kalkınma Hamlesi "
                      "programlarında (Teknoloji, Yerel Kalkınma, Stratejik "
                      "Hamle) verilir."),
        ))
    else:
        oran_tavani, mutlak_tavan = MAKINE_DESTEGI_TAVANI[program]
        if makine_techizat_tl:
            ham = makine_techizat_tl * MAKINE_DESTEGI_ORANI
            tavan = min(sabit_yatirim_tl * oran_tavani, mutlak_tavan)
            tutar = min(ham, tavan)
            sinir = ""
            if ham > tavan:
                sinir = (f" Hesaplanan {_tl(ham)}, tavan nedeniyle "
                         f"{_tl(tavan)} ile sınırlandı "
                         f"(sabit yatırımın %{oran_tavani*100:.0f}'i veya "
                         f"{_tl(mutlak_tavan)}, hangisi küçükse).")
            h.kalemler.append(DestekKalemi(
                ad="Makine desteği", tutar_tl=round(tutar, 2), madde="MADDE 16",
                aciklama=(
                    f"Birim fiyatı {_tl(MAKINE_BIRIM_FIYAT_ESIGI)} ve üzerindeki "
                    f"makine/teçhizat bedelinin "
                    f"%{MAKINE_DESTEGI_ORANI*100:.0f}'i: {_tl(tutar)}.{sinir} "
                    "Birim fiyatı bu eşiğin altındaki makineler dahil değildir."
                ),
            ))
        else:
            h.kalemler.append(DestekKalemi(
                ad="Makine desteği", tutar_tl=None, madde="MADDE 16",
                aciklama=(
                    f"Birim fiyatı {_tl(MAKINE_BIRIM_FIYAT_ESIGI)} ve "
                    f"üzerindeki makine bedelinin "
                    f"%{MAKINE_DESTEGI_ORANI*100:.0f}'i; sabit yatırımın "
                    f"%{oran_tavani*100:.0f}'ini ve {_tl(mutlak_tavan)}'yi "
                    "aşmamak üzere."
                ),
                eksik_bilgi=("Hesap için gerekli: birim fiyatı 2 milyon TL "
                             "üzerindeki makine/teçhizat bedeli."),
            ))

    # --- Toplamlar (iki senaryo) ------------------------------------------
    def _bul(ad: str) -> float:
        for k in h.kalemler:
            if k.ad.startswith(ad):
                return k.tutar_tl or 0.0
        return 0.0

    ortak = _bul("Vergi indirimi") + _bul("Sigorta primi")
    faiz = _bul("Faiz veya kâr payı")
    makine = _bul("Makine desteği")
    h.toplam_faiz_senaryosu_tl = round(ortak + faiz, 2)
    h.toplam_makine_senaryosu_tl = round(ortak + makine, 2)

    if faiz and makine:
        h.uyarilar.append(
            "Faiz desteği ile makine desteği AYNI yatırımda birlikte "
            "alınamaz (MADDE 16/3). Bu yüzden iki ayrı senaryo toplamı "
            "verildi; ikisini toplamayın."
        )

    h.uyarilar.append(
        "Bu tutarlar AZAMİ değerlerdir, garanti değildir: teşvik belgesi "
        "düzenlenmesi Bakanlığın sektörel, malî ve teknik değerlendirmesine "
        "bağlıdır (MADDE 5/4). Vergi indirimi ancak kazanç oluştukça "
        f"kullanılır. Teşvik belgesi müracaatları {BASVURU_SON_TARIHI} "
        "tarihine kadar değerlendirilir."
    )
    if not (makine_techizat_tl or kredi_tl or ilave_istihdam):
        h.uyarilar.append(
            "Yalnızca sabit yatırım tutarı girildi; makine bedeli, kredi "
            "tutarı ve ilave istihdam sayısını da girerseniz toplam desteğin "
            "büyük kısmı hesaplanabilir."
        )
    return h


def programlari_karsilastir(il: str | None, sabit_yatirim_tl: float,
                            **kw) -> list[DestekHesabi]:
    """Bes programi ayni yatirim icin karsilastirir, en yuksek destek basta.

    Kullanici hangi programa basvurabilecegini bilmeyebilir; program secimi
    yatirim konusuna ve Bakanlik degerlendirmesine bagli oldugu icin
    karsilastirma "hangisine girerseniz ne alirsiniz" sorusunu cevaplar.
    """
    sonuclar = [hesapla(p, il, sabit_yatirim_tl, **kw) for p in PROGRAMLAR]
    sonuclar.sort(key=lambda h: -max(h.toplam_faiz_senaryosu_tl,
                                     h.toplam_makine_senaryosu_tl))
    return sonuclar
