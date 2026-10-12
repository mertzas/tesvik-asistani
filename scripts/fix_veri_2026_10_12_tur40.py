"""Tur 40 — tur38'in eklediği KKYDP kaydının (Tebliğ 2026/9 + 2026/10) mevcut kayıtlara birleştirilmesi (2026-10-12).

Tur38 "kaynak dışı" sanılan KKYDP'yi yeni kayıt olarak ekledi; oysa kayıt 78 (KKYP, Tebliğ 2026/9) ve kayıt 80 (TSS,
Tebliğ 2026/10) aynı programlardır (app/tarim_destek_2026.py bu kimliklere bağlı). Kopya kayıt aramada asıl kaydı
geride bıraktı (eski-30 senaryo 1: traktör/KKYP sorusunda %50-%70 ve 30 milyon TL kayboldu). Bu betik:
  * kopya kaydın (başlığı "Kırsal Kalkınma Yatırım Programı (KKYDP) - 2026") doğrulanmış kontrol maddelerini böler:
    tasarruflu/bireysel sulama maddeleri (Tebliğ 2026/10) → 80, diğerleri → 78;
  * iki çağrıyı (2026/9 → 78, 2026/10 → 80) taşır;
  * 78/80'in başvuru süresi metnini uzatmayla günceller (ilk ilan 12 Haziran; süre 30 Haziran 2026'ya uzatıldı —
    çağrının resmî kaynağı, tur38'de birebir doğrulandı);
  * kopya kaydı siler; tur38 kayıt dosyası docs/olcum/2026-10-12-tur38/birlesen/ altına taşınır ki tur38 yeniden
    çalıştırılınca kayıt geri gelmesin.

    python scripts/fix_veri_2026_10_12_tur40.py               (dry-run)
    python scripts/fix_veri_2026_10_12_tur40.py --uygula      (yedek: tesvikler_oncesi_tur40.db.bak)
    python scripts/fix_veri_2026_10_12_tur40.py --self-test
"""
import re
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur40.db.bak"
KAYIT = KOK / "docs/olcum/2026-10-12-tur38/kayit/kkydp-kirsal-kalkinma-yatirimlari.json"
BIRLESEN = KOK / "docs/olcum/2026-10-12-tur38/birlesen"
KOPYA_BASLIK = "Kırsal Kalkınma Yatırım Programı (KKYDP) - 2026"
KKYP, TSS = 78, 80
SULAMA = re.compile(r"sulama|20260403-10", re.I)
SURE = ("2026 başvuru dönemi 29 Nisan – 30 Haziran 2026 saat 23:59 (kapandı; ilk ilan 12 Haziran'dı, süre "
        "30 Haziran'a uzatıldı); yıllık çağrı.")
NOT = ("Tur40 2026-10-12: tur38'in kopya KKYDP kaydı bu kayda birleştirildi (doğrulanmış kontrol maddeleri ve 2026 "
       "çağrısı); başvuru süresi 30/6/2026'ya uzatılmıştı.")


def bol(maddeler: list[dict]) -> tuple[list[dict], list[dict]]:
    """Kontrol maddelerini (KKYP, TSS) olarak ayırır: metni ya da kaynağı tasarruflu sulamaya (Tebliğ 2026/10)
    ait olanlar TSS'ye."""
    kkyp, tss = [], []
    for m in maddeler:
        (tss if SULAMA.search(f"{m.get('metin', '')} {m.get('kaynak_url', '')}") else kkyp).append(m)
    return kkyp, tss


def sure_metni(eski: str) -> str:
    """"29 Nisan – 12 Haziran 2026 saat 23:59 (kapandı); yıllık çağrı." kısmını uzatılmış süreyle değiştirir,
    geri kalanı (uygulama yılı, başvuru adresi, tebliğ) korur."""
    yeni = re.sub(r"^2026 başvuru dönemi 29 Nisan – 12 Haziran 2026 saat 23:59 \(kapandı\); yıllık çağrı\.", SURE, eski)
    return yeni


def birlestir(db, uygula: bool) -> int:
    from app.models import BasvuruTakibi, Tesvik, TesvikNace
    kopya = db.query(Tesvik).filter(Tesvik.baslik.startswith(KOPYA_BASLIK)).all()
    if not kopya:
        print("kopya KKYDP kaydı yok (zaten birleştirilmiş)")
        return 0
    assert len(kopya) == 1, [k.id for k in kopya]
    k = kopya[0]
    hedef = {KKYP: db.get(Tesvik, KKYP), TSS: db.get(Tesvik, TSS)}
    assert "KKYP" in hedef[KKYP].baslik and "TSS" in hedef[TSS].baslik, "78/80 beklenen kayıtlar değil"
    m78, m80 = bol(k.kontrol_listesi or [])
    print(f"kopya: {k.id} {k.baslik[:80]}")
    print(f"  {len(m78)} madde → {KKYP}, {len(m80)} madde → {TSS}")
    for c in k.cagrilar:
        h = TSS if SULAMA.search(c.ad) else KKYP
        print(f"  çağrı {c.id} '{c.ad[:60]}' ({c.acilis} – {c.kapanis}) → {h}")
    for i, t in hedef.items():
        print(f"  {i} başvuru süresi: {sure_metni(t.basvuru_suresi)[:120]}")
    takip = db.query(BasvuruTakibi).filter(BasvuruTakibi.tesvik_id == k.id).count()
    print(f"  başvuru takibi bağlı: {takip}")
    if takip:
        print("HATA: kopya kayda bağlı başvuru takibi var; birleştirme elle yapılmalı")
        return 1
    if not uygula:
        print("dry-run: --uygula ile yazılır")
        return 0
    from app.models import settings
    if not YEDEK.exists():
        shutil.copy2(Path(settings.DATABASE_URL.replace("sqlite:///", "")), YEDEK)
        print(f"yedek: {YEDEK}")
    for i, maddeler in ((KKYP, m78), (TSS, m80)):
        t = hedef[i]
        mevcut = {m.get("metin") for m in t.kontrol_listesi or []}
        t.kontrol_listesi = list(t.kontrol_listesi or []) + [m for m in maddeler if m.get("metin") not in mevcut]
        t.basvuru_suresi = sure_metni(t.basvuru_suresi)
        t.basvuru_bicimi = t.basvuru_bicimi or k.basvuru_bicimi
        if NOT not in (t.durum_notu or ""):
            t.durum_notu = f"{t.durum_notu} | {NOT}" if t.durum_notu else NOT
    for c in list(k.cagrilar):
        c.tesvik_id = TSS if SULAMA.search(c.ad) else KKYP
    db.flush()
    db.query(TesvikNace).filter(TesvikNace.tesvik_id == k.id).delete()
    db.expire(k)
    db.delete(k)
    db.commit()
    if KAYIT.exists():
        BIRLESEN.mkdir(exist_ok=True)
        shutil.move(str(KAYIT), BIRLESEN / KAYIT.name)
        print(f"kayıt dosyası taşındı: {BIRLESEN / KAYIT.name}")
    print(f"birleştirildi; {k.id} silindi")
    return 0


def _self_test() -> int:
    maddeler = [
        {"metin": "Hibeye esas proje tutarı üst limiti 30.000.000 TL.", "kaynak_url": "https://x/20260403-9.htm"},
        {"metin": "Tasarruflu sulama: damla sulama %50.", "kaynak_url": "https://x/20260403-10.htm"},
        {"metin": "Bireysel sulama: Su Kullanım İzin Belgesi şart", "kaynak_url": "https://il.tarimorman.gov.tr/a"},
        {"metin": "Kamera sistemleri hibe kapsamında değil.", "kaynak_url": "https://x/files"},
    ]
    a, b = bol(maddeler)
    eski = ("2026 başvuru dönemi 29 Nisan – 12 Haziran 2026 saat 23:59 (kapandı); yıllık çağrı. Uygulama yılı "
            "1/1/2026–31/12/2026; başvuru tss.tarimorman.gov.tr (Tebliğ 2026/10, RG 3/4/2026)")
    k = [
        ("sulama maddeleri TSS'ye, diğerleri KKYP'ye", [m["metin"][:5] for m in a] == ["Hibey", "Kamer"] and len(b) == 2),
        ("başvuru süresi uzatmayla güncellenir", "30 Haziran 2026" in sure_metni(eski) and "12 Haziran 2026 saat" not in
         sure_metni(eski)),
        ("süre metninin geri kalanı korunur", sure_metni(eski).endswith("(Tebliğ 2026/10, RG 3/4/2026)")),
        ("bilinmeyen süre metni değişmez", sure_metni("Sürekli") == "Sürekli"),
        ("çağrı yönlendirme", bool(SULAMA.search("Tasarruflu Tarımsal Sulama Sistemleri / bireysel sulama"))
         and not SULAMA.search("KKYDP 2026 Başvuru Dönemi (Tebliğ No: 2026/9; ekonomik yatırımlar)")),
        ("yedek ve kayıt yolu", YEDEK.name == "tesvikler_oncesi_tur40.db.bak" and KAYIT.parent.parent.name
         == "2026-10-12-tur38"),
    ]
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
    from app.models import SessionLocal
    db = SessionLocal()
    try:
        sys.exit(birlestir(db, "--uygula" in sys.argv))
    finally:
        db.close()
