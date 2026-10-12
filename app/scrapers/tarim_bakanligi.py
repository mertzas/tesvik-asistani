"""
T.C. Tarım ve Orman Bakanlığı destek programlarının tohum verisi (yeni kurulum ve aylık zamanlanmış iş).

Tohum `app/data/tarim_bakanligi_tohum.json` dosyasındadır ve veritabanındaki DOĞRULANMIŞ kayıtlardan üretilir
(kaynak bağlantıları, alıntılı kontrol listeleri, 2026 tutarları: 8859 sayılı CB Kararı, 10394 ve 11781 sayılı
değişiklik Kararları; kanıt docs/olcum/2026-10-12-tur34/TARIM_2026_KANIT.md).

Neden JSON (persona denemesi 2026-10-12): elle yazılmış eski tohum listesi 310 TL'den kalma tutarlar ve kaynaksız iki
kayıt içeriyordu ("Tarımsal Makineleştirme Destekleri" — bireysel traktör hibesi vaadi, ₺50K-500K; "Sulama Yatırımı
Destekleri"). Bu iki kayıt veritabanında KKYP ve TSS olarak yeniden yazılmıştı; başlık + kurum eşleşmesine bakan
`run()` ayın 5'inde onları eski adlarıyla yeniden ekleyecekti. Artık tohum veritabanının doğrulanmış hâlidir.

Tohumu yeniden üretmek (veritabanı düzeltmesinden sonra):
    python -m app.scrapers.tarim_bakanligi --tohum-uret
Doğrulama:
    python -m app.scrapers.tarim_bakanligi --self-test
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

from app.models import SessionLocal, Tesvik, init_db

TOHUM = Path(__file__).resolve().parent.parent / "data" / "tarim_bakanligi_tohum.json"
ALANLAR = ("kurum", "baslik", "ozet", "detay", "hedef_kitle", "kaynak_url", "kategori", "baslama_tarihi",
           "bitis_tarihi", "tesvil_tutari", "uygunluk_kriterleri", "tutari_min", "tutari_max",
           "tutari_hesaplama_kriteri", "tutari_hesaplama_formulu", "basvuru_sartlari", "gerekli_belgeler",
           "basvuru_yeri", "basvuru_suresi", "destek_verilme_suresi", "kontrol_listesi", "basvuru_bicimi",
           "aktif_mi", "durum_notu")
# Yeniden adlandırılmış eski başlıklar: veritabanında bu adla kayıt yoksa bile EKLENMEZ (kaynaksız eski metinler).
ESKI_BASLIKLAR = ("Tarımsal Makineleştirme Destekleri", "Sulama Yatırımı Destekleri",
                  "Hububat ve Baklagil Üretim Destekleri (Mazot-Gübre)", "Meyve-Sebze Üretim Destekleri (Mazot-Gübre)")


def _yukle() -> list[dict]:
    return json.loads(TOHUM.read_text(encoding="utf-8"))


TARIM_BAKANLIGI_DESTEKLERI: list[dict] = _yukle()


def _tarih(x):
    return date.fromisoformat(x) if isinstance(x, str) else x


def tohum_uret(db) -> int:
    """Veritabanındaki Tarım Bakanlığı kayıtlarından tohum dosyasını yeniden yazar."""
    kayitlar = []
    for t in db.query(Tesvik).filter(Tesvik.kurum == "Tarım Bakanlığı").order_by(Tesvik.id).all():
        d = {a: getattr(t, a) for a in ALANLAR}
        for a in ("baslama_tarihi", "bitis_tarihi"):
            if d[a] is not None:
                d[a] = d[a].isoformat()
        kayitlar.append(d)
    TOHUM.write_text(json.dumps(kayitlar, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return len(kayitlar)


def run() -> int:
    """Tohumdaki programlardan veritabanında olmayanları ekler (başlık + kurum eşleşmesi). Var olanı DEĞİŞTİRMEZ:
    doğrulanmış kaynak ve tutar düzeltmeleri veri betikleriyle (scripts/fix_veri_*) yapılır."""
    init_db()
    db = SessionLocal()
    eklenen = 0
    for d in _yukle():
        if d["baslik"] in ESKI_BASLIKLAR:
            continue
        zaten_var = db.query(Tesvik).filter(Tesvik.baslik == d["baslik"], Tesvik.kurum == d["kurum"]).first()
        if zaten_var is not None:
            continue
        alanlar = {a: d.get(a) for a in ALANLAR}
        alanlar["baslama_tarihi"] = _tarih(alanlar["baslama_tarihi"])
        alanlar["bitis_tarihi"] = _tarih(alanlar["bitis_tarihi"])
        alanlar["kategori"] = alanlar["kategori"] or "tarim"
        db.add(Tesvik(**alanlar, guncelleme_tarihi=datetime.now()))
        eklenen += 1
    db.commit()
    db.close()
    print(f"Tarım Bakanlığı destekleri: {eklenen} yeni kayıt eklendi.")
    return eklenen


def _self_test() -> int:
    from app.tarim_destek_2026 import KATSAYI_BIRIM_TL
    t = _yukle()
    basliklar = {d["baslik"] for d in t}
    k = [("tohum dosyası okunur ve boş değil", len(t) >= 8),
         ("eski kaynaksız başlıklar tohumda yok", not basliklar & set(ESKI_BASLIKLAR)),
         ("her kayıtta kaynak bağlantısı", all(d.get("kaynak_url") for d in t)),
         ("aktif kayıtlarda 2026 birim değeriyle tutar (310 TL'den kalma metin yok)",
          not any("310 TL" in (d.get("tesvil_tutari") or "") for d in t if d.get("aktif_mi"))),
         ("birim değer 367", KATSAYI_BIRIM_TL == 367.0),
         ("ALANLAR Tesvik sütunlarında", all(hasattr(Tesvik, a) for a in ALANLAR))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    for akim in (sys.stdout, sys.stderr):
        akim.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--tohum-uret" in sys.argv:
        _db = SessionLocal()
        print(f"tohum: {tohum_uret(_db)} kayıt -> {TOHUM}")
        _db.close()
        sys.exit(0)
    run()
