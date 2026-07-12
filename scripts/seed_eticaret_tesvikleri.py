"""
Ticaret Bakanlığı'nın e-ihracat/e-ticaret desteklerini ekler - bu kuruma
ait DAHA ONCE HIC KAYIT YOKTU (DB'de sadece KOSGEB/TUBITAK/KGF/Tarım
Bakanlığı vardı). Icerik 2026-07-12'de resmi ticaret.gov.tr sayfalarindan
ve resmi genelgeye atif yapan ikincil kaynaklardan dogrulanmistir (bkz.
her kaydin notlar/kaynak_url alani) - kesin guncel ust limit rakamlari
icin Bakanlik'in kendi "Genelge Ekleri" Excel tablosu esas alinmalidir,
o yuzden TL limitleri buraya KESIN rakam olarak YAZILMAMISTIR, sadece
oran ve genel yapi girilmistir.

Calistirma: python scripts/seed_eticaret_tesvikleri.py
"""
from datetime import date

from app.models import SessionLocal, Tesvik

DOGRULAMA_TARIHI = date(2026, 7, 12)

KAYITLAR = [
    dict(
        kurum="Ticaret Bakanlığı",
        baslik="E-İhracat Destekleri (5986 Sayılı Karar)",
        ozet=(
            "Şirketlerin, e-ihracat konsorsiyumlarının, perakende e-ticaret "
            "sitelerinin ve pazaryerlerinin yurt dışı pazaryerlerinde "
            "komisyon, reklam/tanıtım, depolama, sipariş karşılama, "
            "entegrasyon ve pazara giriş raporu giderlerinin %50'sinin "
            "(bazı hedef ülkelerde %70'e kadar) 3 yıl süreyle karşılandığı "
            "destek programı."
        ),
        detay=(
            "5986 sayılı 'E-İhracat Destekleri Hakkında Karar' kapsamında "
            "7 ayrı gider kalemi desteklenir: (1) pazara giriş raporu, "
            "(2) dijital pazaryeri tanıtım, (3) e-ihracat tanıtım/pazarlama, "
            "(4) sipariş karşılama hizmeti, (5) yurt dışı depo kirası, "
            "(6) pazaryeri entegrasyon, (7) pazaryeri komisyon giderleri. "
            "Standart destek oranı %50'dir; Bakanlık'ın belirlediği hedef "
            "ülkelerde bu oran %70'e kadar çıkabilir. Destek süresi "
            "ülke/gider kalemi başına 3 yıldır. ÖNEMLİ ÖN ŞART: "
            "başvuran firmanın bir ihracatçı birliğine üye olması "
            "zorunludur - üyelik olmadan başvuru kabul edilmez. Yıllık üst "
            "limitler yararlanıcı tipine (şirket / perakende e-ticaret "
            "sitesi / pazaryeri / konsorsiyum) göre değişir ve Bakanlık "
            "tarafından her yıl güncellenir - güncel TL tutarları için "
            "ticaret.gov.tr/destekler/e-ihracat-destekleri/genelge-ekleri "
            "sayfasındaki 'Üst Limitler' tablosuna bakılmalıdır."
        ),
        hedef_kitle="E-ihracat yapan/yapacak şirketler, perakende e-ticaret siteleri, pazaryerleri, e-ihracat konsorsiyumları",
        kaynak_url="https://ticaret.gov.tr/destekler/e-ihracat-destekleri",
        kategori="e_ticaret_ihracat",
        aktif_mi=True,
        durum_notu=f"ticaret.gov.tr ve resmi genelgeye atıfta bulunan ikincil kaynaklardan doğrulandı ({DOGRULAMA_TARIHI}). Kesin güncel TL üst limitleri için Bakanlık'ın 'Genelge Ekleri' sayfasındaki Excel tablosu kontrol edilmelidir - buraya kesin rakam yazılmamıştır.",
        basvuru_sartlari=[
            "Bir ihracatçı birliğine üye olmak (zorunlu ön şart)",
            "Desteklenen gider kalemlerine ilişkin dekont/fatura ile başvuru yapmak",
        ],
        gerekli_belgeler=[
            "İhracatçı birliği üyelik belgesi",
            "Gider dekontu/faturası (pazaryeri komisyon kesinti belgesi, reklam faturası vb.)",
            "Destek başvuru formu (ilgili gider kalemine özel)",
        ],
        basvuru_yeri="İhracatçı Birlikleri Genel Sekreterliği / Ticaret Bakanlığı e-Devlet başvuru sistemi",
        basvuru_suresi="Sürekli (gider kalemine göre dönemsel başvuru pencereleri olabilir)",
        destek_verilme_suresi="Ülke/gider kalemi başına 3 yıl",
        tutari_hesaplama_kriteri="genel",
        tutari_hesaplama_formulu="Desteklenen giderin %50'si (hedef ülkelere göre %70'e kadar); yıllık üst limit yararlanıcı tipine göre değişir, güncel tutar Bakanlık'ın genelge ekleri tablosundan teyit edilmelidir.",
    ),
    dict(
        kurum="Ticaret Bakanlığı",
        baslik="Pazara Girişte Dijital Faaliyetlerin Desteklenmesi",
        ozet=(
            "E-ticaret sitelerine bireysel üyelik, sanal ticaret heyetleri, "
            "sanal fuarlara katılım ve sanal yurt dışı pazarlama "
            "faaliyetlerinin desteklendiği program."
        ),
        detay=(
            "Bakanlık tarafından onaylanan e-ticaret sitelerine (pazaryerlerine) "
            "bireysel üyelik giderleri %60 oranında, yıllık 15.102 TL'ye kadar "
            "desteklenir (dekont tarihine göre güncellenen bir üst limittir - "
            "bu rakam ilk kez 2026-07-12'de doğrulanmıştır, güncel değeri "
            "Bakanlık'ın ilgili sayfasından teyit edin). Programın diğer "
            "kalemleri: sanal ticaret heyetleri, sanal fuarlara katılım, "
            "sanal fuar organizasyonları ve sanal yurt dışı pazarlama "
            "faaliyetleri - bu kalemler için ayrı oran/limitler vardır ve "
            "bu kayıtta detaylandırılmamıştır."
        ),
        hedef_kitle="E-ticarete yeni başlayan veya dijital pazarlamayı büyütmek isteyen ihracatçı firmalar",
        kaynak_url="https://ticaret.gov.tr/destekler/ihracat-destekleri/pazara-giriste-dijital-faaliyetlerin-desteklenmesi",
        kategori="e_ticaret_ihracat",
        aktif_mi=True,
        durum_notu=f"ticaret.gov.tr resmi sayfasından doğrulandı ({DOGRULAMA_TARIHI}) - sadece e-ticaret sitesi bireysel üyelik kalemi (%60, yıllık 15.102 TL) net teyit edildi; diğer kalemlerin (sanal heyet/fuar) oran/limitleri bu kayıtta yok.",
        basvuru_sartlari=[
            "Bakanlık tarafından onaylanan bir e-ticaret sitesine/pazaryerine üyelik gideri yapmış olmak",
        ],
        gerekli_belgeler=[
            "Üyelik dekontu",
            "Destek başvuru formu ve taahhütname",
        ],
        basvuru_yeri="İhracatçı Birlikleri Genel Sekreterliği / Ticaret Bakanlığı",
        basvuru_suresi="Dekont tarihine göre (sürekli başvuru)",
        destek_verilme_suresi="Yıllık",
        tutari_min=None,
        tutari_max=15_102,
        tutari_hesaplama_kriteri="genel",
        tutari_hesaplama_formulu="E-ticaret sitesi bireysel üyelik giderinin %60'ı, yıllık azami 15.102 TL (bu rakam 2026-07-12'de teyit edilmiştir, yıllık güncellenebilir).",
    ),
]


def main():
    db = SessionLocal()
    try:
        for veri in KAYITLAR:
            mevcut = db.query(Tesvik).filter(Tesvik.kaynak_url == veri["kaynak_url"]).first()
            if mevcut:
                for alan, deger in veri.items():
                    setattr(mevcut, alan, deger)
                print(f"güncellendi: {veri['baslik']}")
            else:
                db.add(Tesvik(**veri))
                print(f"eklendi: {veri['baslik']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
