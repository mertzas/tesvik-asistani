"""
KOSGEB Girisimci Destek Programi kaydina, dogrulanmis sirket-turu ve
ortaklik sartlarini ekler.

Kaynak: kosgeb.gov.tr resmi program sayfasi + 2026/2. donem cagri
duyurusu, 2026-08-02'de dogrulandi. Bu bilgiler sistemde yoktu ve
kullanicinin "sahis sirketi yeterli mi" sorusunun cevabini belirliyor.

Calistirma: python scripts/update_kosgeb_girisimci_detay.py
"""
from app.models import SessionLocal, Tesvik

BASLIK = "Girişimci Destek Programı"

EK_SARTLAR = [
    "Şirket türü tutarı belirler: Gerçek kişi (şahıs) işletmesi 10.000 TL, sermaye şirketi (Ltd./A.Ş.) 20.000 TL İş Kurma Desteği alır",
    "Girişimcinin başvurduğu işletmedeki ortaklık payı en az %50 olmalıdır",
    "Desteklenen sektörler arasında imalat, telekomünikasyon, bilgisayar programlama, bilişim altyapısı ve bilimsel Ar-Ge yer alır",
]

EK_NOT = (
    " ŞİRKET TÜRÜ FARKI (2026-08-02'de kosgeb.gov.tr'den doğrulandı): Şahıs "
    "işletmesi bu programa başvurabilir ancak İş Kurma Desteği 10.000 TL ile "
    "sınırlıdır; sermaye şirketi (Ltd./A.Ş.) 20.000 TL alır. Asıl fark ise "
    "burada değil: TÜBİTAK 1507/1501/1601 'sermaye şirketi olmak' şartı "
    "aradığı için şahıs işletmesi o programlara (3,5 milyon TL'ye kadar %75 "
    "hibe) hiç başvuramaz. ORTAKLIK PAYI ŞARTI: girişimcinin kendi "
    "işletmesindeki payı en az %50 olmalıdır - ortaklara pay dağıtırken bu "
    "sınır aşılmamalıdır. DOĞRULANAMAYAN BİR ŞART: bazı ikincil kaynaklar "
    "'son 3 yılda başka bir işletme sahibi/ortağı olmama' şartından "
    "bahsediyor ancak bu KOSGEB'in resmi sayfasında teyit edilemedi - "
    "444 1 567'den sorulmalıdır."
)


def main():
    db = SessionLocal()
    try:
        t = db.query(Tesvik).filter(Tesvik.baslik == BASLIK, Tesvik.kurum == "KOSGEB").first()
        if t is None:
            print(f"UYARI: '{BASLIK}' bulunamadı.")
            return

        mevcut = list(t.basvuru_sartlari or [])
        for s in EK_SARTLAR:
            if s not in mevcut:
                mevcut.append(s)
        t.basvuru_sartlari = mevcut

        if "ŞİRKET TÜRÜ FARKI" not in (t.durum_notu or ""):
            t.durum_notu = (t.durum_notu or "") + EK_NOT

        db.commit()
        print(f"güncellendi: {BASLIK}")
        for s in t.basvuru_sartlari:
            print("  -", s[:95])
    finally:
        db.close()


if __name__ == "__main__":
    main()
