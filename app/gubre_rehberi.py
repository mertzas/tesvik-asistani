"""
Çilek gübre dozaj rehberi - dikim tarihinden hesaplanan fenolojik evreye göre
gerçekçi N-P2O5-K2O-CaO fertigasyon dozları.

Kaynak / temel alınan agronomik referanslar:
  - T.C. Tarım ve Orman Bakanlığı, Çilek Yetiştiriciliği Teknik Talimatı
  - Kacal, E. & Köse, C. (2015) "Çilekte Gübreleme" - Atatürk Bahçe
    Kültürleri Araştırma Enstitüsü
  - Ontario Ministry of Agriculture, "Strawberry Fertigation Guide" (nutrient
    uptake curve şeklen benzer, oran olarak Türkiye pratiğine uyarlanmıştır)

ÖNEMLİ SINIRLAMA: Bu bir toprak/yaprak analizi YERİNE GEÇMEZ. Aşağıdaki
dozlar "ortalama toprak" (orta bünyeli, gübre geçmişi normal) varsayımıyla
dekar başına GENEL YÖN GÖSTERİCİ değerlerdir. Tuzluluk (EC), pH ve toprak
analiz sonucu elinizde varsa mutlaka o veriye göre ayarlama yapılmalıdır -
bu modül öyle bir analiz verisi almaz, sadece fenolojik evreye göre kaba
bir başlangıç noktası sunar.
"""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class GubreEvresi:
    anahtar: str
    ad: str
    gun_araligi: tuple[int, int]  # dikimden itibaren [baslangic, bitis) gün
    n_kg_da: float   # kg/dekar, saf azot (N)
    p2o5_kg_da: float
    k2o_kg_da: float
    cao_kg_da: float
    haftalik_uygulama_sikligi: int  # haftada kaç fertigasyon
    aciklama: str
    dikkat: str = ""


# Dikim sonrası gün sayısına göre sıralı evreler (açık tarla, tek sezonluk
# sonbahar dikimi frigo fide varsayımı - en yaygın Türkiye pratiği).
EVRELER: list[GubreEvresi] = [
    GubreEvresi(
        anahtar="kok_tutma",
        ad="Kök Tutma / Köklenme (0-30 gün)",
        gun_araligi=(0, 30),
        n_kg_da=1.5, p2o5_kg_da=2.0, k2o_kg_da=1.0, cao_kg_da=0.5,
        haftalik_uygulama_sikligi=1,
        aciklama="Bu dönemde azot düşük tutulur; öncelik kök gelişimidir. "
                 "Fosfor ağırlıklı, düşük dozlu fertigasyon önerilir.",
        dikkat="Fide dikiminden sonraki ilk 10 günde gübre YERİNE sadece "
               "temiz su ile can suyu verin; kök çürüklüğü riskini artırır.",
    ),
    GubreEvresi(
        anahtar="vejetatif_gelisim",
        ad="Vejetatif Gelişim / Yaprak-Taç Oluşumu (30-90 gün)",
        gun_araligi=(30, 90),
        n_kg_da=4.0, p2o5_kg_da=2.5, k2o_kg_da=3.0, cao_kg_da=1.5,
        haftalik_uygulama_sikligi=2,
        aciklama="Bitki taç ve yaprak kütlesini oluşturur; azot ihtiyacı "
                 "sezonun en yüksek dönemlerinden biridir.",
        dikkat="Aşırı azot bu dönemde yaprağı şişirip çiçek tomurcuğu "
               "oluşumunu geciktirebilir - önerilen dozu aşmayın.",
    ),
    GubreEvresi(
        anahtar="ciceklenme",
        ad="Çiçeklenme (90-120 gün)",
        gun_araligi=(90, 120),
        n_kg_da=2.5, p2o5_kg_da=3.5, k2o_kg_da=4.0, cao_kg_da=2.0,
        haftalik_uygulama_sikligi=2,
        aciklama="Azot dozu kademeli düşürülür, fosfor ve potasyum "
                 "ağırlığı artar - çiçek tutumu ve tozlaşma başarısı için.",
        dikkat="Bu dönemde ilaçlama yapıyorsanız arı/polinatör aktif "
               "saatlerinde (öğle) uygulamadan kaçının.",
    ),
    GubreEvresi(
        anahtar="meyve_gelisimi",
        ad="Meyve Gelişimi / Büyüme (120-150 gün)",
        gun_araligi=(120, 150),
        n_kg_da=2.0, p2o5_kg_da=2.0, k2o_kg_da=6.0, cao_kg_da=3.0,
        haftalik_uygulama_sikligi=3,
        aciklama="Potasyum ve kalsiyum bu dönemde belirgin şekilde "
                 "yükselir - meyve iriliği, şeker oranı ve sertliği için.",
        dikkat="Kalsiyum eksikliği meyve ucu çürüklüğüne (tip burn benzeri "
               "belirti) yol açabilir; CaO dozunu atlamayın.",
    ),
    GubreEvresi(
        anahtar="hasat_donemi",
        ad="Hasat Dönemi (150-210 gün)",
        gun_araligi=(150, 210),
        n_kg_da=1.5, p2o5_kg_da=1.0, k2o_kg_da=5.0, cao_kg_da=2.5,
        haftalik_uygulama_sikligi=3,
        aciklama="Azot minimumda tutulur (raf ömrünü kısaltır); potasyum "
                 "yüksek kalır - meyve kalitesini korumak için sürekli "
                 "hasat boyunca devam eder.",
        dikkat="Hasat öncesi bekleme süresi (PHI) olan ilaç kalıntısı "
               "riskini önlemek için gübre değil, ilaçlama kayıtlarınızı "
               "kontrol edin (bkz. hasat kilidi paneli).",
    ),
    GubreEvresi(
        anahtar="hasat_sonrasi",
        ad="Hasat Sonrası Toparlanma (210+ gün)",
        gun_araligi=(210, 10_000),
        n_kg_da=2.5, p2o5_kg_da=1.5, k2o_kg_da=2.0, cao_kg_da=1.0,
        haftalik_uygulama_sikligi=1,
        aciklama="Bitkinin gelecek sezon için taç gözü ve kök rezervi "
                 "toparlaması amacıyla dengeli, orta dozlu besleme.",
    ),
]


@dataclass
class GubreDozOnerisi:
    dikim_tarihi: date | None
    gun_sayisi: int | None
    evre: str | None
    evre_aciklama: str | None
    n_kg_da: float | None
    p2o5_kg_da: float | None
    k2o_kg_da: float | None
    cao_kg_da: float | None
    haftalik_uygulama_sikligi: int | None
    dikkat: str | None
    alan_dekar: float | None
    toplam_n_kg: float | None
    toplam_p2o5_kg: float | None
    toplam_k2o_kg: float | None
    toplam_cao_kg: float | None
    notlar: list[str] = field(default_factory=list)


def _evre_bul(gun: int) -> GubreEvresi | None:
    for evre in EVRELER:
        baslangic, bitis = evre.gun_araligi
        if baslangic <= gun < bitis:
            return evre
    return None


def gubre_dozaj_oneri_getir(
    dikim_tarihi: date | None,
    alan_dekar: float | None = None,
    bugun: date | None = None,
) -> GubreDozOnerisi:
    """
    Parselin dikim tarihinden bugüne kadar geçen gün sayısına göre uygun
    fenolojik evreyi bulur ve o evreye ait dekar başı N-P2O5-K2O-CaO
    dozlarını döner. alan_dekar verilmişse parselin TOPLAM ihtiyacını da
    hesaplar.

    dikim_tarihi yoksa (henüz kayıt girilmemişse) evre hesaplanamaz,
    notlar alanında bunu açıkça belirtir - hiçbir zaman varsayılan/tahmini
    bir tarih uydurmaz.
    """
    notlar: list[str] = []

    if dikim_tarihi is None:
        notlar.append(
            "Parsel için dikim tarihi girilmemiş - fenolojik evre "
            "hesaplanamıyor. Doğru dozaj önerisi için parsel kaydına "
            "dikim tarihini ekleyin."
        )
        return GubreDozOnerisi(
            dikim_tarihi=None, gun_sayisi=None, evre=None, evre_aciklama=None,
            n_kg_da=None, p2o5_kg_da=None, k2o_kg_da=None, cao_kg_da=None,
            haftalik_uygulama_sikligi=None, dikkat=None, alan_dekar=alan_dekar,
            toplam_n_kg=None, toplam_p2o5_kg=None, toplam_k2o_kg=None,
            toplam_cao_kg=None, notlar=notlar,
        )

    bugun = bugun or date.today()
    gun_sayisi = (bugun - dikim_tarihi).days

    if gun_sayisi < 0:
        notlar.append("Dikim tarihi gelecekte görünüyor - tarihi kontrol edin.")
        evre = None
    else:
        evre = _evre_bul(gun_sayisi)

    if evre is None:
        notlar.append(
            "Bu gün sayısı için tanımlı bir fenolojik evre bulunamadı."
        )
        return GubreDozOnerisi(
            dikim_tarihi=dikim_tarihi, gun_sayisi=gun_sayisi, evre=None,
            evre_aciklama=None, n_kg_da=None, p2o5_kg_da=None, k2o_kg_da=None,
            cao_kg_da=None, haftalik_uygulama_sikligi=None, dikkat=None,
            alan_dekar=alan_dekar, toplam_n_kg=None, toplam_p2o5_kg=None,
            toplam_k2o_kg=None, toplam_cao_kg=None, notlar=notlar,
        )

    notlar.append(
        "Bu değerler ORTA BÜNYELİ, gübre geçmişi normal toprak varsayımına "
        "dayanan genel yön göstericilerdir; toprak/yaprak analiziniz varsa "
        "onu esas alın."
    )

    toplam_n = toplam_p = toplam_k = toplam_ca = None
    if alan_dekar and alan_dekar > 0:
        toplam_n = round(evre.n_kg_da * alan_dekar, 2)
        toplam_p = round(evre.p2o5_kg_da * alan_dekar, 2)
        toplam_k = round(evre.k2o_kg_da * alan_dekar, 2)
        toplam_ca = round(evre.cao_kg_da * alan_dekar, 2)

    return GubreDozOnerisi(
        dikim_tarihi=dikim_tarihi,
        gun_sayisi=gun_sayisi,
        evre=evre.ad,
        evre_aciklama=evre.aciklama,
        n_kg_da=evre.n_kg_da,
        p2o5_kg_da=evre.p2o5_kg_da,
        k2o_kg_da=evre.k2o_kg_da,
        cao_kg_da=evre.cao_kg_da,
        haftalik_uygulama_sikligi=evre.haftalik_uygulama_sikligi,
        dikkat=evre.dikkat or None,
        alan_dekar=alan_dekar,
        toplam_n_kg=toplam_n,
        toplam_p2o5_kg=toplam_p,
        toplam_k2o_kg=toplam_k,
        toplam_cao_kg=toplam_ca,
        notlar=notlar,
    )


def tum_evreleri_listele() -> list[GubreEvresi]:
    """Tüm sezon boyunca evre haritasını döner - önizleme/planlama ekranı için."""
    return EVRELER
