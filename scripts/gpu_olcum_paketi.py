"""GPU'lu kiralık sunucuda model ölçümü için kamuya açık veritabanı kopyası (2026-10-12).

Kiralık sunucuya yalnız teşvik kayıtları gider: kullanıcı, kuruluş, profil, soru geçmişi, başvuru takibi, İKAS
bağlantısı, oturum belirteci ve çilek modülü tabloları kopyada BOŞALTILIR (şema kalır, uygulama açılabilir).
Kaynak veritabanına dokunulmaz. Çıktı git dışındadır (data/ .gitignore'da).

    python scripts/gpu_olcum_paketi.py                 (data/tesvikler_kamu.db üretir ve denetler)
    python scripts/gpu_olcum_paketi.py --self-test

Kiralık sunucuya kopyalama ve ölçüm adımları: docs/olcum/2026-10-11-ozel-model/GPU_TALIMATI.md
"""
import shutil
import sqlite3
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "data/tesvikler.db"
HEDEF = KOK / "data/tesvikler_kamu.db"
# Kişisel ya da kuruluşa ait veri taşıyan tablolar (ön ek "cilek_" ayrıca boşaltılır).
KISISEL = ("users", "organizations", "financial_profiles", "queries", "basvuru_takipleri", "ikas_baglanti",
           "hesap_belirtecleri")
# Ölçümün okuduğu kamu tabloları; kopyada dolu olmaları beklenir.
KAMU = ("tesvikler", "tesvik_cagrilari", "kurum_iletisim", "il_kosgeb_mudurlugu", "il_tarim_mudurlugu")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def bosaltilacaklar(baglanti) -> list[str]:
    tablolar = [t for (t,) in baglanti.execute("select name from sqlite_master where type='table'")]
    return [t for t in tablolar if t in KISISEL or t.startswith("cilek_")]


def hazirla(kaynak: Path = KAYNAK, hedef: Path = HEDEF) -> dict:
    """Kaynağı kopyalar, kişisel tabloları boşaltır, VACUUM eder; tablo başına satır sayısını döndürür."""
    shutil.copy2(kaynak, hedef)
    b = sqlite3.connect(hedef)
    try:
        for t in bosaltilacaklar(b):
            b.execute(f'DELETE FROM "{t}"')
        b.commit()
        b.execute("VACUUM")
        return {t: b.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                for (t,) in b.execute("select name from sqlite_master where type='table'")}
    finally:
        b.close()


def denetle(sayilar: dict) -> list[str]:
    """Kişisel tabloda satır kaldıysa ya da kamu tablosu boşsa sorun listesi."""
    sorunlar = [f"{t}: {n} satır kaldı" for t, n in sayilar.items()
                if (t in KISISEL or t.startswith("cilek_")) and n]
    sorunlar += [f"{t}: boş" for t in KAMU if not sayilar.get(t)]
    return sorunlar


def _self_test() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        kaynak, hedef = Path(d) / "k.db", Path(d) / "h.db"
        b = sqlite3.connect(kaynak)
        for t in (*KISISEL, *KAMU, "cilek_parseller", "macro_indicators"):
            b.execute(f'CREATE TABLE "{t}" (id INTEGER, deger TEXT)')
            b.execute(f'INSERT INTO "{t}" VALUES (1, "x")')
        b.commit()
        b.close()
        sayilar = hazirla(kaynak, hedef)
        b = sqlite3.connect(kaynak)
        kaynak_sayi = b.execute("select count(*) from users").fetchone()[0]
        b.close()                        # Windows: açık bağlantı geçici klasörün silinmesini engeller
        k = [("kişisel tablolar boşaltılır", all(sayilar[t] == 0 for t in KISISEL) and sayilar["cilek_parseller"] == 0),
             ("kamu tabloları korunur", all(sayilar[t] == 1 for t in KAMU) and sayilar["macro_indicators"] == 1),
             ("kaynağa dokunulmaz", kaynak_sayi == 1),
             ("denetim temiz kopyada boş", denetle(sayilar) == []),
             ("denetim kalan kişisel satırı yakalar", denetle({**sayilar, "users": 3}) == ["users: 3 satır kaldı"])]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    sayilar = hazirla()
    sorunlar = denetle(sayilar)
    for t in sorted(sayilar):
        print(f"  {t:32} {sayilar[t]}")
    print(f"\n{HEDEF} ({HEDEF.stat().st_size // 1024} KB)")
    if sorunlar:
        print("SORUN:", "; ".join(sorunlar))
        HEDEF.unlink()
        sys.exit(1)
    print("Kişisel tablolar boş; kamu tabloları dolu. Kiralık sunucuya yalnız bu dosyayı kopyalayın.")
