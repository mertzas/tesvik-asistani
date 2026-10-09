"""Tur 20 — resmî kaynak bağlantıları, eksik çağrılar ve 2026 bitkisel üretim destek tutarları (2026-10-10).

Kontrol listesi denetiminin (docs/olcum/2026-10-10-kontrol-listesi/RAPOR.md) "Resmî kaynak" bulguları:
  1. Genel sayfaya bağlı programlar: 77, 79, 160, 161 BUGEM ana sayfası; 162 E-ihracat menü sayfası.
     -> Tarım: 8859 sayılı CB Kararı (RG 29.08.2024, programların tanımı ve katsayı tabloları). E-ihracat: 13.04.2026
        tarihli E-İhracat Desteklerine İlişkin Genelge (başvuru usulü).
     -> 174 (1512 BiGG): TÜBİTAK program sayfası 2026-10-10'da gerçek tarayıcıda da "Bu sayfaya erişim izniniz yok";
        kapandığına dair yazılı kaynak yok. Bağlantı değişmez, durum notu eklenir (aktiflik kararı verilmez).
  2. 2026 tutarları: 11781 sayılı CB Kararı (RG 08.09.2026, Madde 1/a ve Madde 6/a) destek katsayı değerini 1.1.2026'dan
     geçerli olarak 310 TL'den 367 TL'ye çıkardı. Kayıtlar 310 TL ile hesaplanmıştı; ayrıca hububat kaydı mısırı 1,3
     katsayıyla veriyordu (8859 Tablo 1-2: mısır dane 1. kategori, 1,0). Tutarlar 8859 tablolarındaki katsayılar × 367 TL.
     Mercimek/nohut havza ilavesi (Madde 1/b) 1.1.2027'den geçerli olduğu için 2026 tutarına katılmaz.
  3. Eksik/çelişik çağrılar: 4 (TEKMER kuruluş desteği son başvuru 07.10.2026; 2026-01 COP31 Hızlandırma 9-30.08.2026),
     55 (1707 2026 taslak takvimi, üç dönem), 59 (1832 2026-2: ön kayıt 08.10, kapanış 12.10.2026), 49 (1812 BİGG+
     2026-1 Tohum Yatırım: 05.10-20.11.2026, ön kayıt 17.11.2026).
Kanıt: docs/olcum/2026-10-10-tur20/kanit.json (+ indirilen metin/PDF dosyaları).

    python scripts/fix_veri_2026_10_10_kaynak_cagri_tur20.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_10_kaynak_cagri_tur20.py --uygula     (önce yedek alır)
    python scripts/fix_veri_2026_10_10_kaynak_cagri_tur20.py --self-test
"""
import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur20 2026-10-10"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur20.db.bak"
BUGUN = date(2026, 10, 10)
RG8859 = "https://www.resmigazete.gov.tr/eskiler/2024/08/20240829-1.pdf"
RG11781 = "https://www.resmigazete.gov.tr/eskiler/2026/09/20260908-7.pdf"
GENELGE = "https://ticaret.gov.tr/data/6447baf113b8761694f892bb/E-İHRACAT DESTEKLERİNE İLİŞKİN GENELGE 13.04.2026.pdf"
DEGER = 367.0  # TL/da, 11781 Madde 1/a, 1.1.2026'dan geçerli


def tl(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


DAYANAK = (f"Dayanak: 8859 sayılı CB Kararı (RG 29.08.2024) tabloları; destek katsayı değeri 2026 için {tl(DEGER)} TL/da "
           "(11781 sayılı CB Kararı, RG 08.09.2026, m.1/a, 1.1.2026'dan geçerli).")

# tesvik_id -> (yeni kaynak_url | None, tesvil_tutari | None, tutari_hesaplama_formulu | None, tutari_max | None)
KAYIT = {
    160: (RG8859 + "#hububat-baklagil",
          f"Dekar başına {tl(2 * DEGER)}–{tl(2 * 1.3 * DEGER)} TL (2026): temel destek + planlı üretim desteği; mercimek, nohut, "
          f"mısır (dane) katsayı 1,0 → {tl(2 * DEGER)} TL/da; arpa, buğday, çavdar, tritikale, yulaf 1,3 → {tl(2 * 1.3 * DEGER)} TL/da. "
          "Sertifikalı tohum desteği ayrıca.",
          f"Temel destek (Tablo 1) + planlı üretim desteği (Tablo 2, havzada planlanan ürün), her biri katsayı × {tl(DEGER)} TL: "
          f"1. kategori (mercimek, nohut, mısır dane) 1,0 → {tl(DEGER)} + {tl(DEGER)}; 2. kategori (arpa, buğday, çavdar, tritikale, "
          f"yulaf) 1,3 → {tl(1.3 * DEGER)} + {tl(1.3 * DEGER)}. Sertifikalı tohum (Tablo 4): arpa/buğday 0,5 → {tl(0.5 * DEGER)}; "
          f"mercimek/nohut 0,4 → {tl(0.4 * DEGER)} TL/da. Mercimek/nohutta havza ilavesi 2027'den geçerlidir. " + DAYANAK,
          round(2 * 1.3 * DEGER, 2)),
    161: (RG8859 + "#sebze-meyve",
          f"Dekar başına {tl(DEGER)} TL temel destek (2026, 1. kategori 'diğer ürünler'); fidan kullanım desteği ayrıca "
          f"{tl(2 * DEGER)} TL/da (standart) veya {tl(5 * DEGER)} TL/da (sertifikalı).",
          f"Sebze ve meyve Tablo 1'de 1. kategori 'diğer ürünler' (katsayı 1,0): temel destek {tl(DEGER)} TL/da. Planlı üretim "
          f"kategorilerinde yer almaz. Yeni meyve bahçesinde fidan kullanım desteği (Tablo 6): standart 2 → {tl(2 * DEGER)}, "
          f"sertifikalı 5 → {tl(5 * DEGER)} TL/da. " + DAYANAK,
          # tutari_max dekar başı tahminde kullanılır (matching.toplam_tahmini_destek): yalnız yeni meyve bahçesine ait
          # fidan desteği her sebze/meyve üreticisinin tahminini şişirmesin diye temel destek.
          DEGER),
    77: (RG8859 + "#organik-tarim",
         f"Dekar başına {tl(0.2 * DEGER)}–{tl(1.5 * DEGER)} TL organik tarım desteği (2026; ürün grubu ve bireysel/grup sertifikaya "
         "göre, 1. derece örgüt üyesine %25 ilave dâhil); temel destek ayrıca ödenir",
         f"Tablo 7 katsayıları × {tl(DEGER)} TL: 1. grup bireysel 1,2 → {tl(1.2 * DEGER)}, grup 0,6 → {tl(0.6 * DEGER)}; 2. grup "
         f"0,6/0,3; 3. grup 0,4/0,2 → en az {tl(0.2 * DEGER)} TL/da. 1. derece tarımsal amaçlı örgüt üyesine katsayının %25'i "
         f"ilave (üst sınır {tl(1.5 * DEGER)} TL/da). Temel destek ayrıca. " + DAYANAK,
         round(1.5 * DEGER, 2)),
    79: (RG8859 + "#ortualti-iyi-tarim",
         f"Dekar başına {tl(DEGER)} TL temel destek; iyi tarım sertifikalı örtüaltı üretimde bireysel sertifikayla "
         f"+{tl(1.7 * DEGER)} TL (en çok {tl(2.7 * DEGER)} TL/da, 2026)",
         f"Temel destek {tl(DEGER)} TL/da (Tablo 1, katsayı 1,0). İyi tarım uygulamaları desteği (Tablo 8) örtüaltı/kapalı ortam: "
         f"bireysel 1,7 → {tl(1.7 * DEGER)}, grup 0,85 → {tl(0.85 * DEGER)} TL/da; üst sınır iki kalemin toplamı. " + DAYANAK,
         round(2.7 * DEGER, 2)),
    162: (GENELGE, None, None, None),
}
DURUM_NOTU = {
    174: ("TÜBİTAK 1512 program sayfası 2026-10-10'da erişime kapalı ('Bu sayfaya erişim izniniz yok', gerçek tarayıcıda "
          "denendi); 1812-BİGG+2026-1 çağrı metni 1512'yi önceki program olarak anıyor. Programın 2026'da yeni çağrı açıp "
          "açmayacağı TÜBİTAK'tan teyit edilmeli."),
}
def _kucuk(il: str) -> str:
    return il.replace("İ", "i").replace("I", "ı").lower()


# İl kısıtı (match_scoring.hard_filter, uygunluk_kriterleri.bolge_kisitli): uygunluk ölçümünde BMZ II Hatay lokantasına
# 1. sırada, Van oteline 3. sırada öneriliyordu (docs/olcum/2026-10-09-uygunluk/RAPOR.md). Kaynak: kriter/126.json alıntısı.
IL_KISITI = {126: [_kucuk(x) for x in ("Adana", "Adıyaman", "Ankara", "Batman", "Bursa", "Diyarbakır", "Gaziantep", "Hatay",
                                       "İstanbul", "İzmir", "Kahramanmaraş", "Kayseri", "Kilis", "Kocaeli", "Konya", "Malatya",
                                       "Mardin", "Mersin", "Osmaniye", "Şanlıurfa")]}
# Ölçek ve NACE kısıtı (match_scoring.hard_filter: max_olcek, tesvik_nace_association). Yalnız alıntısı CANLI resmî
# sayfada bulunan ve açık şart cümlesi olan kriterler (docs/olcum/2026-10-09-uygunluk/kriter/<id>.json); limit tablosu
# satırı ("KOBİ 2.400.000 TL") yalnız KOBİ anlamına gelmeyebileceği için aktarılmaz. Ölçümde büyük A.Ş.'ye KOBİ
# paketleri, Van oteline imalatçı paketi, Hatay lokantasına BMZ II öneriliyordu.
MAX_OLCEK = {
    34: "1501 Sanayi Ar-Ge Destek Programına sadece KOBİ ölçeğinde olan Türkiye’de yerleş",
    90: "İmalatçı KOBİ’lerin yatırım ve işletme harcamalarına yönelik finansman desteği s",
    137: "Yararlanıcının KOBİ vasfını haiz gerçek veya tüzel kişi işletme olması gerekmekt",
    142: "İmalat sanayi sektörlerinde istihdamın korunması ve artırılmasına yönelik olarak",
    146: "TURWIB programı kapsamında sadece KOBİ ölçekli firmalara kredi kullandırımı yapı",
    152: "KOBİ niteliklerine sahip olması",
    153: "TURYIB programı kapsamında sadece KOBİ ölçekli firmalara kredi kullandırımı yapı",
    169: "T.C. Kanunlarına göre kurulmuş KOBİ tanımını haiz işletmeler",
}
NACE = {126: (["C", "62", "72"], "Kısım C-İmalat, Bölüm 62-Bilgisayar programlama, danışmanlık ve ilgili faaliyetl"),
        90: (["C"], "İmalatçı KOBİ’lerin yatırım ve işletme harcamalarına yönelik finansman desteği s")}
COP31 = ("https://webdosya.kosgeb.gov.tr/Content/Upload/Dosya/Haber/2026/"
         "2026-01_COP31_H%C4%B1zland%C4%B1rma_%C3%87a%C4%9Fr%C4%B1s%C4%B1_09_08_2026.pdf")
TEKMER = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9297/teknoloji-merkezi-destek-programi"
T1707 = ("https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/"
         "1707-siparise-dayali-ar-ge-projeleri-icin-kobi-destekleme-cagrisi")
TASLAK = "TÜBİTAK program sayfasındaki 2026 taslak takvimi; kesin tarihler çağrı duyurusunda."
# (tesvik_id, ad, acilis, kapanis, on_kayit_son, kaynak_url, notlar)
CAGRILAR = [
    (4, "Kuruluş Desteği — mevcut (3 yaş altı) TEKMER'ler", date(2025, 10, 7), date(2026, 10, 7), None, TEKMER,
     "Program yürürlük tarihi (07.10.2025) itibarıyla 3 yaşın altındaki TEKMER işletici kuruluşları 1 yıl içinde başvurur."),
    (4, "2026-01 COP31 Hızlandırma Çağrısı", date(2026, 8, 9), date(2026, 8, 30), None, COP31,
     "Hızlandırma Desteği çağrı esaslıdır; sonraki çağrılar KOSGEB duyurusuyla."),
    (55, "2026 yılı 1. çağrı dönemi", date(2026, 1, 2), date(2026, 3, 13), None, T1707, TASLAK),
    (55, "2026 yılı 2. çağrı dönemi", date(2026, 5, 4), date(2026, 7, 17), None, T1707, TASLAK),
    (55, "2026 yılı 3. çağrı dönemi", date(2026, 9, 1), date(2026, 11, 13), None, T1707, TASLAK),
    (59, "1832 2026-2 çağrısı", date(2026, 8, 3), date(2026, 10, 12), date(2026, 10, 8),
     "https://www.tubitak.gov.tr/sites/default/files/2026-09/1832_2026-2_Cagri_Duyurusu_revize_1.pdf",
     "Kuruluş bazlı ön kayıt son tarihi 08.10.2026; çağrı kapanışı 12.10.2026."),
    (49, "1812-BİGG+ 2026-1 Tohum Yatırım Çağrısı", date(2026, 10, 5), date(2026, 11, 20), date(2026, 11, 17),
     "https://tubitak.gov.tr/sites/default/files/2026-08/2026_1_BIGG_Tohum_Yatirim_Cagri_Duyuru_Metni.pdf",
     "1812 tohum öncesi yatırım almış ya da 1512 ile desteklenmiş girişimler için tohum yatırım çağrısı (PRODİS)."),
]


def uygula(db, dry_run: bool = True) -> int:
    from app.models import Tesvik, TesvikCagrisi
    n = 0
    for tid, (url, tutar, formul, tmax) in KAYIT.items():
        t = db.get(Tesvik, tid)
        if t is None:
            raise SystemExit(f"[{tid}] kayıt yok; durduruldu")
        if NOT in (t.durum_notu or ""):
            print(f"[{tid}] zaten uygulanmış; atlandı")
            continue
        eski = {"kaynak_url": t.kaynak_url, "tesvil_tutari": t.tesvil_tutari, "formul": t.tutari_hesaplama_formulu,
                "tutari_max": t.tutari_max}
        print(f"[{tid}] kaynak: {t.kaynak_url} → {url}")
        if tutar:
            print(f"      tutar: '{(t.tesvil_tutari or '')[:80]}…' → '{tutar[:80]}…'  max {t.tutari_max} → {tmax}")
        if not dry_run:
            t.kaynak_url = url
            if tutar:
                t.tesvil_tutari, t.tutari_hesaplama_formulu, t.tutari_max = tutar, formul, tmax
            if t.kontrol_listesi:  # maddelerin kaynağı programın yeni resmî kaynağı (eski sayfada alıntı yoktu)
                t.kontrol_listesi = [{**x, "kaynak_url": url} for x in t.kontrol_listesi]
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: genel sayfa yerine programa özel resmî kaynak; " + ("2026 tutarları 11781 sayılı Kararla (367 TL) "
                "güncellendi; " if tutar else "") + f"eski: {eski}; kanıt docs/olcum/2026-10-10-tur20/kanit.json")
        n += 1
    for tid, notu in DURUM_NOTU.items():
        t = db.get(Tesvik, tid)
        if NOT in (t.durum_notu or ""):
            continue
        print(f"[{tid}] durum notu: {notu[:90]}…")
        if not dry_run:
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + f"{NOT}: {notu}"
        n += 1
    for tid, iller in IL_KISITI.items():
        t = db.get(Tesvik, tid)
        k = dict(t.uygunluk_kriterleri or {})
        if k.get("bolge_kisitli") == iller:
            continue
        print(f"[{tid}] il kısıtı: {len(iller)} il ({', '.join(iller[:4])}…)")
        if not dry_run:
            k["bolge_kisitli"] = iller
            t.uygunluk_kriterleri = k
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: il kısıtı eklendi (resmî sayfadaki 20 il; docs/olcum/2026-10-09-uygunluk/kriter/126.json)")
        n += 1
    for tid, alinti in MAX_OLCEK.items():
        t = db.get(Tesvik, tid)
        k = dict(t.uygunluk_kriterleri or {})
        if k.get("max_olcek"):
            continue
        print(f"[{tid}] max_olcek=orta ('{alinti[:60]}…')")
        if not dry_run:
            k["max_olcek"] = "orta"
            t.uygunluk_kriterleri = k
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: yalnız KOBİ (resmî sayfa: '{alinti}…'; docs/olcum/2026-10-09-uygunluk/kriter/{tid}.json)")
        n += 1
    from app.models import TesvikNace
    for tid, (onekler, alinti) in NACE.items():
        var = {r.nace_prefix for r in db.query(TesvikNace).filter(TesvikNace.tesvik_id == tid)}
        eksik = [x for x in onekler if x not in var]
        if not eksik:
            continue
        print(f"[{tid}] NACE ekle: {eksik} ('{alinti[:50]}…')")
        if not dry_run:
            for x in eksik:
                db.add(TesvikNace(tesvik_id=tid, nace_prefix=x, kaynak="elle:tur20", haric_mi=False))
        n += 1
    for tid, ad, ac, kp, ok, url, notlar in CAGRILAR:
        var = db.query(TesvikCagrisi).filter(TesvikCagrisi.tesvik_id == tid, TesvikCagrisi.ad == ad).first()
        if var:
            print(f"[{tid}] çağrı zaten var: {ad}")
            continue
        print(f"[{tid}] çağrı ekle: {ad} {ac}–{kp}" + (f" (ön kayıt {ok})" if ok else ""))
        if not dry_run:
            db.add(TesvikCagrisi(tesvik_id=tid, ad=ad, acilis=ac, kapanis=kp, on_kayit_son=ok, kaynak_url=url,
                                 dogrulama_tarihi=BUGUN, notlar=notlar))
        n += 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} değişiklik")
    return n


def _self_test() -> int:
    import json
    kanit = json.load(open(KOK / "docs/olcum/2026-10-10-tur20/kanit.json", encoding="utf-8"))
    k = [("tl biçimi", tl(954.2) == "954,20" and tl(1835) == "1.835,00"),
         ("buğday 2 × 1,3 × 367 = 954,20", "954,20" in KAYIT[160][1]),
         ("mısır 1. kategori (1,0), 1,3 değil", "mısır (dane) katsayı 1,0" in KAYIT[160][1]),
         ("2027 havza ilavesi 2026 tutarına katılmaz", "2027'den geçerlidir" in KAYIT[160][2]),
         ("organik 0,2-1,5 × 367", "73,40" in KAYIT[77][1] and "550,50" in KAYIT[77][1]),
         ("sera 367 + 623,90 = 990,90", "623,90" in KAYIT[79][1] and "990,90" in KAYIT[79][1]),
         ("her yeni kaynak kanıtta", all(v[0].split("#")[0] in json.dumps(kanit, ensure_ascii=False) for v in KAYIT.values())),
         ("her çağrının kaynağı kanıtta", all(c[5] in json.dumps(kanit, ensure_ascii=False) for c in CAGRILAR)),
         ("çağrı tarihleri tutarlı", all((c[2] is None or c[2] <= c[3]) and (c[4] is None or c[4] <= c[3]) for c in CAGRILAR)),
         ("kaynak bağlantıları tekil", len({v[0] for v in KAYIT.values()}) == len(KAYIT)),
         ("il kısıtı küçük harf, Türkçe", "şanlıurfa" in IL_KISITI[126] and "istanbul" in IL_KISITI[126]
          and len(IL_KISITI[126]) == 20)]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    from app.models import SessionLocal, settings
    if a.uygula and not YEDEK.exists():
        shutil.copy2(Path(settings.DATABASE_URL.replace("sqlite:///", "")), YEDEK)
        print(f"yedek: {YEDEK}")
    uygula(SessionLocal(), dry_run=not a.uygula)


if __name__ == "__main__":
    main()
