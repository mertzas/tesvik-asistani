"""İşsizlik Sigortası Fonu'ndan finanse edilen istihdam teşviklerini (İŞKUR/SGK) ekler.

Denetim 2 (2026-10-07) ölçümü: Hatay'da restoran işleten mikro işletme "3 kişi daha işe
alacağım, SGK desteği var mı?" sorusunda danışman dürüstçe "bağlamda istihdam/SGK teşviki yok"
dedi — veritabanında bu kayıt yoktu. Kaynak: İŞKUR resmî "Teşvikler" sayfaları (Chrome ile
okundu, 2026-10-07). Sayfada OLMAYAN hiçbir oran/tutar yazılmadı.

  python scripts/seed_istihdam_tesvikleri_4447.py --dry-run
  python scripts/seed_istihdam_tesvikleri_4447.py            # idempotent (kaynak_url ile)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, init_db  # noqa: E402

DOGRULAMA = date(2026, 10, 7)
ISKUR = "https://www.iskur.gov.tr/isveren/tesvikler/"

KAYITLAR: list[dict] = [
    dict(
        kurum="SGK / İŞKUR",
        baslik="Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İstihdamı Teşviki (4447 sayılı Kanun geçici 10. madde)",
        ozet=("31.12.2026 tarihine kadar işsiz kişileri ilave olarak istihdam eden özel sektör işverenlerinin, "
              "prime esas kazanç üst sınırına kadarki sigorta primi işveren paylarının İşsizlik Sigortası Fonu'ndan "
              "karşılandığı teşvik. Süre kadın/genç/mesleki belge durumuna göre 6–54 ay; İŞKUR kaydı +6 ay."),
        detay=(
            "İŞKUR 'Teşvikler' sayfasından (erişim 2026-10-07): 31.12.2026 tarihine kadar işsiz olan kişileri istihdam "
            "eden özel sektör işverenlerinin prime esas kazanç üst sınırına kadarki sosyal güvenlik primi işveren "
            "payları (sayfadaki aralık: 7.184,03 TL ila 64.656,23 TL) İşsizlik Sigortası Fonu'ndan karşılanır. "
            "Destek süreleri: 18 yaş ve üzeri kadınlar 24–54 ay; 18-29 yaş erkekler 24–54 ay; 29 yaş ve üzeri erkekler "
            "6–30 ay; çalışmakta iken 01.03.2011 sonrası mesleki yeterlilik belgesi alanlar / mesleki-teknik eğitimi "
            "tamamlayanlar / işgücü yetiştirme kurslarını bitirenler 12 ay. Kişinin İŞKUR'a kayıtlı olması hâlinde "
            "süreye 6 ay eklenir. Uygulayıcı kurum SGK'dır (finansman İşsizlik Sigortası Fonu). Süre ve tutar "
            "ayrıntıları için SGK'nın güncel genelgesi teyit edilmelidir."
        ),
        hedef_kitle="Özel sektör işverenleri (tüm sektörler, ölçek sınırı yok); işe alınan kişi son 6 aydır işsiz olmalı",
        kaynak_url=ISKUR + "kadin-genc-ve-mesleki-yeterlilik-belgesi-olanlarin-tesviki/",
        kategori="istihdam",
        aktif_mi=True,
        durum_notu=f"İŞKUR resmî sayfasından doğrulandı ({DOGRULAMA}); uygulama 31.12.2026'ya kadar (4447 geçici 10).",
        basvuru_sartlari=[
            "İşe alınan kişinin son 6 aydır işsiz olması",
            "Kişinin, işe alındığı tarihten önceki son 6 ayın ortalama sigortalı çalışan sayısına İLAVE olarak istihdam edilmesi",
            "Özel sektör işvereni olmak; aylık prim ve hizmet belgelerinin yasal süresinde verilmesi ve primlerin ödenmesi (SGK genel şartları)",
            "Uygulama süresi: 31.12.2026 tarihine kadar işe alımlar",
        ],
        gerekli_belgeler=["SGK e-Bildirge üzerinden teşvik kodu ile bildirim", "İŞKUR kaydı (ek 6 ay için)"],
        basvuru_yeri="SGK (e-Bildirge) — uygulayıcı kurum; bilgi: İŞKUR il müdürlükleri",
        basvuru_suresi="Sürekli; 31.12.2026 tarihine kadar yapılan işe alımlar için",
        tutari_hesaplama_formulu=("İşveren prim payı × destek süresi (6–54 ay; kişinin yaşı/cinsiyeti/belgesine göre; "
                                  "İŞKUR kayıtlı ise +6 ay); prim tabanı prime esas kazanç üst sınırına kadar"),
        tutari_hesaplama_kriteri="istihdam",
        uygunluk_kriterleri={"sektorler": ["genel"], "tutar_niteligi": "prim desteği",
                             "sektor_gerekcesi": "4447 geçici 10: tüm özel sektör işverenleri"},
    ),
    dict(
        kurum="SGK / İŞKUR",
        baslik="İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik (4447 sayılı Kanun 50/5)",
        ozet=("İşsizlik ödeneği almakta olan kişileri işe alan işverenlere yönelik, İşsizlik Sigortası Fonu'ndan "
              "finanse edilen prim desteği; uygulayıcı kurum SGK. Süre ve oran ayrıntıları SGK genelgesinde."),
        detay=(
            "İŞKUR 'Teşvikler' sayfasından (erişim 2026-10-07): kanuni dayanak 4447 sayılı Kanunun 50. maddesinin "
            "beşinci fıkrası. Sayfadaki şartlar: aylık prim ve hizmet belgesinin yasal süresinde SGK'ya verilmesi ve "
            "primlerin yasal süresinde ödenmesi; işçinin işten ayrıldığı işyerinde tekrar işe başlaması hâlinde "
            "teşvikten yararlanılamaz. Destek tutarı/süresi İŞKUR sayfasında yer almıyor; SGK mevzuatından teyit edin."
        ),
        hedef_kitle="İşsizlik ödeneği alan kişileri istihdam eden özel sektör işverenleri",
        kaynak_url=ISKUR + "issizlik-odenegi-alanlara-yonelik-tesvik/",
        kategori="istihdam",
        aktif_mi=True,
        durum_notu=f"İŞKUR resmî sayfasından doğrulandı ({DOGRULAMA}); tutar/süre sayfada yok.",
        basvuru_sartlari=[
            "İşe alınan kişinin işsizlik ödeneği alıyor olması",
            "İşçinin, işten ayrıldığı işyerinde tekrar işe başlamaması",
            "Aylık prim ve hizmet belgesinin yasal süresinde verilmesi, primlerin yasal süresinde ödenmesi",
        ],
        gerekli_belgeler=["SGK e-Bildirge üzerinden teşvik kodu ile bildirim"],
        basvuru_yeri="SGK (e-Bildirge)",
        basvuru_suresi="Sürekli",
        tutari_hesaplama_kriteri="istihdam",
        uygunluk_kriterleri={"sektorler": ["genel"], "tutar_niteligi": "prim desteği"},
    ),
]


def calistir(db, *, dry_run: bool = False) -> dict:
    eklenen, guncellenen = [], []
    simdi = datetime.now(timezone.utc)
    for k in KAYITLAR:
        t = db.query(Tesvik).filter(Tesvik.kaynak_url == k["kaynak_url"]).first()
        if t is None:
            eklenen.append(k["baslik"])
            if not dry_run:
                db.add(Tesvik(**k, guncelleme_tarihi=simdi))
        else:
            guncellenen.append(k["baslik"])
            if not dry_run:
                for alan, deger in k.items():
                    setattr(t, alan, deger)
                t.guncelleme_tarihi = simdi
    if not dry_run:
        db.commit()
    return {"eklenen": eklenen, "guncellenen": guncellenen}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    init_db()
    db = SessionLocal()
    try:
        sonuc = calistir(db, dry_run=a.dry_run)
    finally:
        db.close()
    for b in sonuc["eklenen"]:
        print(f"[{'eklenecek' if a.dry_run else 'eklendi'}] {b}")
    for b in sonuc["guncellenen"]:
        print(f"[{'güncellenecek' if a.dry_run else 'güncellendi'}] {b}")


if __name__ == "__main__":
    main()
