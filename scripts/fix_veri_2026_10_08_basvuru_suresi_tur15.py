"""Tur 15 — başvuru süresi boşlukları: 9903 yatırım teşvikleri, KGF kefalet paketleri, KOSGEB Küresel Rekabetçilik.

Ölçüm (docs/olcum/2026-10-08-persona/RAPOR.md): ilk 5 öneride en sık boş alan "başvuru süresi" idi; aktif 54 kayıtta boş.
Bu tur işletmelere dönük 34 kaydı doldurur (akademik TÜBİTAK çağrıları ve KOSGEB 5/6 kapsam dışı).

Kaynaklar (2026-10-08'de okundu; alıntılar docs/olcum/2026-10-08-basvuru-suresi/kanit.json):
  9903 sayılı Yatırımlarda Devlet Yardımları Hakkında Karar (yatirimadestek.gov.tr PDF): m.5/5 "31/12/2030 tarihine
  kadar yapılacak olan teşvik belgesi müracaatları değerlendirilir", m.5/6 müracaattan önceki harcama kapsam dışı,
  m.5/12 belge E-TUYS üzerinden, m.8/3-4 Stratejik Hamle ön değerlendirmesi.
  KGF ürün sayfaları (28 sayfa): yalnız Girişimci Destek Programı Kredi Faiz Programında "Kredi Son Kullandırım Tarihi:
  31.12.2028"; diğerlerinde başvuru/kullandırım son tarihi YOK. KOSGEB'e bağlı paketlerde "Özel Şartlar": önce KOSGEB
  programı onayı. 137: "Başvurular bankalar kanalıyla kefalet.kgf.com.tr üzerinden ... Kefaletten yararlanma süresi
  KGF'nin kefalet tahsis tarihinden itibaren 1 yıldır." 152: TÜBİTAK desteğine hak kazanan proje, doğrudan KGF'ye.
Son tarih yazılmayan yerde tarih uydurulmaz: "sayfada belirtilmemiş, bankadan teyit edin" denir.

Ayrıca çağrı satırları (tesvik_cagrilari): 9903'ün 5 programına "teşvik belgesi müracaat süresi" (kapanış 31.12.2030)
ve KGF İstihdam Koruma paketine (142) KOSGEB İstihdamı Koruma 2026-2 dönemi (31.10.2026; KOSGEB sayfasında canlı
doğrulandı 2026-10-08, docs/olcum/2026-10-08-persona/RAPOR.md).

Idempotent: basvuru_suresi doluysa kayıt atlanır (üzerine yazılmaz); çağrı (tesvik_id, ad) varsa atlanır.

    python scripts/fix_veri_2026_10_08_basvuru_suresi_tur15.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_basvuru_suresi_tur15.py --uygula
    python scripts/fix_veri_2026_10_08_basvuru_suresi_tur15.py --self-test
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

NOT = "Tur15 2026-10-08"
KANIT = KOK / "docs/olcum/2026-10-08-basvuru-suresi/kanit.json"
KARAR_9903 = "https://www.yatirimadestek.gov.tr/pdf/assets/upload/dosyalar/karar-yatirim_tesvik_uygulamalari.pdf"
KOSGEB_7 = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9224/istihdami-koruma-destek-programi"

S_9903 = ("Dönem yok: teşvik belgesi müracaatı E-TUYS üzerinden yapılır ve 31/12/2030 tarihine kadar yapılan müracaatlar "
          "değerlendirilir (9903 sayılı Karar m.5/5, m.5/12). Müracaat tarihinden önce yapılan yatırım harcamaları belge "
          "kapsamına alınmaz (m.5/6): harcamaya başlamadan önce başvurun.")
S_9903_STRATEJIK = S_9903 + (" Stratejik Hamle'de müracaat önce Genel Müdürlükçe ön değerlendirmeye alınır; uygun bulunan "
                             "projeler fizibilite için kalkınma ve yatırım bankasına iletilir (m.8/3-4).")
S_KGF_BANKA = ("Dönemsel başvuru yok: kredi başvurusu ürünün kredi veren bankasına yapılır, KGF kefaletini banka talep eder. "
               "KGF ürün sayfasında son başvuru/kullandırım tarihi belirtilmemiştir (2026-10-08); paketin hâlâ "
               "kullandırımda olduğunu bankadan teyit edin.")


def s_kosgeb(program: str, ek: str = "") -> str:
    return (f"Önce KOSGEB {program} başvurusunun KOSGEB'ce onaylanması gerekir (KGF ürün sayfası, Özel Şartlar); KOSGEB "
            f"başvuruları dönemsel çağrıyla alınır. Onaydan sonra kredi, KOSGEB ile protokollü bankaya başvurularak "
            f"kullanılır.{ek}")


SURELER: dict[int, str] = {
    177: S_9903, 178: S_9903, 179: S_9903_STRATEJIK, 180: S_9903, 181: S_9903,
    81: s_kosgeb("Kapasite Geliştirme Destek Programı"),
    107: s_kosgeb("Küresel Rekabetçilik Destek Programı"),
    125: s_kosgeb("KOBİ Dijital Dönüşüm Destek Programı"),
    142: s_kosgeb("İstihdamı Koruma Destek Programı", " 2026-2 dönemi KOSGEB'de 31.10.2026'da kapanır."),
    170: s_kosgeb("Girişimci Destek Programı (İş Geliştirme Desteği)", " Kredi son kullandırım tarihi: 31.12.2028."),
    137: ("Dönemsel başvuru yok: başvurular bankalar kanalıyla kefalet.kgf.com.tr üzerinden yapılır. Kefaletten "
          "yararlanma süresi, KGF'nin kefalet tahsis tarihinden itibaren 1 yıldır."),
    152: ("Dönemsel başvuru yok: projesi TÜBİTAK tarafından desteklenmeye hak kazandıktan sonra, transfer ödemesi için "
          "doğrudan KGF'ye başvurulur (KGF TÜBİTAK transfer ödemeleri kefalet sayfası)."),
    9: ("Dönemsel: başvurular KOSGEB'in duyurduğu proje teklif çağrısı döneminde KOSGEB KOBİ Bilgi Sistemi (KBS) "
        "üzerinden alınır; dönem tarihleri çağrı duyurusunda ilan edilir (bkz. başvuru dönemleri)."),
    **{i: S_KGF_BANKA for i in (86, 87, 89, 90, 91, 93, 112, 116, 122, 126, 133, 138, 146, 149, 153, 159, 168, 169,
                                171, 172, 173)},
}

CAGRILAR = [
    *[(i, "9903 teşvik belgesi müracaat süresi", None, date(2030, 12, 31), f"{KARAR_9903}#madde-5",
       "Karar m.5/5: 31/12/2030 tarihine kadar yapılan müracaatlar değerlendirilir; müracaattan önceki harcama kapsam dışı "
       "(m.5/6).") for i in (177, 178, 179, 180, 181)],
    (142, "KOSGEB İstihdamı Koruma 2026-2 dönemi", date(2026, 9, 1), date(2026, 10, 31), KOSGEB_7,
     "Kredi kefaleti için önce KOSGEB programı onayı gerekir; bu dönemde yalnız Finansman Desteği kapsamında başvuru alınır."),
]
DOGRULAMA = date(2026, 10, 8)


def uygula(db, dry_run: bool = True) -> dict:
    say = {"sure": 0, "cagri": 0, "atlanan": 0}
    for tid, metin in SURELER.items():
        t = db.get(Tesvik, tid)
        if t is None or not t.aktif_mi:
            raise SystemExit(f"[{tid}] kayıt yok ya da pasif; durduruldu")
        if t.basvuru_suresi and t.basvuru_suresi.strip():
            say["atlanan"] += 1
            continue
        print(f"[{tid}] {t.baslik[:55]}\n      → {metin[:140]}")
        if not dry_run:
            t.basvuru_suresi = metin
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: başvuru süresi resmi kaynaktan ({t.kaynak_url.split('#')[0]}); alıntı "
                f"docs/olcum/2026-10-08-basvuru-suresi/kanit.json")
        say["sure"] += 1
    for tid, ad, acilis, kapanis, kaynak, notlar in CAGRILAR:
        if db.query(TesvikCagrisi).filter(TesvikCagrisi.tesvik_id == tid, TesvikCagrisi.ad == ad).first():
            say["atlanan"] += 1
            continue
        print(f"[{tid}] çağrı '{ad}': {acilis} – {kapanis}")
        if not dry_run:
            db.add(TesvikCagrisi(tesvik_id=tid, ad=ad, acilis=acilis, kapanis=kapanis, kaynak_url=kaynak,
                                 dogrulama_tarihi=DOGRULAMA, notlar=notlar))
        say["cagri"] += 1
    if not dry_run:
        db.commit()
    return say


def _self_test() -> int:
    k_ = json.loads(KANIT.read_text(encoding="utf-8"))
    kgf = {int(i) for i in k_["kgf"]}
    kgf_sureli = {i for i, v in k_["kgf"].items() if v["tarih_ifadeleri"]}
    k = [
        ("34 kayıt", len(SURELER) == 34),
        ("KGF kayıtlarının hepsi kanıtta", {i for i in SURELER if i not in (177, 178, 179, 180, 181, 9)} == kgf),
        ("tarih yalnız kaynağında tarih olan KGF kaydında (170)", kgf_sureli == {"170"}
         and all("31.12.2028" not in m for i, m in SURELER.items() if i != 170)),
        ("9903 alıntıları kanıtta birebir", "31/12/2030" in k_["9903"]["m.5/5"] and "kapsamına alınmaz" in k_["9903"]["m.5/6"]
         and "ön değerlendirmeye" in k_["9903"]["m.8/3"]),
        ("tarihsiz KGF metni teyit uyarısı taşır", "teyit edin" in S_KGF_BANKA and "belirtilmemiştir" in S_KGF_BANKA),
        ("çağrılar: 5 adet 9903 (31.12.2030) + 142", sorted(c[0] for c in CAGRILAR) == [142, 177, 178, 179, 180, 181]
         and all(c[3] == date(2030, 12, 31) for c in CAGRILAR if c[0] != 142)),
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
