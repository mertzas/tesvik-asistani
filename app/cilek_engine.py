"""
Çilek Üretim Yönetim Paneli - Risk & Finans Motoru

Bu modul tum "hesaplanan" degerleri (don riski, mantar hastalik riski,
PHI/hasat kilidi, birim maliyet, nakit akisi) uretir. Tasarim kurallari:

1. HICBIR FONKSIYON EKSIK VERI ICIN CRASH ETMEZ. Sensor okumasi yoksa,
   ilgili DurumSeviyesi.VERI_YOK olarak donulur - asla varsayilan bir
   sayisal deger (0, oda sicakligi vb.) ILE DOLDURULMAZ. Ciftci "guvenli"
   yesil bir kart gorup gercekte sensor kopmus olabilir - bu, gercek bir
   don/hastalik riskinin kacirilmasi anlamina gelir ve kabul edilemez.

2. Butun esik degerleri (nem %, EC dS/m, sicaklik °C) cilek icin YAYGIN
   PRATIKTEN turetilmis YAKLASIK karar-destek esikleridir; toprak tipi,
   cesit, fenolojik donem (cicek/yesil meyve/olgun meyve) ve bolgeye gore
   degisir. Bu bir agronomik teshis/tavsiye sistemi DEGILDIR - suphede
   Ziraat Muhendisi/Tarim Il-Ilce Mudurlugu'ne danisilmalidir. Bu uyari
   ilgili panel mesajlarinda da tekrarlanir (bkz. budget.py'deki benzer
   yasal/etik yaklasim).
"""
from dataclasses import dataclass
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import MacroIndicator
from app.models_cilek import (
    Parsel, SensorOkuma, SensorTipi, OrtamTipi,
    FertigasyonTank, SulamaDongusu,
    Ilaclama,
    PazarFiyati,
    HasatKaydi, SogukZincirOkuma,
    GiderKalemi,
)
from app.schemas_cilek import (
    RiskSeviyesi, SensorKart, DonRiskiDurumu, MantarRiskiDurumu,
    TankDurumu, SulamaDurumuKart, FertigasyonPaneli,
    HasatKilidiDurumu,
    PazarFiyatNoktasi, KaliteBazliTalep, PazarPaneli,
    IsciPerformansi, HasatPerformansiPaneli,
    SogukZincirKart,
    FinansalSaglikPaneli,
    ErkenUyariPaneli,
)
from app.hava_api import bolgesel_hava_durumu_getir, bolgesel_saatlik_tahmin_getir, yas_hazne_sicakligi_tahmin_et

VERI_BAYATLAMA_ESIGI_DAKIKA = 60  # bu sureden eski okuma "bayat/supheli" isaretlenir


def _simdi() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Naive datetime'lari (ör. SQLite'tan donen) UTC olarak isaretler, karsilastirma hatasini onler."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ============ ORTAK: SENSOR OKUMA ============

def en_son_okuma(db: Session, parsel_id: int, sensor_tipi: SensorTipi) -> Optional[SensorOkuma]:
    return (
        db.query(SensorOkuma)
        .filter(SensorOkuma.parsel_id == parsel_id, SensorOkuma.sensor_tipi == sensor_tipi)
        .order_by(SensorOkuma.olcum_zamani.desc())
        .first()
    )


def _sensor_kart(
    okuma: Optional[SensorOkuma],
    risk_hesapla,
) -> SensorKart:
    """risk_hesapla(deger: float) -> (RiskSeviyesi, str) seklinde bir fonksiyon alir."""
    if okuma is None:
        return SensorKart(
            sensor_tipi="bilinmiyor",
            risk_seviyesi=RiskSeviyesi.VERI_YOK,
            mesaj="Bu parsel için henüz hiç sensör verisi alınmadı.",
        )

    olcum_zamani = _aware(okuma.olcum_zamani)
    yas_dakika = (_simdi() - olcum_zamani).total_seconds() / 60.0
    bayat_mi = yas_dakika > VERI_BAYATLAMA_ESIGI_DAKIKA

    if bayat_mi:
        return SensorKart(
            sensor_tipi=okuma.sensor_tipi.value,
            deger=okuma.deger,
            birim=okuma.birim,
            olcum_zamani=olcum_zamani,
            veri_yasi_dakika=round(yas_dakika, 1),
            bayat_mi=True,
            risk_seviyesi=RiskSeviyesi.VERI_YOK,
            mesaj=f"Son veri {int(yas_dakika)} dakika önce alındı - sensör bağlantısını kontrol edin.",
        )

    seviye, mesaj = risk_hesapla(okuma.deger)
    return SensorKart(
        sensor_tipi=okuma.sensor_tipi.value,
        deger=okuma.deger,
        birim=okuma.birim,
        olcum_zamani=olcum_zamani,
        veri_yasi_dakika=round(yas_dakika, 1),
        bayat_mi=False,
        risk_seviyesi=seviye,
        mesaj=mesaj,
    )


# ============ 1. KRİTİK TARIMSAL VERİLER ============

def toprak_nemi_karti(db: Session, parsel_id: int) -> SensorKart:
    def _risk(deger: float):
        if deger < 40:
            return RiskSeviyesi.KRITIK, f"Toprak nemi %{deger:.0f} - kuraklık stresi riski, acil sulama gerekebilir."
        if deger < 60:
            return RiskSeviyesi.RISKLI, f"Toprak nemi %{deger:.0f} - hedef aralığın (60-85%) altında."
        if deger <= 85:
            return RiskSeviyesi.GUVENLI, f"Toprak nemi %{deger:.0f} - hedef aralıkta."
        return RiskSeviyesi.RISKLI, f"Toprak nemi %{deger:.0f} - aşırı yüksek, kök çürüklüğü/oksijen yetersizliği riski."

    return _sensor_kart(en_son_okuma(db, parsel_id, SensorTipi.TOPRAK_NEMI), _risk)


def toprak_ec_karti(db: Session, parsel_id: int) -> SensorKart:
    def _risk(deger: float):
        if deger > 2.0:
            return RiskSeviyesi.KRITIK, f"Toprak EC {deger:.2f} dS/m - tuzluluk kritik seviyede, çilek kökleri hassastır."
        if deger > 1.0:
            return RiskSeviyesi.RISKLI, f"Toprak EC {deger:.2f} dS/m - tuzluluk yükseliyor, gübre/sulama dozunu gözden geçirin."
        return RiskSeviyesi.GUVENLI, f"Toprak EC {deger:.2f} dS/m - normal aralıkta."

    return _sensor_kart(en_son_okuma(db, parsel_id, SensorTipi.TOPRAK_EC), _risk)


def don_riski_hesapla(db: Session, parsel: Parsel) -> DonRiskiDurumu:
    hava_okuma = en_son_okuma(db, parsel.id, SensorTipi.HAVA_SICAKLIGI)
    yas_hazne_okuma = en_son_okuma(db, parsel.id, SensorTipi.YAS_HAZNE_SICAKLIGI)

    hava = hava_okuma.deger if hava_okuma else None
    yas_hazne = yas_hazne_okuma.deger if yas_hazne_okuma else None
    veri_kaynagi = "sensor"

    if hava is None and yas_hazne is None:
        # Saha sensoru yok/kopuk - parselin konumu tanimliysa Open-Meteo'dan
        # BOLGESEL bir yedek dene. Bu gercek sensorun yerini TUTMAZ; sonucta
        # veri_kaynagi="bolgesel_tahmin" olarak acikca isaretlenir.
        if parsel.enlem is not None and parsel.boylam is not None:
            bolgesel = bolgesel_hava_durumu_getir(parsel.enlem, parsel.boylam)
            if bolgesel is not None:
                hava = bolgesel.sicaklik
                if bolgesel.nispi_nem is not None:
                    yas_hazne = yas_hazne_sicakligi_tahmin_et(bolgesel.sicaklik, bolgesel.nispi_nem)
                veri_kaynagi = "bolgesel_tahmin"

        if hava is None and yas_hazne is None:
            return DonRiskiDurumu(
                risk_seviyesi=RiskSeviyesi.VERI_YOK,
                veri_kaynagi=veri_kaynagi,
                mesaj="Sıcaklık sensör verisi yok ve bölgesel tahmin de alınamadı - don riski değerlendirilemiyor.",
            )

    # Yaş hazne sıcaklığı (wet bulb) don koruma sistemlerinde asıl referanstır;
    # buharlaşma soğutması nedeniyle bitki yüzeyi hava sıcaklığından daha düşük olabilir.
    referans = yas_hazne if yas_hazne is not None else hava
    kaynak_adi = "yaş hazne sıcaklığı" if yas_hazne is not None else "hava sıcaklığı"
    kaynak_notu = " (bölgesel tahmin - saha sensörü değil)" if veri_kaynagi == "bolgesel_tahmin" else ""

    if referans <= 0:
        seviye = RiskSeviyesi.KRITIK
        mesaj = f"{kaynak_adi.capitalize()} {referans:.1f}°C{kaynak_notu} - DON RİSKİ KRİTİK! Çiçek/yeşil meyve zarar görebilir, koruma önlemi (sprinkler/örtü) uygulayın."
    elif referans <= 2:
        seviye = RiskSeviyesi.RISKLI
        mesaj = f"{kaynak_adi.capitalize()} {referans:.1f}°C{kaynak_notu} - don riski yaklaşıyor, gece boyu takip edin."
    else:
        seviye = RiskSeviyesi.GUVENLI
        mesaj = f"{kaynak_adi.capitalize()} {referans:.1f}°C{kaynak_notu} - don riski yok."

    return DonRiskiDurumu(
        risk_seviyesi=seviye,
        hava_sicakligi=hava,
        yas_hazne_sicakligi=yas_hazne,
        veri_kaynagi=veri_kaynagi,
        mesaj=mesaj,
    )


def _sicaklik_skoru(sicaklik: float, opt_min: float, opt_max: float, tolerans: float = 8.0) -> float:
    """Optimal aralik icinde 100, disina ciktikca dogrusal azalan 0-100 skoru."""
    if opt_min <= sicaklik <= opt_max:
        return 100.0
    fark = (opt_min - sicaklik) if sicaklik < opt_min else (sicaklik - opt_max)
    return max(0.0, 100.0 - (fark / tolerans) * 100.0)


def _nem_skoru(nem: float, esik_min: float, doygunluk_araligi: float = 15.0) -> float:
    """Esik altinda 0, esik + doygunluk_araligi'nda 100'e ulasan dogrusal skor."""
    if nem <= esik_min:
        return 0.0
    return min(100.0, (nem - esik_min) / doygunluk_araligi * 100.0)


def mantar_riski_hesapla(db: Session, parsel: Parsel) -> MantarRiskiDurumu:
    sicaklik_okuma = en_son_okuma(db, parsel.id, SensorTipi.HAVA_SICAKLIGI)
    nem_okuma = en_son_okuma(db, parsel.id, SensorTipi.NISPI_NEM)
    sirkulasyon_okuma = en_son_okuma(db, parsel.id, SensorTipi.SERA_SIRKULASYON)

    sicaklik = sicaklik_okuma.deger if sicaklik_okuma else None
    nem = nem_okuma.deger if nem_okuma else None
    veri_kaynagi = "sensor"

    # Bolgesel (disari) tahmini SADECE acik tarlada yedek olarak kullanilir.
    # Serada dis ortam nem/sicaklik degerleri ic ortami temsil etmez (orn.
    # kapali sera disaridan cok daha nemli/sicak olabilir) - bu durumda
    # yanlis bir "guvenli" veya "kritik" izlenimi vermemek icin VERI_YOK
    # olarak birakmak, yanlis bolgesel tahminden daha guvenlidir.
    if (sicaklik is None or nem is None) and parsel.ortam_tipi == OrtamTipi.ACIK_TARLA \
            and parsel.enlem is not None and parsel.boylam is not None:
        bolgesel = bolgesel_hava_durumu_getir(parsel.enlem, parsel.boylam)
        if bolgesel is not None and bolgesel.nispi_nem is not None:
            sicaklik = bolgesel.sicaklik
            nem = bolgesel.nispi_nem
            veri_kaynagi = "bolgesel_tahmin"

    if sicaklik is None or nem is None:
        return MantarRiskiDurumu(
            risk_seviyesi=RiskSeviyesi.VERI_YOK,
            veri_kaynagi=veri_kaynagi,
            mesaj="Sıcaklık ve/veya nem verisi eksik, bölgesel tahmin de alınamadı - hastalık riski hesaplanamıyor.",
        )

    # Botrytis (gri küf): yüksek nem (>%85) + ılıman sıcaklık (15-25°C) kombinasyonunda hızlanır.
    botrytis = _nem_skoru(nem, esik_min=85) * (_sicaklik_skoru(sicaklik, 15, 25) / 100.0)
    # Külleme: serbest su gerekmez, orta-yüksek nem (>%60) + 18-27°C aralığında gelişir.
    kulleme = _nem_skoru(nem, esik_min=60) * (_sicaklik_skoru(sicaklik, 18, 27) / 100.0)

    # Sera içinde hava hareketi zayıfsa (durgun nem birikimi) riski artırıcı çarpan uygula.
    sirkulasyon_carpani = 1.0
    if parsel.ortam_tipi == OrtamTipi.SERA and sirkulasyon_okuma is not None and sirkulasyon_okuma.deger < 0.2:
        sirkulasyon_carpani = 1.15

    skor = min(100.0, max(botrytis, kulleme) * sirkulasyon_carpani)
    kaynak_notu = " (bölgesel tahmin - saha sensörü değil)" if veri_kaynagi == "bolgesel_tahmin" else ""

    if skor >= 60:
        seviye = RiskSeviyesi.KRITIK
        etken = "Gri küf (Botrytis)" if botrytis >= kulleme else "Külleme"
        mesaj = f"{etken} riski KRİTİK (skor {skor:.0f}/100){kaynak_notu} - yakın zamanda ilaçlama/havalandırma planlayın."
    elif skor >= 30:
        seviye = RiskSeviyesi.RISKLI
        mesaj = f"Mantar hastalığı riski yükseliyor (skor {skor:.0f}/100){kaynak_notu} - yakından takip edin."
    else:
        seviye = RiskSeviyesi.GUVENLI
        mesaj = f"Mantar hastalığı riski düşük (skor {skor:.0f}/100){kaynak_notu}."

    return MantarRiskiDurumu(
        risk_seviyesi=seviye,
        skor=round(skor, 1),
        botrytis_bileseni=round(botrytis, 1),
        kulleme_bileseni=round(kulleme, 1),
        kullanilan_sicaklik=sicaklik,
        kullanilan_nem=nem,
        veri_kaynagi=veri_kaynagi,
        mesaj=mesaj + " (Karar destek göstergesidir, kesin teşhis için ziraat mühendisine danışın.)",
    )


def erken_uyari_hesapla(parsel: Parsel, saat_sayisi: int = 48) -> ErkenUyariPaneli:
    """
    Open-Meteo'nun SAATLIK TAHMIN verisiyle onumuzdeki `saat_sayisi` saat
    icinde beklenen en dusuk sicaklik (don riski) ve en yuksek hastalik
    riski skorunu hesaplar. don_riski_hesapla/mantar_riski_hesapla'nin
    aksine bu fonksiyon saha sensoru olsa BILE calisir - amac "su an"
    degil "onumuzdeki gunlerde ne olabilir" sorusuna cevap vermektir,
    bu yuzden VERI_YOK yerine sadece konum eksikse/ag hatasi varsa
    kullanilabilir=False doner.
    """
    if parsel.enlem is None or parsel.boylam is None:
        return ErkenUyariPaneli(
            kullanilabilir=False,
            saat_sayisi=saat_sayisi,
            mesaj="Erken uyarı için parselin konumu (enlem/boylam) tanımlı değil.",
        )

    tahminler = bolgesel_saatlik_tahmin_getir(parsel.enlem, parsel.boylam, saat_sayisi)
    if not tahminler:
        return ErkenUyariPaneli(
            kullanilabilir=False,
            saat_sayisi=saat_sayisi,
            mesaj="Bölgesel hava tahmini şu anda alınamıyor.",
        )

    min_sicaklik_saat = min(tahminler, key=lambda t: t.sicaklik)
    min_yas_hazne = yas_hazne_sicakligi_tahmin_et(min_sicaklik_saat.sicaklik, min_sicaklik_saat.nispi_nem) \
        if min_sicaklik_saat.nispi_nem is not None else min_sicaklik_saat.sicaklik
    don_bekleniyor = min_yas_hazne <= 2

    en_yuksek_risk_skoru = None
    en_yuksek_risk_zamani = None
    for t in tahminler:
        if t.nispi_nem is None:
            continue
        botrytis = _nem_skoru(t.nispi_nem, esik_min=85) * (_sicaklik_skoru(t.sicaklik, 15, 25) / 100.0)
        kulleme = _nem_skoru(t.nispi_nem, esik_min=60) * (_sicaklik_skoru(t.sicaklik, 18, 27) / 100.0)
        skor = max(botrytis, kulleme)
        if en_yuksek_risk_skoru is None or skor > en_yuksek_risk_skoru:
            en_yuksek_risk_skoru = skor
            en_yuksek_risk_zamani = t.zaman

    parcalar = []
    if don_bekleniyor:
        parcalar.append(
            f"⚠️ Önümüzdeki {saat_sayisi} saat içinde {min_sicaklik_saat.zaman.strftime('%d.%m %H:%M')} "
            f"civarında don riski bekleniyor (tahmini {min_yas_hazne:.1f}°C)."
        )
    else:
        parcalar.append(f"Önümüzdeki {saat_sayisi} saatte don riski beklenmiyor (en düşük ~{min_yas_hazne:.1f}°C).")

    if en_yuksek_risk_skoru is not None and en_yuksek_risk_skoru >= 60:
        parcalar.append(
            f"⚠️ {en_yuksek_risk_zamani.strftime('%d.%m %H:%M')} civarında mantar hastalığı riski "
            f"yükselecek gibi görünüyor (tahmini skor {en_yuksek_risk_skoru:.0f}/100)."
        )

    return ErkenUyariPaneli(
        kullanilabilir=True,
        saat_sayisi=saat_sayisi,
        don_riski_bekleniyor_mu=don_bekleniyor,
        min_beklenen_sicaklik=round(min_yas_hazne, 1),
        min_sicaklik_zamani=min_sicaklik_saat.zaman,
        en_yuksek_hastalik_riski_skoru=round(en_yuksek_risk_skoru, 1) if en_yuksek_risk_skoru is not None else None,
        en_yuksek_risk_zamani=en_yuksek_risk_zamani,
        mesaj=" ".join(parcalar) + " (Bölgesel hava tahmini bazlı öngörüdür, kesinlik garantisi vermez.)",
    )


# ============ 2. AKILLI SULAMA & FERTİGASYON ============

def fertigasyon_paneli(db: Session, parsel_id: int) -> FertigasyonPaneli:
    tanklar_db = db.query(FertigasyonTank).filter(FertigasyonTank.parsel_id == parsel_id).all()

    tanklar = []
    for t in tanklar_db:
        doluluk_yuzde = None
        risk = RiskSeviyesi.VERI_YOK
        if t.doluluk_litre is not None and t.kapasite_litre:
            doluluk_yuzde = round((t.doluluk_litre / t.kapasite_litre) * 100, 1)
            if doluluk_yuzde < 15:
                risk = RiskSeviyesi.KRITIK
            elif doluluk_yuzde < 30:
                risk = RiskSeviyesi.RISKLI
            else:
                risk = RiskSeviyesi.GUVENLI

        tanklar.append(TankDurumu(
            tank_tipi=t.tank_tipi.value,
            doluluk_yuzde=doluluk_yuzde,
            doluluk_litre=t.doluluk_litre,
            kapasite_litre=t.kapasite_litre,
            risk_seviyesi=risk,
            son_guncelleme=_aware(t.son_guncelleme),
        ))

    dongusu = (
        db.query(SulamaDongusu)
        .filter(SulamaDongusu.parsel_id == parsel_id)
        .order_by(SulamaDongusu.sonraki_sulama_zamani.desc())
        .first()
    )

    if dongusu is None:
        sulama = SulamaDurumuKart(mesaj="Planlanmış sulama döngüsü bulunamadı.")
    else:
        sonraki = _aware(dongusu.sonraki_sulama_zamani)
        geri_sayim = None
        if sonraki is not None:
            geri_sayim = max(0.0, (sonraki - _simdi()).total_seconds() / 60.0)

        sulama = SulamaDurumuKart(
            durum=dongusu.durum.value if dongusu.durum else None,
            sonraki_sulama_zamani=sonraki,
            geri_sayim_dakika=round(geri_sayim, 1) if geri_sayim is not None else None,
            verilen_su_ph=dongusu.verilen_su_ph,
            verilen_su_ec=dongusu.verilen_su_ec,
        )

    return FertigasyonPaneli(tanklar=tanklar, sulama=sulama)


# ============ 3. ZARARLI & HASTALIK / MRL-PHI ============

def hasat_kilidi_durumu(db: Session, parsel_id: int) -> HasatKilidiDurumu:
    """
    Parseldeki TUM ilaclama kayitlarini tarayip, hala PHI suresi dolmamis
    (yani en ileri serbest_kalma_tarihi'ne sahip) kaydi bulur. Kilit durumu
    HER SORGUDA bu kayitlardan yeniden hesaplanir - ayri bir "kilitli"
    bayragi saklanmaz (bkz. models_cilek.Ilaclama docstring).
    """
    kayitlar = db.query(Ilaclama).filter(Ilaclama.parsel_id == parsel_id).all()

    if not kayitlar:
        return HasatKilidiDurumu(kilitli=False, mesaj="Bu parselde ilaçlama kaydı yok - hasat serbest.")

    en_kisitlayici = None
    en_ileri_serbest_tarih = None

    for k in kayitlar:
        uygulama = _aware(k.uygulama_tarihi)
        serbest_tarih = uygulama + timedelta(days=k.phi_gun)
        if en_ileri_serbest_tarih is None or serbest_tarih > en_ileri_serbest_tarih:
            en_ileri_serbest_tarih = serbest_tarih
            en_kisitlayici = k

    simdi = _simdi()
    if en_ileri_serbest_tarih > simdi:
        kalan_saat = (en_ileri_serbest_tarih - simdi).total_seconds() / 3600.0
        return HasatKilidiDurumu(
            kilitli=True,
            ilac_adi=en_kisitlayici.ilac_adi,
            uygulama_tarihi=_aware(en_kisitlayici.uygulama_tarihi),
            serbest_kalma_tarihi=en_ileri_serbest_tarih,
            kalan_saat=round(kalan_saat, 1),
            mesaj=(
                f"HASADA KİLİTLİ: {en_kisitlayici.ilac_adi} uygulaması sonrası PHI süresi "
                f"({en_kisitlayici.phi_gun} gün) dolmadı. Serbest kalma: "
                f"{en_ileri_serbest_tarih.strftime('%d.%m.%Y %H:%M')} "
                f"(kalan ~{kalan_saat:.0f} saat)."
            ),
        )

    return HasatKilidiDurumu(
        kilitli=False,
        ilac_adi=en_kisitlayici.ilac_adi,
        uygulama_tarihi=_aware(en_kisitlayici.uygulama_tarihi),
        serbest_kalma_tarihi=en_ileri_serbest_tarih,
        kalan_saat=0.0,
        mesaj=f"Hasat serbest. Son ilaçlama ({en_kisitlayici.ilac_adi}) PHI süresini tamamladı.",
    )


# ============ 4. ANLIK PAZAR & TİCARİ BORSA ============

def pazar_paneli(db: Session, gun_sayisi: int = 7) -> PazarPaneli:
    esik_tarih = date.today() - timedelta(days=gun_sayisi)
    kayitlar = (
        db.query(PazarFiyati)
        .filter(PazarFiyati.tarih >= esik_tarih)
        .order_by(PazarFiyati.tarih.asc())
        .all()
    )

    if not kayitlar:
        return PazarPaneli(mesaj="Son dönem için pazar fiyat verisi bulunamadı.")

    # Gün bazında ortalama fiyat (tum kaynak/kalite karisik - genel trend gostergesi icin)
    gunluk: dict[date, list[float]] = {}
    for k in kayitlar:
        gunluk.setdefault(k.tarih, []).append(k.fiyat_kg)

    son_7_gun = [
        PazarFiyatNoktasi(tarih=gun, fiyat_kg=round(sum(fiyatlar) / len(fiyatlar), 2))
        for gun, fiyatlar in sorted(gunluk.items())
    ]

    ilk_fiyat = son_7_gun[0].fiyat_kg
    son_fiyat = son_7_gun[-1].fiyat_kg
    degisim_yuzde = ((son_fiyat - ilk_fiyat) / ilk_fiyat * 100) if ilk_fiyat else 0

    if degisim_yuzde > 2:
        trend = "yukselen"
    elif degisim_yuzde < -2:
        trend = "dusen"
    else:
        trend = "sabit"

    # Kalite bazli talep (ortalama fiyat + toplam hacim)
    kalite_gruplari: dict[str, list[PazarFiyati]] = {}
    for k in kayitlar:
        kalite_gruplari.setdefault(k.kalite_sinifi.value, []).append(k)

    kalite_bazli_talep = []
    for kalite, grup in kalite_gruplari.items():
        fiyatlar = [g.fiyat_kg for g in grup]
        hacimler = [g.hacim_kg for g in grup if g.hacim_kg is not None]
        kalite_bazli_talep.append(KaliteBazliTalep(
            kalite_sinifi=kalite,
            ortalama_fiyat_kg=round(sum(fiyatlar) / len(fiyatlar), 2),
            toplam_hacim_kg=round(sum(hacimler), 1) if hacimler else None,
        ))

    return PazarPaneli(
        guncel_fiyat_kg=son_fiyat,
        guncel_fiyat_tarihi=son_7_gun[-1].tarih,
        trend=trend,
        son_7_gun=son_7_gun,
        kalite_bazli_talep=kalite_bazli_talep,
    )


# ============ 5. HASAT & SOĞUK ZİNCİR ============

def hasat_performansi_bugun(db: Session, parsel_id: int) -> HasatPerformansiPaneli:
    bugun = date.today()
    kayitlar = (
        db.query(HasatKaydi)
        .filter(HasatKaydi.parsel_id == parsel_id, HasatKaydi.tarih == bugun)
        .all()
    )

    if not kayitlar:
        return HasatPerformansiPaneli(mesaj="Bugün için henüz hasat kaydı girilmedi.")

    isci_gruplari: dict[str, list[HasatKaydi]] = {}
    for k in kayitlar:
        ad = k.isci_adi or "Bilinmeyen İşçi"
        isci_gruplari.setdefault(ad, []).append(k)

    isciler = []
    toplam_kg = 0.0
    toplam_maliyet = 0.0
    maliyet_hesaplanabildi = True

    for ad, grup in isci_gruplari.items():
        kg = sum(g.toplanan_kasa * (g.kasa_agirlik_kg or 5.0) for g in grup)
        sure = sum(g.sure_saat for g in grup if g.sure_saat is not None) or None
        kasa_saat = None
        if sure:
            kg_per_saat = kg / sure
            kasa_saat = round(kg_per_saat / (grup[0].kasa_agirlik_kg or 5.0), 2)

        iscilik_maliyeti = None
        for g in grup:
            if g.sure_saat is not None and g.saatlik_ucret is not None:
                iscilik_maliyeti = (iscilik_maliyeti or 0.0) + g.sure_saat * g.saatlik_ucret

        toplam_kg += kg
        if iscilik_maliyeti is not None:
            toplam_maliyet += iscilik_maliyeti
        else:
            maliyet_hesaplanabildi = False

        isciler.append(IsciPerformansi(
            isci_adi=ad,
            toplanan_kg=round(kg, 1),
            sure_saat=sure,
            kasa_saat_hizi=kasa_saat,
            iscilik_maliyeti=round(iscilik_maliyeti, 2) if iscilik_maliyeti is not None else None,
        ))

    return HasatPerformansiPaneli(
        bugunku_toplam_kg=round(toplam_kg, 1),
        bugunku_toplam_iscilik_maliyeti=round(toplam_maliyet, 2) if maliyet_hesaplanabildi and toplam_maliyet else None,
        isciler=isciler,
    )


def soguk_zincir_durumu(db: Session, org_id) -> list[SogukZincirKart]:
    # Her depo icin en son okumayi bul (depo_adi bazinda distinct son kayit)
    alt_sorgu = (
        db.query(
            SogukZincirOkuma.depo_adi,
            func.max(SogukZincirOkuma.olcum_zamani).label("son_zaman"),
        )
        .filter(SogukZincirOkuma.org_id == org_id)
        .group_by(SogukZincirOkuma.depo_adi)
        .subquery()
    )

    son_okumalar = (
        db.query(SogukZincirOkuma)
        .join(
            alt_sorgu,
            (SogukZincirOkuma.depo_adi == alt_sorgu.c.depo_adi)
            & (SogukZincirOkuma.olcum_zamani == alt_sorgu.c.son_zaman),
        )
        .all()
    )

    kartlar = []
    for okuma in son_okumalar:
        if okuma.sicaklik is None:
            risk = RiskSeviyesi.VERI_YOK
            mesaj = "Sıcaklık verisi alınamıyor - depo sensörünü kontrol edin."
        elif okuma.sicaklik > okuma.hedef_sicaklik_max + 3 or okuma.sicaklik < okuma.hedef_sicaklik_min - 3:
            risk = RiskSeviyesi.KRITIK
            mesaj = f"{okuma.sicaklik:.1f}°C - hedef aralığın ({okuma.hedef_sicaklik_min:.0f}-{okuma.hedef_sicaklik_max:.0f}°C) çok dışında, soğuk zincir kırılmış olabilir."
        elif okuma.sicaklik > okuma.hedef_sicaklik_max or okuma.sicaklik < okuma.hedef_sicaklik_min:
            risk = RiskSeviyesi.RISKLI
            mesaj = f"{okuma.sicaklik:.1f}°C - hedef aralığın hafif dışında."
        else:
            risk = RiskSeviyesi.GUVENLI
            mesaj = f"{okuma.sicaklik:.1f}°C - hedef aralıkta."

        kartlar.append(SogukZincirKart(
            depo_adi=okuma.depo_adi,
            sicaklik=okuma.sicaklik,
            hedef_sicaklik_min=okuma.hedef_sicaklik_min,
            hedef_sicaklik_max=okuma.hedef_sicaklik_max,
            risk_seviyesi=risk,
            olcum_zamani=_aware(okuma.olcum_zamani),
            mesaj=mesaj,
        ))

    return kartlar


# ============ 6. MİKRO FİNANSAL SAĞLIK ============

def finansal_saglik_hesapla(db: Session, parsel_id: int, gun_sayisi: int = 30) -> FinansalSaglikPaneli:
    bugun = date.today()
    baslangic = bugun - timedelta(days=gun_sayisi)

    giderler = (
        db.query(GiderKalemi)
        .filter(GiderKalemi.parsel_id == parsel_id, GiderKalemi.tarih >= baslangic, GiderKalemi.tarih <= bugun)
        .all()
    )
    hasatlar = (
        db.query(HasatKaydi)
        .filter(HasatKaydi.parsel_id == parsel_id, HasatKaydi.tarih >= baslangic, HasatKaydi.tarih <= bugun)
        .all()
    )

    toplam_gider = sum(g.tutar for g in giderler)
    gider_dagilimi: dict[str, float] = {}
    for g in giderler:
        gider_dagilimi[g.kategori.value] = gider_dagilimi.get(g.kategori.value, 0.0) + g.tutar

    toplam_hasat_kg = sum(h.toplanan_kasa * (h.kasa_agirlik_kg or 5.0) for h in hasatlar)

    notlar = [
        f"Hesaplama dönemi: son {gun_sayisi} gün ({baslangic.strftime('%d.%m.%Y')} - {bugun.strftime('%d.%m.%Y')}).",
    ]

    # Mevcut TCMB EVDS entegrasyonundan (app/scrapers/tuik_macro.py ile beslenen
    # MacroIndicator tablosu) yillik enflasyon ve tarimsal girdi fiyat artislarini
    # cek - bu, giderlerin gecen donemden bu yana neden arttigina dair baglam sunar.
    tufe = db.query(MacroIndicator).filter(MacroIndicator.anahtar == "yillik_tufe").first()
    if tufe is not None:
        notlar.append(
            f"Yıllık TÜFE %{tufe.deger:.1f} (TCMB/EVDS) - girdi maliyetlerinizin bu dönemde "
            f"enflasyon oranında artmış olabileceğini dikkate alın."
        )

    en_hizli_artan_girdi = None
    girdi_anahtarlari = {
        "tarim_gubre_yillik_degisim": "Gübre",
        "tarim_ilac_yillik_degisim": "Tarımsal İlaç",
        "tarim_bina_yillik_degisim": "Sera/Bina Yapımı",
        "tarim_makine_bakim_yillik_degisim": "Makine Bakımı",
    }
    en_yuksek_artis = None
    for anahtar, etiket in girdi_anahtarlari.items():
        gosterge = db.query(MacroIndicator).filter(MacroIndicator.anahtar == anahtar).first()
        if gosterge is not None and (en_yuksek_artis is None or gosterge.deger > en_yuksek_artis[1]):
            en_yuksek_artis = (etiket, gosterge.deger)

    if en_yuksek_artis is not None:
        en_hizli_artan_girdi = en_yuksek_artis
        notlar.append(
            f"TÜİK Tarımsal Girdi Fiyat Endeksi'ne göre en hızlı artan girdi kaleminiz "
            f"{en_hizli_artan_girdi[0]} (son 1 yılda %{en_hizli_artan_girdi[1]:.1f}) - "
            f"bu kalemde toplu alım/sözleşmeli tedarik seçeneklerini değerlendirin."
        )

    birim_maliyet_kg = None
    if toplam_hasat_kg > 0:
        birim_maliyet_kg = round(toplam_gider / toplam_hasat_kg, 2)
    elif toplam_gider > 0:
        notlar.append("Dönem içinde gider girildi ama henüz hasat kaydı yok - birim maliyet hesaplanamıyor.")

    tahmini_gelir = None
    net_kar_marji_yuzde = None

    if toplam_hasat_kg > 0:
        # kalite bazinda hasat kg'sini guncel pazar fiyatlarina karsi degerle;
        # kalite bilgisi olmayan kayitlar icin genel ortalama fiyat kullanilir.
        pazar = pazar_paneli(db, gun_sayisi=7)
        if pazar.guncel_fiyat_kg is not None:
            kalite_fiyat_haritasi = {k.kalite_sinifi: k.ortalama_fiyat_kg for k in pazar.kalite_bazli_talep}

            gelir = 0.0
            for h in hasatlar:
                kg = h.toplanan_kasa * (h.kasa_agirlik_kg or 5.0)
                kalite = h.kalite_sinifi.value if h.kalite_sinifi else None
                fiyat = kalite_fiyat_haritasi.get(kalite, pazar.guncel_fiyat_kg)
                gelir += kg * fiyat

            tahmini_gelir = round(gelir, 2)
            if tahmini_gelir > 0:
                net_kar_marji_yuzde = round((tahmini_gelir - toplam_gider) / tahmini_gelir * 100, 1)
                notlar.append(
                    "Gelir tahmini, hasat edilen miktarın güncel pazar fiyatlarıyla çarpılmasıyla "
                    "elde edilen bir PROJEKSİYONDUR; gerçek satış fiyatı alıcıya/pazarlık payına göre farklılık gösterebilir."
                )
        else:
            notlar.append("Güncel pazar fiyatı verisi yok - gelir/kâr marjı tahmin edilemiyor.")
    else:
        notlar.append("Henüz hasat kaydı yok - gelir/kâr marjı hesaplanamıyor.")

    return FinansalSaglikPaneli(
        donem_baslangic=baslangic,
        donem_bitis=bugun,
        toplam_gider=round(toplam_gider, 2),
        gider_dagilimi={k: round(v, 2) for k, v in gider_dagilimi.items()},
        toplam_hasat_kg=round(toplam_hasat_kg, 1),
        birim_maliyet_kg=birim_maliyet_kg,
        tahmini_gelir=tahmini_gelir,
        net_kar_marji_yuzde=net_kar_marji_yuzde,
        notlar=notlar,
    )


# ============ KRİTİK UYARI ÖZETİ (üst banner için) ============

@dataclass
class KritikUyariGirdisi:
    seviye: RiskSeviyesi
    mesaj: str


def kritik_uyarilari_topla(*durumlar: KritikUyariGirdisi) -> list[str]:
    """KRITIK seviyedeki tum durumlarin mesajlarini, en tepede gosterilmek uzere toplar."""
    return [d.mesaj for d in durumlar if d.seviye == RiskSeviyesi.KRITIK]
