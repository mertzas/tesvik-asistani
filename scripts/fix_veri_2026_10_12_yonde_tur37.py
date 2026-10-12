"""YÖNDE (kayıt 5) düzeltmesinin geri alınması (2026-10-12, tur37).

Tur35 (scripts/fix_veri_2026_10_12_persona_tur35.py) YÖNDE'yi kaydın `detay` alanındaki metne dayanarak "%80, 280.000 TL,
yalnız imalat küçük/orta, mikro yararlanamaz" diye daraltmıştı. 5. hakem turu kaydın durum notuyla çelişkiyi bildirdi
(Denetim2-T6 2026-10-07: "canlı sayfada imalat/ölçek şartı yok"). Resmî sayfa 2026-10-12 08:12'de yeniden çekildi
(docs/olcum/2026-10-12-tur34/kaynak/9ef78a8d785053a6.txt): "Destek Oranı: Geri ödemesiz olarak %100", "Program Üst
Limiti: Toplam 700.000 TL", yararlanıcı yalnız "Türk Ticaret Kanunu'na göre gerçek veya tüzel kişi statüsünde olan,
KOSGEB sisteminde kayıtlı ve aktif işletmeler"; dört hizmet (Bağımsız Değerlendirme dahil). `detay` eski sayfa
sürümünden kalmıştı. Bu betik tutar, üst limit, kriter ve kontrol listesini tur35 öncesi (canlı sayfayla aynı) değerlere
döndürür, `detay`ın program bölümünü canlı metinle değiştirir. Tur35 betiğinden YÖNDE kalemleri çıkarıldı.

Kullanım:
    python scripts/fix_veri_2026_10_12_yonde_tur37.py --self-test
    python scripts/fix_veri_2026_10_12_yonde_tur37.py            (kuru çalıştırma)
    python scripts/fix_veri_2026_10_12_yonde_tur37.py --uygula   (yedek: docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur37.db.bak)
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
KAYNAK = KOK / "docs" / "olcum" / "2026-10-12-tur34" / "kaynak" / "9ef78a8d785053a6.txt"
YEDEK_DIZIN = KOK / "docs" / "olcum" / "2026-10-07-denetim2"
URL = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9165/yonde-yonderlik-ve-degerlendirme-destek-programi"
TARIH = "2026-10-12"

TUTAR = ("%100 geri ödemesiz; program üst limiti toplam 700.000 TL; program süresi 36 ay. Hizmet başına/toplam üst "
         "limit: Dijital Dönüşüm Değerlendirme Analizi ve Yol Haritası 20.000/40.000 TL, Sürdürülebilirlik Raporlaması "
         "100.000/200.000 TL, Yalın Olgunluk Değerlendirme Analizi (YODA) 20.000/40.000 TL, Bağımsız Değerlendirme "
         "150.000/450.000 TL. Yazılım veya donanım alımı değil, belgeli danışmandan alınan hizmet desteklenir.")
# Canlı sayfada birebir geçmesi gereken ifadeler (self-test)
KANIT = ("Destek Oranı: Geri ödemesiz olarak %100", "Program Üst Limiti: Toplam 700.000 TL", "Program Süresi: 36 ay",
         "Türk Ticaret Kanunu'na göre gerçek veya tüzel kişi statüsünde olan, KOSGEB sisteminde kayıtlı ve aktif "
         "işletmeler.", "Hizmet başına üst limit 20.000 TL, program süresince toplam limit 40.000 TL'dir.",
         "Hizmet başına üst limit 100.000 TL, toplam limit 200.000 TL'dir.",
         "Hizmet başına üst limit 20.000 TL, toplam limit 40.000 TL'dir.",
         "Hizmet başına üst limit 150.000 TL, toplam limit 450.000 TL'dir.")
YANLIS = ("Mikro ölçekli işletmeler bu destekten yararlanamaz", "Kısım C - İmalat sektöründe")
ESKI_MADDE = "NACE Kısım C (imalat) sektöründe faaliyet gösteren"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


def canli_metin() -> str:
    return _norm(KAYNAK.read_text(encoding="utf-8"))


def detay_bolumu(metin: str) -> str:
    """Canlı sayfanın program bölümü: amaçtan Bağımsız Değerlendirme limitine kadar."""
    bas = metin.index("YÖNDE Destek Programı'nın amacı nedir?")
    son = metin.index("toplam limit 450.000 TL'dir.") + len("toplam limit 450.000 TL'dir.")
    return metin[bas:son]


def degisiklikler(t, metin: str) -> list[tuple[str, object, object]]:
    p = []
    yeni = {
        "tesvil_tutari": TUTAR,
        "tutari_max": 700000.0,
        "uygunluk_kriterleri": {"sektorler": ["genel"]},
        "kontrol_listesi": [m for m in (t.kontrol_listesi or []) if not (m.get("metin") or "").startswith(ESKI_MADDE)],
        "detay": detay_bolumu(metin),
    }
    for alan, deger in yeni.items():
        if getattr(t, alan) != deger:
            p.append((alan, getattr(t, alan), deger))
    return p


def uygula(yaz: bool) -> int:
    from app.models import SessionLocal, Tesvik
    metin = canli_metin()
    db = SessionLocal()
    try:
        t = db.get(Tesvik, 5)
        assert t is not None and "YÖNDE" in t.baslik, "kayıt 5 YÖNDE değil"
        d = degisiklikler(t, metin)
        for alan, eski, yeni in d:
            print(f"{alan}:\n  eski: {str(eski)[:160]}\n  yeni: {str(yeni)[:160]}")
        print(f"{len(d)} alan {'güncellenecek' if not yaz else 'güncellendi'}")
        if yaz and d:
            from app.models import engine
            db_yolu = Path(engine.url.database)
            yedek = YEDEK_DIZIN / "tesvikler_oncesi_tur37.db.bak"
            if not yedek.exists():
                shutil.copy2(db_yolu, yedek)
                print(f"yedek: {yedek}")
            for alan, _, yeni in d:
                setattr(t, alan, yeni)
            t.durum_notu = (t.durum_notu or "") + (
                f" | Tur37 {TARIH}: tur35'teki imalat/küçük-orta/mikro hariç daraltması ve %80/280.000 TL geri alındı; "
                f"canlı sayfa ({URL}, 2026-10-12 08:12): %100 geri ödemesiz, toplam 700.000 TL, sektör/ölçek şartı yok; "
                "detay eski sayfa sürümündendi, canlı metinle değiştirildi (kanıt docs/olcum/2026-10-12-tur34/kaynak/"
                "9ef78a8d785053a6.txt)")
            db.commit()
        return 0
    finally:
        db.close()


def self_test() -> int:
    metin = canli_metin()
    sonuc = [
        ("canlı sayfada bütün kanıt ifadeleri birebir var", all(_norm(k) in metin for k in KANIT)),
        ("canlı sayfada imalat/mikro dışlaması yok", not any(y in metin for y in YANLIS)),
        ("detay bölümü amaçtan Bağımsız Değerlendirme limitine", detay_bolumu(metin).startswith("YÖNDE Destek")
         and detay_bolumu(metin).endswith("450.000 TL'dir.")),
        ("tutar metnindeki bütün TL değerleri kanıtta", all(
            x in " ".join(KANIT) for x in re.findall(r"\d{2,3}\.\d{3}", TUTAR))),
    ]

    class _T:
        kontrol_listesi = [{"tur": "sart", "metin": ESKI_MADDE + " küçük ya da orta"}, {"tur": "belge", "metin": "Form"}]
        tesvil_tutari = TUTAR
        tutari_max = 700000.0
        uygunluk_kriterleri = {"sektorler": ["genel"]}
        detay = detay_bolumu(metin)
    d = degisiklikler(_T(), metin)
    sonuc.append(("yanlış mikro maddesi çıkarılır, diğerleri kalır", len(d) == 1 and d[0][0] == "kontrol_listesi"
                  and d[0][2] == [{"tur": "belge", "metin": "Form"}]))
    _T.kontrol_listesi = d[0][2]
    sonuc.append(("idempotent", degisiklikler(_T(), metin) == []))
    for ad, ok in sonuc:
        print(("GEÇTİ " if ok else "KALDI ") + ad)
    gecen = sum(ok for _, ok in sonuc)
    print(f"self-test: {gecen}/{len(sonuc)} geçti")
    return 0 if gecen == len(sonuc) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(uygula("--uygula" in sys.argv))
