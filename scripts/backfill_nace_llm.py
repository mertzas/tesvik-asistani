"""Teşvik kayıtlarının NACE kapsamını LLM ile çıkarıp tesvik_nace_association'a yazar.

Çıkarım hattı: app/nace_extraction.py (güvenlik ağları orada). Bu betik yalnızca
dolaştırır, raporlar ve yazar.

  python scripts/backfill_nace_llm.py --dry-run --id 98        # tek kayıt, yazmaz
  python scripts/backfill_nace_llm.py --dry-run --limit 20     # ilk 20
  python scripts/backfill_nace_llm.py                          # uygula
  python scripts/backfill_nace_llm.py --geri-al                # llm_extraction satırlarını sil

NOT: --dry-run da API çağrısı yapar (maliyet: kayıt başına 1 çağrı); yalnızca
veritabanına yazmaz. Program metinleri kamuya açıktır, kişisel veri içermez.

Kurallar:
  * Elle girilen ("elle") satırı olan kayda dokunulmaz.
  * Başlık-regex'iyle ("otomatik:...") kilitlenmiş ama LLM'in YATAY dediği
    kayıtlar ÇAKIŞMA olarak raporlanır; yalnızca --otomatik-yatay-ise-sil ile
    o otomatik satırlar silinir.
  * Aynı kayıt için llm_extraction satırı varsa atlanır (--yeniden ile tekrar).
  * Her karar --log dosyasına JSONL olarak yazılır (denetim için).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, TesvikNace, init_db  # noqa: E402
from app.nace_extraction import (  # noqa: E402
    KAYNAK_LLM,
    ExtractionError,
    KapsamTuru,
    extract_nace_scope,
)

OTOMATIK_ONEKI = "otomatik:"


async def _isle(tesvik, sem, client, model, min_guven):
    async with sem:
        try:
            return tesvik, await extract_nace_scope(
                tesvik, client=client, model=model, min_guven=min_guven, tesvik_id=tesvik.id), None
        except ExtractionError as e:
            return tesvik, None, str(e)
        except Exception as e:  # ağ/kota: tek kayıt tüm koşuyu düşürmesin
            return tesvik, None, f"{type(e).__name__}: {e}"


def _satir_ekle(db, mevcut: set, satir: dict) -> bool:
    anahtar = (satir["tesvik_id"], satir["nace_prefix"])
    if anahtar in mevcut:
        return False
    db.add(TesvikNace(**satir))
    mevcut.add(anahtar)
    return True


async def calistir(db, *, dry_run=False, geri_al=False, yeniden=False,
                   otomatik_yatay_ise_sil=False, limit=None, tesvik_id=None,
                   tumunu=False, min_guven=0.8, model=None, eszamanlilik=4,
                   log_yolu: Path | None = None, client=None) -> dict:
    sayac = {"islenen": 0, "yazilan_satir": 0, "yatay": 0, "belirsiz": 0, "kisitli": 0,
             "atlanan": 0, "hata": 0, "cakisma": 0, "silinen": 0}
    cikti: list[str] = []

    if geri_al:
        sorgu = db.query(TesvikNace).filter(TesvikNace.kaynak == KAYNAK_LLM)
        sayac["silinen"] = sorgu.count()
        if not dry_run:
            sorgu.delete(synchronize_session=False)
            db.commit()
        return {**sayac, "satirlar": cikti}

    kayitlar = db.query(Tesvik).order_by(Tesvik.id)
    if tesvik_id is not None:
        kayitlar = kayitlar.filter(Tesvik.id == tesvik_id)
    elif not tumunu:
        kayitlar = kayitlar.filter(Tesvik.aktif_mi.isnot(False))
    kayitlar = kayitlar.all()

    mevcut_satirlar = db.query(TesvikNace).all()
    mevcut = {(r.tesvik_id, r.nace_prefix) for r in mevcut_satirlar}
    elle = {r.tesvik_id for r in mevcut_satirlar if r.kaynak == "elle"}
    llm_var = {r.tesvik_id for r in mevcut_satirlar if r.kaynak == KAYNAK_LLM}
    otomatik = {}
    for r in mevcut_satirlar:
        if r.kaynak.startswith(OTOMATIK_ONEKI):
            otomatik.setdefault(r.tesvik_id, []).append(r)

    hedefler = []
    for t in kayitlar:
        if t.id in elle or (t.id in llm_var and not yeniden):
            sayac["atlanan"] += 1
            continue
        hedefler.append(t)
    if limit:
        hedefler = hedefler[:limit]

    sem = asyncio.Semaphore(eszamanlilik)
    sonuclar = await asyncio.gather(*[_isle(t, sem, client, model, min_guven) for t in hedefler])

    log = log_yolu.open("a", encoding="utf-8") if (log_yolu and not dry_run) else None
    try:
        for t, sonuc, hata in sonuclar:
            sayac["islenen"] += 1
            if hata or sonuc is None:
                sayac["hata"] += 1
                cikti.append(f"[{t.id}] {t.baslik}: HATA {hata}")
                continue
            k = sonuc.kapsam
            tur = k.kapsam_turu
            sayac[{"YATAY": "yatay", "BELIRSIZ": "belirsiz", "SEKTOR_KISITLI": "kisitli"}[tur.value]] += 1
            kodlar = ",".join(r["nace_prefix"] for r in sonuc.rows) or "-"
            cikti.append(f"[{t.id}] {t.baslik}: {tur.value} {k.yararlanici_tipi.value} kodlar={kodlar}"
                         f" | {k.analiz_notu}"
                         + (f" | reddedilen={sonuc.reddedilenler}" if sonuc.reddedilenler else "")
                         + (f" | hariç={[x.nace_prefix for x in k.haric_tutulan_nace_kodlari]}"
                            if k.haric_tutulan_nace_kodlari else ""))
            if log:
                log.write(json.dumps({"tesvik_id": t.id, "baslik": t.baslik,
                                      "kapsam": k.model_dump(mode="json"),
                                      "reddedilen": sonuc.reddedilenler}, ensure_ascii=False) + "\n")

            if tur is KapsamTuru.YATAY and t.id in otomatik:
                sayac["cakisma"] += 1
                cikti.append(f"    ÇAKIŞMA: başlık-regex kilidi {[r.nace_prefix for r in otomatik[t.id]]}, "
                             "LLM YATAY diyor")
                if otomatik_yatay_ise_sil and not dry_run:
                    for r in otomatik[t.id]:
                        db.delete(r)
                        mevcut.discard((r.tesvik_id, r.nace_prefix))
                        sayac["silinen"] += 1

            if yeniden and not dry_run:
                for r in db.query(TesvikNace).filter(TesvikNace.tesvik_id == t.id,
                                                     TesvikNace.kaynak == KAYNAK_LLM):
                    db.delete(r)
                    mevcut.discard((r.tesvik_id, r.nace_prefix))
            for satir in sonuc.rows:
                if dry_run:
                    sayac["yazilan_satir"] += 1
                elif _satir_ekle(db, mevcut, satir):
                    sayac["yazilan_satir"] += 1
        if not dry_run:
            db.commit()
    finally:
        if log:
            log.close()
    return {**sayac, "satirlar": cikti}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="Veritabanına yazma (API çağrısı yapılır)")
    ap.add_argument("--geri-al", action="store_true")
    ap.add_argument("--yeniden", action="store_true", help="Zaten LLM satırı olanları tekrar işle")
    ap.add_argument("--otomatik-yatay-ise-sil", action="store_true")
    ap.add_argument("--tumunu", action="store_true", help="Kapalı (aktif_mi=False) programlar dahil")
    ap.add_argument("--id", type=int, dest="tesvik_id")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--min-guven", type=float, default=0.8)
    ap.add_argument("--model")
    ap.add_argument("--eszamanlilik", type=int, default=4)
    ap.add_argument("--log", type=Path, default=Path("data/nace_extraction_log.jsonl"))
    a = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        sonuc = asyncio.run(calistir(
            db, dry_run=a.dry_run, geri_al=a.geri_al, yeniden=a.yeniden,
            otomatik_yatay_ise_sil=a.otomatik_yatay_ise_sil, limit=a.limit,
            tesvik_id=a.tesvik_id, tumunu=a.tumunu, min_guven=a.min_guven,
            model=a.model, eszamanlilik=a.eszamanlilik, log_yolu=a.log))
    finally:
        db.close()
    for s in sonuc.pop("satirlar"):
        print(s)
    etiket = "(DRY-RUN) " if a.dry_run else ""
    print("\n" + etiket + " ".join(f"{k}={v}" for k, v in sonuc.items()))


if __name__ == "__main__":
    main()
