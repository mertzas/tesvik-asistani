"""Denetim 2 / Aşama A (Tur 2) veri düzeltmeleri — aktif KGF/KOSGEB/TÜBİTAK kayıtlarının canlı
sayfa karşılaştırması. Aynı mekanizma: scripts/fix_veri_2026_10_07_denetim2.uygula (idempotent;
durum_notu etiketi "Denetim2-T2 2026-10-07").

    python scripts/fix_veri_2026_10_07_denetim2_tur2.py --dry-run
    python scripts/fix_veri_2026_10_07_denetim2_tur2.py --uygula
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal  # noqa: E402
from scripts import fix_veri_2026_10_07_denetim2 as t1  # noqa: E402

KGF = "https://www.kgf.com.tr/index.php/tr/urunlerimiz/"
KOS = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/"
TUB = "https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/"


def _k(tutar, yol):
    return dict(aktif_mi=True, tesvil_tutari=tutar, kaynak=KGF + yol, not_="ürün sayfası yayında; limit/vade sayfadan")


DEGISIKLIKLER = {
    # KGF (aktif paketler 2025 / özkaynak)
    90: _k("Vade: işletme kredisi azami 24 ay, yatırım kredisi azami 120 ay (ödemesiz dönem dahil); kredi komisyonu azami %1, KGF kefalet komisyonu %0,5", "hazine-destekli-kefaletler/aktif-destek-paketleri-2025/yatirim-isletme-destek-paketi"),
    91: _k("Kefalet 150 Milyon TL, kredi 500 Milyon TL; kefalet oranı %80", "hazine-destekli-kefaletler/aktif-destek-paketleri-2025/tkyb-kredi-destek-paketi"),
    94: _k("İşletme kredisi 10 Milyon TL (azami 24 ay), yatırım kredisi 20 Milyon TL (azami 60 ay), 12 ay ödemesiz; %80 kefalet; başvuru ücreti kredinin %0,15'i (asgari 10.000 TL)", "ozkaynak-kefaletlerimiz/banka-kredileri/tarim-kefalet-destek-programi"),
    118: _k("Kefalet oranı %100; vade ilgili KOSGEB geri ödemeli destek programına göre", "ozkaynak-kefaletlerimiz/dogrudan-krediler/kosgeb-geri-odemeli-destekleri"),
    125: _k("Vade: işletme azami 12 ay, yatırım azami 36 ay (ödemesiz dahil); komisyon azami %1, kefalet komisyonu %0,5", "hazine-destekli-kefaletler/aktif-destek-paketleri-2025/2024-dijital-donusum-destek-paketi"),
    146: dict(aktif_mi=True, kaynak=KGF + "hazine-destekli-kefaletler/aktif-destek-paketleri-2025/turwib-programi-destek-paketi", not_="sayfa yayında; %49+ kamu ortaklı firmalar hariç; tutar sayfada yok"),
    153: _k("85 Milyon TL; kefalet oranı %80", "hazine-destekli-kefaletler/aktif-destek-paketleri-2025/turyib-programi-destek-paketi"),
    154: dict(aktif_mi=True, kaynak=KGF + "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-genel-destek-programi", not_="sayfa yayında; komisyon yıllık %1,5; limit sayfada yok"),
    159: _k("Azami 24 ay vade (anapara ödemesiz dahil); reeskont kredilerinde kefalet %100; komisyon %1", "hazine-destekli-kefaletler/aktif-destek-paketleri-2025/i-hracat-destek-paketi"),
    # KOSGEB (2026 çağrı takvimi: kosgeb.gov.tr duyuruları 9374 / 9391 / 9453)
    1: dict(basvuru_suresi="Dönemsel çağrı: İş Geliştirme 2026/2 dönemi 20 Nisan – 8 Mayıs 2026 (kapandı); yılda iki dönem, güncel takvim KOSGEB duyurularından",
            kaynak="https://www.kosgeb.gov.tr/site/tr/genel/detay/9374/girisimci-destek-programi-is-gelistirme-cagrisi-2026-yili-2-donem-basvurulari-basladi",
            not_="2026/2 dönemi duyurusu: 2 M TL'ye kadar destek; kadın/genç girişimciye 1 M TL'ye kadar işletme sermayesi kredi desteği"),
    8: dict(basvuru_suresi="Dönemsel çağrı: 2026 yılı 2. başvuru dönemi 6 Haziran 2026'da başladı; güncel takvim KOSGEB duyurularından",
            kaynak="https://www.kosgeb.gov.tr/site/tr/genel/detay/9391/ureten-kobilere-guclu-destek-yeni-basvuru-donemi-basladi", not_="2026/2 dönemi duyurusu"),
    4: dict(aktif_mi=True, tesvil_tutari="Her bir desteğin yıllık üst limiti 5.000.000 TL (2025; her takvim yılı güncellenir); hızlandırma desteği 10 yıl; COP31 çağrısı: 6,5 M TL'ye kadar %100 geri ödemeli",
            tutari_max=6500000.0, basvuru_suresi="2026-01 COP31 Hızlandırma Çağrısı başvuruları 9–30 Ağustos 2026 (kapandı); çağrı bazlı",
            kaynak=KOS + "9297/teknoloji-merkezi-destek-programi", not_="TEKMER/TGB işletici kuruluş programı; COP31 çağrı duyurusu 9453"),
    6: dict(aktif_mi=True, tesvil_tutari="İşletici kuruluş yıllık destek üst limiti 6.506.000 TL, %100 geri ödemesiz ((TÜFE+Yİ-ÜFE)/2 ile güncellenir)",
            tutari_max=6506000.0, kaynak=KOS + "9327/sektorel-gelisim-merkezi-segem-destek-programi", not_="SEGEM işletici kuruluş programı"),
    7: dict(aktif_mi=True, tesvil_tutari="Kredi üst limiti KOBİ 50 Milyon TL, büyük işletme 150 Milyon TL; banka azami faiz/kâr payı %37; masraflar ≤%1",
            tutari_max=50000000.0, basvuru_suresi="2026-2 dönemi başvuruları: 1 Eylül – 31 Ekim 2026",
            kaynak=KOS + "9224/istihdami-koruma-destek-programi", not_="2026-2 dönemi açık"),
    9: dict(aktif_mi=True, tesvil_tutari="2026/1. başvuru dönemi: destek üst limiti 75.000.000 TL / 30.000.000 TL; talep edilen kredi alt limiti 30 Milyon TL; proje 24 ay",
            tutari_min=30000000.0, tutari_max=75000000.0, kaynak=KOS + "9206/kuresel-rekabetcilik-destek-programi", not_="2026 yılı 1. başvuru dönemi çağrısı"),
    # TÜBİTAK sanayi
    14: dict(tesvil_tutari="Takvim yılı başına destek en fazla 25 Milyon TL; Türk uyruklu Ar-Ge personeli %75, yabancı uyruklu %25–%100", tutari_max=25000000.0,
             kaynak=TUB + "1515-oncul-ar-ge-laboratuvarlari-destekleme-programi", not_="Uygulama Esasları MADDE 5"),
    15: dict(tesvil_tutari="1702 Patent Lisans: proje bütçesi üst sınırı 4.000.000 TL, süre ≤60 ay; temel destek oranı %25, KOBİ +%15, EPO/JPO/KIPO/CNIPA/USPTO patenti +%10 (yüksek teknoloji/Yeşil Mutabakat ilaveleri)",
             tutari_max=4000000.0, kaynak=TUB + "1702-patent-tabanli-teknoloji-transferi-destekleme-cagrisi", not_="sayfa canlı"),
    39: dict(tesvil_tutari="Destek oranı tek ortaklı: KOBİ %75 / büyük %60; çok ortaklı: KOBİ %60 / büyük %40 (bütçe üst limitleri çağrıda)",
             kaynak="https://www.tubitak.gov.tr/tr/destekler/sanayi/uluslararasi-ortakli-destek-programlari/1509-tubitak-uluslararasi-sanayi-ar-ge-projeleri-destekleme-programi", not_="sayfa canlı"),
    44: dict(tesvil_tutari="Proje bütçesi en fazla 3.500.000 TL; ilk 5 projede %75 hibe (en az ikisi ortaklı başvuru kaydıyla); 2026 yılı 2. çağrı dokümanı",
             tutari_max=3500000.0, kaynak=TUB + "1507-tubitak-kobi-ar-ge-baslangic-destek-programi", not_="2026/2 çağrısı"),
    55: dict(basvuru_suresi="2026 çağrı takvimi (taslak): 2 Ocak, 13 Mart, 4 Mayıs, 17 Temmuz, 1 Eylül, 13 Kasım 2026; başvuru eteydeb.tubitak.gov.tr",
             kaynak=TUB + "1707-siparise-dayali-ar-ge-projeleri-icin-kobi-destekleme-cagrisi", not_="sayfa canlı"),
    59: dict(tesvil_tutari="1832 2026-2: destek süresi ≤24 ay; proje bütçesi üst limiti mikro/küçük 15.000.000 TL (orta/büyük limitleri çağrıda); ilave %20 hibe kaldırıldı; yürütücü ≥%75 özel sektör",
             kaynak=TUB + "1832-sanayide-yesil-donusum-cagrisi", not_="2026-2 çağrısı"),
    57: dict(aktif_mi=None, kaynak=TUB + "1503-proje-pazarlari-destekleme-programi", not_="sayfa canlı ama tarih/tutar sinyali yok; aktiflik kararsız"),
    # Akademik ikili işbirliği çağrıları (kapanmış)
    21: dict(aktif_mi=False, not_="son başvuru 14 Ağustos 2026 (e-imza 21 Ağustos 2026)"),
    32: dict(aktif_mi=False, not_="son başvuru 17 Temmuz 2026"),
    66: dict(aktif_mi=None, not_="yalnızca 2025 başvuru duyurusu; 2026 bilgisi yok"),
}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    t1.DEGISIKLIKLER = DEGISIKLIKLER
    t1.NOT = "Denetim2-T2 2026-10-07"
    db = SessionLocal()
    try:
        n = t1.uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} kayıt")
    finally:
        db.close()
