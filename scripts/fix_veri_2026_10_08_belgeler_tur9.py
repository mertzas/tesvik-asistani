"""Denetim 2 / Aşama I (Tur 9) — en sık eşleşen programlarda başvuru belgeleri, başvuru yeri ve eksik şartlar.

Seçim: 12 persona × ilk 12 eşleşmede görünen 49 aktif programdan belge/yer/şart alanı boş olan 34'ü
(docs/olcum/2026-10-07-denetim2/I_aday_listesi.json). Kaynaklar 2026-10-08'de Chrome ile salt okunur okundu;
alıntılar ve gerekçeler: I_tarama.json ve I_RAPOR.md.

Kurallar
  - Yalnızca BOŞ alan doldurulur; dolu alan değişmez (önceki doğrulamaların üzerine yazılmaz).
  - Yalnızca kaynak sayfada görülen bilgi yazılır. Kaynakta olmayan alan boş bırakılır (KOSGEB 5/7 başvuru yeri,
    Tarım 77/79 belgeleri, 9903 programına özel belge listesi — uygulama tebliği metni taranmadı).
  - Değerlendirme/izleme/ödeme aşaması formları listeye alınmaz; yalnızca başvuruda kullanıcıdan istenenler.
  - KGF ayrı belge listesi yayımlamaz (Portföy Garanti Sistemi: KOBİ bankaya kredi başvurusu yapar, banka kefalet
    talebini KGF'ye iletir — https://www.kgf.com.tr/index.php/tr/kefalet-isleyisi/surec). Bu yüzden KGF kayıtlarında
    belge = "bankanın kredi başvurusu belgeleri" + sayfadaki pakete özgü şart belgeleri ve kefalet başvuru ücreti.

Idempotent: durum_notu'nda "Denetim2-T9" varsa kayıt atlanır.

    python scripts/fix_veri_2026_10_08_belgeler_tur9.py --dry-run   (varsayılan)
    python scripts/fix_veri_2026_10_08_belgeler_tur9.py --uygula
    python scripts/fix_veri_2026_10_08_belgeler_tur9.py --self-test
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Denetim2-T9 2026-10-08"
KGF_SUREC = "https://www.kgf.com.tr/index.php/tr/kefalet-isleyisi/surec"
ETUYS = "https://www.sanayi.gov.tr/destek-ve-tesvikler/yatirim-tesvik-sistemleri"
KGF_BANKA_BELGESI = ("Kredi veren bankanın kredi başvurusu için istediği belgeler (KGF ayrı belge listesi yayımlamaz; "
                     "kefalet talebini banka KGF'ye iletir)")


def _kgf_yeri(bankalar: str) -> str:
    return f"Kredi veren bankalar: {bankalar} (KOBİ bankaya kredi başvurusu yapar, banka kefalet talebini KGF'ye iletir)"


def _ucret(metin: str) -> str:
    return f"Kefalet başvuru ücreti: {metin}"


ETUYS_BELGELERI = [
    "E-TUYS yetkilendirmesi için Dilekçe, Taahhütname ve Kullanıcı Yetkilendirme Formu (Bakanlığın KEP adresine "
    "Kayıtlı Elektronik Posta ile gönderilir)",
    "Yetkilendirme sonrası yatırım teşvik belgesi başvurusu E-TUYS üzerinden yapılır; istenen bilgi ve belgeler "
    "E-TUYS kılavuzlarında tanımlıdır",
]

# id -> {alan: değer, "kaynak": url}. Alanlar: gerekli_belgeler (liste), basvuru_yeri (metin), basvuru_sartlari (liste).
KAYITLAR: dict[int, dict] = {
    # ---- KOSGEB ----
    2: {"kaynak": "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9414/yapay-zek-kredi-programi",
        "gerekli_belgeler": ["Yapay Zekâ Kredisi Başvuru Formu (KOSGEB sistemi / e-Devlet üzerinden elektronik)",
                             "Yapay Zekâ Kredisi Taahhütnamesi", "Yapay Zekâ Kredisi Hizmet Giderleri Tablosu",
                             "Bankadan Kesin Teminat Mektubu (kredinin GO Dijital Cüzdan hesabına blokeli aktarımı için "
                             "zorunlu)"]},
    9: {"kaynak": "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9206/kuresel-rekabetcilik-destek-programi",
        "gerekli_belgeler": ["Proje Başvuru Formu (1. ve 2. Bölüm)", "Küresel Rekabetçilik Destek Programı Taahhütnamesi",
                             "Başvuru Kontrol Formu",
                             "Başvuru Kılavuzu ve dönemin proje teklif çağrısına göre hazırlık"],
        "basvuru_yeri": "KOSGEB KOBİ Bilgi Sistemi (KBS) üzerinden, dönemsel proje teklif çağrısına göre"},
    7: {"kaynak": "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9224/istihdami-koruma-destek-programi",
        "gerekli_belgeler": ["İstihdamı Koruma Destek Programı Başvuru Formu",
                             "İstihdamı Koruma Destek Programı Taahhütnamesi", "Destek Hesaplama Tablosu"]},
    5: {"kaynak": "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9165/yonde-yonderlik-ve-degerlendirme-destek-programi",
        "gerekli_belgeler": ["YÖNDE Başvuru Formu", "YÖNDE Taahhütnamesi",
                             "Başvuru ve Ödeme Belgeleri Tablosu'nda sayılan belgeler"]},
    # ---- TÜBİTAK (başvurular PRODİS: eteydeb.tubitak.gov.tr) ----
    75: {"kaynak": "https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/1505-universite-sanayi-isbirligi-destek-programi",
         "gerekli_belgeler": ["Proje Öneri Bilgileri Formu (AGY105; PRODİS'te doldurulur)",
                              "Ar-Ge Yardımı İstek Formu (AGY305) ve hazırlama kılavuzu",
                              "Bursiyer Bilgi Formu (bursiyer varsa)", "PTİ Bilgi Formu"],
         "basvuru_yeri": "Elektronik olarak PRODİS (https://eteydeb.tubitak.gov.tr); başvurular yıl boyunca açık"},
    39: {"kaynak": "https://www.tubitak.gov.tr/tr/destekler/sanayi/uluslararasi-ortakli-destek-programlari/1509-tubitak-uluslararasi-sanayi-ar-ge-projeleri-destekleme-programi",
         "gerekli_belgeler": ["Proje Öneri Bilgileri (AGY103; PRODİS'te doldurulur, sayfadaki form yalnızca bilgi amaçlı)",
                              "Ar-Ge Yardımı İstek Formu hazırlama kılavuzu"],
         "basvuru_yeri": "Yalnızca elektronik ortamda PRODİS (https://eteydeb.tubitak.gov.tr); başvurular yıl boyunca açık"},
    49: {"kaynak": "https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/1812-yatirim-tabanli-girisimcilik-destek-programi-bigg-yatirim",
         "gerekli_belgeler": ["AGY112 İş Planı", "1812 Tahmini Maliyet Formları",
                              "Eş Yatırım Taahhütnamesi ve Eş Yatırım Bilgi Formu (eş yatırım varsa)",
                              "ARDEB Muvafakatname Formu (gerekiyorsa)"],
         "basvuru_yeri": ("PRODİS (https://eteydeb.tubitak.gov.tr) üzerinden, uygulayıcı kuruluşların açtığı "
                          "hızlandırma programı çağrılarına")},
    25: {"kaynak": "https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/1511-tubitak-oncelikli-alanlar-arastirma-teknoloji-gelistirme-ve-yenilik-p-d-pteknoloji-odakli-sanayi-hamlesi-programi",
         "gerekli_belgeler": ["Proje Öneri Bilgileri Formu (PRODİS'te; Proje Öneri Başvuru Formu Hazırlama Kılavuzu)",
                              "Ar-Ge Yardımı İstek Formu (AGY311) ve hazırlama kılavuzu"],
         "basvuru_yeri": "PRODİS (https://eteydeb.tubitak.gov.tr), çağrı dönemlerinde"},
    55: {"kaynak": "https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/1707-siparise-dayali-ar-ge-projeleri-icin-kobi-destekleme-cagrisi",
         "gerekli_belgeler": ["Proje Öneri Formu (PRODİS'te; sayfada örneği var)",
                              "Müşteri Kuruluş ile Tedarikçi Kuruluş arasında imzalı işbirliği (sipariş) sözleşmesi"],
         "basvuru_yeri": "PRODİS (https://eteydeb.tubitak.gov.tr), çağrı dönemlerinde",
         "basvuru_sartlari": ["Müşteri Kuruluş: Ar-Ge'ye dayalı çözüme ihtiyacı olan ve bunun için Tedarikçi Kuruluşla "
                              "işbirliği sözleşmesi imzalayan kuruluş (sektör ve ölçekten bağımsız)"]},
    48: {"kaynak": "https://tubitak.gov.tr/tr/destekler/sanayi/uluslararasi-ortakli-destek-programlari/1709-eureka-eurostars",
         "gerekli_belgeler": ["Ulusal ön proje başvurusu (PRODİS'te, kuruluş bazlı ön kayıttan sonra)",
                              "2. Aşama Proje Öneri Bilgileri (PRODİS'te; sayfadaki form bilgi amaçlı)",
                              "Ar-Ge Yardımı İstek Formu hazırlama kılavuzu", "Bursiyer Bilgi Formu (bursiyer varsa)"]},
    # ---- 9903 yatırım teşvikleri (başvuru yeri zaten E-TUYS) ----
    **{tid: {"kaynak": ETUYS, "gerekli_belgeler": ETUYS_BELGELERI} for tid in (177, 178, 179, 180, 181)},
    # ---- Tarım ----
    76: {"kaynak": "https://www.tarimorman.gov.tr/HAYGEM/Duyuru/268/2026-Yili-Buyukbas-Hayvancilik-_buzagi_malak_-Desteklemeleri-Talimati-Yayinlanmistir",
         "gerekli_belgeler": ["Başvuru dilekçesi (2026 büyükbaş hayvancılık desteklemeleri talimatı ekindeki örneğe göre; "
                              "talimat ve iş takvimi HAYGEM duyurusunda)"]},
    # ---- KGF ----
    172: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/dijital-kefalet-destek-programi",
          "gerekli_belgeler": [KGF_BANKA_BELGESI, _ucret("10.000 TL")],
          "basvuru_yeri": _kgf_yeri("Akbank (krediler dijital kanallardan tahsis yöntemiyle kullandırılır)")},
    87: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/halk-bankasi-sahis-isletmeleri-destek-kredisi-projesi",
         "gerekli_belgeler": [KGF_BANKA_BELGESI, "Esnaf Odası, Ticaret ve Sanayi Odası veya Meslek Odası kaydı",
                              _ucret("7.500 TL")],
         "basvuru_yeri": _kgf_yeri("Halkbank")},
    81: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/kosgeb-destekli-kefaletler/kapasite-gelistirme-destek-paketi",
         "gerekli_belgeler": [KGF_BANKA_BELGESI, "KOSGEB Kapasite Geliştirme Destek Programı kapsamında destek onayı"],
         "basvuru_yeri": _kgf_yeri("Ziraat Bankası, Vakıfbank, Halkbank, Ziraat Katılım")},
    159: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/hazine-destekli-kefaletler/aktif-destek-paketleri-2025/i-hracat-destek-paketi",
          "gerekli_belgeler": [KGF_BANKA_BELGESI, "İhracat taahhüdü (krediler taahhütlü kullandırılır)"],
          "basvuru_yeri": _kgf_yeri("Akbank, Denizbank, Garanti Bankası, Eximbank, Halkbank, İş Bankası, Türk Ekonomi "
                                    "Bankası, QNB Finansbank, Vakıfbank, Yapı Kredi Bankası, Ziraat Bankası")},
    168: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/ziraat-bankasi-yesil-ihracat-kredisi-destek-paketii",
          "gerekli_belgeler": [KGF_BANKA_BELGESI, "İhracat taahhüdü (krediler ihracat taahhütlü kullandırılır)",
                               _ucret("kredi tutarının %0,1'i (asgari 10 bin TL)")],
          "basvuru_yeri": _kgf_yeri("Ziraat Bankası"),
          "basvuru_sartlari": ["KOBİ olmak", "Krediler TL işletme kredisi olarak, ihracat taahhütlü kullandırılır",
                               "Kefalet üst limiti azami 40 milyon TL, kefalet oranı %80"]},
    125: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/hazine-destekli-kefaletler/aktif-destek-paketleri-2025/2024-dijital-donusum-destek-paketi",
          "gerekli_belgeler": [KGF_BANKA_BELGESI, "KOSGEB KOBİ Dijital Dönüşüm Destek Programı başvuru onayı ve kredi "
                                                  "faiz desteğine hak kazanma"],
          "basvuru_yeri": _kgf_yeri("Türkiye İş Bankası, Türk Ekonomi Bankası (KOSGEB ile protokollü bankalar)")},
    122: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/halkbank-ilk-adim-kredisi-projesi",
          "gerekli_belgeler": [KGF_BANKA_BELGESI],
          "basvuru_yeri": _kgf_yeri("Halkbank (yalnızca yeni ve ilave TL krediler)")},
    90: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/hazine-destekli-kefaletler/aktif-destek-paketleri-2025/yatirim-isletme-destek-paketi",
         "gerekli_belgeler": [KGF_BANKA_BELGESI],
         "basvuru_yeri": _kgf_yeri("Ziraat Bankası, Vakıfbank, Halkbank, İş Bankası, Garanti Bankası, Yapı ve Kredi "
                                   "Bankası, Akbank, Denizbank, QNB Bank, TEB, Şekerbank, Anadolubank, ING Bank")},
    152: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/dogrudan-krediler/tubitak-transfer-odemeleri",
          "gerekli_belgeler": ["TÜBİTAK tarafından desteklenen Ar-Ge projesi (destek kararı)",
                               "KGF'ye kefalet başvurusu",
                               "Proje başına bir defaya mahsus 250 TL başvuru ücretinin KGF hesabına yatırılması"],
          "basvuru_yeri": ("Doğrudan KGF'ye (doğrudan kefalet işleyişi); kefalet mektubu desteği sağlayan TÜBİTAK'a "
                           "hitaben düzenlenir")},
    126: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/istihdam-taahhutlu-kobi-finansman-destek-programi",
          "gerekli_belgeler": [KGF_BANKA_BELGESI, _ucret("5.000 TL")],
          "basvuru_yeri": _kgf_yeri("Garanti BBVA")},
    137: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/ozkaynak",
          "gerekli_belgeler": [KGF_BANKA_BELGESI],
          "basvuru_yeri": ("KGF ile protokol imzalayan ve KGF'ye ortak bankalar ile bunların hâkim ortağı olduğu "
                           "finansal kiralama ve finansman şirketleri (kefalet talebini kredi veren kurum KGF'ye iletir)")},
    107: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/kosgeb-destekli-kefaletler/kuresel-rekabetcilik-destek-paketi",
          "gerekli_belgeler": [KGF_BANKA_BELGESI, "KOSGEB Küresel Rekabetçilik Destek Programı başvuru onayı ve kredi "
                                                  "faiz desteğine hak kazanma"],
          "basvuru_yeri": _kgf_yeri("Ziraat Bankası, Vakıfbank, Halkbank, Ziraat Katılım (KOSGEB ile protokollü)")},
    142: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/kosgeb-destekli-kefaletler/istihdam-koruma-destek-programi",
          "gerekli_belgeler": [KGF_BANKA_BELGESI,
                               "2025 Kasım-Aralık aylarına ait muhtasar ve prim hizmet beyannameleri (kredi limiti "
                               "bunlardan hesaplanır)",
                               _ucret("10.000 TL; kefalet komisyonu yıllık %1,5")],
          "basvuru_yeri": _kgf_yeri("DenizBank, Garanti BBVA, Halk Bankası, İş Bankası, Ziraat Bankası, Yapı Kredi "
                                    "Bankası, VakıfBank"),
          "basvuru_sartlari": ["İşletme başına kredi limiti, 2025 Kasım-Aralık muhtasar ve prim hizmet beyannamelerinde "
                               "beyan edilen prime esas kazanç toplamının aylık ortalamasını geçemez; üst limit 50 "
                               "milyon TL"]},
    149: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/kosgeb-destekli-kefaletler/refinansman-kefalet-programi",
          "gerekli_belgeler": [KGF_BANKA_BELGESI, _ucret("10.000 TL; kefalet komisyonu yıllık %1,5")],
          "basvuru_yeri": _kgf_yeri("Ziraat Bankası, Vakıfbank, Halkbank, İşbankası, Garanti BBVA, Yapı Kredi Bankası, "
                                    "QNB Bank, Denizbank, Akbank")},
    91: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/hazine-destekli-kefaletler/aktif-destek-paketleri-2025/tkyb-kredi-destek-paketi",
         "gerekli_belgeler": [KGF_BANKA_BELGESI],
         "basvuru_yeri": _kgf_yeri("Türkiye Kalkınma ve Yatırım Bankası A.Ş.")},
    86: {"kaynak": "https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/tobb-nefes-kredisi-2026-destek-programi",
         "gerekli_belgeler": [KGF_BANKA_BELGESI, "TOBB'a bağlı ticaret/sanayi/deniz ticaret odası veya ticaret borsası "
                                                 "üyeliği"],
         "basvuru_yeri": _kgf_yeri("Akbank, Denizbank, Garanti BBVA, Halkbank, QNB Bank, Vakıfbank, Yapı Kredi, "
                                   "Ziraat Bankası, Ziraat Katılım (yalnızca TL kefalet)")},
}
ALANLAR = ("gerekli_belgeler", "basvuru_yeri", "basvuru_sartlari")


def _bos(v) -> bool:
    return v is None or v == "" or v == [] or v == "[]"


def uygula(db, dry_run: bool) -> tuple[int, int, int]:
    n = atlanan = korunan = 0
    for tid, veri in KAYITLAR.items():
        t = db.get(Tesvik, tid)
        if t is None:
            print(f"!! {tid} yok")
            atlanan += 1
            continue
        if t.durum_notu and NOT in t.durum_notu:
            print(f"[{tid}] zaten işlenmiş, atlandı")
            continue
        yazilan = []
        for alan in ALANLAR:
            if alan not in veri:
                continue
            if not _bos(getattr(t, alan)):
                korunan += 1
                print(f"   [{tid}] {alan} dolu, korunuyor")
                continue
            yazilan.append(alan)
            if not dry_run:
                setattr(t, alan, veri[alan])
        if not yazilan:
            continue
        print(f"[{tid}] {t.baslik[:60]}  <- {', '.join(yazilan)}")
        for alan in yazilan:
            deger = veri[alan]
            print(f"      {alan}: {deger if isinstance(deger, str) else ' | '.join(deger)}"[:230])
        if not dry_run:
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: {', '.join(yazilan)} kaynak sayfadan dolduruldu ({veri['kaynak']})")
        n += 1
    if not dry_run:
        db.commit()
    return n, atlanan, korunan


def _self_test() -> int:
    kontroller = [
        ("34 adaydan 32'si kapsandı (77 ve 79 kaynaksız, bilerek dışarıda)", len(KAYITLAR) == 32
         and not {77, 79} & set(KAYITLAR)),
        ("her kayıtta kaynak adresi var", all(v.get("kaynak", "").startswith("https://") for v in KAYITLAR.values())),
        ("her kayıt en az bir alan dolduruyor", all(set(v) & set(ALANLAR) for v in KAYITLAR.values())),
        ("liste alanları liste, yer alanı metin",
         all(isinstance(v.get(a, []), list) for v in KAYITLAR.values() for a in ("gerekli_belgeler", "basvuru_sartlari"))
         and all(isinstance(v["basvuru_yeri"], str) for v in KAYITLAR.values() if "basvuru_yeri" in v)),
        ("değerlendirme/izleme/ödeme formu listeye girmedi",
         not any(k in b for v in KAYITLAR.values() for b in v.get("gerekli_belgeler", [])
                 for k in ("Teknik İnceleme", "Kurul Karar", "Kurul Değerlendirme", "İzleme Formu", "Sonuç Rapor",
                           "Ödeme Talep"))),
        ("kaynaksız başvuru yeri yazılmadı (KOSGEB 5 ve 7)", all("basvuru_yeri" not in KAYITLAR[i] for i in (5, 7))),
        ("ASCII Türkçe yok", not any(k in str(v) for v in KAYITLAR.values()
                                     for k in (" icin ", "basvuru ", "Basvuru ", " degil", "isletme "))),
    ]
    for ad, ok in kontroller:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in kontroller)
    print(f"\nself-test: {gecen}/{len(kontroller)} geçti")
    return 0 if gecen == len(kontroller) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    db = SessionLocal()
    try:
        n, atlanan, korunan = uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} kayıt, {atlanan} atlandı, {korunan} dolu alan korundu")
    finally:
        db.close()
