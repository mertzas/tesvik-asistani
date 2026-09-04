"""
TÜBİTAK 1512 BiGG (Bireysel Genç Girişim) kaydini ekler.

NEDEN ONEMLI: Veritabaninda 1612 (uygulayici kurulusa yonelik cagri) ve
1812 (BiGG Yatirim) vardi ama girisimcinin DOGRUDAN basvurdugu asil
program olan 1512 hic yoktu. Sirketi henuz olmayan bir girisimci icin
TUBITAK'in tek acik kapisi bu - digerleri (1507/1501/1601) "sermaye
sirketi olmak" sartini ariyor.

TUTAR KONUSUNDA BELIRSIZLIK VAR, bilerek kesin rakam yazilmadi:
  - ODTU Teknokent BiGG sayfasi (uygulayici kurulus, 2026): 1.350.000 TL,
    TUBITAK BiGG Fonu araciligiyla %3 hisse karsiligi yatirim olarak
  - Cesitli universite TTO sayfalari (muhtemelen eski donem): 150.000 TL
    (110.000 proje + 40.000 sermaye)
Iki kaynak celisiyor ve TUBITAK'in kendi sayfasi 403 dondugu icin
dogrudan teyit edilemedi. Bu yuzden tutar alani "dogrulanmasi gereken"
olarak isaretlendi - projenin uydurma-yasak ilkesi geregi kesin rakam
yazilmiyor.

Calistirma: python scripts/seed_bigg_1512.py
"""
from datetime import date

from app.models import SessionLocal, Tesvik

DOGRULAMA_TARIHI = date(2026, 9, 4)

KAYIT = dict(
    kurum="TUBITAK",
    baslik="1512 - Girişimcilik Destek Programı (BiGG - Bireysel Genç Girişim)",
    ozet=(
        "Şirketi henüz olmayan bireysel girişimcilere yönelik, teknoloji ve "
        "yenilik odaklı iş fikirlerini şirketleşmeye taşıyan iki aşamalı program. "
        "Destek, TÜBİTAK BiGG Fonu aracılığıyla %3 hisse karşılığı yatırım "
        "olarak kurulacak şirkete aktarılır."
    ),
    detay=(
        "TÜBİTAK 1512 BiGG, teknoloji tabanlı iş fikri olan bireysel girişimcilere "
        "yöneliktir ve iki aşamada yürütülür. 1. Aşamada iş fikri başvurusu alınır ve "
        "uygulayıcı kuruluşlar (üniversite TTO'ları, teknokentler) eğitim/mentorluk "
        "verir; 2. Aşamada iş planı değerlendirilir ve panel sonucunda desteklenmeye "
        "hak kazanan girişimciler belirli süre içinde şirketlerini (A.Ş. veya Ltd.) "
        "kurar.\n\n"
        "KRİTİK ŞART - ŞİRKET SIRALAMASI: Başvuru tarihi itibarıyla girişimcinin "
        "HERHANGİ BİR İŞLETMENİN ORTAKLIK YAPISINDA YER ALMAMASI gerekir. Yani şirket "
        "kurulduktan SONRA bu programa başvurulamaz; sıralama önce başvuru, sonra "
        "şirket kuruluşudur. Bu, TÜBİTAK'ın diğer programlarının (1507/1501/1601) "
        "'sermaye şirketi olmak' şartıyla taban tabana zıttır - hangi kapıdan "
        "gireceğinize şirket kurmadan ÖNCE karar vermelisiniz.\n\n"
        "Ayrıca başvuran, daha önce Bilim/Sanayi ve Teknoloji Bakanlığı Teknogirişim "
        "Sermayesi Desteği veya TÜBİTAK 1512 2. Aşama sermaye desteği almamış olmalıdır.\n\n"
        "DESTEK TUTARI DOĞRULANMALI: ODTÜ Teknokent'in BiGG sayfası 2026 için "
        "1.350.000 TL (%3 hisse karşılığı yatırım) belirtiyor; çeşitli üniversite TTO "
        "sayfaları ise 150.000 TL (110.000 proje + 40.000 sermaye) diyor - bu muhtemelen "
        "eski döneme ait. TÜBİTAK'ın kendi sayfası doğrudan çekilemediği için kesin "
        "güncel tutar teyit edilememiştir; başvuru öncesi 444 66 90'dan doğrulayın."
    ),
    hedef_kitle="Şirketi olmayan bireysel girişimciler; üniversitelerin ön lisans/lisans/yüksek lisans/doktora öğrencileri ve mezunları",
    kaynak_url="https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/1512-girisimcilik-destek-programi-bigg",
    kategori="girisimcilik",
    aktif_mi=True,
    durum_notu=(
        f"Uygulayıcı kuruluş (ODTÜ Teknokent) sayfasından aktif olduğu doğrulandı "
        f"({DOGRULAMA_TARIHI}). Çağrı dönemlidir - son başvuru tarihi geçmiş olabilir, "
        f"güncel çağrı takvimi TÜBİTAK'tan (444 66 90) teyit edilmeli."
    ),
    uygunluk_kriterleri={"sektorler": ["genel", "arge"]},
    basvuru_sartlari=[
        "Başvuru tarihi itibarıyla HERHANGİ BİR İŞLETMENİN ortaklık yapısında yer almamak (şirket kurulduysa başvurulamaz)",
        "Üniversitelerin ön lisans/lisans/yüksek lisans/doktora programlarından öğrenci veya mezun olmak",
        "Daha önce Teknogirişim Sermayesi Desteği veya TÜBİTAK 1512 2. Aşama sermaye desteği almamış olmak",
        "Teknoloji/yenilik odaklı bir iş fikrine sahip olmak",
    ],
    gerekli_belgeler=[
        "İş fikri başvuru formu (1. Aşama)",
        "İş planı (2. Aşama)",
        "Öğrenci belgesi veya diploma",
    ],
    basvuru_yeri="Uygulayıcı kuruluşlar (üniversite TTO'ları, teknokentler) üzerinden; TÜBİTAK çağrı duyurusuna göre",
    basvuru_suresi="Çağrı dönemli - güncel takvim TÜBİTAK'tan teyit edilmeli",
    tutari_hesaplama_kriteri="genel",
    tutari_hesaplama_formulu=(
        "TÜBİTAK BiGG Fonu aracılığıyla %3 hisse karşılığı yatırım. Tutar kaynaklara "
        "göre çelişiyor (2026 için 1.350.000 TL vs eski dönem 150.000 TL) - kesin "
        "rakam TÜBİTAK'tan doğrulanmalıdır."
    ),
)


def main():
    db = SessionLocal()
    try:
        mevcut = db.query(Tesvik).filter(Tesvik.kaynak_url == KAYIT["kaynak_url"]).first()
        if mevcut:
            for alan, deger in KAYIT.items():
                setattr(mevcut, alan, deger)
            print(f"güncellendi: {KAYIT['baslik']}")
        else:
            db.add(Tesvik(**KAYIT))
            print(f"eklendi: {KAYIT['baslik']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
