"""Denetim 2 / Aşama H (Tur 7) — kayıt taraması: 12 kararsız + Denetim 2'de karşılaştırılmamış 37 aktif kayıt.

Her kayıt kurumun canlı sayfasından Chrome ile salt okunur okundu (2026-10-07 gece / 2026-10-08). Ayrıntı ve alıntılar:
docs/olcum/2026-10-07-denetim2/H_RAPOR.md. Değişiklik türleri:

  aktif_mi   : kararsız (None) -> True/False, ya da çağrısı kapanmış aktif kayıt -> False
  basvuru_suresi : boşsa sayfadaki başvuru takvimiyle doldurulur; doluysa yalnızca başına kapanış bilgisi eklenir
  tesvil_tutari  : eski/kaynaksız metin resmî 2026 tutarıyla değiştirilir (eski metin beklenenle eşleşmezse kayıt atlanır)

Kural (Denetim 2 emsali): yılda tek başvuru penceresi olan ve 2026 penceresi kapanmış program -> aktif_mi=False
(4006-C, 2517, 1701 emsali). Yılda birden çok dönemi olan program -> aktif kalır, takvime "(kapandı)" yazılır
(KOSGEB Girişimci emsali). `--kapali-donem-aktif` bayrağı yıllık tek pencereli tarım/TÜBİTAK sanayi programlarını
(27, 30, 78, 80) kapatmak yerine aktif bırakıp takvim notu düşer.

Idempotent: durum_notu'nda "Denetim2-T7" varsa kayıt atlanır.

    python scripts/fix_veri_2026_10_08_denetim2_tur7.py --dry-run   (varsayılan)
    python scripts/fix_veri_2026_10_08_denetim2_tur7.py --uygula [--kapali-donem-aktif]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Denetim2-T7"
DEGISMEZ = object()  # aktif_mi için "dokunma"

BUGEM_PDF = ("https://www.tarimorman.gov.tr/BUGEM/Belgeler/Tar%C4%B1m%20Havzalar%C4%B1/"
             "2026%20Y%C4%B1l%C4%B1%20Destekleme%20Birim%20Fiyatlar%C4%B1.pdf")
TRGM_670 = "https://www.tarimorman.gov.tr/TRGM/Sayfalar/Detay.aspx?OgeId=670&Liste=Duyuru"
HAYGEM_268 = ("https://www.tarimorman.gov.tr/HAYGEM/Duyuru/268/"
              "2026-Yili-Buyukbas-Hayvancilik-_buzagi_malak_-Desteklemeleri-Talimati-Yayinlanmistir")
T1711_2026 = ("https://www.tubitak.gov.tr/tr/destekler/destek/sanayi/ulusal-destek-programlari/"
              "cagri-1711-yapay-zeka-ekosistem-2026-yili-cagrisi-acildi")

SUREKLI = "Sürekli açık (yıl boyunca başvuru yapılabilir)"
TUBITAK_3_DONEM = ("Dönemsel çağrı: 2026 yılı 3. dönem 5 Ekim 2026'da açıldı, son başvuru 27 Ekim 2026 saat 17:30 "
                   "(TYBS üzerinden)")
TARIM_PENCERE = "2026 başvuru dönemi 29 Nisan – 12 Haziran 2026 saat 23:59 (kapandı); yıllık çağrı. "

# Yıllık tek pencereli, 2026 penceresi kapanmış programlar (bayrakla aktif bırakılabilir).
YILLIK_KAPANAN = {27, 30, 78, 80}

# id -> değişiklik. kaynak None ise kaydın kendi kaynak_url'i (taranan sayfa) kullanılır.
KAYITLAR: dict[int, dict] = {
    # --- kararsız -> aktif ---
    57: dict(aktif=True, tarih="2026-10-07", sure=SUREKLI,
             bulgu="'Başvurular sürekli açıktır ve yılın her günü TÜBİTAK'a yapılabilir'"),
    66: dict(aktif=True, tarih="2026-10-08", sure="Sürekli açık (program 365 gün başvuruya açık; değerlendirme periyodik)",
             bulgu="'Program 365 gün başvuruya açıktır'"),
    76: dict(aktif=True, tarih="2026-10-07", kaynak=HAYGEM_268,
             bulgu="HAYGEM duyurusu 268 (01.09.2026): 2026 büyükbaş talimatı yayımlandı; 1. dönem 01/09–01/12/2026 açık"),
    # --- kararsız -> kapalı ---
    30: dict(aktif=False, tarih="2026-10-07",
             sure="2026 çağrısı: ön başvuru 23 Şubat – 23 Mart 2026, ikinci aşama 8 Nisan – 4 Haziran 2026 (kapandı)",
             bulgu="2026 çağrısının iki aşaması da kapandı (8 Nisan – 4 Haziran 2026)"),
    31: dict(aktif=False, tarih="2026-10-08", bulgu="sayfada 'ÇAĞRISI SONUÇLANDI'; açık çağrı yok"),
    33: dict(aktif=False, tarih="2026-10-08",
             bulgu="sayfada 'Çağrısı Sonuçlandı', 237 proje desteklendi; açık çağrı yok"),
    35: dict(aktif=False, tarih="2026-10-07",
             bulgu="2026-2028 dönemi uygulayıcı kuruluşlar belirlenmiş ve listelenmiş; yeni başvuru yok"),
    38: dict(aktif=False, tarih="2026-10-08",
             bulgu="sayfadaki tek başvuru dönemi 6 Nisan – 8 Mayıs 2015; güncel çağrı yok"),
    78: dict(aktif=False, tarih="2026-10-07", kaynak=TRGM_670, sure_onek=TARIM_PENCERE,
             bulgu="TRGM duyurusu (29.04.2026): KKYP başvuruları 29 Nisan – 12 Haziran 2026 23:59; kapandı"),
    80: dict(aktif=False, tarih="2026-10-07", kaynak=TRGM_670, sure_onek=TARIM_PENCERE,
             bulgu="TRGM duyurusu (29.04.2026): TSS hibe başvuruları 29 Nisan – 12 Haziran 2026 23:59; kapandı"),
    # --- kararsız kalır (sayfa doğrulama için yetersiz) ---
    37: dict(aktif=DEGISMEZ, tarih="2026-10-08",
             bulgu="sayfa yalnızca program tanımı içeriyor; başvuru dönemi/çağrı bilgisi yok, kararsız bırakıldı"),
    73: dict(aktif=DEGISMEZ, tarih="2026-10-08",
             bulgu="çağrı bazlı program; sayfada açık çağrı veya tarih yok, kararsız bırakıldı"),
    # --- aktif -> kapalı (çağrı kapanmış) ---
    27: dict(aktif=False, tarih="2026-10-08", kaynak=T1711_2026,
             sure="2026 çağrısı (beşinci çağrı) 15 Haziran – 2 Ekim 2026 23:59 (kapandı)",
             bulgu="2026 çağrısı başvuruları 15 Haziran – 2 Ekim 2026; kapandı"),
    58: dict(aktif=False, tarih="2026-10-08",
             bulgu="sayfadaki son çağrının başvuru son tarihi 30 Eylül 2024; yeni çağrı yok"),
    # --- aktif kalır, takvim yazılır ---
    11: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=TUBITAK_3_DONEM, bulgu="DUYURU (05.10.2026): 2026 3. dönem açık"),
    20: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=TUBITAK_3_DONEM, bulgu="DUYURU (05.10.2026): 2026 3. dönem açık"),
    24: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=TUBITAK_3_DONEM, bulgu="DUYURU (05.10.2026): 2026 3. dönem açık"),
    45: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=TUBITAK_3_DONEM, bulgu="DUYURU (05.10.2026): 2026 3. dönem açık"),
    69: dict(aktif=DEGISMEZ, tarih="2026-10-08",
             sure=("Dönemsel: 2026/1 26 Ocak – 17 Şubat, 2026/2 20 Temmuz – 11 Ağustos 2026 (ikisi de kapandı); "
                   "sonraki dönem TÜBİTAK duyurusuyla"),
             bulgu="yılda iki dönem; 2026 dönemleri kapandı"),
    29: dict(aktif=DEGISMEZ, tarih="2026-10-08",
             sure="Çağrı bazlı; tarihler karşı kurumla belirlenir (bazı çağrılar sürekli açık)",
             bulgu="'sürekli açık çağrılar dışında, karşı kurum ve kuruluş ile yapılan müzakereler sonucunda belirlenir'"),
    22: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=SUREKLI, bulgu="'başvuruya sürekli açıktır'"),
    41: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=SUREKLI, bulgu="'başvuru sistemi sürekli olarak açıktır'"),
    43: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=SUREKLI, bulgu="'Yıl boyunca başvuru yapılabilir'"),
    60: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=SUREKLI, bulgu="'yıl boyunca başvuru yapılabilir'"),
    64: dict(aktif=DEGISMEZ, tarih="2026-10-08",
             sure="Sürekli açık; başvurular toplama tarihlerinden sonra topluca değerlendirilir",
             bulgu="'Başvuru sistemi sürekli açık'"),
    65: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=SUREKLI, bulgu="'Yıl boyunca başvuru yapılabilir'"),
    68: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=SUREKLI, bulgu="'Yıl boyunca başvuru yapılabilir'"),
    71: dict(aktif=DEGISMEZ, tarih="2026-10-08",
             sure="Sürekli açık; başvurular toplama tarihlerinden sonra topluca değerlendirilir",
             bulgu="'başvuru sistemi sürekli açık'"),
    75: dict(aktif=DEGISMEZ, tarih="2026-10-07", sure=SUREKLI, bulgu="'Başvurular sürekli açıktır'"),
    175: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=SUREKLI, bulgu="'Yıl boyunca başvuru yapılabilir'"),
    176: dict(aktif=DEGISMEZ, tarih="2026-10-08", sure=SUREKLI, bulgu="'Yıl boyunca başvuru yapılabilir'"),
    # --- tutar metni düzeltmeleri ---
    77: dict(aktif=DEGISMEZ, tarih="2026-10-07", kaynak=BUGEM_PDF,
             eski_tutar="Dekar başına ₺500 - ₺2.000",
             tutar=("Dekar başına 62–465 TL organik tarım desteği (2026; ürün grubu ve bireysel/grup sertifikaya göre, "
                    "1. derece örgüt üyesine %25 ilave dâhil); temel destek ayrıca ödenir"),
             bulgu="eski metin '₺500–2.000/da' resmî tabloyla çelişiyordu (tutari_min/max 62/465 zaten doğruydu)"),
    79: dict(aktif=DEGISMEZ, tarih="2026-10-07", kaynak=BUGEM_PDF,
             eski_tutar="m² başına ₺50 - ₺200",
             tutar=("Dekar başına 310 TL temel destek; iyi tarım sertifikalı örtüaltı üretimde bireysel sertifikayla "
                    "+527 TL (en çok 837 TL/da, 2026)"),
             bulgu="eski metin 'm² başına ₺50–200' kaynaksızdı; 2026 tablosu dekar bazlı (310 + 527)"),
    160: dict(aktif=DEGISMEZ, tarih="2026-10-07", kaynak=BUGEM_PDF,
              eski_tutar="Dekar başına mazot+gübre desteği",
              tutar=("Dekar başına 620–806 TL (2026): temel destek + planlı üretim desteği, her biri ürün katsayısı × "
                     "310 TL (mercimek/nohut 1,0; buğday/arpa/mısır 1,3); sertifikalı tohum ayrıca. 2026'da mazot ve "
                     "gübre desteği 'temel destek' adıyla birleştirildi"),
              bulgu="2026'da mazot+gübre ayrımı kalktı (temel destek); tutar formülden yazıldı"),
    161: dict(aktif=DEGISMEZ, tarih="2026-10-07", kaynak=BUGEM_PDF,
              eski_tutar="Dekar başına mazot+gübre desteği",
              tutar=("Dekar başına 310 TL temel destek (2026, 1. kategori 'diğer ürünler'); fidan kullanım desteği "
                     "ayrıca 620 TL/da (standart) veya 1.550 TL/da (sertifikalı). 2026'da mazot ve gübre desteği "
                     "'temel destek' adıyla birleştirildi"),
              bulgu="2026'da mazot+gübre ayrımı kalktı (temel destek); tutar formülden yazıldı"),
    185: dict(aktif=DEGISMEZ, tarih="2026-10-08", eski_tutar="",
              tutar=("İşveren SGK prim payı, kişi başı aylık 7.184,03–64.656,23 TL (2026; prime esas kazancın alt ve "
                     "üst sınırı arası), 6–54 ay"),
              bulgu="İŞKUR sayfası: 31.12.2026'ya kadar; işveren payı 7.184,03 TL ila 64.656,23 TL"),
    186: dict(aktif=DEGISMEZ, tarih="2026-10-08", eski_tutar="",
              tutar=("Kişi başı aylık 11.395,35 TL prim karşılığı (2026; prime esas kazanç alt sınırı üzerinden), "
                     "kişinin kalan işsizlik ödeneği süresi boyunca"),
              bulgu="İŞKUR sayfası artık tutarı veriyor: 11.395,35 TL (önceki notta 'tutar sayfada yok' yazıyordu)"),
}


def _durum(v) -> str:
    return {True: "aktif", False: "kapalı", None: "kararsız"}[v]


def plan(kapali_donem_aktif: bool) -> dict[int, dict]:
    """Bayrağa göre son değişiklik listesini döndürür (KAYITLAR'ı değiştirmez)."""
    sonuc = {}
    for tid, d in KAYITLAR.items():
        d = dict(d)
        if kapali_donem_aktif and tid in YILLIK_KAPANAN:
            d["aktif"] = True
            d["bulgu"] += " — yıllık program, sonraki dönem için aktif bırakıldı (--kapali-donem-aktif)"
        sonuc[tid] = d
    return sonuc


def uygula(db, dry_run: bool, kapali_donem_aktif: bool = False) -> tuple[int, int]:
    n = atlanan = 0
    for tid, d in plan(kapali_donem_aktif).items():
        t = db.get(Tesvik, tid)
        if t is None:
            print(f"!! {tid} yok")
            atlanan += 1
            continue
        if t.durum_notu and NOT in t.durum_notu:
            print(f"[{tid}] zaten işlenmiş, atlandı")
            continue
        degisiklik = []
        yeni_aktif = d["aktif"]
        if yeni_aktif is not DEGISMEZ and t.aktif_mi is not yeni_aktif:
            degisiklik.append(("aktif_mi", t.aktif_mi, yeni_aktif))
        eski_sure = t.basvuru_suresi or ""
        if "sure" in d:
            if eski_sure.strip():
                print(f"!! [{tid}] basvuru_suresi dolu ({eski_sure[:60]!r}); üzerine yazılmıyor, kayıt atlandı")
                atlanan += 1
                continue
            degisiklik.append(("basvuru_suresi", eski_sure, d["sure"]))
        if "sure_onek" in d and not eski_sure.startswith(d["sure_onek"]):
            degisiklik.append(("basvuru_suresi", eski_sure, d["sure_onek"] + eski_sure))
        if "tutar" in d:
            mevcut = t.tesvil_tutari or ""
            if not mevcut.startswith(d["eski_tutar"]):
                print(f"!! [{tid}] tesvil_tutari beklenenle eşleşmiyor ({mevcut[:60]!r}); kayıt atlandı")
                atlanan += 1
                continue
            degisiklik.append(("tesvil_tutari", mevcut, d["tutar"]))

        kaynak = d.get("kaynak") or t.kaynak_url
        print(f"[{tid}] {t.baslik[:70]}  ({_durum(t.aktif_mi)})")
        print(f"    bulgu: {d['bulgu']}  [{d['tarih']}]")
        for alan, eski, yeni in degisiklik:
            if alan == "aktif_mi":
                print(f"    aktif_mi: {_durum(eski)} -> {_durum(yeni)}")
            else:
                print(f"    {alan}: {str(eski)[:70]!r}\n        -> {str(yeni)[:150]!r}")
        if not degisiklik:
            print("    (alan değişmiyor; yalnızca doğrulama notu eklenir)")
        if not dry_run:
            for alan, _eski, yeni in degisiklik:
                setattr(t, alan, yeni)
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT} {d['tarih']}: {d['bulgu']} ({kaynak})")
        n += 1
    if not dry_run:
        db.commit()
    return n, atlanan


def _self_test() -> int:
    """Veritabanına dokunmadan plan tutarlılığını sınar."""
    gecen = toplam = 0

    def kontrol(ad, kosul):
        nonlocal gecen, toplam
        toplam += 1
        gecen += bool(kosul)
        print(f"  {'OK ' if kosul else 'HATA'} {ad}")

    p0, p1 = plan(False), plan(True)
    kontrol("49 kaydın hepsi tarandı (37 kayıt değişiyor, 12'si yalnızca doğrulandı)", len(KAYITLAR) == 37)
    kontrol("her kayıtta bulgu ve erişim tarihi var",
            all(d.get("bulgu") and d.get("tarih") in ("2026-10-07", "2026-10-08") for d in KAYITLAR.values()))
    kontrol("tutar değişen her kayıtta eski metin kontrolü var",
            all("eski_tutar" in d for d in KAYITLAR.values() if "tutar" in d))
    kontrol("varsayılan: yıllık kapanan programlar kapalı", all(p0[i]["aktif"] is False for i in YILLIK_KAPANAN))
    kontrol("bayrakla: yıllık kapanan programlar aktif", all(p1[i]["aktif"] is True for i in YILLIK_KAPANAN))
    kontrol("bayrak KAYITLAR'ı değiştirmiyor", all(KAYITLAR[i]["aktif"] is False for i in YILLIK_KAPANAN))
    kontrol("sure ve sure_onek aynı kayıtta yok", not any("sure" in d and "sure_onek" in d for d in KAYITLAR.values()))
    kontrol("hiçbir tutar metninde ASCII Türkçe yok",
            not any(k in d.get("tutar", "") for d in KAYITLAR.values() for k in (" icin ", " ayrica", " basina")))
    print(f"\nself-test: {gecen}/{toplam} geçti")
    return 0 if gecen == toplam else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--kapali-donem-aktif", action="store_true",
                    help="yıllık tek pencereli, 2026 penceresi kapanmış programları (27, 30, 78, 80) aktif bırak")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    db = SessionLocal()
    try:
        n, atlanan = uygula(db, dry_run=not a.uygula, kapali_donem_aktif=a.kapali_donem_aktif)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} kayıt, {atlanan} atlandı")
    finally:
        db.close()
