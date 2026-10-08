"""Tur 16 — boş şart / belge / başvuru yeri / başvuru süresi alanları, resmi kaynaktan (2026-10-08).

Ölçüm: aktif kayıtlarda en sık boşluklar tarım şart listeleri (76, 77, 79), KGF başvuru yerleri (kredi veren bankalar),
KOSGEB 4-6 başvuru yeri, akademik/bilim-toplum TÜBİTAK çağrılarının başvuru süresi. Alıntılar ve kaynak adresleri:
docs/olcum/2026-10-08-tur16/kanit.json (her alıntı indirilen kaynak metninde birebir denetlendi).

Kaynaklar:
  Hayvancılık Desteklemeleri Uygulama Tebliği (Tebliğ No 2024/23), RG 17.08.2024 — 2024-2026 Hayvancılık
    Desteklemelerine İlişkin Karar'a dayanır (m.4/1, m.4/3-a, m.6/1).
  2025-2027 Bitkisel Üretime Yönelik Desteklemeler … Tebliğ (Tebliğ No 2024/39) — m.3, m.7/3, m.7/4, m.8/1, m.15/1, m.17.
  KGF ürün sayfaları ("İlgili Finans Kuruluşları"), KOSGEB program sayfaları, TÜBİTAK program sayfaları ("Başvuru
    Tarihleri" bölümü ve duyurular).
Kural: yalnız BOŞ alan doldurulur (dolu alanın üzerine yazılmaz); kaynakta tarih yoksa tarih yazılmaz.

Bulgu (bu tur değiştirmez, raporlanır): 26 ve 50 (2223-D Türkiye-Birleşik Krallık / Katip Çelebi-Newton) sayfalarındaki
tek başvuru dönemi 16.05–24.06.2016, etkinlik son tarihi 31.12.2017 — program büyük olasılıkla sona ermiş; 79 Sera
kaydının açıklaması "kurulum hibesi" diyor ama tutarı dekar bazlı üretim desteğine dayanıyor.

    python scripts/fix_veri_2026_10_08_sart_yer_sure_tur16.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_sart_yer_sure_tur16.py --uygula
    python scripts/fix_veri_2026_10_08_sart_yer_sure_tur16.py --self-test
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

NOT = "Tur16 2026-10-08"
KANIT = KOK / "docs/olcum/2026-10-08-tur16/kanit.json"
T23, T39 = "Tebliğ 2024/23", "Tebliğ 2024/39"


def banka(liste: str, ek: str = "") -> str:
    return f"Kredi veren banka(lar): {liste} (KGF ürün sayfası, İlgili Finans Kuruluşları){ek}"


# alan -> {kayıt id: değer}; liste alanları JSON listesi olarak yazılır
VERI: dict[str, dict[int, object]] = {
    "basvuru_sartlari": {
        76: [f"Buzağı/malak: TÜRKVET'te kayıtlı ve destekleme yılında Türkiye'de doğmuş olması ({T23} m.4/1-a)",
             f"Buzağı/malak: TÜRKVET kayıtlarına göre en az 4 ay (120 gün) yaşamış olması ({T23} m.4/1-b)",
             f"Buzağı/malak: programlı aşıları (dişilerde brusella ve şap, erkeklerde şap) yapılmış ve VETBİS'e kaydedilmiş "
             f"olması ({T23} m.4/1-c)",
             f"Kuzu/oğlak: destekleme yılında doğmuş, küpelenmiş, TÜRKVET'e kayıtlı ve doğduğu işletmede en az 120 gün "
             f"yaşamış olması ({T23} m.6/1-a)",
             f"Kuzu/oğlak: yetiştiricinin damızlık koyun keçi yetiştiricileri birliğine üye olması (il birliği olmayan "
             f"illerde aranmaz) ({T23} m.6/1-c)"],
        77: [f"Ürünlerin ilgili üretim yılında ÇKS ve OTBİS'te kayıtlı olması ({T39} m.7/3-a)",
             f"Arazinin yetkilendirilmiş kuruluşça kontrol edilmiş ve geçiş süreci-2, geçiş süreci-3 ya da organik statüde "
             f"olması; geçiş süreci-1 arazisi yararlanamaz ({T39} m.7/3-a-1, m.17/12)",
             f"Hasadın yapılmış ve ürün sertifikasının düzenlenmiş olması ({T39} m.7/3-a-2)",
             f"Organik desteği alan arazi aynı yıl iyi tarım uygulamaları desteğinden yararlanamaz ({T39} m.17/9)",
             f"OTBİS'teki bilgilerin tamamlanması çiftçinin sorumluluğundadır ({T39} m.7/3-ç)"],
        79: [f"Örtüaltı/kapalı ortam üretim yerinin ÖKS/KOBÜKS'te kayıtlı olması ({T39} m.3, m.8/1-a)",
             f"Destek türüne göre ek şart: iyi tarım uygulamaları desteğinde sertifikanın ÖKS/KOBÜKS'e kaydı ({T39} m.7/4-a); "
             f"biyolojik/biyoteknik mücadele desteğinde BKÜ faturası ve onaylı ÜKD kayıtları ({T39} m.8/1-b, c)"],
        116: ["Kooperatif ya da kooperatif birliği tüzel kişisi olmak: tarım satış kooperatifleri birlikleri, ecza üretim "
              "temin ve dağıtım kooperatifleri, kadın girişimi üretim ve işletme kooperatifleri birlikleri, üretim ve "
              "pazarlama kooperatifleri, küçük sanat kooperatifleri (KGF ürün sayfası)"],
        149: ["İmalat sektöründe faaliyet gösteren KOBİ olmak (KGF ürün sayfası)",
              "Kredi mevcut kredilerin refinansmanı içindir; asgari 6 ay anapara ödemesiz dahil asgari 24, azami 48 ay vade "
              "(KGF ürün sayfası)"],
    },
    "gerekli_belgeler": {
        77: [f"EK-3 Destekleme Ödemesi Başvuru Dilekçesi (ÇKS'de kayıtlı olunan il/ilçe müdürlüğüne; {T39} m.15/1)",
             f"Ürün sertifikası (yetkilendirilmiş kuruluşça düzenlenen; {T39} m.7/3-a-2)"],
        79: [f"EK-3 Destekleme Ödemesi Başvuru Dilekçesi (ÇKS ve/veya ÖKS/KOBÜKS'te kayıtlı olunan il/ilçe müdürlüğüne; "
             f"{T39} m.15/1)"],
        4: ["Teknoloji Merkezi Destek Programı Kuruluş Desteği Ön Başvuru Formu",
            "Teknoloji Merkezi Destek Programı Kuruluş Desteği Başvuru Formu"],
    },
    "basvuru_yeri": {
        89: banka("Halkbank"), 93: banka("Vakıfbank"), 112: banka("Halkbank"),
        116: banka("Ziraat Bankası, Vakıfbank, Halkbank"),
        133: banka("Halkbank, Vakıfbank, Ziraat Bankası, Ziraat Katılım, Denizbank, Yapı ve Kredi Bankası"),
        138: banka("Halkbank"), 146: banka("Akbank, Denizbank, QNB Finansbank, TEB, Yapı ve Kredi Bankası"),
        153: banka("Şekerbank"), 169: banka("Ziraat Bankası"),
        170: banka("Vakıfbank, Halkbank, Ziraat Bankası", "; önce KOSGEB Girişimci Destek Programı onayı"),
        171: banka("Ziraat Katılım Bankası"), 173: banka("Vakıfbank"),
        4: "KOSGEB'e Kuruluş Desteği Ön Başvuru Formu ve Başvuru Formu ile; kurucular münferiden ya da müştereken "
           "başvurur. Hızlandırma Desteği çağrı esaslıdır.",
        5: "KOSGEB sistemi (www.kosgeb.gov.tr) üzerinden YÖNDE başvuru formu ile",
        6: "www.kosgeb.gov.tr \"e-hizmetler\" menüsünden çevrim içi",
        51: "ARDEB Proje Başvuru Sistemi (ardeb-pbs.tubitak.gov.tr), ARBİS hesabıyla",
        67: "ARDEB Proje Başvuru Sistemi (ardeb-pbs.tubitak.gov.tr), e-imza ile",
        53: "TÜBİTAK Yönetim Bilgi Sistemi (tybs.tubitak.gov.tr), BİDEB yönlendirmesiyle",
        72: "BİDEB Başvuru ve İzleme Sistemi (e-bideb.tubitak.gov.tr)",
        74: "BİDEB Başvuru ve İzleme Sistemi (e-bideb.tubitak.gov.tr)",
        52: "bilimiz.tubitak.gov.tr",
        42: "bilimtoplum-pbs.tubitak.gov.tr",
    },
    "basvuru_suresi": {
        5: "Sayfada başvuru dönemi belirtilmemiştir. Başvurular en geç 15 gün içinde kontrol edilir; destek, başvurunun "
           "KOSGEB'ce onaylandığı tarihte başlar.",
        6: "Program sürekli olarak başvuruya açıktır (KOSGEB program sayfası).",
        14: "Dönem yok: program sürekli başvuruya açıktır; başvurular yılın herhangi bir iş gününde yapılabilir.",
        15: "Çağrı, TÜBİTAK ayrıca bir duyuru yapana kadar sürekli başvuruya açıktır.",
        18: "Çağrı, TÜBİTAK ayrıca bir duyuru yapana kadar sürekli başvuruya açıktır.",
        39: "Başvurular sürekli açıktır, yılın her günü PRODİS (eteydeb.tubitak.gov.tr) üzerinden; çağrılı uluslararası "
            "programlarda proje, ilgili çağrının değerlendirme takvimine uygun sunulmalıdır.",
        51: "Belirli bir zaman aralığı yok; başvuru tarihleri çağrı kapsamında ilan edilir.",
        67: "Dönemsel: 2026 yılı 2. dönemi 29 Temmuz – 14 Eylül 2026 (çevrim içi başvuru ve e-imza son günü 14 Eylül 2026) "
            "kapandı; sonraki dönem TÜBİTAK duyurusuyla açılır.",
        26: "Sayfadaki tek başvuru dönemi 16 Mayıs – 24 Haziran 2016; güncel çağrı bulunmuyor (TÜBİTAK sayfası, 2026-10-08).",
        50: "Sayfadaki tek başvuru dönemi 16 Mayıs – 24 Haziran 2016 (etkinlikler 31 Aralık 2017'ye kadar); güncel çağrı "
            "bulunmuyor (TÜBİTAK sayfası, 2026-10-08).",
        53: "Çağrı esaslı: başvurular çağrı duyurusunda belirtilen tarihler içinde yapılır.",
        72: "Çağrı esaslı: başvurular çağrı duyurusunda belirtilen tarihler içinde; etkinlik başlangıcı son başvuru "
            "tarihinden en az 60, en çok 270 gün sonra olmalıdır.",
        74: "Etkinlik bazlı çağrılar: son çağrı (76. Lindau Nobel Ödüllü Bilim İnsanları Toplantısı) başvuruları 7 Eylül'de "
            "açıldı, uzatmayla 29 Eylül 2026 17:30'da kapandı; yeni çağrılar program sayfasında duyurulur.",
        52: "13. dönem (2026) 4006-A ve 4006-B çağrıları açık: başvurular 13 Kasım 2026 saat 17:30'a kadar.",
        42: "Açık çağrı: 3. dönem başvuruları sürüyor (TÜBİTAK sayfası, 2026-10-08); son tarih sayfada belirtilmemiştir.",
        59: "Çağrı esaslı: Türkiye Yeşil Sanayi Projesi süresince TÜBİTAK farklı türde çağrılar açar; sayfada güncel "
            "çağrı tarihi yoktur.",
        13: "Çağrı esaslı: başvuru tarihleri yıllık çağrı metninde ilan edilir (sayfada 4007 Çağrı Metni 2026 yayımlı).",
        16: "Çağrı esaslı: TÜBİTAK'ın yayımlayacağı çağrıya başvurulur; sayfadaki son çağrılar 2018 ve 2021 yıllarına ait.",
        49: "Çağrı esaslı: başvurular uygulayıcı kuruluşların çağrıları üzerinden (BiGG Yatırım 2026-2 çağrı metni "
            "yayımlı; bkz. başvuru dönemleri).",
        54: "Çağrı esaslı: kamu kurumlarının ihtiyaçlarından belirlenen çağrılar TÜBİTAK internet sayfasında duyurulur.",
    },
}

# (tesvik_id, ad, açılış, kapanış, kanıt anahtarı, not)
CAGRILAR = [
    (67, "2026 yılı 2. dönem", date(2026, 7, 29), date(2026, 9, 14), "tubitak_67",
     "Çevrim içi başvuru ve e-imza son günü 14 Eylül 2026; PBS üzerinden."),
    (74, "76. Lindau Nobel Ödüllü Bilim İnsanları Toplantısı", date(2026, 9, 7), date(2026, 9, 29), "tubitak_74",
     "Başvuru uzatıldı (duyuru 24.09.2026); kapanış saati 17:30."),
    (52, "13. dönem (2026) 4006-A ve 4006-B", None, date(2026, 11, 13), "tubitak_52", "Kapanış saati 17:30; bilimiz.tubitak.gov.tr."),
]
KANIT_ANAHTARI = {76: "teblig_2024_23", 77: "teblig_2024_39", 79: "teblig_2024_39"}


def _kanit_anahtari(tid: int, kurum: str) -> str:
    if tid in KANIT_ANAHTARI:
        return KANIT_ANAHTARI[tid]
    return {"KGF": "kgf", "KOSGEB": "kosgeb", "TUBITAK": "tubitak"}[kurum] + f"_{tid}"


def _bos(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v)


def uygula(db, dry_run: bool = True) -> dict:
    kanit = json.loads(KANIT.read_text(encoding="utf-8"))["kaynaklar"]
    say = {"alan": 0, "cagri": 0, "atlanan": 0}
    for alan, kayitlar in VERI.items():
        for tid, deger in kayitlar.items():
            t = db.get(Tesvik, tid)
            if t is None or not t.aktif_mi:
                raise SystemExit(f"[{tid}] kayıt yok ya da pasif; durduruldu")
            if not _bos(getattr(t, alan)):
                say["atlanan"] += 1
                continue
            k = kanit[_kanit_anahtari(tid, t.kurum)]
            print(f"[{tid}] {alan}: {str(deger)[:120]}")
            if not dry_run:
                setattr(t, alan, deger)
                t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                    f"{NOT}: {alan} resmi kaynaktan ({k['url']}); alıntı docs/olcum/2026-10-08-tur16/kanit.json")
            say["alan"] += 1
    for tid, ad, acilis, kapanis, anahtar, notlar in CAGRILAR:
        if db.query(TesvikCagrisi).filter(TesvikCagrisi.tesvik_id == tid, TesvikCagrisi.ad == ad).first():
            say["atlanan"] += 1
            continue
        print(f"[{tid}] çağrı '{ad}': {acilis} – {kapanis}")
        if not dry_run:
            db.add(TesvikCagrisi(tesvik_id=tid, ad=ad, acilis=acilis, kapanis=kapanis, kaynak_url=kanit[anahtar]["url"],
                                 dogrulama_tarihi=date(2026, 10, 8), notlar=notlar))
        say["cagri"] += 1
    if not dry_run:
        db.commit()
    return say


def _self_test() -> int:
    k_ = json.loads(KANIT.read_text(encoding="utf-8"))["kaynaklar"]
    kurum = {i: ("KGF" if i in (89, 93, 112, 116, 133, 138, 146, 149, 153, 169, 170, 171, 173) else
                 "KOSGEB" if i in (4, 5, 6) else "TUBITAK") for alan in VERI.values() for i in alan}
    eksik_kanit = [i for i, kr in kurum.items() if _kanit_anahtari(i, kr) not in k_]
    tum = " ".join(str(v) for alan in VERI.values() for v in alan.values())
    k = [
        ("her kayıt için kanıt kaynağı var", not eksik_kanit),
        ("tarım şartları tebliğ maddesiyle", all(("m." in s) for s in VERI["basvuru_sartlari"][76] + VERI["basvuru_sartlari"][77])),
        ("liste alanları liste, metin alanları metin", all(isinstance(v, list) for a in ("basvuru_sartlari", "gerekli_belgeler")
                                                           for v in VERI[a].values())
         and all(isinstance(v, str) for a in ("basvuru_yeri", "basvuru_suresi") for v in VERI[a].values())),
        ("kanıtta olmayan tarih yazılmadı", all(t in json.dumps(k_, ensure_ascii=False)
                                                for t in ("14 Eylül 2026", "13 Kasım 2026", "29 Eylül 2026", "16 Mayıs 2016"))),
        ("geçmiş çağrılar kapalı, 4006 açık", [c[3] < date(2026, 10, 8) for c in CAGRILAR] == [True, True, False]),
        ("sahte kesinlik yok: tarihsiz kaynaklarda 'belirtilmemiş'", "belirtilmemiştir" in VERI["basvuru_suresi"][5]
         and "belirtilmemiştir" in VERI["basvuru_suresi"][42] and "2028" not in tum),
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
