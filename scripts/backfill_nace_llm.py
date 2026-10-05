"""Teşvik kayıtlarının NACE kapsamını LLM ile çıkarıp tesvik_nace_association'a yazar.

Çıkarım hattı: app/nace_extraction.py (temizleyici + güvenlik ağları orada).
Bu betik dolaştırır, öncelik kuralını uygular, raporlar ve yazar.

  python scripts/backfill_nace_llm.py --dry-run --id 98        # tek kayıt, yazmaz
  python scripts/backfill_nace_llm.py --dry-run --limit 20     # ilk 20
  python scripts/backfill_nace_llm.py                          # uygula
  python scripts/backfill_nace_llm.py --geri-al                # llm_extraction satırlarını sil

NOT: --dry-run da API çağrısı yapar (kayıt başına 1 çağrı); yalnızca veritabanına
yazmaz. Program metinleri kamuya açıktır, kişisel veri içermez.

Öncelik (yüksekten düşüğe):
  elle (manual)  >  llm_extraction (güven >= eşik)  >  otomatik:* (başlık-regex)
  * "elle" satırı olan kayda hiç dokunulmaz (LLM bile çağrılmaz).
  * LLM güvenle (>= --min-guven) spesifik kod(lar) ya da YATAY bulursa o kaydın
    otomatik:* satırları EZİLİR (supersede): aynı kod ise kaynağı yükseltilir,
    diğerleri silinir. LLM BELIRSIZ derse otomatik kilit korunur.
  * Ezme/korunma olan her durum ÇAKIŞMA olarak sınıflandırılıp log dosyasına
    yazılır: yatay_kilidi_kaldirildi, sektor_degisimi (A->C), kapsam_daralmasi
    (C->10.83), kapsam_genislemesi (10.83->C), karisik_degisim,
    ayni_kod_kaynak_yukseltildi, korundu_belirsiz.
  * Hariç tutma satırları (haric_mi=True) bağımsız yazılır; kanıtı yetersiz
    dışlama varsa kayıt manuel incelemeye işaretlenir.
  --supersede-yok ile ezme kapatılır (yalnızca raporlanır).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, TesvikNace, init_db  # noqa: E402
from app.nace_extraction import (  # noqa: E402
    KAYNAK_LLM,
    ExtractionError,
    ExtractionResult,
    KapsamTuru,
    NaceKapsami,
    extract_nace_scope,
    kaynak_metni,
    satirlari_uret,
)
from app.nace_hiyerarsi import _cift_uyumu, kisim_of  # noqa: E402

OTOMATIK_ONEKI = "otomatik:"


def _alt_kume_mi(alt: str, ust: str) -> bool:
    return alt != ust and _cift_uyumu(alt, ust) == 1.0


def cakisma_turu(eski: list[str], yeni: list[str], yatay: bool) -> str:
    """Eski (otomatik) kilit ile LLM sonucu arasındaki ilişki (saf fonksiyon)."""
    if yatay:
        return "yatay_kilidi_kaldirildi"
    if set(eski) == set(yeni):
        return "ayni_kod_kaynak_yukseltildi"
    if not ({kisim_of(k) for k in eski} & {kisim_of(k) for k in yeni}):
        return "sektor_degisimi"
    if all(any(_alt_kume_mi(y, e) or y == e for e in eski) for y in yeni):
        return "kapsam_daralmasi"
    if all(any(_alt_kume_mi(e, y) or e == y for y in yeni) for e in eski):
        return "kapsam_genislemesi"
    return "karisik_degisim"


def kararlari_yukle(yol: Path) -> dict[int, NaceKapsami]:
    """Daha önceki (genellikle --dry-run) koşunun JSONL logundan kararları okur.
    Aynı kayıt birden çok kez varsa sonuncusu geçerlidir."""
    kararlar: dict[int, NaceKapsami] = {}
    for satir in yol.read_text(encoding="utf-8").splitlines():
        if satir.strip():
            kayit = json.loads(satir)
            kararlar[int(kayit["tesvik_id"])] = NaceKapsami.model_validate(kayit["kapsam"])
    return kararlar


def _tekrar_oynat(tesvik, kapsam: NaceKapsami, min_guven: float) -> ExtractionResult:
    """API'ye gitmeden kaydı loglanmış karardan yeniden üretir. Güvenlik ağları
    (dayanak metin, güven eşiği) GÜNCEL metne karşı yeniden çalışır."""
    satirlar, reddedilen, kapsam, inceleme = satirlari_uret(
        tesvik.id, kapsam, kaynak_metni(tesvik), min_guven=min_guven)
    return ExtractionResult(kapsam=kapsam, rows=satirlar, reddedilenler=reddedilen,
                            inceleme_nedenleri=inceleme)


async def _isle(tesvik, sem, client, model, min_guven, kararlar=None, tutarlilik=False):
    if kararlar and tesvik.id in kararlar:
        return tesvik, _tekrar_oynat(tesvik, kararlar[tesvik.id], min_guven), None
    async with sem:
        try:
            return tesvik, await extract_nace_scope(
                tesvik, client=client, model=model, min_guven=min_guven, tesvik_id=tesvik.id,
                tutarlilik_kontrolu=tutarlilik), None
        except ExtractionError as e:
            return tesvik, None, str(e)
        except Exception as e:  # ağ/kota: tek kayıt tüm koşuyu düşürmesin
            return tesvik, None, f"{type(e).__name__}: {e}"


def _supersede(db, eski_satirlar: list, yeni_kodlar: set[str], mevcut: set) -> int:
    """Otomatik satırları ez: yeni kümede olanın kaynağını yükselt, kalanı sil."""
    silinen = 0
    for r in eski_satirlar:
        if r.nace_prefix in yeni_kodlar:
            r.kaynak = KAYNAK_LLM
        else:
            mevcut.discard((r.tesvik_id, r.nace_prefix))
            db.delete(r)
            silinen += 1
    return silinen


async def calistir(db, *, dry_run=False, geri_al=False, yeniden=False,
                   supersede=True, limit=None, tesvik_id=None, tumunu=False,
                   min_guven=0.8, model=None, eszamanlilik=4,
                   log_yolu: Path | None = None, client=None,
                   kararlar_logu: Path | None = None, tutarlilik: bool = False) -> dict:
    sayac = {"islenen": 0, "yazilan_satir": 0, "haric_satir": 0, "yatay": 0, "belirsiz": 0,
             "kisitli": 0, "atlanan": 0, "hata": 0, "cakisma": 0, "ezilen_otomatik": 0,
             "inceleme": 0, "silinen": 0, "atlanan_yatay": 0, "logdan_oynatilan": 0}
    cikti: list[str] = []

    if geri_al:
        sorgu = db.query(TesvikNace).filter(TesvikNace.kaynak == KAYNAK_LLM)
        sayac["silinen"] = sorgu.count()
        if not dry_run:
            sorgu.delete(synchronize_session=False)
            # LLM'in kalıcı kapsam kararları da sıfırlanır; yoksa YATAY işaretli kayıtlar
            # geri aldıktan sonra da atlanırdı.
            db.query(Tesvik).filter(Tesvik.nace_kapsam_kaynak == KAYNAK_LLM).update(
                {"nace_kapsam_turu": None, "nace_kapsam_guven": None,
                 "nace_kapsam_kaynak": None, "nace_kapsam_tarihi": None},
                synchronize_session=False)
            db.commit()
        return {**sayac, "satirlar": cikti}

    kayitlar = db.query(Tesvik).order_by(Tesvik.id)
    if tesvik_id is not None:
        kayitlar = kayitlar.filter(Tesvik.id == tesvik_id)
    elif not tumunu:
        kayitlar = kayitlar.filter(Tesvik.aktif_mi.isnot(False))
    kayitlar = kayitlar.all()

    tum_satirlar = db.query(TesvikNace).all()
    mevcut = {(r.tesvik_id, r.nace_prefix) for r in tum_satirlar}
    elle = {r.tesvik_id for r in tum_satirlar if r.kaynak == "elle"}
    llm_var = {r.tesvik_id for r in tum_satirlar if r.kaynak == KAYNAK_LLM}
    otomatik: dict[int, list] = {}
    for r in tum_satirlar:
        if r.kaynak.startswith(OTOMATIK_ONEKI) and not r.haric_mi:
            otomatik.setdefault(r.tesvik_id, []).append(r)

    hedefler = []
    for t in kayitlar:
        if t.id in elle or (t.id in llm_var and not yeniden):
            sayac["atlanan"] += 1
            continue
        # Kalıcı YATAY kararı: satır olmadığı için "işlenmemiş" görünürdü, her koşuda
        # API'ye gidilirdi. --yeniden bu korumayı aşar.
        if (not yeniden and t.nace_kapsam_turu == KapsamTuru.YATAY.value
                and (t.nace_kapsam_guven or 0.0) >= min_guven):
            sayac["atlanan_yatay"] += 1
            continue
        hedefler.append(t)
    if limit:
        hedefler = hedefler[:limit]

    sem = asyncio.Semaphore(eszamanlilik)
    kararlar = kararlari_yukle(kararlar_logu) if kararlar_logu else None
    if kararlar:
        sayac["logdan_oynatilan"] = sum(1 for t in hedefler if t.id in kararlar)
    sonuclar = await asyncio.gather(*[_isle(t, sem, client, model, min_guven, kararlar, tutarlilik) for t in hedefler])

    log = None
    if log_yolu:
        yol = log_yolu.with_suffix(".dry-run.jsonl") if dry_run else log_yolu
        yol.parent.mkdir(parents=True, exist_ok=True)
        log = yol.open("a", encoding="utf-8")
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
            dahil = [r["nace_prefix"] for r in sonuc.rows if not r["haric_mi"]]
            haric = [r["nace_prefix"] for r in sonuc.rows if r["haric_mi"]]
            satir = (f"[{t.id}] {t.baslik}: {tur.value} {k.yararlanici_tipi.value} "
                     f"kodlar={','.join(dahil) or '-'} hariç={','.join(haric) or '-'} "
                     f"| {k.analiz_notu}")
            if sonuc.reddedilenler:
                satir += f" | reddedilen={sonuc.reddedilenler}"
            cikti.append(satir)
            if sonuc.manuel_inceleme_gerekli:
                sayac["inceleme"] += 1
                cikti.append(f"    MANUEL İNCELEME: {sonuc.inceleme_nedenleri}")

            # --- öncelik: LLM (güvenli) > otomatik
            eski = otomatik.get(t.id, [])
            eski_kodlar = [r.nace_prefix for r in eski]
            guvenli_yatay = tur is KapsamTuru.YATAY and k.kapsam_guven >= min_guven
            guvenli_kod = tur is KapsamTuru.SEKTOR_KISITLI and bool(dahil)
            cakisma = None
            if eski and (guvenli_yatay or guvenli_kod):
                turu = cakisma_turu(eski_kodlar, dahil, yatay=guvenli_yatay)
                aksiyon = "ezildi" if supersede else "yalnizca_raporlandi"
                cakisma = {"tur": turu, "eski": eski_kodlar, "yeni": dahil, "aksiyon": aksiyon}
                sayac["cakisma"] += 1
                cikti.append(f"    ÇAKIŞMA [{turu}]: {eski_kodlar} -> {dahil or 'YATAY'} ({aksiyon})")
                if supersede and not dry_run:
                    sayac["ezilen_otomatik"] += _supersede(db, eski, set(dahil), mevcut)
                elif supersede:
                    sayac["ezilen_otomatik"] += len([c for c in eski_kodlar if c not in dahil])
            elif eski and tur is KapsamTuru.BELIRSIZ:
                cakisma = {"tur": "korundu_belirsiz", "eski": eski_kodlar, "yeni": [],
                           "aksiyon": "otomatik_kilit_korundu"}
                sayac["cakisma"] += 1
                cikti.append(f"    ÇAKIŞMA [korundu_belirsiz]: LLM emin değil, {eski_kodlar} korundu")

            if log:
                log.write(json.dumps({
                    "tesvik_id": t.id, "baslik": t.baslik, "kapsam": k.model_dump(mode="json"),
                    "reddedilen": sonuc.reddedilenler, "haric": haric,
                    "manuel_inceleme_gerekli": sonuc.manuel_inceleme_gerekli,
                    "inceleme_nedenleri": sonuc.inceleme_nedenleri, "cakisma": cakisma,
                }, ensure_ascii=False) + "\n")

            if dry_run:
                sayac["yazilan_satir"] += len(dahil)
                sayac["haric_satir"] += len(haric)
                continue
            t.nace_kapsam_turu = tur.value
            t.nace_kapsam_guven = k.kapsam_guven
            t.nace_kapsam_kaynak = KAYNAK_LLM
            t.nace_kapsam_tarihi = datetime.now(timezone.utc).replace(tzinfo=None)
            if yeniden:
                for r in db.query(TesvikNace).filter(TesvikNace.tesvik_id == t.id,
                                                     TesvikNace.kaynak == KAYNAK_LLM):
                    db.delete(r)
                    mevcut.discard((r.tesvik_id, r.nace_prefix))
            for s in sonuc.rows:
                anahtar = (s["tesvik_id"], s["nace_prefix"])
                if anahtar in mevcut:       # supersede ile kaynağı yükseltilmiş satır olabilir
                    continue
                db.add(TesvikNace(**s))
                mevcut.add(anahtar)
                sayac["haric_satir" if s["haric_mi"] else "yazilan_satir"] += 1
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
    ap.add_argument("--log-dan-uygula", type=Path, metavar="LOG",
                    help="API'ye GİTMEDEN, önceki (dry-run) logdaki kararları uygula "
                         "(güvenlik ağları güncel metne karşı yeniden çalışır)")
    ap.add_argument("--tek-cagri", action="store_true",
                    help="Tutarlılık doğrulamasını kapat (varsayılan: SEKTOR_KISITLI kararlar "
                         "ikinci bağımsız çağrıyla doğrulanır, +%%50 API maliyeti)")
    ap.add_argument("--supersede-yok", action="store_true",
                    help="Otomatik (başlık-regex) satırları ezme; yalnızca çakışmayı raporla")
    ap.add_argument("--tumunu", action="store_true", help="Kapalı (aktif_mi=False) programlar dahil")
    ap.add_argument("--id", type=int, dest="tesvik_id")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--min-guven", type=float, default=0.8)
    ap.add_argument("--model")
    ap.add_argument("--eszamanlilik", type=int, default=4)
    ap.add_argument("--log", type=Path, default=Path("data/nace_extraction_log.jsonl"),
                    help="JSONL denetim logu (--dry-run'da <ad>.dry-run.jsonl)")
    a = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        sonuc = asyncio.run(calistir(
            db, dry_run=a.dry_run, geri_al=a.geri_al, yeniden=a.yeniden,
            supersede=not a.supersede_yok, limit=a.limit, tesvik_id=a.tesvik_id,
            tumunu=a.tumunu, min_guven=a.min_guven, model=a.model,
            eszamanlilik=a.eszamanlilik, log_yolu=a.log, kararlar_logu=a.log_dan_uygula,
            tutarlilik=not a.tek_cagri))
    finally:
        db.close()
    for s in sonuc.pop("satirlar"):
        print(s)
    etiket = "(DRY-RUN) " if a.dry_run else ""
    print("\n" + etiket + " ".join(f"{k}={v}" for k, v in sonuc.items()))


if __name__ == "__main__":
    main()
