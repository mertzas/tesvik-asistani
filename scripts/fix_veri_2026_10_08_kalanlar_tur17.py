"""Tur 17 — tur16 sonrası kalanlar (2026-10-08): TÜBİTAK şart/belge/yer, KOSGEB 6-7, 79 Sera metni, bayat 2 kayıt.

Kapsam kararı (ölçüm): kalan 35 TÜBİTAK kaydının 31'i akademik/aracı çağrı ve hiçbir işletme profiline önerilmiyor
(matching.uygunluk_engeli). İşletmeye önerilebilen 4 kayda (1515, 1702, 1719, 1832) şart/belge/yer elle seçilmiş tam
cümlelerle yazılır; akademik kayıtlara yalnız sayfadaki başvuru sistemi adresi (yer) yazılır. Otomatik çıkarılan
şart/belge parçaları gürültülüydü ("Çağrı duyurusu için tıklayınız", yarım cümleler); yazılmadı.
Sayfasında başvuru kanalı cümlesi bulunmayan 13, 18, 41, 57, 64, 71 boş kalır.

Düzeltmeler:
  79 Sera: özet/açıklama "kurulum hibesi ve kredi" diyordu; tutarı (310 TL/da temel destek + iyi tarım sertifikalı
     örtüaltında 527 TL/da, 2026 birim fiyat tablosu) ve Tebliğ 2024/39 m.5, m.7/4 ile tutarlı metne çevrilir. Eski
     metin durum_notu'na yazılır.
  26 ve 50 (2223-D Türkiye-Birleşik Krallık / Katip Çelebi-Newton): sayfalardaki tek başvuru dönemi 16.05–24.06.2016,
     etkinlik son tarihi 31.12.2017 (kanıt docs/olcum/2026-10-08-tur16/kanit.json) → aktif_mi=False.
Çağrılar: 2223-C, 2223-B, 2224-B, 2224-A "Başvurular, 27 Ekim 2026 saat 17:30'a kadar TYBS üzerinden".

Alıntılar docs/olcum/2026-10-08-tur17/kanit.json (23 kaynak, hepsi metinde birebir denetlendi).
Idempotent: boş olmayan alan atlanır (79 metni için "Tur17" notu), pasif kayıt atlanır, var olan çağrı atlanır.

    python scripts/fix_veri_2026_10_08_kalanlar_tur17.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_kalanlar_tur17.py --uygula
    python scripts/fix_veri_2026_10_08_kalanlar_tur17.py --self-test
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from app.models import SessionLocal, Tesvik, TesvikCagrisi  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur17 2026-10-08"
KANIT = KOK / "docs/olcum/2026-10-08-tur17/kanit.json"
KANIT16 = KOK / "docs/olcum/2026-10-08-tur16/kanit.json"
PRODIS = "PRODİS (eteydeb.tubitak.gov.tr) üzerinden çevrim içi"
ARDEB = "ARDEB Proje Başvuru Sistemi (ardeb-pbs.tubitak.gov.tr), ARBİS hesabıyla"
TYBS = "TÜBİTAK Yönetim Bilgi Sistemi (tybs.tubitak.gov.tr) üzerinden çevrim içi"
UIDB = "Uluslararası İşbirliği Proje Başvuru Sistemi (uidb-pbs.tubitak.gov.tr), ARBİS hesabıyla"

VERI: dict[str, dict[int, object]] = {
    "basvuru_sartlari": {
        14: ["Süreç, ana kuruluşun TEYDEB'e niyet beyanıyla başlar; niyet beyanı Yürütme Komitesince uygun bulunursa başvuru "
             "aşamasına geçilir",
             "Ana kuruluşun son üç yıldan herhangi birinde Ar-Ge harcamasının 15 milyon TL ve üzeri olması (2022 tutarı; her "
             "yıl Ocak'ta TÜFE ortalama değişimi oranında artırılır)",
             "Başvuruyu ana kuruluş ya da ana kuruluşun yönetim hakkına sahip olduğu Türkiye'de yerleşik sermaye şirketi yapar"],
        15: ["Başvuran (Müşteri Kuruluş): patentle korunan teknolojileri lisanslama ya da devir yoluyla edinerek ekonomik değer "
             "oluşturmayı hedefleyen, Türkiye'de yerleşik sermaye şirketi",
             "Edinilecek teknoloji, Teknoloji Sağlayıcı Kuruluşun hak sahibi olduğu ulusal ya da uluslararası patentle "
             "korunmalı"],
        46: ["Sermaye şirketleri, yükseköğretim kurumları, kamu araştırma merkez ve enstitüleri, eğitim ve araştırma "
             "hastaneleri, 6550 sayılı Kanun kapsamındaki araştırma altyapıları başvurabilir",
             "Sermaye şirketi dışındakiler tek başına başvuramaz; en az bir sermaye şirketi ortaklığı gerekir ve sermaye şirketi "
             "yürütücü (muhatap) kuruluş olmalıdır"],
        59: ["Yeşil teknoloji, ürün ya da süreç geliştirmeye yönelik yeşil yenilik faaliyetinde bulunan, Türkiye'de yerleşik "
             "sermaye şirketi olmak (KOBİ ya da büyük ölçekli)",
             "Ar-Ge çalışması THS 3-9 aralığında olmalı; THS 3'ten önce ya da THS 8'den başlayan çalışmalar kapsam dışı",
             "En fazla üç ortaklı başvuru yapılabilir"],
    },
    "gerekli_belgeler": {
        14: ["Niyet beyanı (Niyet Beyanı Kılavuzu'na göre)", "1515 Başvuru Formu ve Kılavuzu",
             "1515 Ortak Kuruluş Başvuru Formu ve Kılavuzu (ortak kuruluş varsa)"],
        46: ["1719 Eureka Network Çağrısı Başvuru Formu (örneği program sayfasında)"],
        59: ["Proje başvurusu PRODİS üzerinde (örnek başvuru formu bilgilendirme amaçlıdır)",
             "Çevresel ve Sosyal Risk Yönetimi Beyan Formu", "Ekonomik Fizibilite Raporu (program sayfasındaki formata göre)"],
        6: ["SEGEM Destek Programı Ön Başvuru Formu", "SEGEM Destek Programı Başvuru Formu"],
    },
    "basvuru_yeri": {
        14: "TÜBİTAK TEYDEB'e niyet beyanıyla başlar; uygun bulunursa başvuru formuyla",
        15: "PRODİS (eteydeb.tubitak.gov.tr) üzerinden", 46: PRODIS + " (ön başvuru ve ikinci aşama)", 59: PRODIS,
        11: TYBS, 20: TYBS, 24: TYBS, 45: TYBS, 66: TYBS,
        16: "ARDEB Proje Başvuru Sistemi (ardeb-pbs.tubitak.gov.tr)", 43: ARDEB, 54: ARDEB, 60: ARDEB, 65: ARDEB, 68: ARDEB,
        175: ARDEB, 176: ARDEB, 22: UIDB.replace(", ARBİS hesabıyla", ""), 29: UIDB,
        69: "BİDEB Başvuru ve İzleme Sistemi (e-bideb.tubitak.gov.tr), çağrı duyurusundaki tarihlerde",
        7: "KOSGEB'e 2026-2 dönemi formlarıyla (Başvuru Formu, Taahhütname); kredi, bankalardan kullanılır",
    },
}
KANIT_ANAHTARI = {6: "kosgeb_6", 7: "kosgeb_7"}

S79_OZET = ("Örtüaltı (sera) bitkisel üretim yapan çiftçilere dekar başına temel destek; iyi tarım uygulamaları sertifikalı "
            "örtüaltı üretimde ilave destek (2026).")
S79_DETAY = ("Temel destek ÇKS'ye kayıtlı arazi üzerinden Kararın Tablo 1 kategorisine göre ödenir (Tebliğ 2024/39 m.5). İyi "
             "tarım uygulamaları desteği ÇKS/ÖKS/KOBÜKS'te kayıtlı, sertifikalı ürünlere Tablo 8 katsayısıyla ödenir; 1. grup "
             "ürünlerde ÖKS/KOBÜKS'te kayıtlı olmayan alanlar açıkta üretim desteğinden yararlanır (m.7/4). 2026 birim "
             "değerleri: temel destek 310 TL/da; örtüaltı iyi tarım bireysel sertifika katsayısı 1,7 = 527 TL/da (grup "
             "sertifikasında 0,85). Sera kurulumu için yatırım hibesi bu kaydın kapsamında değildir.")
PASIF = {26: "2223-D Türkiye-Birleşik Krallık", 50: "2223-D Katip Çelebi-Newton Fonu"}
CAGRILAR = [(i, "Başvuru dönemi (son gün 27 Ekim 2026)", None, date(2026, 10, 27), f"tubitak_{i}", "Kapanış saati 17:30; TYBS.")
            for i in (11, 20, 24, 45)]


def _anahtar(tid: int) -> str:
    return KANIT_ANAHTARI.get(tid, f"tubitak_{tid}")


def _bos(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v)


def _not(t: Tesvik, metin: str) -> None:
    t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + f"{NOT}: {metin}"


def uygula(db, dry_run: bool = True) -> dict:
    kanit = json.loads(KANIT.read_text(encoding="utf-8"))["kaynaklar"]
    say = {"alan": 0, "metin": 0, "pasif": 0, "cagri": 0, "atlanan": 0}
    for alan, kayitlar in VERI.items():
        for tid, deger in kayitlar.items():
            t = db.get(Tesvik, tid)
            if t is None or not t.aktif_mi:
                raise SystemExit(f"[{tid}] kayıt yok ya da pasif; durduruldu")
            if not _bos(getattr(t, alan)):
                say["atlanan"] += 1
                continue
            print(f"[{tid}] {alan}: {str(deger)[:110]}")
            if not dry_run:
                setattr(t, alan, deger)
                _not(t, f"{alan} resmi kaynaktan ({kanit[_anahtar(tid)]['url']}); alıntı docs/olcum/2026-10-08-tur17/kanit.json")
            say["alan"] += 1
    t = db.get(Tesvik, 79)
    if NOT in (t.durum_notu or ""):
        say["atlanan"] += 1
    else:
        print(f"[79] özet/açıklama düzeltiliyor: '{(t.ozet or '')[:60]}' → '{S79_OZET[:60]}'")
        if not dry_run:
            _not(t, f"özet/açıklama tutar ve Tebliğ 2024/39 m.5, m.7/4 ile uyumlu hâle getirildi; eski özet: '{t.ozet}'")
            t.ozet, t.detay = S79_OZET, S79_DETAY
        say["metin"] += 1
    for tid, ad in PASIF.items():
        t = db.get(Tesvik, tid)
        if not t.aktif_mi:
            say["atlanan"] += 1
            continue
        print(f"[{tid}] {ad} → pasif (yalnız 2016 dönemi)")
        if not dry_run:
            t.aktif_mi = False
            _not(t, "pasif: TÜBİTAK sayfasındaki tek başvuru dönemi 16.05–24.06.2016, etkinlik son tarihi 31.12.2017 "
                    f"({t.kaynak_url}; alıntı docs/olcum/2026-10-08-tur16/kanit.json)")
        say["pasif"] += 1
    for tid, ad, acilis, kapanis, anahtar, notlar in CAGRILAR:
        if db.query(TesvikCagrisi).filter(TesvikCagrisi.tesvik_id == tid, TesvikCagrisi.ad == ad).first():
            say["atlanan"] += 1
            continue
        print(f"[{tid}] çağrı '{ad}'")
        if not dry_run:
            db.add(TesvikCagrisi(tesvik_id=tid, ad=ad, acilis=acilis, kapanis=kapanis, kaynak_url=kanit[anahtar]["url"],
                                 dogrulama_tarihi=date(2026, 10, 8), notlar=notlar))
        say["cagri"] += 1
    if not dry_run:
        db.commit()
    return say


def _self_test() -> int:
    k_ = json.loads(KANIT.read_text(encoding="utf-8"))["kaynaklar"]
    k16 = json.dumps(json.loads(KANIT16.read_text(encoding="utf-8")), ensure_ascii=False)
    idler = {i for alan in VERI.values() for i in alan}
    k = [
        ("her kayıt için kanıt var", all(_anahtar(i) in k_ for i in idler)),
        ("akademik kayıtlara şart/belge yazılmadı", set(VERI["basvuru_sartlari"]) == {14, 15, 46, 59}
         and set(VERI["gerekli_belgeler"]) <= {14, 46, 59, 6}),
        ("kanal cümlesi olmayanlar boş kalır", not {13, 18, 41, 57, 64, 71, 26, 50} & set(VERI["basvuru_yeri"])),
        ("79 metni tutarla tutarlı", "527" in S79_DETAY and "310" in S79_DETAY and "kurulum" not in S79_OZET.lower()),
        ("pasif kanıtı tur16'da", "16 Mayıs 2016" in k16 and "31 Aralık 2017" in k16),
        ("27 Ekim çağrıları kanıtta", all("27 Ekim 2026" in " ".join(k_[f"tubitak_{i}"]["alintilar"]) for i in (11, 20, 24, 45))),
    ]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in k)
    print(f"\nself-test: {gecen}/{len(k)} geçti")
    return 0 if gecen == len(k) else 1


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
        s = uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {s}")
    finally:
        db.close()
