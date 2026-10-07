"""Denetim 2 / Aşama C (Tur 3) kayıt temizliği — danışman yanıt ölçümünde görünen çelişkili/eski metinler.

Kaynaklar (hepsi 2026-10-07'de Chrome ile salt okunur okundu):
  - 48  : https://tubitak.gov.tr/.../1709-eureka-eurostars (sayfa artık "2026/2" çağrısını gösteriyor)
  - 2   : https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9414/yapay-zek-kredi-programi (SSS bölümü)
  - 7   : https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9224/istihdami-koruma-destek-programi (2026-2 metni)
  - 163 / 174: Aşama A bulguları (A_fark_tablosu.json); 163 için 5973 Genelge limiti bulunamadı, eski 15.102 TL ifadesi
    güncel sayılmaz olarak işaretlenir (yeni rakam UYDURULMAZ).

Idempotent: durum_notu'nda "Denetim2-T3" varsa kayıt atlanır. Metin değişimlerinde eski ifade bulunamazsa hata verir.

    python scripts/fix_veri_2026_10_07_denetim2_tur3.py --dry-run     (varsayılan; DB'ye yazmaz)
    python scripts/fix_veri_2026_10_07_denetim2_tur3.py --uygula
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik  # noqa: E402

NOT = "Denetim2-T3 2026-10-07"
SET_ALANLARI = ("ozet", "detay", "tesvil_tutari", "tutari_hesaplama_formulu", "basvuru_suresi",
                "basvuru_yeri", "basvuru_sartlari")

KOS7 = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9224/istihdami-koruma-destek-programi"
KOS2 = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9414/yapay-zek-kredi-programi"
TUB48 = "https://tubitak.gov.tr/tr/destekler/sanayi/uluslararasi-ortakli-destek-programlari/1709-eureka-eurostars"

DEGISIKLIKLER = {
    # 163 — Pazara Girişte Dijital Faaliyetler: eski 15.102 TL ifadesi çelişiyordu
    163: dict(
        kaynak="https://ticaret.gov.tr/destekler/ihracat-destekleri/pazara-giriste-dijital-faaliyetlerin-desteklenmesi",
        not_="15.102 TL 2022 yılı değeri olarak işaretlendi; 5973 Genelge limiti sayfada bulunamadı, güncel TL limiti teyit edilmeli",
        degistir={"detay": [(
            "yıllık 15.102 TL'ye kadar desteklenir (dekont tarihine göre güncellenen bir üst limittir - bu rakam ilk kez 2026-07-12'de doğrulanmıştır, güncel değeri Bakanlık'ın ilgili sayfasından teyit edin)",
            "yıllık bir üst limite kadar desteklenir (limit, 5973 sayılı Karar kapsamında Bakanlık Genelgesi ve yıllık 'Destek Üst Limitleri' belgesinde belirlenir; eski 15.102 TL rakamı 2022 yılına aittir, güncel kabul edilmemelidir)")]},
        set=dict(tutari_hesaplama_formulu="E-ticaret sitesi bireysel üyelik giderinin %60'ı (kurum sayfası, 2026-07-12); yıllık TL üst limiti için 5973 sayılı Karar Genelgesi / 'Destek Üst Limitleri' belgesine bakın (15.102 TL 2022 yılı değeridir, güncel sayılmaz)"),
    ),
    # 174 — BiGG: eski 150.000 TL ve "teyit edilemedi" metni
    174: dict(
        kaynak="https://bigg.tubitak.gov.tr/",
        not_="detaydaki eski 150.000 TL ifadesi geçersiz; tutar resmî BiGG portalına göre 1.350.000 TL (2026)",
        degistir={"detay": [(
            "DESTEK TUTARI DOĞRULANMALI: ODTÜ Teknokent'in BiGG sayfası 2026 için 1.350.000 TL (%3 hisse karşılığı yatırım) belirtiyor; çeşitli üniversite TTO sayfaları ise 150.000 TL (110.000 proje + 40.000 sermaye) diyor - bu muhtemelen eski döneme ait. TÜBİTAK'ın kendi sayfası doğrudan çekilemediği için kesin güncel tutar teyit edilememiştir; başvuru öncesi 444 66 90'dan doğrulayın.",
            "DESTEK TUTARI (resmî BiGG portalı https://bigg.tubitak.gov.tr/, erişim 2026-10-07): 2026 için BiGG Fonu hisse karşılığı yatırım 1.350.000 TL; 2022'de 900.000 TL idi; 2025'ten itibaren GCİP kapsamında 600.000 TL ek yatırım imkânı vardır. Üniversite sayfalarındaki 150.000 TL (110.000 proje + 40.000 sermaye) ifadesi eski dönemdir, geçersizdir. TÜBİTAK'ın 1512 program sayfasına erişim engeli olduğundan hisse oranı ve çağrı takvimini portaldan veya 444 66 90'dan doğrulayın.")]},
        set=dict(tutari_hesaplama_formulu="BiGG Fonu hisse karşılığı yatırım: 1.350.000 TL (2026). Hisse oranı kayıtlarda farklı (1512 kaydı %3; 1812 metni: çağrıda ilan edilir, en fazla %5); çağrıdan teyit edin."),
    ),
    # 48 — Eurostars: sayfa artık 2026/2
    48: dict(
        kaynak=TUB48,
        not_="canlı sayfa 2026/2 çağrısını gösteriyor (kayıtta eski 2026/1 vardı); başvuru koşulları ve bütçe sınırları sayfadan eklendi; son başvuru tarihi çağrı duyurusu belgesinde (PDF, indirilmedi)",
        degistir={"detay": [("2026/1", "2026/2")], "ozet": [("2026/1", "2026/2")]},
        set=dict(
            tesvil_tutari="Eurostars-3 Ulusal Çağrı 2026/2: ulusal çağrı bütçesi 4.000.000 Avro; Türk proje ortakları için proje bütçesi ≤600.000 Avro; Türk kuruluşlarının ortaklı başvurusunda toplam ≤850.000 Avro; sermaye şirketi dışı kurumların bütçesi toplamın ≤%50'si ve ≤300.000 Avro; proje ≤36 ay; destek oranı KOBİ %75, büyük %60, kamu/vakıf üniversitesi/araştırma kurumları %100",
            basvuru_suresi="Çağrı dönemli: 1709-EUREKA-EUROSTARS 2026/2 ulusal çağrısı; son başvuru tarihi ve uluslararası takvim çağrı duyurusu belgesinde (PDF); başvuru eteydeb.tubitak.gov.tr (PRODİS)",
            basvuru_yeri="PRODİS (https://eteydeb.tubitak.gov.tr); önce kuruluş bazlı ön kayıt, ulusal ön proje başvurusu, sonra uluslararası değerlendirme",
            basvuru_sartlari=[
                "Sermaye şirketi, yükseköğretim kurumu, kamu araştırma merkezi/enstitüsü, eğitim ve araştırma hastanesi veya 6550 sayılı Kanun kapsamındaki araştırma altyapısı olmak",
                "En az bir Türk ve bir Eurostars üyesi ülkeden ortağın katıldığı uluslararası proje",
                "Sermaye şirketi Yürütücü Kuruluş (Muhatap Kuruluş) olmalı; üniversite, kamu araştırma kurumu, hastane ve araştırma altyapıları tek başına başvuramaz",
                "Her sermaye şirketinde proje konusuyla ilgili en az lisans dereceli en az bir proje personeli bulunmalı",
                "Aynı uluslararası projedeki Türk ortaklar tek bir ulusal ön proje başvurusu yapmalı (ayrı başvurular kabul edilmez)",
            ]),
    ),
    # 2 — Yapay Zekâ Kredisi: menü metni yerine sayfanın SSS içeriği
    2: dict(
        kaynak=KOS2,
        not_="menü kazıması yerine sayfanın SSS içeriği (uygunluk: KOBİ + KOSGEB kaydı + Teknogirişim Rozeti + GO Dijital Cüzdan; faiz/komisyon yok; kesin teminat mektubu)",
        set=dict(
            ozet="Teknoloji ve yenilik odaklı KOBİ'lerin yapay zekâ teknolojilerini iş süreçlerinde kullanmasını, dijital kapasitelerini ve üretim yetkinliklerini geliştirmesini sağlayan faizsiz ve komisyonsuz KOSGEB kredisi. Başvuruda geçerli Teknogirişim Rozeti ve GO Dijital Cüzdan hesabı gerekir.",
            detay=("Yapay Zekâ Kredisi (KOSGEB). Programın amacı: teknoloji ve yenilik odaklı işletmelerin yapay zekâ teknolojilerini iş süreçlerinde etkin şekilde kullanmalarını sağlamak, dijital kapasitelerini ve üretim yetkinliklerini geliştirmek. "
                   "Kimler başvurabilir: Türk Ticaret Kanunu'nda tanımlı gerçek veya tüzel kişi statüsünde KOBİ olan; KOSGEB sisteminde kayıtlı, işletme beyanı güncel ve aktif olan; başvuru tarihi itibarıyla geçerli Teknogirişim Rozeti sahibi olan; GO Dijital Cüzdan hesabı bulunan işletmeler. "
                   "Başvuru: KOSGEB bilgi sistemi (www.kosgeb.gov.tr ve/veya e-Devlet) üzerinden elektronik ortamda; yararlanma koşulları sistem tarafından otomatik kontrol edilir. "
                   "Tutar: işletme başına kredi alt limiti 500.000 TL, üst limiti 5.000.000 TL; Türk Lirası cinsinden. Faiz veya komisyon uygulanmaz. "
                   "Vade: toplam 24 ay; kredi başlangıcından itibaren ilk 12 ay ödemesiz. "
                   "Teminat: kredinin GO Dijital Cüzdan hesabına blokeli aktarılabilmesi için bankadan Kesin Teminat Mektubu zorunludur; tanımlanan kredi limiti getirilen teminat tutarı kadardır (en az 500.000 TL). "
                   "Teminat mektubu şartları: GO Dijital Teknoloji Hizmetleri Anonim Şirketi'ne hitaben alınması; üzerinde 'GO Dijital Yapay Zeka Kredisi' ifadesi; vadesinin süresiz olması veya son geri ödeme tarihinden 6 ay sonrasını kapsaması (mümkün değilse en az 1 yıl süreli); şirketin yazılı muvafakati olmadan risk kapaması ve çıkış yapılmaması ibaresi. "
                   "Kullanım: KOSGEB 'Yapay Zeka Kredisi Hizmet Sağlayıcılar Listesi'ndeki hizmet sağlayıcılardan alınan hizmet giderlerinin GO Dijital Cüzdan üzerinden ödenmesi; işletme faturayı cüzdana yükler, uygunluk incelemesinden sonra bloke çözülür. "
                   f"Kaynak: {KOS2} (erişim 2026-10-07)."),
            basvuru_sartlari=[
                "Türk Ticaret Kanunu'nda tanımlı gerçek veya tüzel kişi statüsünde KOBİ olmak",
                "KOSGEB sisteminde kayıtlı, işletme beyanı güncel ve aktif olmak",
                "Başvuru tarihi itibarıyla geçerli Teknogirişim Rozeti sahibi olmak",
                "GO Dijital Cüzdan hesabına sahip olmak",
                "Bankadan GO Dijital Teknoloji Hizmetleri A.Ş.'ye hitaben Kesin Teminat Mektubu getirmek (limit = teminat tutarı, en az 500.000 TL)",
            ],
            basvuru_yeri="KOSGEB bilgi sistemi (www.kosgeb.gov.tr ve/veya e-Devlet) üzerinden Yapay Zeka Kredi Başvurusu",
            basvuru_suresi="Sayfada dönem/son tarih belirtilmiyor; başvuru KOSGEB bilgi sistemi üzerinden elektronik ortamda, koşullar sistemce otomatik kontrol edilir",
            tesvil_tutari="Kredi 500.000 – 5.000.000 TL; faiz ve komisyon yok; vade 24 ay (ilk 12 ay ödemesiz); GO Dijital Cüzdan'a blokeli, bankadan Kesin Teminat Mektubu zorunlu (limit = teminat tutarı, en az 500.000 TL); geçerli Teknogirişim Rozeti şartı"),
    ),
    # 7 — İstihdamı Koruma: kayıttaki metin 2026-1 dönemine aitti (2025 Kasım-Aralık referansı, Haziran sonu kullanım)
    7: dict(
        kaynak=KOS7,
        not_="kayıt metni 2026-1 dönemine aitti (2025 Kasım-Aralık referansı, 30 Nisan/Haziran sonu); 2026-2 canlı metniyle değiştirildi (referans 2026 Ocak-Haziran, kredi 50/150 Milyon TL, faiz ≤%37, komisyon ≤%1)",
        set=dict(
            ozet="İmalat sanayinde (NACE Kısım C) istihdamın korunması için KOBİ ve büyük işletmelere bankalardan kredi ve finansman desteği (12 puan, geri ödemesiz) sağlayan KOSGEB programı. 2026-2 dönemi başvuruları 1 Eylül – 31 Ekim 2026.",
            detay=("İstihdamı Koruma Destek Programı (KOSGEB). Amaç: imalat sanayi sektörlerinde istihdamın korunması ve artırılması; 5510 sayılı Kanunun 4. maddesinin birinci fıkrasının (a) bendi kapsamında çalışan sigortalılar için işletmelere katkı. "
                   "Başvuru şartları: merkez veya şube, ana veya yan faaliyet NACE kodunun Kısım C – İmalat başlığı altında olması; İşletme Beyanının güncel olması; Türk Ticaret Kanunu'nda tanımlı gerçek veya tüzel kişi statüsünde olmak. Programa KOBİ ve büyük işletmeler başvurabilir. "
                   "2026-2 dönemi için Finansman Desteği kapsamında başvurular alınır; program başvuru tarihleri 1 Eylül – 31 Ekim 2026. "
                   "Finansmana erişim: Kısım C – İmalat NACE kodlu KOBİ veya büyük işletmeler bankalardan kredi kullanabilir. Kullanılabilecek kredi tutarı, işletmenin 2026 yılı Ocak-Haziran dönemine ait muhtasar ve prim hizmet beyannamelerinde, destek kapsamındaki iş yerleri için beyan edilen prime esas kazanç toplamının aylık ortalaması kadar olabilir. "
                   "Kredi üst limiti KOBİ'ler için 50 milyon TL, büyük işletmeler için 150 milyon TL. Krediler azami 6 ay anapara ödemesiz, azami 36 ay vadelidir. Tüm bankalarda sabit faizli/kâr paylı kullandırılır; katılım bankaları hariç diğer bankalarda değişken faizli/kâr paylı da kullanılabilir. "
                   "Sabit faizde banka azami oranı %37, değişken faizde TLREF+1. Tahsis ve kullandırım ücretleri dahil komisyon kredinin %1'ini geçemez. "
                   "Destek unsuru (İstihdamın Korunması): kredi kullanan ve 2026 Ocak-Haziran dönemine ait ortalama aylık prim gün sayısını 2026 Temmuz-Aralık döneminde koruyan KOBİ ve büyük işletmeler finansman desteğinden yararlanır. "
                   "Destek, başvuru tarihi sonrasında kullanılan azami 6 ay anapara ödemesiz ve 36 aya kadar vadeli bir kredi için azami 12 destek puanına karşılık gelen tutarla sınırlıdır (geri ödemesiz). Geri ödemesiz destek tutarları yalnızca vergi dairesi ve SGK prim borçlarının ödenmesinde kullanılabilir. "
                   "Kefalet kuruluşları ve banka listesi için program sayfasına bakın. "
                   f"Kaynak: {KOS7} (erişim 2026-10-07)."),
            tesvil_tutari="2026-2: kredi üst limiti KOBİ 50 Milyon TL, büyük işletme 150 Milyon TL (kredi tutarı 2026 Ocak-Haziran prime esas kazanç aylık ortalamasını geçemez); azami 6 ay ödemesiz, 36 ay vade; banka azami faizi %37 (sabit) / TLREF+1 (değişken); komisyon ≤%1; finansman desteği 12 puan, geri ödemesiz, yalnızca vergi ve SGK prim borçlarına kullanılır",
            basvuru_sartlari=[
                "Merkez veya şube; ana veya yan faaliyet NACE kodunun Kısım C – İmalat başlığı altında yer alması",
                "İşletme Beyanının güncel olması",
                "Türk Ticaret Kanunu'nda tanımlı gerçek veya tüzel kişi statüsünde olması",
                "KOBİ veya büyük işletme olması (ikisi de başvurabilir)",
                "Kredi kullanmak ve 2026 Ocak-Haziran ortalama aylık prim gün sayısını 2026 Temmuz-Aralık döneminde korumak (finansman desteği için)",
            ]),
    ),
}


def _goster(eski, yeni):
    return f"{str(eski)[:70]!r} ({len(str(eski or ''))} kar) -> {str(yeni)[:70]!r} ({len(str(yeni))} kar)"


def uygula(db, dry_run: bool) -> int:
    degisen = 0
    for tid, d in DEGISIKLIKLER.items():
        t = db.get(Tesvik, tid)
        if t is None:
            print(f"!! {tid}: kayıt yok, atlandı")
            continue
        if t.durum_notu and NOT in t.durum_notu:
            print(f"[{tid}] zaten işlenmiş, atlandı")
            continue
        farklar = []
        for alan, cifter in d.get("degistir", {}).items():
            metin = getattr(t, alan) or ""
            for eski, yeni in cifter:
                adet = metin.count(eski)
                if adet == 0:
                    raise SystemExit(f"HATA [{tid}] {alan}: değiştirilecek ifade bulunamadı: {eski[:80]!r}")
                metin = metin.replace(eski, yeni)
                farklar.append(f"{alan}: {adet}x değiştirildi: {eski[:55]!r} -> {yeni[:55]!r}")
            if not dry_run:
                setattr(t, alan, metin)
        for alan, yeni in d.get("set", {}).items():
            assert alan in SET_ALANLARI, alan
            if getattr(t, alan) != yeni:
                farklar.append(f"{alan}: {_goster(getattr(t, alan), yeni)}")
                if not dry_run:
                    setattr(t, alan, yeni)
        not_ = f"{NOT}: {d['not_']} ({d['kaynak']})"
        if not dry_run:
            t.durum_notu = (t.durum_notu + " | " if t.durum_notu else "") + not_
        degisen += 1
        print(f"[{tid}] {t.baslik[:55]}\n    " + "\n    ".join(farklar) + f"\n    not: {not_[:150]}")
    if not dry_run:
        db.commit()
    return degisen


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true", help="DB'ye yaz (verilmezse dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="varsayılan davranış; açıkça belirtmek için")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        n = uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} kayıt")
    finally:
        db.close()
