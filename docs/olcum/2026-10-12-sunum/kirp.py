"""Ekran görüntülerini slayt kutusuna (1180×824, oran ~1,43) uyacak biçimde kırpar ve JPEG'e çevirir (2026-10-12).

Uzun ekranlarda üst kısım alınır (başlık, kısa cevap, ilk kartlar); e-ihracat hesaplayıcıda sonuç alt kısımda
olduğu için alt kısım. Çıktı: data/sunum_ekran/_kirp/<persona>__<dosya>.jpg

    python docs/olcum/2026-10-12-sunum/kirp.py --self-test
    python docs/olcum/2026-10-12-sunum/kirp.py
"""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[3]
KAYNAK = KOK / "data/sunum_ekran"
CIKTI = KAYNAK / "_kirp"
ORAN = 1180 / 824
GENISLIK = 1500
ALTTAN = {"06_eihracat.png"}


def kutu(w: int, h: int, alttan: bool) -> tuple[int, int, int, int]:
    """(sol, üst, sağ, alt): genişlik korunur, boy en çok w/ORAN."""
    boy = min(h, round(w / ORAN))
    return (0, h - boy, w, h) if alttan else (0, 0, w, boy)


def _self_test() -> int:
    k = [("uzun ekran üstten", kutu(1695, 2550, False) == (0, 0, 1695, 1184)),
         ("kısa ekran tam", kutu(1695, 700, False) == (0, 0, 1695, 700)),
         ("e-ihracat alttan", kutu(1695, 1920, True) == (0, 736, 1695, 1920))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    from PIL import Image
    CIKTI.mkdir(exist_ok=True)
    n = 0
    for p in sorted(KAYNAK.glob("*/*.png")):
        if p.parent.name.startswith("_"):
            continue
        im = Image.open(p).convert("RGB")
        im = im.crop(kutu(*im.size, p.name in ALTTAN))
        if im.width > GENISLIK:
            im = im.resize((GENISLIK, round(im.height * GENISLIK / im.width)), Image.LANCZOS)
        im.save(CIKTI / f"{p.parent.name}__{p.stem}.jpg", quality=86, optimize=True)
        n += 1
    print(f"{n} görüntü → {CIKTI}")
