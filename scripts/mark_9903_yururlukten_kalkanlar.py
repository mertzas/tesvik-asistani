#!/usr/bin/env python3
"""
2012/3305 sayili Karar'a dayanan tesvik kayitlarini "yururlukten kalkti"
olarak isaretler ve 9903 sayili yeni Karar'in programlarini ekler.

NEDEN
-----
9903 sayili "Yatirimlarda Devlet Yardimlari Hakkinda Karar" (Resmi Gazete,
30/05/2025), 2012/3305 sayili Karar'i ve 2018/11201 sayili Cazibe Merkezleri
Karari'ni YURURLUKTEN KALDIRDI. Veritabanindaki su 4 kayit eski karari
anlatiyor ve aktif_mi=None (hic dogrulanmamis) durumda duruyordu:

    Genel Tesvik Uygulamalari
    Bolgesel Tesvik Uygulamalari
    Buyuk Olcekli Yatirimlarin Tesviki
    Stratejik Yatirimlarin Tesviki

Bu, kullaniciyi kaldirilmis bir mevzuata gore yatirim planlamaya yonlendirir.
Kayitlar SILINMIYOR - varliklarindan haberdar olmak degerli - ama aktif_mi
False yapilip durum_notu ile hangi karara gecildigi yaziliyor. app/rag.py
sistem promptu "aktif degil" isaretli kayitlari basvurulabilir gibi sunmuyor.

Yeni sistemin yapisi (Karar 9903):
    Turkiye Yuzyili Kalkinma Hamlesi
        - Teknoloji Hamlesi Programi
        - Yerel Kalkinma Hamlesi Programi
        - Stratejik Hamle Programi
    Sektorel Tesvik Sistemi
        - Oncelikli Yatirimlar Tesvik Sistemi
        - Hedef Yatirimlar Tesvik Sistemi
    Bolgesel Tesvikler

Kullanim:
    python -m scripts.mark_9903_yururlukten_kalkanlar          # rapor (yazmaz)
    python -m scripts.mark_9903_yururlukten_kalkanlar --uygula
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from app.models import SessionLocal, Tesvik  # noqa: E402

RESMI_GAZETE = "https://www.resmigazete.gov.tr/eskiler/2025/05/20250530-2.pdf"
KARAR_URL = ("https://www.yatirimadestek.gov.tr/pdf/assets/upload/dosyalar/"
             "karar-yatirim_tesvik_uygulamalari.pdf")

KALKANLAR = {
    "Genel Teşvik Uygulamaları",
    "Bölgesel Teşvik Uygulamaları",
    "Büyük Ölçekli Yatırımların Teşviki",
    "Stratejik Yatırımların Teşviki",
}

DURUM_NOTU = (
    "⚠️ ARTIK AKTİF DEĞİL. Bu uygulama 2012/3305 sayılı Karar'a dayanıyordu; "
    "söz konusu Karar, 9903 sayılı 'Yatırımlarda Devlet Yardımları Hakkında "
    "Karar' ile (Resmî Gazete, 30/05/2025) yürürlükten kaldırıldı. Yeni sistem "
    "üç başlıkta yürüyor: Türkiye Yüzyılı Kalkınma Hamlesi (Teknoloji / Yerel "
    "Kalkınma / Stratejik Hamle programları), Sektörel Teşvik Sistemi "
    "(Öncelikli ve Hedef Yatırımlar) ve Bölgesel Teşvikler. Yatırım konunuzun "
    "desteklenip desteklenmediği artık NACE Rev.2.1 kodu üzerinden Karar'ın "
    f"EK-3 listesiyle eşleştiriliyor. Karar metni: {KARAR_URL}"
)

# 9903 ile gelen programlar. Destek ORANI/TUTARI yazilmiyor: oranlar bolgeye,
# programa ve yatirim konusuna gore Karar ve tebliglerde ayri ayri belirlenir.
# Somut bir oran uydurmak yerine kullanici Karar metnine yonlendiriliyor.
YENI_PROGRAMLAR = [
    {
        "baslik": "Teknoloji Hamlesi Programı (9903 sayılı Karar)",
        "parca": "teknoloji-hamlesi",
        "ozet": "Türkiye Yüzyılı Kalkınma Hamlesi kapsamında, orta-yüksek ve "
                "yüksek teknoloji sınıfındaki ürünlerin yurt içinde üretimine "
                "yönelik yatırımlar için teşvik programı.",
        "detay": "Destek unsurları: gümrük vergisi muafiyeti, KDV istisnası, "
                 "vergi indirimi, faiz/kâr payı desteği, makine desteği, "
                 "yatırım yeri tahsisi. Teknoloji sınıflandırması Karar'ın "
                 "EK-1 listesinde NACE Rev.2.1 kodlarıyla tanımlanır "
                 "(yüksek teknoloji: 21, 26, 30.3; orta-yüksek teknoloji: "
                 "20, 25.3, 27, 28, 29, 30 (30.1 ve 30.3 hariç), 32.5). "
                 "Destek oranları bölge ve programa göre değişir; güncel oran "
                 "ve süreler için Karar metnine ve ilgili tebliğlere bakın.",
        "hedef_kitle": "Orta-yüksek/yüksek teknoloji alanında yatırım yapacak firmalar",
        "kategori": "Yatırım Teşvik",
        "uygunluk_kriterleri": {
            "sektorler": ["imalat", "arge", "genel"],
            "sektor_gerekcesi": "Karar EK-1 teknoloji siniflandirmasi imalat "
                                "(NACE 20-32) kodlarina dayanir.",
        },
    },
    {
        "baslik": "Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar)",
        "parca": "yerel-kalkinma-hamlesi",
        "ozet": "Türkiye Yüzyılı Kalkınma Hamlesi kapsamında, illerin kendi "
                "potansiyeline dayalı yatırımları desteklemeye yönelik program.",
        "detay": "Destek unsurları: gümrük vergisi muafiyeti, KDV istisnası, "
                 "vergi indirimi, faiz/kâr payı desteği, makine desteği, "
                 "yatırım yeri tahsisi. Desteklenen yatırım konuları Karar'ın "
                 "EK-3 listesinde NACE Rev.2.1 kodlarıyla ve konu bazlı "
                 "şartlarla (asgari kapasite, entegrasyon zorunluluğu vb.) "
                 "belirlenir. İl-bölge eşleşmesi EK-2'de yer alır.",
        "hedef_kitle": "Yerel potansiyele dayalı yatırım yapacak firmalar",
        "kategori": "Yatırım Teşvik",
        "uygunluk_kriterleri": {
            "sektorler": ["genel", "tarim", "imalat", "hizmet"],
            "sektor_gerekcesi": "EK-3 listesi tarim, imalat, ulastirma, "
                                "konaklama, bilisim ve saglik bolumlerini kapsar.",
        },
    },
    {
        "baslik": "Stratejik Hamle Programı (9903 sayılı Karar)",
        "parca": "stratejik-hamle",
        "ozet": "İthalat bağımlılığı yüksek ürünlerin yurt içinde üretimini "
                "hedefleyen stratejik nitelikli yatırımlar için program.",
        "detay": "Destek unsurları: gümrük vergisi muafiyeti, KDV istisnası, "
                 "vergi indirimi, faiz/kâr payı desteği, makine desteği, "
                 "yatırım yeri tahsisi. Asgari yatırım tutarı, yerlilik ve "
                 "ithal ikamesi kriterleri Karar ve tebliğlerde belirlenir; "
                 "başvurular proje bazlı değerlendirilir.",
        "hedef_kitle": "Stratejik/ithal ikamesi yatırımı yapacak firmalar",
        "kategori": "Yatırım Teşvik",
        "uygunluk_kriterleri": {
            "sektorler": ["imalat", "genel"],
            "sektor_gerekcesi": "Ithal ikamesi hedefi imalat sanayine yoneliktir.",
        },
    },
    {
        "baslik": "Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)",
        "parca": "hedef-yatirimlar",
        "ozet": "Sektörel Teşvik Sistemi kapsamında, Karar'ın EK-3 listesinde "
                "yer alan yatırım konularına yönelik teşvik belgesi sistemi. "
                "Başvurular NACE kodu üzerinden bu listeyle eşleştirilir.",
        "detay": "Projenin EK-3'teki yatırım konularına ve şartlarına uygun "
                 "olması gerekir. Örnek şartlar: sera yatırımlarında asgari "
                 "20 dekar (1-2. bölge), 15 dekar (3. bölge), 10 dekar "
                 "(4-5. bölge), 5 dekar (6. bölge); sütü sağılan büyükbaş "
                 "hayvan yetiştiriciliğinde asgari 500 adet/dönem "
                 "(1-3. bölge), 300 (4-5. bölge), 150 (6. bölge). Çağrı "
                 "merkezi yatırımları yalnızca 6. bölgede desteklenir. "
                 "Tam liste ve şartlar için Karar'ın EK-3 bölümüne bakın.",
        "hedef_kitle": "EK-3 listesindeki yatırım konularında yatırım yapacaklar",
        "kategori": "Yatırım Teşvik",
        "uygunluk_kriterleri": {
            "sektorler": ["genel", "tarim", "imalat", "hizmet"],
            "sektor_gerekcesi": "EK-3, Karar'in A/B/C/D/H/I/K/N/O/Q/R "
                                "bolumlerini kapsar.",
        },
    },
    {
        "baslik": "Öncelikli Yatırımlar Teşvik Sistemi (9903 sayılı Karar)",
        "parca": "oncelikli-yatirimlar",
        "ozet": "Sektörel Teşvik Sistemi kapsamında, öncelikli ürün listesinde "
                "yer alan ürünlere yönelik yatırımlar için teşvik sistemi.",
        "detay": "Öncelikli ürün listesi, Bakanlık tarafından dış ticaret "
                 "verileri esas alınarak belirlenir. Destek unsurları ve "
                 "oranlar Karar ve tebliğlerde tanımlanır.",
        "hedef_kitle": "Öncelikli ürün listesindeki alanlarda yatırım yapacaklar",
        "kategori": "Yatırım Teşvik",
        "uygunluk_kriterleri": {
            "sektorler": ["imalat", "genel"],
            "sektor_gerekcesi": "Oncelikli urun listesi dis ticaret verilerine "
                                "dayali olarak imalat sanayine odaklidir.",
        },
    },
]

YENI_DURUM_NOTU = (
    "9903 sayılı Karar (R.G. 30/05/2025) ile yürürlükte. Destek oranları "
    "bölge ve programa göre değişir; güncel oran/süre için Karar metnini ve "
    "tebliğleri esas alın."
)
BASVURU_YERI = ("Sanayi ve Teknoloji Bakanlığı Teşvik Uygulama ve Yabancı "
                "Sermaye Genel Müdürlüğü (E-TUYS)")


def calistir(uygula: bool) -> int:
    db = SessionLocal()
    try:
        simdi = datetime.now(timezone.utc)
        etiket = "yazilacak" if uygula else "RAPOR"

        print("== YURURLUKTEN KALKAN KAYITLAR ==")
        degisen = 0
        for t in db.query(Tesvik).all():
            if t.baslik not in KALKANLAR:
                continue
            print(f"  [{etiket}] {t.baslik}")
            print(f"      onceki: aktif_mi={t.aktif_mi}, "
                  f"durum_notu={(t.durum_notu or '-')[:40]}")
            if uygula:
                t.aktif_mi = False
                t.durum_notu = DURUM_NOTU
                # kaynak_url'e DOKUNULMUYOR: kolonda UNIQUE kisiti var
                # (scraper'larin tekillestirme anahtari) ve dort kayit ayni
                # Resmi Gazete adresini paylasamaz - denenince tum islem
                # IntegrityError ile geri aliniyordu. Adres zaten durum_notu
                # metninin icinde kullaniciya gosteriliyor.
                t.guncelleme_tarihi = simdi
            degisen += 1

        print("\n== 9903 PROGRAMLARI ==")
        eklenen = 0
        for p in YENI_PROGRAMLAR:
            if db.query(Tesvik).filter(Tesvik.baslik == p["baslik"]).first():
                print(f"  [zaten var] {p['baslik']}")
                continue
            print(f"  [{'eklenecek' if uygula else 'RAPOR'}] {p['baslik']}")
            if uygula:
                db.add(Tesvik(
                    kurum="Sanayi ve Teknoloji Bakanlığı",
                    baslik=p["baslik"], ozet=p["ozet"], detay=p["detay"],
                    hedef_kitle=p["hedef_kitle"], kategori=p["kategori"],
                    # Her kayda ayri adres: kaynak_url UNIQUE. Bes program
                    # ayni Karar metninde tanimli oldugu icin adres, program
                    # adini tasiyan bir parca (fragment) ile tekillestiriliyor;
                    # temel adres birebir ayni resmi belgeye gidiyor.
                    kaynak_url=f"{KARAR_URL}#{p['parca']}",
                    uygunluk_kriterleri=p["uygunluk_kriterleri"],
                    basvuru_yeri=BASVURU_YERI,
                    aktif_mi=True, durum_notu=YENI_DURUM_NOTU,
                    guncelleme_tarihi=simdi,
                ))
            eklenen += 1

        if uygula:
            db.commit()
            print(f"\nYAZILDI: {degisen} kayit isaretlendi, {eklenen} kayit eklendi.")
        else:
            print(f"\nRAPOR: {degisen} kayit isaretlenecek, {eklenen} kayit eklenecek.")
            print("Uygulamak icin --uygula ile tekrar calistirin.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="9903 gecisi.")
    a.add_argument("--uygula", action="store_true",
                   help="Degisiklikleri veritabanina yaz (varsayilan: sadece rapor).")
    sys.exit(calistir(a.parse_args().uygula))
