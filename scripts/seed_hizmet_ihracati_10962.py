"""Girişim modunda eksik olan üç programı resmî kaynaktan doğrulayarak ekler.

1) Ticaret Bakanlığı – Hizmet İhracatı Destekleri, BİLİŞİM sektörü (10962 sayılı Karar).
   Kaynak: Karar metni (Cumhurbaşkanı Kararı 26/2/2026, S. 10962; R.G. 27/2/2026, S. 33181),
   ticaret.gov.tr'den indirilip okundu (doğrulama 2026-10-07). MADDE 49: 5447 (E-Turquality)
   ve 5448 sayılı Kararlar yürürlükten kaldırıldı; MADDE 50: 1/1/2026'dan itibaren geçerli.
   Oran/limitler Karar'daki madde numaralarıyla birebir yazıldı.
2) KOSGEB Ar-Ge, Ür-Ge ve İnovasyon Destek Programı – KAPALI. kosgeb.gov.tr sayfası
   "Yürürlükten Kaldırılan Destekler" altında; son çağrı 2022-02 (doğrulama 2026-10-07).
3) KOSGEB KOBİGEL – KAPALI. Aynı şekilde "Yürürlükten Kaldırılan Destekler" altında; son
   çağrı 2022.01 (doğrulama 2026-10-07).

Kapalı programlar bilerek ekleniyor: kullanıcı/danışman "bu program kapandı" diyebilsin,
"bilgim yok" demesin. Eşleşme (esles) kapalı kayıtları zaten listelemez.

  python scripts/seed_hizmet_ihracati_10962.py --dry-run
  python scripts/seed_hizmet_ihracati_10962.py            # idempotent (kaynak_url ile)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, TesvikNace, init_db  # noqa: E402

DOGRULAMA = date(2026, 10, 7)
KARAR_URL = "https://ticaret.gov.tr/data/69a9d756269de18b843851b7/%C3%87er%C3%A7eve%20Karar.pdf"
GENELGE_URL = ("https://ticaret.gov.tr/data/69abe397269de14590bea074/0.%20Hizmet%20Sekt%C3%B6rlerinin"
               "%20Desteklenmesine%20%C4%B0li%C5%9Fkin%20Genelge.pdf")

KAYITLAR: list[dict] = [
    dict(
        kurum="Ticaret Bakanlığı",
        baslik="Hizmet İhracatı Destekleri – Bilişim Sektörü (10962 sayılı Karar, Hizmet Sektörleri Atılım Programı)",
        ozet=("Yazılım, mobil uygulama ve dijital oyun geliştiren şirketlerin yurt dışı pazara girişine yönelik "
              "barındırma, reklam/tanıtım, platform komisyonu, yazılım lisansı, rapor/veri tabanı üyeliği, "
              "uluslararası kuruluş üyeliği, yurt içi/yurt dışı etkinlik katılımı ve tanıtım personeli "
              "giderlerinin %50'sinin geri ödemesiz karşılandığı program. 5447 (E-Turquality) ve 5448 sayılı "
              "Kararların yerini aldı; 1/1/2026'dan itibaren geçerli."),
        detay=(
            "10962 sayılı Karar, Hizmet Sektörleri Atılım Programı – bilişim sektörüne yönelik destek "
            "unsurları (oran ve yıllık üst limitler Karar metninden): "
            "Barındırma desteği (MADDE 16): yazılım/mobil uygulama/dijital oyun/dijital aracılık platformunun "
            "yurt dışı pazara girişi için barındırma giderleri %50, yıllık en fazla 5.000.000 TL, yararlanıcı "
            "başına en fazla 5 yıl. "
            "Dijital ürün tanıtım desteği (MADDE 17): yurt dışına yönelik reklam, tanıtım ve pazarlama giderleri "
            "%50, yıllık en fazla 50.000.000 TL; yılda en fazla 10 ürün, ürün başına yıllık en fazla 15.000.000 TL; "
            "en fazla 5 yıl. "
            "İş gücü geliştirme desteği (MADDE 19/2-3): uluslararası tanıtım ve pazarlama için yurt içinde "
            "istihdam edilen en fazla 5 personelin giderleri %50, personel başına aylık en fazla 90.000 TL; "
            "yurt dışı birimlerde en fazla 5 personel %50, personel başına aylık en fazla 250.000 TL; her fıkra "
            "için en fazla 5 yıl; personel nitelikleri Bakanlıkça belirlenir. "
            "Platform komisyon desteği (MADDE 22): yurt dışı satış/dağıtım platform komisyonları %50, yıllık en "
            "fazla 20.000.000 TL; yılda en fazla 10 ürün, ürün başına yıllık en fazla 4.000.000 TL; en fazla 5 yıl. "
            "Rapor ve veri tabanı üyeliği desteği (MADDE 23): yurt dışı pazar stratejisi raporları ve veri tabanı "
            "üyelikleri %50, yıllık en fazla 2.500.000 TL; en fazla 5 yıl. "
            "Uluslararası kuruluşlara üyelik desteği (MADDE 26): %50, yıllık en fazla 2.500.000 TL. "
            "Yazılım lisans desteği (MADDE 31): satın alınan/kiralanan yazılım lisansları %50, yıllık en fazla "
            "2.500.000 TL; en fazla 5 yıl. "
            "Yurt dışı etkinlik katılım desteği (MADDE 13): %50, etkinlik başına en fazla 1.500.000 TL (prestijli "
            "etkinlikte 2 katı). Yurt içi etkinlik katılım desteği (MADDE 15): %50, etkinlik başına en fazla "
            "600.000 TL (prestijli etkinlikte 2 katı). "
            "Uygulama usul ve esasları Hizmet Sektörlerinin Desteklenmesine İlişkin Genelge'de; başvurular "
            "incelemeci kuruluş olan Hizmet İhracatçıları Birliği Genel Sekreterliği tarafından incelenir "
            "(Genelge MADDE 4). TL tutarları Karar'daki değerlerdir; güncellenip güncellenmediği Bakanlık "
            f"sayfasından teyit edilmeli. Genelge: {GENELGE_URL}"
        ),
        hedef_kitle=("Bilişim sektöründe faaliyet gösteren, Türkiye'de yerleşik ve TTK'ya göre kurulmuş şirketler "
                     "(yazılım, mobil uygulama, dijital oyun, SaaS); kooperatifler"),
        kaynak_url=KARAR_URL,
        kategori="e_ticaret_ihracat",
        aktif_mi=True,
        durum_notu=(f"Karar metninden doğrulandı ({DOGRULAMA}). R.G. 27/2/2026 S. 33181; MADDE 50 ile 1/1/2026'dan "
                    "itibaren geçerli. 5447 ve 5448 sayılı Kararlar MADDE 49 ile yürürlükten kaldırıldı."),
        basvuru_sartlari=[
            "Yararlanıcı: Türkiye'de yerleşik, 6102 sayılı TTK hükümlerine göre kurulmuş şirket (veya 1163 sayılı "
            "Kanun kapsamında kooperatif) olmak (Karar MADDE 3 – 'Yararlanıcı' tanımı); şahıs işletmesi ve "
            "şirketleşmemiş girişim yararlanıcı tanımına girmez",
            "Bilişim sektöründe faaliyet göstermek; desteğe konu ürün yararlanıcının kendi yazılımı, mobil "
            "uygulaması veya dijital oyunu olmak (MADDE 16, 17, 22)",
            "Giderlerin yurt dışı pazara giriş / yurt dışına yönelik faaliyetlere ilişkin olması (MADDE 16, 17, 22)",
            "Ürün bazlı desteklerde yılda en fazla 10 ürün; yararlanıcı başına destek süresi en fazla 5 yıl "
            "(MADDE 16/2, 17/2-3, 22/2-3, 23/2, 31/2)",
            "Destek, giderler yapılıp belgelendikten sonra ödenir (geri ödemesiz, harcama sonrası); usul ve "
            "esaslar Genelge'de (Genelge MADDE 1-4)",
        ],
        gerekli_belgeler=[
            "Destek Yönetim Sistemi (DYS) üzerinden başvuru ve gider belgeleri (Genelge MADDE 3 dayanağı: "
            "2019/7 sayılı Ticaret Bakanlığı DYS Genelgesi)",
            "Gider faturaları/dekontları ve ödeme belgeleri",
        ],
        basvuru_yeri="Ticaret Bakanlığı Uluslararası Hizmet Ticareti Genel Müdürlüğü; incelemeci kuruluş: "
                     "Hizmet İhracatçıları Birliği Genel Sekreterliği (DYS üzerinden)",
        basvuru_suresi="Sürekli (program bazlı; yararlanıcı başına en fazla 5 yıl)",
        tutari_hesaplama_formulu=("Her kalemde giderin %50'si; yıllık üst limitler kalem bazında: barındırma 5M TL, "
                                  "tanıtım 50M TL (ürün başına 15M), platform komisyonu 20M TL (ürün başına 4M), "
                                  "yazılım lisansı 2,5M TL, rapor/veri tabanı 2,5M TL, kuruluş üyeliği 2,5M TL "
                                  "(10962 sayılı Karar MADDE 16-31)"),
        tutari_hesaplama_kriteri="genel",
        uygunluk_kriterleri={
            "sektorler": ["ihracat", "arge", "hizmet", "e-ticaret"],
            "sektor_gerekcesi": "10962 sayılı Karar MADDE 2/b: Hizmet Sektörleri Atılım Programı bilişim sektörü",
            "tutar_niteligi": "hibe",
        },
        nace=[("62", "elle"), ("63", "elle"), ("58.2", "elle")],
    ),
    dict(
        kurum="KOSGEB",
        baslik="Ar-Ge, Ür-Ge ve İnovasyon Destek Programı (yürürlükten kaldırıldı)",
        ozet=("KOBİ ve girişimcilerin Ar-Ge/inovasyon projeleriyle yeni ürün, süreç ve hizmet geliştirmesine ve "
              "Ür-Ge faaliyetleriyle ürünlerini pazar talebine uyarlamasına destek veren program. KOSGEB sitesinde "
              "'Yürürlükten Kaldırılan Destekler' altında; yeni başvuru alınmıyor."),
        detay=("KOSGEB'in resmî program sayfasındaki destek tablosu (kapalı programa ait): makine-teçhizat/yazılım/"
               "hizmet alımı geri ödemesiz 200.000 TL'ye kadar (%75, yerli malı +%15) ve geri ödemeli 300.000 TL'ye "
               "kadar (%75); nitelikli personel 300.000 TL'ye kadar (%100); sınai mülkiyet hakları 100.000 TL'ye "
               "kadar (%75); test/analiz/belgelendirme 100.000 TL'ye kadar (%75). Son proje teklif çağrısı 2022-02 "
               "(Savunma ve Elektrikli/Hibrit Otomotiv). KOSGEB'in güncel Ar-Ge/yenilik odaklı finansman programları: "
               "Küresel Rekabetçilik Destek Programı ve Kapasite Geliştirme Destek Programı (ayrı kayıtlar)."),
        hedef_kitle="KOBİ'ler ve girişimciler (program kapalı)",
        kaynak_url="https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/7664/arge-urge-ve-inovasyon-destek-programi",
        kategori="arge_kobi",
        aktif_mi=False,
        durum_notu=(f"KOSGEB sitesinde 'Yürürlükten Kaldırılan Destekler' kategorisinde ({DOGRULAMA}); sayfada "
                    "açık çağrı yok, son çağrı 2022-02. İzlemesi süren eski projeler etkilenmez. Yeni başvuru için "
                    "Küresel Rekabetçilik veya Kapasite Geliştirme Destek Programı'na bakın."),
        basvuru_sartlari=["Program yürürlükten kaldırılmıştır; yeni başvuru alınmamaktadır"],
        uygunluk_kriterleri={"sektorler": ["arge", "genel"], "tutar_niteligi": "hibe"},
        nace=[],
    ),
    dict(
        kurum="KOSGEB",
        baslik="KOBİGEL – KOBİ Gelişim Destek Programı (yürürlükten kaldırıldı)",
        ozet=("KOBİ'lerin rekabet gücünü ve sağladıkları katma değeri yükseltmeye yönelik proje bazlı destek programı. "
              "KOSGEB sitesinde 'Yürürlükten Kaldırılan Destekler' altında; yeni çağrı açılmıyor."),
        detay=("KOSGEB'in resmî program sayfası (kapalı programa ait): proje bazlı destek üst limiti 2.000.000 TL; "
               "personel dışı giderlerde en az %60 destek, makine/yazılım/hizmet alımlarının %70'i geri ödemeli, "
               "personel giderleri limit dahilinde %100 geri ödemesiz. Son çağrı 2022.01 'İmalat Sanayi Sektöründe "
               "Dijitalleşme Sürecine Katkı Sağlayabilecek Yerli Teknoloji Geliştiricisi KOBİ'lerin Desteklenmesi'. "
               "KOSGEB'in güncel büyüme programları: Kapasite Geliştirme ve Küresel Rekabetçilik Destek Programları."),
        hedef_kitle="İmalat sanayi KOBİ'leri (program kapalı)",
        kaynak_url="https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/3288/kobigel-kobi-gelisim-destek-programi",
        kategori="kobi_finansman",
        aktif_mi=False,
        durum_notu=(f"KOSGEB sitesinde 'Yürürlükten Kaldırılan Destekler' kategorisinde ({DOGRULAMA}); sayfadaki tek "
                    "çağrı 2022.01. Yeni başvuru için Kapasite Geliştirme veya Küresel Rekabetçilik Destek "
                    "Programı'na bakın."),
        basvuru_sartlari=["Program yürürlükten kaldırılmıştır; yeni çağrı açılmamaktadır"],
        uygunluk_kriterleri={"sektorler": ["imalat", "genel"], "tutar_niteligi": "hibe"},
        nace=[],
    ),
]


def calistir(db, *, dry_run: bool = False) -> dict:
    eklenen, guncellenen = [], []
    simdi = datetime.now(timezone.utc)
    for k in KAYITLAR:
        k = dict(k)
        nace = k.pop("nace")
        t = db.query(Tesvik).filter(Tesvik.kaynak_url == k["kaynak_url"]).first()
        if t is None:
            eklenen.append(k["baslik"])
            if not dry_run:
                t = Tesvik(**k, guncelleme_tarihi=simdi)
                db.add(t)
                db.flush()
        else:
            guncellenen.append(k["baslik"])
            if not dry_run:
                for alan, deger in k.items():
                    setattr(t, alan, deger)
                t.guncelleme_tarihi = simdi
        if not dry_run and nace:
            mevcut = {(r.nace_prefix, r.haric_mi) for r in db.query(TesvikNace).filter(TesvikNace.tesvik_id == t.id)}
            for prefix, kaynak in nace:
                if (prefix, False) not in mevcut:
                    db.add(TesvikNace(tesvik_id=t.id, nace_prefix=prefix, kaynak=kaynak))
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
