"""Tur 30 — kontrol listesindeki birinci tekil beyan metinleri (2026-10-11).

Bağımsız değerlendirme (docs/olcum/2026-10-11-yerel-danisman/degerlendirme4..8_*.json): kontrol listesi maddeleri
kullanıcının ağzından yazılmıştı ("Özel sektör işvereniyim", "PRODİS'te hazırladım", "5 proje desteği almadım").
Danışman bu metni şart, kural ve yol haritası satırlarında aynen basıyordu; hakemler her turda "birinci tekil şablon
sızıntısı" diye işaretledi. Madde metni nötr şart diline çevrilir ("işvereni olmak", "almamış olmak", "hazırlanır").
Anlam ve resmî alıntı (alinti alanı) değişmez; yalnız `metin` alanı değişir. Panelin Evet/Hayır sorusu da bu metni
gösterir; nötr şart cümlesi her iki yerde okunur.

tur19 yeniden koşulursa bu düzeltmeyi kaybetmesin diye tur19'un SONRAKI_TURLAR kancasına eklidir (`duzelt`,
`DUZELTILEN`).

    python scripts/fix_veri_2026_10_11_birinci_tekil_tur30.py             (dry-run)
    python scripts/fix_veri_2026_10_11_birinci_tekil_tur30.py --uygula
    python scripts/fix_veri_2026_10_11_birinci_tekil_tur30.py --self-test
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur30 2026-10-11"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur30.db.bak"

# (eski ifade, yeni ifade): uzun ifadeler önce; her biri madde metninde birebir aranır.
DEGISIKLIKLER: list[tuple[str, str]] = [
    ("Tanıtım yapacağım ülkede kapsama alınmış yurt dışı birimim yoksa: Türkiye'de tescilli markam var ve tanıtım "
     "yapacağım ülkede marka tescilim ya da tescil başvurum var",
     "Tanıtım yapılacak ülkede kapsama alınmış yurt dışı birim yoksa: Türkiye'de tescilli marka ve tanıtım yapılacak "
     "ülkede marka tescili ya da tescil başvurusu olmalı"),
    ("Tanıtım yapacağım ülkede kapsama alınmış yurt dışı birimim yoksa: yurt içi marka tescil belgem ve tanıtım "
     "ülkesindeki marka tescil belgem ya da tescil başvuru belgem hazır",
     "Tanıtım yapılacak ülkede kapsama alınmış yurt dışı birim yoksa: yurt içi marka tescil belgesi ve tanıtım "
     "ülkesindeki marka tescil belgesi ya da tescil başvuru belgesi"),
    ("Reklam giderlerim yurt dışı pazaryerlerinde verdiğim dijital reklamlara ait ve reklamdan dönen toplam satışımın "
     "%20'sini aşmıyor",
     "Reklam giderleri yurt dışı pazaryerlerinde verilen dijital reklamlara ait olmalı ve reklamdan dönen toplam "
     "satışın %20'sini aşmamalı"),
    ("Kendi markama ait e-ticaret sitesi üzerinden perakende satış yapıyorum, toplam satış hasılatımın en az üçte ikisi "
     "çevrim içi ve iş merkezim Türkiye'de",
     "Kendi markasına ait e-ticaret sitesi üzerinden perakende satış yapmak; toplam satış hasılatının en az üçte ikisi "
     "çevrim içi ve iş merkezi Türkiye'de olmalı"),
    ("iş planını (AGY112 taslağına göre) PRODİS'te hazırladım ve uygulayıcı kuruluşa onaylattım",
     "iş planı (AGY112 taslağına göre) PRODİS'te hazırlanır ve uygulayıcı kuruluşa onaylatılır"),
    ("Ulusal ön başvuruyu ve ikinci aşama başvurusunu PRODİS'te hazırladım",
     "Ulusal ön başvuru ve ikinci aşama başvurusu PRODİS'te hazırlanır"),
    ("Kabul davet yazısı aldıktan sonra 2. aşama ulusal başvurusunu PRODİS'ten gönderdim",
     "Kabul davet yazısı alındıktan sonra 2. aşama ulusal başvurusu PRODİS'ten gönderilir"),
    ("vakıf üniversitesiysem: Bursiyer Bilgi Formu hazırlandı",
     "vakıf üniversitesi ise: Bursiyer Bilgi Formu hazırlanır"),
    ("Teşvik belgesi müracaatımı E-TUYS üzerinden yaptım", "Teşvik belgesi müracaatı E-TUYS üzerinden yapılır"),
    ("Teminat mektubu talebim için", "Teminat mektubu talebi için"),
    ("teminat mektubu istiyorsam", "teminat mektubu isteniyorsa"),
    ("Refinansmana konu mevcut bir banka kredim var", "Refinansmana konu mevcut bir banka kredisi olmak"),
    ("öğrencisiyim veya mezunuyum", "öğrencisi veya mezunu olmak"),
    ("yönetici şirketiyim", "yönetici şirketi olmak"),
    ("anonim şirketim", "anonim şirket olmak"),
    ("kayıtlı/aktifim", "kayıtlı/aktif olmak"),
    ("belgeleri hazırladım", "belgeler hazır olmalı"),
    ("aktif durumdayım", "aktif durumda olmak"),
    ("kredi kullanıyorum/kullanacağım", "kredi kullanmak"),
    ("Hızlı büyüyen işletmeyim", "Hızlı büyüyen işletme olmak"),
    ("Rozetine sahibim", "Rozetine sahip olmak"),
    ("bildirilmiş işletmeyim", "bildirilmiş işletme olmak"),
    ("metnini okudum", "metnini okumak"),
    ("bir sermaye şirketiyim", "bir sermaye şirketi olmak"),
    ("proje desteği almadım", "proje desteği almamış olmak"),
    ("desteği almadım", "desteği almamış olmak"),
    ("ortağı değilim", "ortağı olmamak"),
    ("TOBB üyesi bir işletmeyim", "TOBB üyesi bir işletme olmak"),
    ("taahhüdü verdim", "taahhüdü vermek"),
    ("Yatırımım, Karar", "Yatırım, Karar"),
    ("en az birine giriyor", "en az birine girmeli"),
    ("bir şirket veya kooperatifim", "bir şirket veya kooperatif olmak"),
    ("faaliyet gösteriyorum", "faaliyet göstermek"),
    ("kendi ürünüm", "başvuranın kendi ürünü olmalı"),
    ("Özel sektör işvereniyim", "Özel sektör işvereni olmak"),
    ("Şunlardan en az birini sağlıyorum:", "Şunlardan en az birini sağlamak:"),
    ("5 kriterden en az 3'ünü sağlıyorum:", "5 kriterden en az 3'ünü sağlamak:"),
    ("kadar öz kaynağım var", "kadar öz kaynak olmalı"),
    ("vergi ve SGK borcum yok", "vergi ve SGK borcu olmamak"),
]
# Kalıntı denetimi: düzeltmeden sonra metinde bu birinci tekil kalıplar kalmamalı.
KALINTI = re.compile(r"\b\w+(?:iyim|ıyım|uyum|üyüm|eyim|ayım|yorum|acağım|eceğim|madım|medim|ysem|ysam|ladım|"
                     r"ledim|aldım|ptım|rdim|rdım|ttım|ttim)\b|\b\w+(?:ım|im|um|üm)\s+(?:var|yok|hazır)\b|"
                     r"\b(?:kredim|birimim|markam|markama|tescilim|ürünüm|merkezim|talebim|sahibim|şirketim|"
                     r"kooperatifim|hasılatım|satışım|giderlerim)\b")
# Kalıba giren ama beyan olmayan kelimeler (isim ya da 3. tekil).
KALINTI_ISTISNA: set[str] = set()


def duzelt(metin: str) -> str:
    for eski, yeni in DEGISIKLIKLER:
        metin = metin.replace(eski, yeni)
    return metin


def kalinti(metin: str) -> list[str]:
    return [k for k in KALINTI.findall(metin) if k not in KALINTI_ISTISNA]


def uygula(db, dry_run: bool = True) -> tuple[int, set[int]]:
    from app.models import Tesvik
    n, kayitlar = 0, set()
    for t in db.query(Tesvik).order_by(Tesvik.id).all():
        liste = t.kontrol_listesi or []
        yeni = [({**m, "metin": duzelt(m["metin"])} if duzelt(m["metin"]) != m["metin"] else m) for m in liste]
        degisen = [(a["metin"], b["metin"]) for a, b in zip(liste, yeni) if a["metin"] != b["metin"]]
        if not degisen:
            continue
        for eski, yeni_metin in degisen:
            print(f"[{t.id}] {eski[:70]!r}\n      → {yeni_metin[:70]!r}")
        kayitlar.add(t.id)
        n += len(degisen)
        if not dry_run:
            t.kontrol_listesi = yeni
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: kontrol listesindeki birinci tekil beyan metni nötr şart diline çevrildi ({len(degisen)} madde)")
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} madde, {len(kayitlar)} kayıt")
    return n, kayitlar


DUZELTILEN = {4, 5, 6, 7, 8, 9, 25, 44, 46, 48, 49, 75, 86, 149, 152, 159, 173, 179, 181, 182, 185, 191, 192,
              196}


def _self_test() -> int:
    k = [("işveren", duzelt("Özel sektör işvereniyim") == "Özel sektör işvereni olmak"),
         ("olumsuz geçmiş", duzelt("Bu programdan daha önce 5 proje desteği almadım (ilk 5 proje)")
          == "Bu programdan daha önce 5 proje desteği almamış olmak (ilk 5 proje)"),
         ("edilgen adım", duzelt("Teşvik belgesi müracaatımı E-TUYS üzerinden yaptım (not).")
          == "Teşvik belgesi müracaatı E-TUYS üzerinden yapılır (not)."),
         ("koşullu belge kalıbı korunur (danışman koşullu belgeyi gizler)",
          "ise: Bursiyer Bilgi Formu hazırlanır" in duzelt("vakıf üniversitesiysem: Bursiyer Bilgi Formu hazırlandı")),
         ("ikinci koşuda değişiklik yok", duzelt(duzelt("Özel sektör işvereniyim")) == "Özel sektör işvereni olmak"),
         ("ilgisiz metne dokunulmaz", duzelt("Yönetim Kurulu kararı") == "Yönetim Kurulu kararı"),
         ("kalıntı denetimi isimleri saymaz",
          kalinti("Kasım ayında yatırım, eğitim, üretim ve dönüşüm; Teknogirişim; yükseköğretim") == []),
         ("borç beyanı", duzelt("vadesi geçmiş vergi ve SGK borcum yok") == "vadesi geçmiş vergi ve SGK borcu olmamak"),
         ("kalıntı denetimi beyanı yakalar", kalinti("TOBB üyesi bir işletmeyim") == ["işletmeyim"])]
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
    from app.models import SessionLocal, Tesvik, settings
    if a.uygula and not YEDEK.exists():
        shutil.copy2(Path(settings.DATABASE_URL.replace("sqlite:///", "")), YEDEK)
        print(f"yedek: {YEDEK}")
    db = SessionLocal()
    try:
        _, kayitlar = uygula(db, dry_run=not a.uygula)
        eksik = kayitlar - DUZELTILEN
        if eksik:
            print(f"UYARI: DUZELTILEN listesinde olmayan kayıtlar değişti: {sorted(eksik)}")
        kalan = [(t.id, k) for t in db.query(Tesvik).filter(Tesvik.aktif_mi != False).all()  # noqa: E712
                 for m in t.kontrol_listesi or [] for k in kalinti(duzelt(m["metin"]))]
        print(f"kalıntı birinci tekil ifade: {len(kalan)}" + (f" → {kalan[:10]}" if kalan else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
