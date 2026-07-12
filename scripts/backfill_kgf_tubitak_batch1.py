"""
Faz 3 - ilk parti: KGF ve TUBITAK'in 145 bos kayitindan en yuksek etkili
6 tanesini gercek, WebFetch ile dogrulanmis icerikle doldurur.

Her kayit icin veri, kaydin kendi kaynak_url'inden (resmi KGF/TUBITAK
sayfasi) 2026-07-12 tarihinde cekilmistir - hicbir sart/tutar/oran
uydurulmamistir. Kalan ~139 kayit icin ayni yontemle devam edilecektir
(bkz. proje notlari).

Calistirma: python scripts/backfill_kgf_tubitak_batch1.py
"""
from datetime import date

from app.models import SessionLocal, Tesvik

DOGRULAMA_TARIHI = date(2026, 7, 12)

GUNCELLEMELER = {
    94: dict(  # KGF - Tarım Kefalet Destek Programı
        kategori="tarim",
        aktif_mi=True,
        durum_notu=f"KGF resmi ürün sayfasından doğrulandı ({DOGRULAMA_TARIHI}).",
        basvuru_sartlari=[
            "Tarım, ormancılık veya balıkçılık sektöründe faaliyet gösteren gerçek veya tüzel kişi işletme olmak",
            "Programa katılan 10 bankadan biri üzerinden kredi başvurusu yapmak",
        ],
        gerekli_belgeler=[
            "İlgili bankanın standart kredi başvuru evrakı",
            "İşletme/çiftçi kayıt belgesi",
            "Banka tarafından istenecek teminat/gelir belgeleri",
        ],
        basvuru_yeri="Programa dahil 10 bankadan biri: Vakıfbank, İşbankası, Garanti BBVA, Şekerbank, Denizbank, Akbank, Ziraat Bankası, Halkbank, TEB, YKB",
        basvuru_suresi="Sürekli (banka şubesi üzerinden bireysel başvuru)",
        destek_verilme_suresi="İşletme kredisi: azami 24 ay (12 ay ödemesiz dahil); Yatırım kredisi: azami 60 ay (12 ay ödemesiz dahil)",
        tutari_min=None,
        tutari_max=20_000_000,
        tutari_hesaplama_kriteri="genel",
        tutari_hesaplama_formulu="İşletme kredisi 10 milyon TL'ye, yatırım kredisi 20 milyon TL'ye kadar; kefalet oranı %80. Başvuru ücreti kredi tutarının %0,15'i (asgari 10.000 TL), yıllık komisyon %2.",
    ),
    154: dict(  # KGF - KGF Genel Destek Programı
        kategori="kobi_finansman",
        aktif_mi=True,
        durum_notu=f"KGF resmi ürün sayfasından doğrulandı ({DOGRULAMA_TARIHI}).",
        basvuru_sartlari=[
            "KOBİ tanımına uyan işletme olmak",
            "Programa dahil 15 bankadan biri üzerinden başvuru yapmak",
            "Talep edilen kredinin döviz/altın/mücevher finansmanı amaçlı olmaması",
        ],
        gerekli_belgeler=[
            "İlgili bankanın standart kredi başvuru evrakı",
            "İşletme faaliyet/vergi levhası",
        ],
        basvuru_yeri="Programa dahil 15 bankadan biri: Akbank, Anadolubank, Burgan Bank, Denizbank, Garanti BBVA, Halkbank, İşbankası, QNB, Şekerbank, TEB, TSKB, Vakıfbank, Yapı Kredi, Ziraat Bankası, Ziraat Katılım",
        basvuru_suresi="Sürekli (banka şubesi üzerinden bireysel başvuru)",
        destek_verilme_suresi="Azami 24 ay (6 ay ödemesiz dahil); stratejik sektörlerde 36 aya kadar",
        tutari_min=None,
        tutari_max=None,
        tutari_hesaplama_kriteri="genel",
        tutari_hesaplama_formulu="Kredi tutarına göre değişen kefalet oranı; başvuru ücreti 3 milyon TL altı krediler için 5.000 TL, üzeri için 10.000 TL (reddedilirse iade edilmez). Yıllık komisyon %1,5.",
    ),
    118: dict(  # KGF - KOSGEB Geri Ödemeli Destekleri
        kategori="kobi_finansman",
        aktif_mi=True,
        durum_notu=f"KGF resmi ürün sayfasından doğrulandı ({DOGRULAMA_TARIHI}).",
        basvuru_sartlari=[
            "KOSGEB tarafından onaylanmış bir destek ödemesi almaya hak kazanmış KOBİ olmak",
        ],
        gerekli_belgeler=[
            "KOSGEB destek onay yazısı",
        ],
        basvuru_yeri="Doğrudan KGF'nin kendi web sitesi üzerinden",
        basvuru_suresi="Sürekli",
        destek_verilme_suresi="KGF kefalet tahsis tarihinden itibaren 6 ay",
        tutari_min=None,
        tutari_max=5_000_000,
        tutari_hesaplama_kriteri="genel",
        tutari_hesaplama_formulu="İşletme/risk grubu başına standart limit 3.000.000 TL, KGF Yönetim Kurulu onayıyla 5.000.000 TL'ye kadar çıkabilir. Kefalet oranı %100. İnceleme ücreti: 1M TL'ye kadar 500 TL, 1-3M TL arası 1.500 TL, 3-5M TL arası 3.000 TL. Yıllık azami komisyon %1,5.",
    ),
    44: dict(  # TUBITAK 1507
        kategori="arge_kobi",
        aktif_mi=True,
        durum_notu=f"TÜBİTAK resmi program sayfasından doğrulandı ({DOGRULAMA_TARIHI}).",
        basvuru_sartlari=[
            "Türkiye'de yerleşik, sermaye şirketi statüsünde bir KOBİ olmak",
            "Aynı anda en fazla 5 projeye destek alınabilir, bunların en az 2'si ortaklı proje olmalı",
        ],
        gerekli_belgeler=[
            "PRODİS sistemi üzerinden proje öneri formu",
            "Şirket kuruluş/faaliyet belgeleri",
        ],
        basvuru_yeri="Elektronik olarak PRODİS sistemi (https://eteydeb.tubitak.gov.tr)",
        basvuru_suresi="Yılda iki çağrı dönemi: genellikle Ocak-Şubat ve Temmuz-Ağustos (güncel duyuru tubitak.gov.tr'den teyit edilmeli)",
        destek_verilme_suresi="Proje süresi azami 18 ay",
        tutari_min=None,
        tutari_max=3_500_000,
        tutari_hesaplama_kriteri="genel",
        tutari_hesaplama_formulu="Proje bütçesinin %75'i hibe (geri ödemesiz), proje başına azami 3.500.000 TL. Personel, seyahat, ekipman/yazılım, malzeme, danışmanlık ve hizmet alımı giderlerini kapsar.",
    ),
    34: dict(  # TUBITAK 1501
        kategori="arge_kobi",
        aktif_mi=True,
        durum_notu=f"TÜBİTAK resmi program sayfasından doğrulandı ({DOGRULAMA_TARIHI}).",
        basvuru_sartlari=[
            "Türkiye'de yerleşik, sermaye şirketi statüsünde bir KOBİ olmak",
            "Proje başvurusundan önce tamamlanmış Ar-Ge faaliyetleri desteklenmez",
        ],
        gerekli_belgeler=[
            "PRODİS sistemi üzerinden proje öneri formu",
            "Şirket kuruluş/faaliyet belgeleri",
        ],
        basvuru_yeri="Elektronik olarak PRODİS sistemi (https://eteydeb.tubitak.gov.tr)",
        basvuru_suresi="Yılda iki çağrı dönemi: genellikle Ocak-Şubat ve Temmuz-Ağustos (güncel duyuru tubitak.gov.tr'den teyit edilmeli)",
        destek_verilme_suresi="Proje süresi azami 36 ay",
        tutari_min=None,
        tutari_max=None,
        tutari_hesaplama_kriteri="genel",
        tutari_hesaplama_formulu="Proje bütçesinin %75'i hibe (geri ödemesiz); çağrı duyurusunda aksi belirtilmedikçe üst limit yok. Personel, seyahat, ekipman/yazılım/yayın, malzeme, danışmanlık ve üniversite/araştırma kurumu hizmet alımı giderlerini kapsar.",
    ),
    40: dict(  # TUBITAK 1601
        kategori="arge_ekosistem",
        aktif_mi=True,
        durum_notu=(
            f"TÜBİTAK resmi program sayfasından doğrulandı ({DOGRULAMA_TARIHI}). "
            "DİKKAT: Bu program bireysel çiftçi/KOBİ'nin doğrudan başvurabileceği bir "
            "program DEĞİLDİR - üniversiteler, sanayi/ticaret odaları, OSB'ler ve "
            "sermaye şirketleri gibi kurumlara yöneliktir; KOBİ'ler bu kurumların "
            "yürüttüğü programlar üzerinden dolaylı yararlanabilir."
        ),
        basvuru_sartlari=[
            "Türkiye'de yerleşik sermaye şirketi, üniversite, araştırma kurumu, sanayi/ticaret odası, OSB veya ihracatçı birliği olmak (bireysel girişimci başvuramaz)",
            "Çağrı duyurusunda başvuru yapabilecek kuruluşlar ayrıca kısıtlanabilir",
        ],
        gerekli_belgeler=[
            "Çağrıya özel başvuru formu (tubitak.gov.tr güncel çağrı duyurusundan)",
        ],
        basvuru_yeri="TÜBİTAK PRODİS sistemi, çağrıya özel; iletişim: 1601@tubitak.gov.tr",
        basvuru_suresi="Çağrıya bağlı - 2026 itibarıyla açık örnek: Küresel Temiz Teknoloji Girişimcilik Programı",
        destek_verilme_suresi="Azami 36 ay (uzatmalar dahil)",
        tutari_min=None,
        tutari_max=None,
        tutari_hesaplama_kriteri="genel",
        tutari_hesaplama_formulu="Geri ödemesiz hibe, bazı çağrılarda %100'e kadar; bütçe tavanı çağrı duyurusunda belirtilir.",
    ),
}


def main():
    db = SessionLocal()
    try:
        for tesvik_id, veri in GUNCELLEMELER.items():
            t = db.query(Tesvik).filter(Tesvik.id == tesvik_id).first()
            if t is None:
                print(f"UYARI: id={tesvik_id} bulunamadı, atlandı.")
                continue
            for alan, deger in veri.items():
                setattr(t, alan, deger)
            print(f"güncellendi: id={tesvik_id} | {t.baslik}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
