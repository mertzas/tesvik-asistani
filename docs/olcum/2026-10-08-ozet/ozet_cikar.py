"""Özeti yalnız menü metni olan aktif kayıtlar için kaynak sayfadan amaç/açıklama bölümünü birebir çıkarır (salt okuma).
Çıktı: sayfalar/<id>.txt ve sayfalar/aday.json. 2026-10-08 koşusu: 22 kayıttan 12'si başlıkla bulundu, TÜBİTAK 22/25/46
elle belirlenen bölümle eklendi; KGF 93/116/125/153/154/171/173'te içerik JS ile yüklendiği için metin yok.
Gözden geçirilmiş sonuç: tur13_ozetler.json (scripts/fix_veri_2026_10_08_ozet_tur13.py girdisi).

    python docs/olcum/2026-10-08-ozet/ozet_cikar.py"""
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.stdout.reconfigure(encoding="utf-8")
from app.basvuru_taslagi import _temiz_ozet  # noqa: E402
from app.models import SessionLocal, Tesvik  # noqa: E402

DIZIN = Path(__file__).resolve().parent / "sayfalar"
DIZIN.mkdir(exist_ok=True)
BASLIKLAR = ["Programın Amacı", "Paket Açıklaması", "Paketin Amacı", "Programın amacı", "Amaç", "Ürün Açıklaması",
             "Destek Programının Amacı", "Program Hakkında"]
BITIS = ["Başvuru Şartları", "Kimler Başvurabilir", "Destek Unsurları", "Hedef Kitle", "Kefalet", "Başvuru",
         "Paket Özellikleri", "Paket Detayları", "Destek Üst Limiti", "Program Süresi", "Mevzuat", "Kredi Tutarı",
         "Kimler Yararlanabilir", "Sık Sorulan", "Destek Oranı"]

db = SessionLocal()
adaylar = []
for t in db.query(Tesvik).filter(Tesvik.aktif_mi.is_(True)).order_by(Tesvik.id).all():
    if _temiz_ozet(t.ozet):
        continue
    kayit = {"id": t.id, "kurum": t.kurum, "baslik": t.baslik, "kaynak_url": t.kaynak_url, "amac": None, "baslik_bulunan": None}
    try:
        r = requests.get(t.kaynak_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        kayit["http"] = r.status_code
        metin = "\n".join(s.strip() for s in BeautifulSoup(r.text, "html.parser").get_text("\n").splitlines() if s.strip())
        (DIZIN / f"{t.id}.txt").write_text(metin, encoding="utf-8")
        for b in BASLIKLAR:
            m = re.search(rf"(?m)^{re.escape(b)}\s*:?\s*$", metin)
            if not m:
                continue
            govde = metin[m.end():]
            kes = len(govde)
            for son in BITIS:
                n = re.search(rf"(?m)^{re.escape(son)}", govde)
                if n and n.start() < kes:
                    kes = n.start()
            parca = " ".join(govde[:kes].split())
            if len(parca) > 40:
                kayit["amac"], kayit["baslik_bulunan"] = parca[:1200], b
                break
    except requests.RequestException as e:
        kayit["hata"] = str(e)
    adaylar.append(kayit)
    print(f"[{t.id}] {t.kurum} {t.baslik[:45]} | {kayit.get('http')} | {kayit['baslik_bulunan']} | {(kayit['amac'] or '—')[:110]}")
    time.sleep(0.6)
(DIZIN / "aday.json").write_text(json.dumps(adaylar, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n{len(adaylar)} kayıt; amaç bulunan {sum(1 for a in adaylar if a['amac'])}")
