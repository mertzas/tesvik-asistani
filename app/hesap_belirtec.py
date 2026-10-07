"""Parola sıfırlama ve e-posta doğrulama için tek kullanımlık belirteçler (Denetim 2 / Aşama E).

- Ham belirteç `secrets.token_urlsafe(32)`; yalnızca e-postayla gider, DB'de SHA-256 özeti tutulur.
- Aynı amaçla yeni belirteç üretilince kullanıcının önceki kullanılmamış belirteçleri geçersiz olur.
- Tüketim tek seferlik ve süreli; özet karşılaştırması DB'de benzersiz indeksle yapılır (ham değer
  asla karşılaştırılmaz ya da günlüğe yazılmaz).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import HesapBelirteci, User

SIFIRLAMA = "sifre_sifirlama"
DOGRULAMA = "eposta_dogrulama"
GECERLILIK = {SIFIRLAMA: timedelta(hours=1), DOGRULAMA: timedelta(hours=48)}


def _ozet(ham: str) -> str:
    return hashlib.sha256(ham.encode()).hexdigest()


def _simdi() -> datetime:
    # DB DateTime sütunları zaman dilimsiz; her yerde UTC-naif karşılaştırılır.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def belirtec_uret(db: Session, user: User, amac: str) -> str:
    """Yeni belirteç üretir, önceki kullanılmamışları iptal eder, HAM belirteci döndürür (commit yapar)."""
    simdi = _simdi()
    for eski in db.query(HesapBelirteci).filter(HesapBelirteci.user_id == user.id, HesapBelirteci.amac == amac,
                                                HesapBelirteci.kullanildi.is_(None)).all():
        eski.kullanildi = simdi
    ham = secrets.token_urlsafe(32)
    db.add(HesapBelirteci(user_id=user.id, amac=amac, belirtec_ozeti=_ozet(ham), olusturma=simdi,
                          bitis=simdi + GECERLILIK[amac]))
    db.commit()
    return ham


def belirtec_tuket(db: Session, ham: str, amac: str) -> User | None:
    """Geçerli (süresi dolmamış, kullanılmamış, amacı doğru) belirteci tüketip kullanıcıyı döndürür; yoksa None."""
    if not ham or len(ham) > 200:
        return None
    kayit = db.query(HesapBelirteci).filter(HesapBelirteci.belirtec_ozeti == _ozet(ham),
                                            HesapBelirteci.amac == amac).first()
    simdi = _simdi()
    if kayit is None or kayit.kullanildi is not None or kayit.bitis < simdi:
        return None
    kayit.kullanildi = simdi
    user = db.get(User, kayit.user_id)
    db.flush()
    return user if user is not None and user.is_active else None
