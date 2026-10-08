"""
Faz 2 - İKAS'tan çekilen sipariş verisini FinancialProfile alanlarına
(sektör, yıllık ciro, gider tahmini) otomatik dönüştürür.

Manuel profil doldurmanın yerini alır: kullanıcı hiçbir rakam girmeden,
son 12 ayki gerçek sipariş verisinden ciro ve kategori bilgisini üretir.

2026-10-08 düzeltmeleri:
  - İptal/iade denetimi `orderPaymentStatus` alanına bakıyordu; CANCELLED/REFUNDED değerleri `Order.status`
    (OrderStatusEnum) alanındadır, ödeme durumu enum'unda yoktur. Bu yüzden iptal edilmiş siparişler ciroya
    giriyordu. Artık `status` denetlenir; taslak ve upsell bekleyen siparişler de satış sayılmaz.
  - Ciro yalnızca TRY siparişlerinden toplanır. Döviz cinsinden siparişler kur çevrimi YAPILMADAN ayrıca
    raporlanır (Order.currencyRates alanının anlamı İKAS belgesinde tanımlı değil; tahmini kur kullanılmaz).
  - E-ihracat göstergeleri: teslimat ülkesi TR dışı olan siparişler (5986 e-ihracat desteği ve KOSGEB/Ticaret
    Bakanlığı ihracat programları için başvuru bağlamı).
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ikas_integration import SiparisSatiri
from app.models import FinancialProfile

# OrderStatusEnum (SDK admin/generated): satış sayılmayan durumlar. PARTIALLY_CANCELLED / PARTIALLY_REFUNDED
# siparişler kalır: totalFinalPrice kısmi iptal/iade sonrasını mı gösteriyor belgede yok (notta belirtilir).
SATIS_DISI_DURUMLAR = {"CANCELLED", "REFUNDED", "DRAFT", "WAITING_UPSELL_ACTION"}
KISMI_DURUMLAR = {"PARTIALLY_CANCELLED", "PARTIALLY_REFUNDED"}
YERLI_PARA = "TRY"


def _sayi(x: float) -> str:
    """Türkçe sayı biçimi: 3.051,18 (app/tarim_destek_2026._tl ile aynı yöntem)."""
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class EslemeSonucu:
    yillik_ciro: float
    siparis_sayisi: int
    en_cok_satan_urun_kategorileri: list[tuple[str, float]] = field(default_factory=list)
    kaynak_donem_baslangic: datetime | None = None
    kaynak_donem_bitis: datetime | None = None
    notlar: list[str] = field(default_factory=list)
    doviz_toplamlari: dict[str, float] = field(default_factory=dict)   # {"EUR": 1234.5} - TRY dışı, çevrilmedi
    yurt_disi_siparis: int = 0
    yurt_disi_ciro_try: float = 0.0
    yurt_disi_ulkeler: list[str] = field(default_factory=list)
    haric_tutulan: int = 0

    def gostergeler(self) -> dict:
        """Panelde ve başvuru taslağı bağlamında kullanılan özet (IkasBaglanti.son_ozet'e yazılır)."""
        d = asdict(self)
        for k in ("kaynak_donem_baslangic", "kaynak_donem_bitis"):
            d[k] = d[k].date().isoformat() if d[k] else None
        d["en_cok_satan_urun_kategorileri"] = [[u, c] for u, c in self.en_cok_satan_urun_kategorileri]
        d["yurt_disi_oran"] = round(self.yurt_disi_siparis / self.siparis_sayisi, 4) if self.siparis_sayisi else 0.0
        return d


def _tarih_ayristir(deger) -> datetime | None:
    """İKAS Timestamp'i ms cinsinden sayıdır; eski kayıtlar/testler ISO metin taşıyabilir."""
    if deger is None or deger == "":
        return None
    if isinstance(deger, (int, float)) and not isinstance(deger, bool):
        try:
            return datetime.fromtimestamp(deger / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        dt = datetime.fromisoformat(str(deger).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def siparislerden_ozet_cikar(siparisler: list[SiparisSatiri], gun_sayisi: int = 365) -> EslemeSonucu:
    """Son `gun_sayisi` gündeki satış siparişlerinden yıllık ciro (TRY), ürün dağılımı, döviz ve yurt dışı
    göstergelerini hesaplar. İptal/iade/taslak siparişler dahil edilmez - net ciroyu şişirmemek için."""
    simdi = datetime.now(timezone.utc)
    esik = simdi - timedelta(days=gun_sayisi)

    gecerli, haric, kismi = [], 0, 0
    for s in siparisler:
        tarih = _tarih_ayristir(s.orderedAt)
        if tarih is None or tarih < esik:
            continue
        durum = (s.status or "").upper()
        if durum in SATIS_DISI_DURUMLAR:
            haric += 1
            continue
        kismi += durum in KISMI_DURUMLAR
        gecerli.append((s, tarih))

    try_siparisler = [(s, t) for s, t in gecerli if (s.currencyCode or YERLI_PARA).upper() == YERLI_PARA]
    yillik_ciro = round(sum(s.totalFinalPrice for s, _ in try_siparisler), 2)
    doviz: dict[str, float] = {}
    for s, _ in gecerli:
        kod = (s.currencyCode or YERLI_PARA).upper()
        if kod != YERLI_PARA:
            doviz[kod] = round(doviz.get(kod, 0.0) + s.totalFinalPrice, 2)

    yurt_disi = [s for s, _ in gecerli if s.teslimat_ulkesi and s.teslimat_ulkesi.upper() != "TR"]
    ulkeler = sorted({s.teslimat_ulkesi.upper() for s in yurt_disi})

    urun_toplamlari: dict[str, float] = {}
    for s, _ in try_siparisler:
        for kalem in s.urunler:
            ad = kalem.get("productName") or "Diğer"
            urun_toplamlari[ad] = urun_toplamlari.get(ad, 0.0) + (kalem.get("finalPrice") or 0.0)
    en_cok_satanlar = sorted(urun_toplamlari.items(), key=lambda x: x[1], reverse=True)[:5]

    notlar = []
    if not gecerli:
        notlar.append(
            "Son 12 ayda satış siparişine rastlanmadı - mağaza yeni olabilir "
            "veya senkronizasyon aralığı dışında sipariş bulunmuyor olabilir."
        )
    else:
        tarihler = [t for _, t in gecerli]
        notlar.append(
            f"{len(gecerli)} satış siparişi, {min(tarihler).date()} - {max(tarihler).date()} "
            f"tarih aralığından hesaplandı."
        )
    if haric:
        notlar.append(f"{haric} iptal, iade veya taslak sipariş ciroya katılmadı.")
    if kismi:
        notlar.append(f"{kismi} kısmi iptal/iade siparişi toplam tutarıyla katıldı; muhasebe kaydınızla karşılaştırın.")
    if doviz:
        notlar.append("Döviz cinsinden siparişler yıllık ciroya (TL) katılmadı, ayrıca gösterildi: "
                      + ", ".join(f"{_sayi(t)} {k}" for k, t in sorted(doviz.items())) + ".")
    if yurt_disi:
        notlar.append(f"{len(yurt_disi)} sipariş yurt dışına teslim edildi ({', '.join(ulkeler)}). E-ihracat "
                      f"desteklerinde (ör. 5986 sayılı Karar) gümrük beyannamesi/ETGB ile belgelenen satışlar sayılır.")

    return EslemeSonucu(
        yillik_ciro=yillik_ciro,
        siparis_sayisi=len(gecerli),
        en_cok_satan_urun_kategorileri=en_cok_satanlar,
        kaynak_donem_baslangic=min((t for _, t in gecerli), default=None),
        kaynak_donem_bitis=max((t for _, t in gecerli), default=None),
        notlar=notlar,
        doviz_toplamlari=doviz,
        yurt_disi_siparis=len(yurt_disi),
        yurt_disi_ciro_try=round(sum(s.totalFinalPrice for s in yurt_disi
                                     if (s.currencyCode or YERLI_PARA).upper() == YERLI_PARA), 2),
        yurt_disi_ulkeler=ulkeler,
        haric_tutulan=haric,
    )


def baglam_alanlari(ozet: dict | None) -> dict:
    """IkasBaglanti.son_ozet'ten başvuru taslağı/danışman bağlamına eklenecek alanlar (yalnızca toplamlar;
    müşteri adı/adresi gibi kişisel veri yok). Özet yoksa boş sözlük."""
    if not ozet or not ozet.get("siparis_sayisi"):
        return {}
    alanlar = {"e-ticaret satışları (İKAS mağaza verisi, son 12 ay)":
               f"{ozet['siparis_sayisi']} satış siparişi; TL siparişlerin toplamı {_sayi(ozet.get('yillik_ciro', 0))} TL"
               + (f" ({ozet['kaynak_donem_baslangic']} - {ozet['kaynak_donem_bitis']})"
                  if ozet.get("kaynak_donem_baslangic") else "")}
    if ozet.get("yurt_disi_siparis"):
        alanlar["yurt dışına teslim edilen siparişler (İKAS)"] = (
            f"{ozet['yurt_disi_siparis']} sipariş (%{100 * ozet.get('yurt_disi_oran', 0):.1f}); ülkeler: "
            + ", ".join(ozet.get("yurt_disi_ulkeler") or []) + "; gümrük beyannamesi/ETGB ile belgelenmesi gerekir")
    if ozet.get("doviz_toplamlari"):
        alanlar["döviz cinsinden satışlar (İKAS, TL'ye çevrilmedi)"] = ", ".join(
            f"{_sayi(t)} {k}" for k, t in sorted(ozet["doviz_toplamlari"].items()))
    return alanlar


def profili_ikas_verisiyle_guncelle(db: Session, org_id, siparisler: list[SiparisSatiri]) -> EslemeSonucu:
    """FinancialProfile'ı İKAS'tan çekilen siparişlerden hesaplanan ciroyla
    günceller (yoksa oluşturur). sektor='e-ticaret' olarak sabitlenir -
    İKAS bir e-ticaret platformu olduğu için bu varsayım güvenlidir.
    Kullanıcının elle girdiği diğer alanlar (hedefler, bölge vb.)
    DOKUNULMADAN korunur - sadece ciro İKAS kaynaklı olarak işaretlenir.
    Yurt dışı teslimat varsa hedeflere "ihracat" eklenir (kullanıcının hedefleri silinmez)."""
    ozet = siparislerden_ozet_cikar(siparisler)

    profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == org_id).first()
    if profil is None:
        profil = FinancialProfile(org_id=org_id, sektor="e-ticaret")
        db.add(profil)

    if ozet.siparis_sayisi > 0:
        profil.sektor = profil.sektor or "e-ticaret"
        profil.yillik_ciro = ozet.yillik_ciro
    if ozet.yurt_disi_siparis and "ihracat" not in (profil.hedefler or []):
        profil.hedefler = [*(profil.hedefler or []), "ihracat"]

    db.commit()
    return ozet
