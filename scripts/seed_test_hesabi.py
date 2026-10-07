"""YEREL geliştirme için test hesabı: BUSINESS plan (tüm özellikler açık), dolu profil.

  python scripts/seed_test_hesabi.py          # oluştur / sıfırla (idempotent)
  python scripts/seed_test_hesabi.py --sil    # hesabı ve verisini sil

Yalnızca yerel veritabanında çalıştırın; üretimde ASLA. Giriş bilgileri aşağıdaki
sabitlerdedir (test değerleridir, gerçek bir hesapla ilgisi yoktur).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    Base, FinancialProfile, Organization, PlanType, SessionLocal, User, init_db,
)

TEST_EMAIL = "test@example.com"
TEST_SIFRE = "TesvikTest#2026"
TEST_FIRMA = "Test Gıda Tarım Ltd."

PROFIL = dict(
    sektor="imalat", bolge="Konya", calisan_sayisi=12, yillik_ciro=4_500_000,
    hedefler=["yatirim", "ihracat"], nace_kodu="10.71", ozellikler=["genc_girisimci"],
    giderler={"stok": 1_800_000, "reklam": 120_000, "toplam": 3_900_000},
)


def _temizle(db) -> None:
    kullanici = db.query(User).filter(User.email == TEST_EMAIL).first()
    if kullanici is None:
        return
    org_id = kullanici.org_id
    for tablo in reversed(Base.metadata.sorted_tables):
        if tablo.name == "organizations":
            db.execute(tablo.delete().where(tablo.c.id == org_id))
        elif tablo.name == "users":
            db.execute(tablo.delete().where(tablo.c.id == kullanici.id))
        else:
            for kolon in ("org_id", "organization_id"):
                if kolon in tablo.c:
                    db.execute(tablo.delete().where(tablo.c[kolon] == org_id))
                    break
    db.commit()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sil", action="store_true")
    a = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        _temizle(db)
        if a.sil:
            print("Test hesabı silindi.")
            return
        org = Organization(name=TEST_FIRMA, email=TEST_EMAIL, plan=PlanType.BUSINESS,
                           ai_yurtdisi_riza=False)
        db.add(org)
        db.flush()
        db.add(User(email=TEST_EMAIL, hashed_password=hash_password(TEST_SIFRE),
                    full_name="Test Kullanıcı", org_id=org.id))
        db.add(FinancialProfile(org_id=org.id, **PROFIL))
        db.commit()
        print(f"Test hesabı hazır: {TEST_EMAIL} (BUSINESS plan, dolu profil). "
              "Şifre bu dosyadaki TEST_SIFRE sabitidir.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
