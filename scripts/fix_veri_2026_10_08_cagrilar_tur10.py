"""Tur 10 — dönemsel başvuru çağrıları (tablo tesvik_cagrilari, göç l9a1c3e5f901).

Ölçüm (2026-10-08): aktif 100 kaydın hiçbirinde bitiş tarihi yoktu; "son başvuru" ve tarih hatırlatıcısı
yapılamıyordu. Bu tur, resmi duyurusu bugün okunan 8 çağrıyı yapılandırılmış satır olarak ekler. Tarihler kaynak
sayfadan ya da kurumun çağrı PDF'inin "Çağrı Takvimi" tablosundan alındı (PDF metni PyMuPDF ile çıkarıldı).
Tarihi sayfada görülemeyen çağrı EKLENMEDİ (KOSGEB TEKMER 2026-01 COP31: tarih yalnız ilan PDF'inde, okunmadı).

Kurallar
  - Yalnız kaynakta açıkça yazan tarih; tahmin yok. "Yılda iki dönem" gibi genel ifadeler çağrı satırı olmaz.
  - Idempotent: (tesvik_id, ad) varsa satır atlanır (tablodaki benzersizlik kısıtıyla aynı).
  - Program kaydına (tesvikler) dokunulmaz; yalnız tesvik_cagrilari'na ekleme.

    python scripts/fix_veri_2026_10_08_cagrilar_tur10.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_cagrilar_tur10.py --uygula
    python scripts/fix_veri_2026_10_08_cagrilar_tur10.py --self-test
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, TesvikCagrisi  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DOGRULAMA = date(2026, 10, 8)
TUBITAK_1501_PDF = ("https://tubitak.gov.tr/sites/default/files/2026-07/"
                    "1501_Sanayi_Ar-Ge_Destek_Programi_2026-2_Proje_Cagri_Metni_13.07.2026_v2.pdf")
TUBITAK_1507_PDF = ("https://tubitak.gov.tr/sites/default/files/2026-07/"
                    "1507_KOBI_Ar-Ge_Baslangic_Destek_Programlari_2026-2_Proje_Cagri_Metni_13.07.2026_v2.pdf")
TUBITAK_1812_PDF = "https://www.tubitak.gov.tr/sites/default/files/2026-09/1812-2026-2_Cagri_Duyurusu_v2.pdf"
KOSGEB_KR_PDF = ("https://webdosya.kosgeb.gov.tr/Content/Upload/Dosya/KURESEL%20REKABETC%C4%B0L%C4%B0K/2026/"
                 "2026.09.07/2026_Y%C4%B1l%C4%B1_1._Proje_Teklif_C%CC%A7ag%CC%86r%C4%B1s%C4%B1.pdf")
KOSGEB_IKD = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9224/istihdami-koruma-destek-programi"

# (tesvik_id, ad, açılış, kapanış, kaynak, not). Beklenen başlık parçası self-test ve uygulamada denetlenir.
CAGRILAR = [
    (34, "2026 yılı 2. çağrı", date(2026, 7, 20), date(2026, 10, 26), TUBITAK_1501_PDF,
     "Kapanış 26.10.2026 saat 23:59. Kuruluş bazlı ön kayıt başvurusu PRODİS üzerinden en geç 22.10.2026 23:59; "
     "ön kayıt evrakı kapanıştan en az bir iş günü önce TÜBİTAK'a ulaşmalı."),
    (44, "2026 yılı 2. çağrı", date(2026, 7, 20), date(2026, 11, 11), TUBITAK_1507_PDF,
     "Kapanış 11.11.2026 saat 23:59. Kuruluş bazlı ön kayıt başvurusu PRODİS üzerinden en geç 09.11.2026 23:59; "
     "ön kayıt evrakı kapanıştan en az bir iş günü önce TÜBİTAK'a ulaşmalı."),
    (49, "1812-2026-2 Aşama 2 başvuruları", date(2026, 8, 31), date(2026, 9, 30), TUBITAK_1812_PDF,
     "Başvurular uygulayıcı kuruluşun hızlandırma programı üzerinden; değerlendirme 12 Ekim – 4 Aralık 2026, "
     "destek başlangıcı 1 Ocak 2027."),
    (9, "2026 yılı 1. başvuru dönemi", date(2026, 9, 7), date(2026, 9, 30), KOSGEB_KR_PDF,
     "Proje teklif çağrısı."),
    (7, "2026-2 dönemi", date(2026, 9, 1), date(2026, 10, 31), KOSGEB_IKD,
     "Bu dönemde yalnız Finansman Desteği kapsamında başvuru alınır."),
    (7, "2026-1 dönemi", date(2026, 3, 3), date(2026, 4, 30), KOSGEB_IKD, None),
    (8, "2026 yılı 2. başvuru dönemi", date(2026, 6, 6), date(2026, 6, 30),
     "https://www.kosgeb.gov.tr/site/tr/genel/detay/9391/ureten-kobilere-guclu-destek-yeni-basvuru-donemi-basladi",
     None),
    (1, "İş Geliştirme Çağrısı 2026 yılı 2. dönem", date(2026, 4, 20), date(2026, 5, 8),
     "https://www.kosgeb.gov.tr/site/tr/genel/detay/9374/girisimci-destek-programi-is-gelistirme-cagrisi-2026-yili-2-donem-basvurulari-basladi",
     None),
]
BASLIK_PARCASI = {34: "1501", 44: "1507", 49: "1812", 9: "Küresel Rekabetçilik", 7: "İstihdamı Koruma",
                  8: "Kapasite Geliştirme", 1: "Girişimci Destek"}


def uygula(db, dry_run: bool = True) -> tuple[int, int]:
    eklenen = atlanan = 0
    for tid, ad, acilis, kapanis, kaynak, notlar in CAGRILAR:
        t = db.get(Tesvik, tid)
        if t is None or BASLIK_PARCASI[tid] not in t.baslik:
            raise SystemExit(f"[{tid}] beklenen program bulunamadı (başlık '{BASLIK_PARCASI[tid]}' içermeli); durduruldu")
        if db.query(TesvikCagrisi).filter(TesvikCagrisi.tesvik_id == tid, TesvikCagrisi.ad == ad).first():
            atlanan += 1
            print(f"   [{tid}] {ad}: zaten var, atlandı")
            continue
        print(f"[{tid}] {t.baslik[:55]} <- {ad}: {acilis} – {kapanis}")
        if not dry_run:
            db.add(TesvikCagrisi(tesvik_id=tid, ad=ad, acilis=acilis, kapanis=kapanis, kaynak_url=kaynak,
                                 dogrulama_tarihi=DOGRULAMA, notlar=notlar))
        eklenen += 1
    if not dry_run:
        db.commit()
    return eklenen, atlanan


def _self_test() -> int:
    kontroller = [
        ("8 çağrı, her biri kaynaklı", len(CAGRILAR) == 8 and all(c[4].startswith("https://") for c in CAGRILAR)),
        ("açılış kapanıştan önce", all(c[2] <= c[3] for c in CAGRILAR)),
        ("(program, ad) benzersiz", len({(c[0], c[1]) for c in CAGRILAR}) == len(CAGRILAR)),
        ("her program için başlık denetimi tanımlı", all(c[0] in BASLIK_PARCASI for c in CAGRILAR)),
        ("TEKMER (tarihi doğrulanmadı) eklenmedi", all(c[0] != 4 for c in CAGRILAR)),
        ("doğrulama tarihi bugün", DOGRULAMA == date(2026, 10, 8)),
    ]
    for ad, ok in kontroller:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in kontroller)
    print(f"\nself-test: {gecen}/{len(kontroller)} geçti")
    return 0 if gecen == len(kontroller) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    db = SessionLocal()
    try:
        n, atlanan = uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} çağrı eklendi, {atlanan} atlandı")
    finally:
        db.close()
