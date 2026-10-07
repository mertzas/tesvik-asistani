"""Denetim 2 / Aşama A (Tur 1) veri düzeltmeleri — canlı kaynak karşılaştırmasına dayanır.

Kaynak tablosu: docs/olcum/2026-10-07-denetim2/A_fark_tablosu.json (kayıt id | alan | bizde |
kaynakta | URL | erişim tarihi). Her değişiklik durum_notu'na "Denetim2 2026-10-07: ... (URL)"
olarak işlenir; idempotent (aynı not varsa tekrar yazılmaz).

Kullanım:
    python scripts/fix_veri_2026_10_07_denetim2.py --dry-run   (varsayılan; DB'ye yazmaz)
    python scripts/fix_veri_2026_10_07_denetim2.py --uygula
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik  # noqa: E402

T = "2026-10-07"
NOT = f"Denetim2 {T}"
TUB = "https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/"
TUBU = "https://tubitak.gov.tr/tr/destekler/sanayi/uluslararasi-ortakli-destek-programlari/"
KGF = "https://www.kgf.com.tr/index.php/tr/urunlerimiz/"
KOS = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/"
RG = "https://www.resmigazete.gov.tr/eskiler/"


def _kgf(tutar, yol):
    return dict(aktif_mi=True, tesvil_tutari=tutar, kaynak=KGF + yol, not_="ürün sayfası yayında; limit/vade sayfadan")


# id -> {alan: değer}; "kaynak" ve "not_" durum_notu'na gider.
DEGISIKLIKLER = {
    # --- Bilinen sorunlular
    174: dict(tesvil_tutari="BiGG Fonu hisse karşılığı yatırım: 1.350.000 TL (2026); +600.000 TL GCİP ek yatırım imkânı (2025'ten itibaren)",
              tutari_max=1350000.0, tutari_min=None, tutar_niteligi="hisse karşılığı yatırım",
              kaynak_url="https://bigg.tubitak.gov.tr/", kaynak="https://bigg.tubitak.gov.tr/",
              not_="tubitak.gov.tr/1512 sayfası 'Erişim engellendi' (Chrome dahil); resmî BiGG Portalı kaynak alındı; "
                   "eski 150.000 TL ifadesi geçersiz (2022'de 900.000 TL, 2026'da 1.350.000 TL)"),
    34: dict(tesvil_tutari="Hibe: ilk 5 proje %75 (en fazla 20 M TL/proje), 6. ve sonrası %60 (en fazla 20 M TL); süre ≤36 ay",
             tutari_max=20000000.0, kaynak=TUB + "1501-tubitak-sanayi-ar-ge-projeleri-destekleme-programi",
             not_="2026 yılı 2. çağrı dokümanı yayında"),
    25: dict(aktif_mi=True,
             tesvil_tutari="KOBİ: Ar-Ge destek oranı %75, en fazla 20 M TL; büyük ölçekli: %50, en fazla 40 M TL (Teknoloji Odaklı Sanayi Hamlesi)",
             tutari_max=40000000.0, basvuru_suresi="Çağrı dönemli: duyurular www.hamle.gov.tr; ön başvuru + kesin başvuru aşamaları",
             kaynak=TUB + "1511-tubitak-oncelikli-alanlar-arastirma-teknoloji-gelistirme-ve-yenilik-p-d-pteknoloji-odakli-sanayi-hamlesi-programi",
             not_="sayfa canlı; yalnızca Türkiye'de yerleşik sermaye şirketleri"),
    48: dict(aktif_mi=True, kaynak_url=TUBU + "1709-eureka-eurostars",
             tesvil_tutari="Eurostars-3 Ulusal Çağrı 2026/2: ulusal çağrı bütçesi 4.000.000 Avro; proje ≤36 ay (destek oranı çağrı duyurusunda)",
             basvuru_suresi="Çağrı dönemli (2026/2 çağrısı açık); başvuru eteydeb.tubitak.gov.tr",
             kaynak=TUBU + "1709-eureka-eurostars", not_="eski adres 404; yeni adres 'uluslararasi-ortakli-destek-programlari' altında"),
    46: dict(aktif_mi=True, kaynak_url=TUBU + "1719-eureka-network-cagrilari",
             basvuru_suresi="Açık ulusal çağrılar: Uygulamalı Kuantum Teknolojileri, Hafifletme Teknolojileri, Afetlerde Dirençlilik (takvim çağrı duyurularında)",
             kaynak=TUBU + "1719-eureka-network-cagrilari", not_="eski adres 404; yeni adres bulundu"),
    70: dict(aktif_mi=False, kaynak=TUB + "1831-yesil-inovasyon-teknoloji-mentorluk-cagrisi", not_="son çağrılar 2023-01 ve 2024-02; 2025/2026 çağrısı yok"),
    36: dict(aktif_mi=False, kaynak=TUB + "1701-ar-ge-proje-degerlendirme-ve-izleme-cagrisi", not_="çağrı 2 Eylül–31 Ekim 2024; kapandı"),
    23: dict(aktif_mi=False, kaynak=TUB + "1514-girisim-sermayesi-destekleme-programi-tech-investr",
             not_="Tech-InvesTR: TTO/TGB/AA fon katılım payının %50'si TÜBİTAK hibesi; son çağrı metni 2018; işletmelere doğrudan destek değil"),
    30: dict(tesvil_tutari="SAYEM platform bütçe üst limiti: KOBİ 28 M TL, büyük ölçekli 70 M TL (yürütücü Ar-Ge harcaması eşikleri: 2025 ≥46,7 M TL)",
             tutari_max=70000000.0, kaynak=TUB + "1833-sayem-yesil-donusum-cagrisi", not_="çağrı tarihi sayfada yok; aktiflik belirsiz"),
    35: dict(kaynak=TUB + "1612-bigg-1asama-uygulayici-kurulus-cagrisi", not_="2026-2028 dönemi BiGG 1. aşama Uygulayıcı Kuruluş çağrısı (hızlandırıcılar için); 1601 2025-1 çağrı metni"),
    # --- KOSGEB
    1: dict(aktif_mi=True,
            tesvil_tutari="İş Kurma: gerçek kişi 10.000 TL / sermaye şirketi 20.000 TL (%100 geri ödemesiz; genç/kadın/engelli/gazi/şehit yakını +10.000 TL); "
                          "İş Geliştirme: 1.500.000 TL'ye kadar (%80 geri ödemeli, +150.000 TL ilave); kredi faiz/kâr payı desteği: 1.000.000 TL kredi, faizin %50'si geri ödemesiz",
            tutari_min=10000.0, tutari_max=30000.0, kaynak=KOS + "1231/girisimci-destek-programi", not_="sayfa canlı; tutarlar 'Destek Unsurları' tablosundan"),
    2: dict(aktif_mi=True, tesvil_tutari="Kredi 500.000 – 5.000.000 TL; vade 24 ay (ilk 12 ay ödemesiz); GO Dijital Cüzdan'a blokeli, banka kesin teminat mektubu",
            tutari_min=500000.0, tutari_max=5000000.0, kaynak=KOS + "9414/yapay-zek-kredi-programi", not_="sayfa canlı"),
    3: dict(aktif_mi=True, kaynak=KOS + "9144/kobi-dijital-donusum-destek-programi", not_="1–20 M TL, 36 ay, C-İmalat teyit edildi"),
    5: dict(aktif_mi=True, tesvil_tutari="%100 geri ödemesiz; program üst limiti toplam 700.000 TL (hizmet başına 20.000–150.000 TL; kalemler 40.000/200.000/40.000/450.000 TL)",
            tutari_max=700000.0, kaynak=KOS + "9165/yonde-yonderlik-ve-degerlendirme-destek-programi", not_="sayfa canlı"),
    8: dict(aktif_mi=True, kaynak=KOS + "9200/kapasite-gelistirme-destek-programi", not_="1–20 M TL, ≤36 ay, tek finansal kuruluş teyit edildi"),
    # --- KGF (22)
    81: _kgf("Kredi üst limiti 20 Milyon TL; azami 36 ay vade", "kosgeb-destekli-kefaletler/kapasite-gelistirme-destek-paketi"),
    86: _kgf("Azami kredi 3.000.000 TL, azami kefalet 2.400.000 TL (TOBB Nefes 2026)", "ozkaynak-kefaletlerimiz/banka-kredileri/tobb-nefes-kredisi-2026-destek-programi"),
    87: _kgf("Kefalet üst limiti 400 bin TL; kefalet başvuru ücreti 7.500 TL; yalnızca TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/halk-bankasi-sahis-isletmeleri-destek-kredisi-projesi"),
    89: _kgf("Azami kefalet 1.200.000 TL / kredi 6.000.000 TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/halkbank-mesleki-egitim-kredisi-destek-paketi"),
    93: _kgf("İşletme kefalet üst limiti 800 bin TL; azami 36 ay (6 ay ödemesiz dahil)", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/vakifbank-hukuk-burosu-destek-paketi"),
    107: _kgf("Kredi üst limiti 50 Milyon TL; azami 36 ay", "kosgeb-destekli-kefaletler/kuresel-rekabetcilik-destek-paketi"),
    112: _kgf("Kefalet: işletme 800 bin / yatırım 2,4 Milyon TL; kredi: işletme 1 Milyon / yatırım 3 Milyon TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/halkbank-genc-isi-kredisi-projesi"),
    116: _kgf("Kefalet üst limitleri kooperatif ölçeğine göre 640 M / 80 M / 20 M TL; 12 ay ödemesiz, 24 ay vade", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-kooperatif-destek-paketi"),
    122: _kgf("İşletme kredisi: kefalet azami 800 bin TL, kredi 1 Milyon TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/halkbank-ilk-adim-kredisi-projesi"),
    126: _kgf("Kredi asgari 1.520.000 – azami 1.600.000 TL; kefalet başvuru ücreti 5.000 TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/istihdam-taahhutlu-kobi-finansman-destek-programi"),
    133: _kgf("Üst limit 20 Milyon TL", "ozkaynak-kefaletlerimiz/banka-kredileri/savunma-sanayi-i-tedari-kci-destek-programi"),
    137: _kgf("Yararlanıcı/grup başına kefalet azami 5 Milyon TL; işletme kredisi 6–60 ay (ödemesiz ≤1 yıl), yatırım 6–84 ay (ödemesiz ≤2 yıl); işlem ücreti ≥5.000 TL", "ozkaynak-kefaletlerimiz/banka-kredileri/ozkaynak"),
    138: _kgf("800 bin TL; kefalet başvuru ücreti 7.500 TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/halk-bankasi-genciz-kredisi-programi-destek-paketi"),
    142: _kgf("Üst limit 45 Milyon TL; başvuru ücreti 10.000 TL", "kosgeb-destekli-kefaletler/istihdam-koruma-destek-programi"),
    149: _kgf("Üst limit 24 Milyon TL; başvuru ücreti 10.000 TL", "kosgeb-destekli-kefaletler/refinansman-kefalet-programi"),
    152: _kgf("İşletme başına toplam kefalet 1,25 Milyon TL (veya muadili döviz); kefalet oranı %100", "ozkaynak-kefaletlerimiz/dogrudan-krediler/tubitak-transfer-odemeleri"),
    168: _kgf("Azami 40 Milyon TL; %80 kefalet; 6 ay ödemesiz, 24 ay vade; komisyon kredinin %0,1'i (asgari 10 bin TL)", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/ziraat-bankasi-yesil-ihracat-kredisi-destek-paketii"),
    169: _kgf("4 Milyon TL; %80 kefalet; başvuru ücreti 10.000 TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/ziraat-bankasi-kadin-ve-genc-girisimci-destek-paketi"),
    170: _kgf("Kefalet %90; 1.000.000 TL; yıllık %1,5 komisyon; başvuru ücreti 8.500 TL", "kosgeb-destekli-kefaletler/girisimci-destek-programi-kredi-faiz-programi"),
    171: _kgf("4.000.000 / 6.000.000 TL; %80; 36 ay (6 ay ödemesiz); başvuru ücreti KOBİ 10.000 / KOBİ dışı 20.000 TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/ziraat-katilim-bankasi-katilim-finans-destek-paketi"),
    172: _kgf("%80 kefalet; şahıs 2,2 Milyon / tüzel 5 Milyon TL; yıllık %2; başvuru ücreti 10.000 TL", "ozkaynak-kefaletlerimiz/banka-kredileri/dijital-kefalet-destek-programi"),
    173: _kgf("Nakdi 3.000.000 TL (36 ay) / gayri nakdi 6.000.000 TL (48 ay); %80; başvuru ücreti 10.000 TL", "ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/vakifbank-basin-ilan-kurumu-destek-paketi"),
    # --- Tarım
    76: dict(basvuru_suresi="2026 Talimatı: büyükbaş (buzağı/malak) 1. dönem 01/09/2026–01/12/2026, 2. dönem 01/04/2027–15/06/2027; küçükbaş 3 dönem "
                            "(01/09/2026–01/12/2026; 01/04/2027–15/06/2027; 01/11/2027–19/11/2027); başvuru il/ilçe müdürlüğü veya birlik üzerinden (HDS)",
             kaynak_url="https://www.tarimorman.gov.tr/HAYGEM/Duyuru/268/2026-Yili-Buyukbas-Hayvancilik-_buzagi_malak_-Desteklemeleri-Talimati-Yayinlanmistir",
             tesvil_tutari="Birim tutarlar 8760 sayılı CB Kararı (2024-2026 Hayvancılık Desteklemeleri, RG 26/7/2024) ekindedir; sistemde teyit edilemedi (taranmış PDF)",
             kaynak=RG + "2024/08/20240817-11.htm", not_="Uygulama Tebliği 2024/23 ve 2026 talimatları; takvim talimattan"),
    78: dict(baslik="Kırsal Kalkınma Yatırım Programı (KKYP) – Tarımsal İşleme/Depolama ve Makine Parkı Hibeleri",
             ozet="Tarım ve Orman Bakanlığı (TRGM) Kırsal Kalkınma Yatırım Programı: tarımsal ürünlerin işlenmesi, paketlenmesi ve depolanması, "
                  "kanatlı/büyükbaş/küçükbaş yetiştiriciliği, gübre işleme, tarımsal amaçlı örgütler için ortak makine parkı vb. yatırım konularına "
                  "hibe. Bireysel traktör/makine alımı bu programda desteklenmez.",
             tesvil_tutari="Hibe: KDV dâhil hibeye esas proje tutarının %50–%70'i (EK-2'ye göre); hibeye esas tutar 100.000 – 30.000.000 TL (aile işletmesi ≤8.000.000 TL)",
             tutari_min=100000.0, tutari_max=30000000.0,
             basvuru_suresi="2026 uygulama yılı; başvuru hibe.tarimorman.gov.tr (Tebliğ 2026/9, RG 3/4/2026)",
             kaynak_url=RG + "2026/04/20260403-9.htm",
             basvuru_sartlari=["Gerçek/tüzel kişiler ve tarımsal amaçlı örgütler; kadın ve genç girişimciler (18-40 yaş) öncelikli (MADDE 2, 14)",
                               "Hibeye esas proje tutarı 100.000 TL alt, 30.000.000 TL üst limit; aile işletmesi 8.000.000 TL (MADDE 14)",
                               "Hibe oranı KDV dâhil hibeye esas tutarın %50–%70'i, kalan kısım faydalanıcı öz kaynağı (MADDE 14/4)",
                               "Yatırım konuları Tebliğ'deki başlıklarla sınırlı (işleme/paketleme/depolama, hayvancılık, gübre işleme, ortak makine parkı vb.)",
                               "Yasal izin ve ruhsatlar alınmış/alınacak olmalı; kiralık mülkte en az 7 yıl kira süresi"],
             kaynak=RG + "2026/04/20260403-9.htm", not_="eski kayıt BUGEM ana sayfasına bağlıydı ve kaynaksız '₺50.000-₺500.000 makine hibesi' diyordu; kapsam KKYP Tebliği 2026/9'a göre yeniden yazıldı (10802 sayılı CB Kararı)"),
    80: dict(baslik="Tasarruflu Tarımsal Sulama Sistemleri (TSS) Hibe Desteği",
             ozet="Kırsal Kalkınma Yatırım Programı kapsamında tarla içi damla, yağmurlama, mikro yağmurlama, yüzey altı damla, center pivot/lineer/tamburlu ve güneş enerjili sulama sistemlerine hibe (81 il).",
             tesvil_tutari="Hibe oranı %50 (damla, yağmurlama), %60 (mikro yağmurlama; center pivot/lineer/tamburlu; güneş enerjili), %70 (yüzey altı damla); hibeye esas proje tutarı en fazla 10.000.000 TL",
             tutari_max=10000000.0, tutari_min=None,
             basvuru_suresi="Uygulama yılı 1/1/2026–31/12/2026; başvuru tss.tarimorman.gov.tr (Tebliğ 2026/10, RG 3/4/2026)",
             kaynak_url=RG + "2026/04/20260403-10.htm",
             basvuru_sartlari=["Gerçek/tüzel kişiler; kadın ve genç girişimciler ile birinci derece tarımsal örgütler öncelikli; bütçenin en az %20'si kadın/genç girişimcilere (MADDE 11)",
                               "Hibe oranı sulama sistemi türüne göre %50/%60/%70 (MADDE 11/4)",
                               "Hibeye esas proje tutarı 10.000.000 TL'yi geçemez; aşan kısım ayni katkı (MADDE 11/6)",
                               "Makine-ekipman alımı hibe sözleşmesinden sonra ve 75 gün içinde teslim (MADDE 9)"],
             kaynak=RG + "2026/04/20260403-10.htm", not_="eski kayıt TRGM ana sayfasına bağlıydı ve kaynaksız '₺100.000-₺1.000.000' diyordu; TSS Tebliği 2026/10'a göre yeniden yazıldı"),
    # --- Ticaret
    163: dict(tesvil_tutari="5973 sayılı İhracat Destekleri Hakkında Karar kapsamında; e-ticaret sitesi üyeliği oranı/limiti Bakanlık Genelgesi ve yıllık 'Destek Üst Limitleri' belgesinden teyit edilmeli (15.102 TL ifadesi 2022 yılına aitti)",
              tutari_max=None, kaynak="https://ticaret.gov.tr/destekler/ihracat-destekleri/pazara-giriste-dijital-faaliyetlerin-desteklenmesi",
              not_="2573 sayılı Karar MÜLGA (18.08.2022); yürürlükte 5973 sayılı Karar"),
    # --- Akademik TÜBİTAK aktiflik (sayfa sinyali)
    12: dict(aktif_mi=False, not_="son çağrı 2025 (13. çağrı); 2026 çağrısı yok"), 13: dict(aktif_mi=True, not_="4007 çağrı metni 2026"),
    16: dict(aktif_mi=True, not_="sürekli program; usul ve esaslar 06.05.2026"), 26: dict(aktif_mi=True, not_="dönemsel çalıştay çağrıları"),
    28: dict(aktif_mi=False, not_="çağrı 4 Kasım 2025'te kapandı"), 42: dict(aktif_mi=True, not_="4001-A kitapçığı 30 Haziran 2026"),
    50: dict(aktif_mi=True, not_="dönemsel çalıştay çağrıları"), 51: dict(aktif_mi=True, not_="burs üst sınırları 1 Ocak 2026'dan geçerli"),
    52: dict(aktif_mi=True, not_="2026 yılı 13. dönem"), 54: dict(aktif_mi=True, not_="Kamu Yapay Zekâ Ekosistemi 2026 çağrısı"),
    56: dict(aktif_mi=False, not_="son başvuru 5 Kasım 2024"), 61: dict(aktif_mi=False, not_="son başvuru 5 Eylül 2024"),
    62: dict(aktif_mi=False, not_="2026 başvurusu 17 Nisan 2026'da kapandı"), 63: dict(aktif_mi=False, not_="2025 yılı çağrısı"),
    67: dict(aktif_mi=True, tesvil_tutari="2026/1 dönemi proje destek üst limiti 3.000.000 TL (burs dahil, PTİ ve kurum hissesi hariç)", tutari_max=3000000.0, not_="2026/1"),
    74: dict(aktif_mi=True, not_="yeni dönem çağrısı 24.09.2026'da uzatıldı"),
}

ALANLAR = ("aktif_mi", "tesvil_tutari", "tutari_min", "tutari_max", "basvuru_suresi",
           "kaynak_url", "baslik", "ozet", "basvuru_sartlari")
# tutar_niteligi sütun değil, uygunluk_kriterleri JSON'unda tutulur (bkz. fix_veri_butunlugu_2026_10).


def uygula(db, dry_run: bool) -> int:
    degisen = 0
    for tid, d in DEGISIKLIKLER.items():
        t = db.get(Tesvik, tid)
        if t is None:
            print(f"!! {tid}: kayıt yok, atlandı")
            continue
        kaynak = d.get("kaynak") or (t.kaynak_url if "kaynak_url" not in d else d["kaynak_url"])
        not_ = f"{NOT}: {d.get('not_', 'canlı kaynakla karşılaştırıldı')} ({kaynak})"
        if t.durum_notu and NOT in t.durum_notu:
            continue  # idempotent: bu kayıt zaten işlendi
        farklar = []
        for alan in ALANLAR:
            if alan in d and getattr(t, alan) != d[alan]:
                farklar.append(f"{alan}: {str(getattr(t, alan))[:60]!r} -> {str(d[alan])[:60]!r}")
                if not dry_run:
                    setattr(t, alan, d[alan])
        if "tutar_niteligi" in d:
            uk = dict(t.uygunluk_kriterleri or {})
            if uk.get("tutar_niteligi") != d["tutar_niteligi"]:
                farklar.append(f"uygunluk_kriterleri.tutar_niteligi: {uk.get('tutar_niteligi')!r} -> {d['tutar_niteligi']!r}")
                if not dry_run:
                    uk["tutar_niteligi"] = d["tutar_niteligi"]
                    t.uygunluk_kriterleri = uk
        if not dry_run:
            t.durum_notu = (t.durum_notu + " | " if t.durum_notu else "") + not_
        degisen += 1
        print(f"[{tid}] {t.baslik[:50]}\n    " + ("\n    ".join(farklar) if farklar else "(yalnızca durum_notu)") + f"\n    not: {not_[:120]}")
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
