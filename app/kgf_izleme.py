"""KGF ürün sayfası izleme (2026-10-08): son tarih eklenirse ya da ürün metni değişirse haber ver.

Tur15'te KGF'nin 28 ürün sayfasında başvuru/kullandırım son tarihi bulunmadığı için başvuru süresi metinleri
"sayfada belirtilmemiş, bankadan teyit edin" diye yazıldı. KGF bir pakete son tarih koyarsa ya da paketi değiştirirse
bu metinler eskir. Bu modül aktif KGF kayıtlarının kaynak sayfasındaki ÜRÜN BÖLÜMÜNÜ (menü hariç: son "Kurumsal
İletişim" ile "Buradasınız" arası) özetler, tabanla (app/data/kgf_taban.json) karşılaştırır ve raporlar:
  degisen: ürün metni değişen sayfalar, yeni_tarih: tabanda olmayan tarih/son kullandırım ifadesi,
  erisilemeyen: alınamayan ya da ürün bölümü bulunamayan sayfalar, yeni: tabanda olmayan kayıtlar.
Veritabanına yazmaz; tabanı yalnız --taban-yaz günceller (insan incelemesinden sonra).
Zamanlayıcı (app/scheduler.py) ayda bir çalıştırır ve bulguları WARNING olarak günlüğe yazar.

    python -m app.kgf_izleme --self-test
    python -m app.kgf_izleme --kontrol           (ağ; rapor)
    python -m app.kgf_izleme --taban-yaz         (ağ; tabanı günceller)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

TABAN = Path(__file__).resolve().parent / "data" / "kgf_taban.json"
TARIH = re.compile(r"[^.]{0,60}(\d{1,2}[./]\d{1,2}[./]20\d\d|son kullandırım|son başvuru|tarihine kadar)[^.]{0,30}",
                   re.IGNORECASE)


def urun_bolumu(metin: str) -> str | None:
    """Sayfa metninden ürün bölümü; işaretler yoksa None (sayfa yapısı değişmiş demektir)."""
    son = metin.find("Buradasınız")
    bas = metin.rfind("Kurumsal İletişim", 0, son) if son >= 0 else -1
    if son < 0 or bas < 0:
        return None
    bolum = " ".join(metin[bas + len("Kurumsal İletişim"): son].split())
    return bolum or None


def tarih_ifadeleri(bolum: str) -> list[str]:
    return sorted({" ".join(m.group(0).split()) for m in TARIH.finditer(bolum)})


def ozet(bolum: str) -> str:
    return hashlib.sha256(bolum.encode("utf-8")).hexdigest()[:16]


def sayfa_metni(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")
    for x in s(["script", "style"]):
        x.decompose()
    return " ".join(s.get_text(" ").split())


def tara(kayitlar: list[tuple[int, str, str]], taban: dict, getir: Callable[[str], str] = sayfa_metni,
         bekle: float = 0.5) -> tuple[dict, dict]:
    """(rapor, yeni_taban). kayitlar: (id, başlık, kaynak_url)."""
    rapor = {"degisen": [], "yeni_tarih": [], "erisilemeyen": [], "yeni": [], "taranan": 0}
    yeni_taban = {}
    for tid, baslik, url in kayitlar:
        anahtar = str(tid)
        try:
            bolum = urun_bolumu(getir(url))
        except Exception as e:  # ağ hatası tek sayfayı düşürür, taramayı değil
            rapor["erisilemeyen"].append({"id": tid, "baslik": baslik, "neden": str(e)[:120]})
            if anahtar in taban:
                yeni_taban[anahtar] = taban[anahtar]
            continue
        if bolum is None:
            rapor["erisilemeyen"].append({"id": tid, "baslik": baslik, "neden": "ürün bölümü bulunamadı"})
            if anahtar in taban:
                yeni_taban[anahtar] = taban[anahtar]
            continue
        rapor["taranan"] += 1
        kayit = {"ozet": ozet(bolum), "tarihler": tarih_ifadeleri(bolum), "url": url, "tarih": date.today().isoformat()}
        yeni_taban[anahtar] = kayit
        eski = taban.get(anahtar)
        if eski is None:
            rapor["yeni"].append({"id": tid, "baslik": baslik})
            continue
        if eski["ozet"] != kayit["ozet"]:
            rapor["degisen"].append({"id": tid, "baslik": baslik, "url": url})
        eklenen = sorted(set(kayit["tarihler"]) - set(eski.get("tarihler", [])))
        if eklenen:
            rapor["yeni_tarih"].append({"id": tid, "baslik": baslik, "ifadeler": eklenen})
        if bekle:
            time.sleep(bekle)
    return rapor, yeni_taban


def _kayitlar() -> list[tuple[int, str, str]]:
    from app.models import SessionLocal, Tesvik

    db = SessionLocal()
    try:
        return [(t.id, t.baslik, t.kaynak_url) for t in db.query(Tesvik).filter(
            Tesvik.kurum == "KGF", Tesvik.aktif_mi.is_(True)).order_by(Tesvik.id)]
    finally:
        db.close()


def taban_oku() -> dict:
    return json.loads(TABAN.read_text(encoding="utf-8")) if TABAN.exists() else {}


def run(taban_yaz: bool = False) -> str:
    """Zamanlayıcı ve CLI girişi. Bulguları WARNING olarak günlüğe yazar; özet metni döner."""
    rapor, yeni = tara(_kayitlar(), taban_oku())
    for anahtar, ad in (("yeni_tarih", "yeni tarih ifadesi"), ("degisen", "ürün metni değişti"),
                        ("erisilemeyen", "erişilemedi"), ("yeni", "tabanda yok")):
        for x in rapor[anahtar]:
            logger.warning("KGF izleme: %s [%s] %s %s", ad, x["id"], x["baslik"], x.get("ifadeler") or x.get("neden") or "")
    if taban_yaz:
        TABAN.write_text(json.dumps(yeni, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return (f"{rapor['taranan']} sayfa; değişen {len(rapor['degisen'])}, yeni tarih {len(rapor['yeni_tarih'])}, "
            f"erişilemeyen {len(rapor['erisilemeyen'])}, tabanda yok {len(rapor['yeni'])}"
            + ("; taban yazıldı" if taban_yaz else ""))


def _self_test() -> int:
    menu = "Anasayfa — Ürünlerimiz — Bize Ulaşın — Kurumsal İletişim "
    sayfa = lambda govde: menu * 2 + govde + " Buradasınız: Anasayfa / Ürünlerimiz"  # noqa: E731
    v1 = "TOBB NEFES KREDİSİ Ürün açıklaması Reel sektör. Ürün Vadesi Azami 48 ay"
    v2 = v1 + " Kredi Son Kullandırım Tarihi : 31.12.2026"
    sayfalar = {"u1": sayfa(v1), "u2": sayfa(v1), "u3": "yapısı bozuk sayfa"}
    taban = {"1": {"ozet": ozet(urun_bolumu(sayfa(v1))), "tarihler": []},
             "2": {"ozet": ozet(urun_bolumu(sayfa(v1))), "tarihler": []}}
    kayit = [(1, "A", "u1"), (2, "B", "u2"), (3, "C", "u3"), (4, "D", "u4")]

    def getir(u):
        if u == "u4":
            raise ConnectionError("ağ yok")
        return sayfalar[u]

    r0, _ = tara(kayit, taban, getir, bekle=0)
    sayfalar["u2"] = sayfa(v2)
    r1, yeni = tara(kayit, taban, getir, bekle=0)
    k = [
        ("ürün bölümü menüsüz", urun_bolumu(sayfa(v1)) == v1),
        ("değişiklik yokken rapor boş", not r0["degisen"] and not r0["yeni_tarih"]),
        ("son tarih eklenince: değişen + yeni tarih", [x["id"] for x in r1["degisen"]] == [2]
         and any("31.12.2026" in s for s in r1["yeni_tarih"][0]["ifadeler"])),
        ("bozuk yapı ve ağ hatası erişilemeyen, tarama sürer", {x["id"] for x in r1["erisilemeyen"]} == {3, 4}
         and r1["taranan"] == 2),
        ("erişilemeyen kaydın eski tabanı korunur", "1" in yeni and "3" not in yeni),
        ("taban dosyası paketin içinde", TABAN.parent.name == "data" and TABAN.parent.parent.name == "app"),
    ]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in k)
    print(f"\nself-test: {gecen}/{len(k)} geçti")
    return 0 if gecen == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s", stream=sys.stdout)  # cp1254 stderr
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--kontrol" in sys.argv or "--taban-yaz" in sys.argv:
        print(run(taban_yaz="--taban-yaz" in sys.argv))
        sys.exit(0)
    print(__doc__)
