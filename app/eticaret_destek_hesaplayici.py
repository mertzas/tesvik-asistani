"""
E-ihracat pazaryeri komisyon/reklam/depolama giderleri icin Ticaret
Bakanlığı'nın 5986 sayılı E-İhracat Destekleri Kararı kapsamındaki geri
ödeme tahminini hesaplar.

Kaynak: scripts/seed_eticaret_tesvikleri.py ile eklenen Tesvik kaydı
(2026-07-12'de ticaret.gov.tr ve resmi genelgeye atıfta bulunan ikincil
kaynaklardan doğrulandı). Standart oran %50, hedef ülkelerde %70'e kadar
çıkabilir - hangi ülkelerin "hedef ülke" sayıldığı Bakanlık'ın güncel
listesine bağlıdır ve burada sabit kodlanmamıştır (kullanıcıya bunu
teyit etmesi gerektiği açıkça söylenir).

ÖNEMLİ SINIRLAMA: Bu bir başvuru garantisi DEĞİLDİR. İhracatçı birliği
üyeliği olmayan bir firma bu destekten yararlanamaz - hesaplayıcı bu
şartı sağlayıp sağlamadığını sormaz, sadece "eğer uygunsanız ne kadar
geri alabilirsiniz" sorusuna kaba bir tahmin verir.
"""
from dataclasses import dataclass, field

STANDART_ORAN = 0.50
HEDEF_ULKE_ORAN = 0.70

DESTEKLENEN_GIDER_KALEMLERI = [
    "pazara_giris_raporu",
    "dijital_pazaryeri_tanitim",
    "e_ihracat_tanitim",
    "siparis_karsilama_hizmeti",
    "yurt_disi_depo_kirasi",
    "pazaryeri_entegrasyon",
    "pazaryeri_komisyon",
]

GIDER_KALEMI_ETIKETLERI = {
    "pazara_giris_raporu": "Pazara giriş raporu",
    "dijital_pazaryeri_tanitim": "Dijital pazaryeri tanıtım (reklam)",
    "e_ihracat_tanitim": "E-ihracat tanıtım/pazarlama",
    "siparis_karsilama_hizmeti": "Sipariş karşılama hizmeti",
    "yurt_disi_depo_kirasi": "Yurt dışı depo kirası",
    "pazaryeri_entegrasyon": "Pazaryeri entegrasyon",
    "pazaryeri_komisyon": "Pazaryeri komisyon",
}


@dataclass
class GiderKalemiSonucu:
    kalem: str
    etiket: str
    yillik_gider_tl: float
    tahmini_geri_odeme_tl: float


@dataclass
class EticaretDestekSonucu:
    hedef_ulke_mi: bool
    uygulanan_oran: float
    kalemler: list[GiderKalemiSonucu] = field(default_factory=list)
    toplam_yillik_gider_tl: float = 0.0
    toplam_tahmini_geri_odeme_tl: float = 0.0
    notlar: list[str] = field(default_factory=list)


def eticaret_destek_hesapla(
    giderler: dict[str, float],
    hedef_ulke_mi: bool = False,
    ihracatci_birligi_uyesi_mi: bool | None = None,
) -> EticaretDestekSonucu:
    """
    `giderler`: DESTEKLENEN_GIDER_KALEMLERI anahtarlarından (tümü opsiyonel)
    yıllık TL tutarına bir sözlük. Tanınmayan anahtarlar sessizce yok
    sayılır (yazım hatası riskine karşı, en azından crash etmez).

    ihracatci_birligi_uyesi_mi: None ise (bilinmiyor) uyarı notu eklenir;
    False ise net bir "bu haliyle başvuramazsınız" uyarısı eklenir.
    """
    oran = HEDEF_ULKE_ORAN if hedef_ulke_mi else STANDART_ORAN
    notlar = []

    kalemler = []
    toplam_gider = 0.0
    toplam_geri_odeme = 0.0
    for kalem, tutar in (giderler or {}).items():
        if kalem not in DESTEKLENEN_GIDER_KALEMLERI or not tutar or tutar <= 0:
            continue
        geri_odeme = round(tutar * oran, 2)
        kalemler.append(GiderKalemiSonucu(
            kalem=kalem,
            etiket=GIDER_KALEMI_ETIKETLERI[kalem],
            yillik_gider_tl=tutar,
            tahmini_geri_odeme_tl=geri_odeme,
        ))
        toplam_gider += tutar
        toplam_geri_odeme += geri_odeme

    if ihracatci_birligi_uyesi_mi is False:
        notlar.append(
            "⚠️ İhracatçı birliği üyeliğiniz yok görünüyor - bu şart karşılanmadan "
            "E-İhracat Destekleri'ne (5986 sayılı Karar) başvuru KABUL EDİLMEZ. "
            "Aşağıdaki tahmin, önce üyelik sağladığınız senaryo içindir."
        )
    elif ihracatci_birligi_uyesi_mi is None:
        notlar.append(
            "İhracatçı birliği üyeliğiniz bilinmiyor - bu destek SADECE bir "
            "ihracatçı birliğine üye firmalara açıktır, üyelik olmadan başvuru "
            "kabul edilmez. Üyeliğinizi teyit edin."
        )

    notlar.append(
        f"Uygulanan oran %{oran*100:.0f} olarak hesaplandı "
        + ("(hedef ülke listesinde olduğunuzu belirttiniz)." if hedef_ulke_mi
           else "(standart oran; hedef ülke listesindeki bir pazara satış yapıyorsanız oran %70'e çıkabilir - Bakanlık'ın güncel hedef ülke listesini kontrol edin).")
    )
    notlar.append(
        "Bu bir TAHMİNDİR, başvuru garantisi değildir. Yıllık üst limitler "
        "yararlanıcı tipine (şirket/pazaryeri/konsorsiyum) göre değişir ve her "
        "yıl güncellenir - Bakanlık'ın 'Genelge Ekleri' sayfasındaki güncel "
        "üst limit tablosuyla karşılaştırın, hesaplanan tutar bu limiti aşıyorsa "
        "gerçek geri ödemeniz limitle sınırlı kalır."
    )
    if not kalemler:
        notlar.append("Hiçbir desteklenen gider kalemi girilmedi - tahmin hesaplanamadı.")

    return EticaretDestekSonucu(
        hedef_ulke_mi=hedef_ulke_mi,
        uygulanan_oran=oran,
        kalemler=kalemler,
        toplam_yillik_gider_tl=round(toplam_gider, 2),
        toplam_tahmini_geri_odeme_tl=round(toplam_geri_odeme, 2),
        notlar=notlar,
    )
