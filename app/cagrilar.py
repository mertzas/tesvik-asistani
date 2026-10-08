"""Dönemsel başvuru çağrıları (2026-10-08): programın açık/yaklaşan/kapanmış çağrısı ve kalan gün.

Program (Tesvik) ile çağrı (TesvikCagrisi) ayrıdır. Aktif 100 kaydın hiçbirinde bitiş tarihi yoktu (ölçüm 2026-10-08);
"son başvuru" ve tarih hatırlatıcısı yalnızca resmi duyurudan doğrulanmış çağrı satırlarından üretilir.

    python -m app.cagrilar --self-test
"""
from __future__ import annotations

import sys
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_org
from app.models import FinancialProfile, Organization, Tesvik, TesvikCagrisi, get_db

router = APIRouter(prefix="/api/cagrilar", tags=["başvuru çağrıları"])

DURUM_SIRASI = {"acik": 0, "yaklasan": 1, "tarihsiz": 2, "on_kayit_kapandi": 3, "kapandi": 4}
DURUM_METNI = {"acik": "Başvuruya açık", "yaklasan": "Yakında açılacak", "kapandi": "Kapandı",
               "tarihsiz": "Tarih duyurulmadı",
               "on_kayit_kapandi": "Ön kayıt kapandı; yalnız ön kaydı yapılmış başvurular tamamlanabilir"}


def son_gun(c: TesvikCagrisi) -> date | None:
    """Yeni başvuranın son günü: ön kayıt/kuruluş başvurusu son tarihi varsa o, yoksa çağrı kapanışı.
    Ölçüm 2026-10-08: TÜBİTAK 1501'de ön kayıt 22.10, kapanış 26.10; çip kapanışı gösterdiği için 4 gün kaçıyordu."""
    return c.on_kayit_son or c.kapanis


def durum(c: TesvikCagrisi, bugun: date | None = None) -> dict:
    """Çağrının bugüne göre durumu. Tarihler dahil gündür (son gün hâlâ açık). kalan_gun yeni başvuranın son
    gününe (son_gun) göre sayılır."""
    bugun = bugun or date.today()
    if c.kapanis is not None and c.kapanis < bugun:
        d, kalan = "kapandi", None
    elif c.acilis is not None and c.acilis > bugun:
        d, kalan = "yaklasan", (c.acilis - bugun).days
    elif c.on_kayit_son is not None and c.on_kayit_son < bugun:
        d, kalan = "on_kayit_kapandi", (c.kapanis - bugun).days if c.kapanis else None
    elif son_gun(c) is not None:
        d, kalan = "acik", (son_gun(c) - bugun).days
    elif c.acilis is not None:
        d, kalan = "acik", None  # açıldı, kapanış duyurulmamış
    else:
        d, kalan = "tarihsiz", None
    return {"durum": d, "durum_metni": DURUM_METNI[d], "kalan_gun": kalan}


def sozluk(c: TesvikCagrisi, bugun: date | None = None) -> dict:
    return {"id": c.id, "ad": c.ad, "acilis": c.acilis.isoformat() if c.acilis else None,
            "kapanis": c.kapanis.isoformat() if c.kapanis else None,
            "on_kayit_son": c.on_kayit_son.isoformat() if c.on_kayit_son else None,
            "son_gun": son_gun(c).isoformat() if son_gun(c) else None, "kaynak_url": c.kaynak_url,
            "dogrulama_tarihi": c.dogrulama_tarihi.isoformat(), "notlar": c.notlar, **durum(c, bugun)}


def program_cagrilari(t: Tesvik, bugun: date | None = None, kapanmis_en_cok: int = 1) -> list[dict]:
    """Programın çağrıları: açık ve yaklaşanlar önce (en yakın tarih başta), kapanmışlardan en yenisi sonda."""
    hepsi = [sozluk(c, bugun) for c in (t.cagrilar or [])]
    canli = sorted((x for x in hepsi if x["durum"] != "kapandi"),
                   key=lambda x: (DURUM_SIRASI[x["durum"]], x["kalan_gun"] if x["kalan_gun"] is not None else 10**6))
    kapanmis = sorted((x for x in hepsi if x["durum"] == "kapandi"), key=lambda x: x["kapanis"], reverse=True)
    return canli + kapanmis[:kapanmis_en_cok]


@router.get("")
def yaklasan_cagrilar(gun: int = Query(90, ge=1, le=365), sadece_eslesen: bool = False,
                      current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Açık ya da `gun` içinde açılacak çağrılar, en yakın kapanış başta. sadece_eslesen: yalnızca kuruluşun
    profiliyle eşleşen programlar (profil yoksa boş liste)."""
    bugun = date.today()
    sinir = date.fromordinal(bugun.toordinal() + gun)
    sorgu = (db.query(TesvikCagrisi, Tesvik).join(Tesvik, Tesvik.id == TesvikCagrisi.tesvik_id)
             .filter(or_(TesvikCagrisi.kapanis.is_(None), TesvikCagrisi.kapanis >= bugun))
             .filter(or_(TesvikCagrisi.acilis.is_(None), TesvikCagrisi.acilis <= sinir)))
    izinli = None
    if sadece_eslesen:
        from app.matching import esles
        profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
        izinli = {e.tesvik.id for e in esles(profil, db)} if profil else set()
    sonuc = []
    for c, t in sorgu.all():
        if izinli is not None and t.id not in izinli:
            continue
        x = sozluk(c, bugun)
        # Pencere dışında kapanan açık çağrı "yaklaşan" değildir (9903: müracaatlar 31.12.2030'a kadar; tur15).
        # Kalanlar: penceredeki açılış (yaklaşan), penceredeki son gün, kapanışı duyurulmamış açık çağrı.
        if x["durum"] != "yaklasan" and x["son_gun"] is not None and x["son_gun"] > sinir.isoformat():
            continue
        sonuc.append({**x, "tesvik_id": t.id, "baslik": t.baslik, "kurum": t.kurum})
    sonuc.sort(key=lambda x: (x["son_gun"] or "9999-12-31", x["baslik"]))
    return {"cagrilar": sonuc, "bugun": bugun.isoformat()}


def _self_test() -> int:
    b = date(2026, 10, 8)
    s = [
        ("kapanış günü açık", durum(TesvikCagrisi(acilis=date(2026, 9, 1), kapanis=b), b)["durum"] == "acik"),
        ("kapanıştan sonra kapandı", durum(TesvikCagrisi(kapanis=date(2026, 10, 7)), b)["durum"] == "kapandi"),
        ("açılmamış: yaklaşan + kalan gün", durum(TesvikCagrisi(acilis=date(2026, 10, 18), kapanis=date(2026, 11, 30)), b)
         == {"durum": "yaklasan", "durum_metni": "Yakında açılacak", "kalan_gun": 10}),
        ("açık + kapanışa kalan gün", durum(TesvikCagrisi(acilis=date(2026, 10, 1), kapanis=date(2026, 10, 31)), b)["kalan_gun"] == 23),
        ("tarihsiz", durum(TesvikCagrisi(), b)["durum"] == "tarihsiz"),
        ("ön kayıt varsa kalan gün ona göre", durum(TesvikCagrisi(acilis=date(2026, 7, 20), kapanis=date(2026, 10, 26),
                                                                  on_kayit_son=date(2026, 10, 22)), b)["kalan_gun"] == 14),
        ("ön kayıt geçti, kapanış gelmedi", durum(TesvikCagrisi(kapanis=date(2026, 10, 26),
                                                               on_kayit_son=date(2026, 10, 7)), b)["durum"] == "on_kayit_kapandi"),
    ]
    t = Tesvik(cagrilar=[TesvikCagrisi(ad="eski1", kapanis=date(2025, 1, 1), dogrulama_tarihi=b, kaynak_url="u"),
                         TesvikCagrisi(ad="eski2", kapanis=date(2026, 3, 1), dogrulama_tarihi=b, kaynak_url="u"),
                         TesvikCagrisi(ad="yakin", acilis=date(2026, 11, 1), dogrulama_tarihi=b, kaynak_url="u"),
                         TesvikCagrisi(ad="acik", kapanis=date(2026, 12, 1), dogrulama_tarihi=b, kaynak_url="u")])
    s.append(("program sıralaması: açık, yaklaşan, son kapanan", [x["ad"] for x in program_cagrilari(t, b)]
              == ["acik", "yakin", "eski2"]))
    for ad, ok in s:
        print(("  ✓ " if ok else "  ✗ ") + ad)
    gecen = sum(ok for _, ok in s)
    print(f"self-test: {gecen}/{len(s)} geçti")
    return 0 if gecen == len(s) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print("Kullanım: python -m app.cagrilar --self-test")
