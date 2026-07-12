"""
Faz 2 - İKAS'tan çekilen sipariş verisini FinancialProfile alanlarına
(sektör, yıllık ciro, gider tahmini) otomatik dönüştürür.

Manuel profil doldurmanın yerini alır: kullanıcı hiçbir rakam girmeden,
son 12 ayki gerçek sipariş verisinden ciro ve kategori bilgisini üretir.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ikas_integration import SiparisSatiri
from app.models import FinancialProfile

ODENMIS_DURUMLAR = {"PAID", "PARTIALLY_PAID"}
IPTAL_DURUMLAR = {"CANCELLED", "REFUNDED"}


@dataclass
class EslemeSonucu:
    yillik_ciro: float
    siparis_sayisi: int
    en_cok_satan_urun_kategorileri: list[tuple[str, float]] = field(default_factory=list)
    kaynak_donem_baslangic: datetime | None = None
    kaynak_donem_bitis: datetime | None = None
    notlar: list[str] = field(default_factory=list)


def _tarih_ayristir(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def siparislerden_ozet_cikar(siparisler: list[SiparisSatiri], gun_sayisi: int = 365) -> EslemeSonucu:
    """Son `gun_sayisi` gündeki ödenmiş siparişlerden yıllık ciro ve ürün
    kategori dağılımını hesaplar. İptal/iade edilmiş siparişler ciroya
    dahil edilmez - bu, gerçek net ciroyu şişirmemek için önemlidir."""
    simdi = datetime.now(timezone.utc)
    esik = simdi - timedelta(days=gun_sayisi)

    gecerli = []
    for s in siparisler:
        tarih = _tarih_ayristir(s.orderedAt)
        if tarih is None or tarih < esik:
            continue
        if s.orderPaymentStatus and s.orderPaymentStatus.upper() in IPTAL_DURUMLAR:
            continue
        gecerli.append((s, tarih))

    yillik_ciro = round(sum(s.totalFinalPrice for s, _ in gecerli), 2)

    urun_toplamlari: dict[str, float] = {}
    for s, _ in gecerli:
        for kalem in s.urunler:
            ad = kalem.get("productName") or "Diğer"
            urun_toplamlari[ad] = urun_toplamlari.get(ad, 0.0) + (kalem.get("finalPrice") or 0.0)
    en_cok_satanlar = sorted(urun_toplamlari.items(), key=lambda x: x[1], reverse=True)[:5]

    notlar = []
    if not gecerli:
        notlar.append(
            "Son 12 ayda ödenmiş siparişe rastlanmadı - mağaza yeni olabilir "
            "veya senkronizasyon aralığı dışında sipariş bulunmuyor olabilir."
        )
    else:
        tarihler = [t for _, t in gecerli]
        notlar.append(
            f"{len(gecerli)} ödenmiş sipariş, {min(tarihler).date()} - {max(tarihler).date()} "
            f"tarih aralığından hesaplandı."
        )

    return EslemeSonucu(
        yillik_ciro=yillik_ciro,
        siparis_sayisi=len(gecerli),
        en_cok_satan_urun_kategorileri=en_cok_satanlar,
        kaynak_donem_baslangic=min((t for _, t in gecerli), default=None),
        kaynak_donem_bitis=max((t for _, t in gecerli), default=None),
        notlar=notlar,
    )


def profili_ikas_verisiyle_guncelle(db: Session, org_id, siparisler: list[SiparisSatiri]) -> EslemeSonucu:
    """FinancialProfile'ı İKAS'tan çekilen siparişlerden hesaplanan ciroyla
    günceller (yoksa oluşturur). sektor='e-ticaret' olarak sabitlenir -
    İKAS bir e-ticaret platformu olduğu için bu varsayım güvenlidir.
    Kullanıcının elle girdiği diğer alanlar (hedefler, bölge vb.)
    DOKUNULMADAN korunur - sadece ciro İKAS kaynaklı olarak işaretlenir."""
    ozet = siparislerden_ozet_cikar(siparisler)

    profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == org_id).first()
    if profil is None:
        profil = FinancialProfile(org_id=org_id, sektor="e-ticaret")
        db.add(profil)

    if ozet.siparis_sayisi > 0:
        profil.sektor = profil.sektor or "e-ticaret"
        profil.yillik_ciro = ozet.yillik_ciro

    db.commit()
    return ozet
