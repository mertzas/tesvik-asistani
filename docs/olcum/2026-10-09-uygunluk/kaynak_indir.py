"""Uygunluk ölçümü 1. adım: işletmeye yönelik aktif programların resmî kaynak sayfalarını indirip metne çevirir.

  python docs/olcum/2026-10-09-uygunluk/kaynak_indir.py            -> kaynak/<id>.txt + kaynak/indirme.json
  python docs/olcum/2026-10-09-uygunluk/kaynak_indir.py --self-test

Her program için kaynak metin = kayıtlı detay (veritabanı) + canlı sayfa (HTML veya PDF). Ajanların alıntıları bu
dosyalara karşı makineyle doğrulanır (kriter_dogrula.py). Ağ hatası olan sayfa için yalnız detay kalır ve indirme.json'da
hata yazılır; sessizce atlanmaz.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time

KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, KOK)
OUT = os.path.dirname(os.path.abspath(__file__))
KAYNAK = os.path.join(OUT, "kaynak")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0 Safari/537.36"}


def html_metin(icerik: bytes | str) -> str:
    from bs4 import BeautifulSoup
    s = BeautifulSoup(icerik, "html.parser")
    for x in s(["script", "style", "noscript", "header", "footer", "nav"]):
        x.decompose()
    return re.sub(r"\n\s*\n+", "\n\n", s.get_text("\n")).strip()


def pdf_metin(icerik: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(icerik)).pages).strip()


def indir(url: str) -> tuple[str, str | None]:
    import requests
    try:
        r = requests.get(url.split("#")[0], headers=HEADERS, timeout=40)
        r.raise_for_status()
    except Exception as e:  # ağ/HTTP hatası kaydedilir
        return "", f"{type(e).__name__}: {e}"[:300]
    tur = r.headers.get("Content-Type", "")
    try:
        if "pdf" in tur or r.content[:4] == b"%PDF":
            return pdf_metin(r.content), None
        # Başlıktaki charset esas: BeautifulSoup baytlardan tahmin ederken KOSGEB sayfalarını latin-1 sandı (mojibake).
        return html_metin(r.content.decode(r.encoding or r.apparent_encoding or "utf-8", errors="replace")), None
    except Exception as e:
        return "", f"ayrıştırma: {type(e).__name__}: {e}"[:300]


def main():
    from app.models import SessionLocal, Tesvik
    from app.nace_extraction import clean_grant_text
    os.makedirs(KAYNAK, exist_ok=True)
    progs = json.load(open(os.path.join(OUT, "programlar.json"), encoding="utf-8"))
    db = SessionLocal()
    onbellek: dict[str, tuple[str, str | None]] = {}
    rapor = []
    for p in progs:
        t = db.get(Tesvik, p["id"])
        url = p["url"].split("#")[0]
        if url not in onbellek:
            onbellek[url] = indir(url)
            time.sleep(1.0)  # kurum sunucularına nazik
        canli, hata = onbellek[url]
        detay = clean_grant_text(t.detay or "", baslik=t.baslik)
        alanlar = "\n".join(f"{ad}: {deger}" for ad, deger in [
            ("Başvuru şartları (kayıt)", "; ".join(t.basvuru_sartlari or [])), ("Gerekli belgeler (kayıt)", "; ".join(t.gerekli_belgeler or [])),
            ("Tutar/oran (kayıt)", t.tesvil_tutari), ("Hesaplama (kayıt)", t.tutari_hesaplama_formulu),
            ("Başvuru yeri (kayıt)", t.basvuru_yeri), ("Başvuru süresi (kayıt)", t.basvuru_suresi)] if deger)
        metin = (f"# [{t.id}] {t.kurum} — {t.baslik}\nKaynak: {t.kaynak_url}\n\n## KAYITLI ALANLAR\n{alanlar}\n\n"
                 f"## KAYITLI DETAY (veritabanı)\n{detay}\n\n## CANLI SAYFA ({url}, indirildi 2026-10-09)\n"
                 + (canli if canli else f"(indirilemedi: {hata})"))
        io.open(os.path.join(KAYNAK, f"{t.id}.txt"), "w", encoding="utf-8").write(metin)
        rapor.append(dict(id=t.id, url=url, canli_kar=len(canli), hata=hata, detay_kar=len(detay)))
        print(f"[{t.id:3}] canlı {len(canli):6} kar  detay {len(detay):6}  {('HATA ' + hata) if hata else ''}"[:160])
    json.dump(rapor, open(os.path.join(KAYNAK, "indirme.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{sum(1 for r in rapor if r['canli_kar'] > 500)}/{len(rapor)} programda canlı sayfa > 500 karakter; "
          f"hata: {sum(1 for r in rapor if r['hata'])}")


def _self_test() -> int:
    k = [("HTML metni (script atılır)", html_metin(b"<html><script>x()</script><p>Kimler</p><p>KOBI</p></html>") == "Kimler\nKOBI"),
         ("programlar.json var", os.path.exists(os.path.join(OUT, "programlar.json")))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(_self_test() if "--self-test" in sys.argv else main())
