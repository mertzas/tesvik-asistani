"""Soru anlama (Groq) ölçümü, 2026-10-12: kelime kalıpları ile kalıplar + Groq etiketleri karşılaştırılır.

Soru seti: eski değerlendirmenin 30 senaryosu ve persona denemesinin 45 sorusu (75 özgün soru; sentetik, kişisel veri
yok) ve Groq'un her biri için ürettiği, kalıpları tetikleyen kelimelerden kaçınan 2 farklı söyleniş (150 soru).
Altın etiket: özgün sorudaki kalıp etiketleri, ALTIN_DUZELTME ile elle düzeltilmiş hâli; söylenişler özgün sorunun
etiketini taşır.

Ölçümler (rapor.md, rapor.json):
  * Etiket isabeti: ihtiyaç ve niyet için mikro kesinlik / duyarlılık / F1 ve tam küme eşleşmesi; yöntemler: kalıp,
    kalıp + Groq (üretim birleştirmesi, app/ihtiyac dışlama kurallarıyla), yalnız Groq.
  * Kayıt örtüşmesi: söyleniş sorusunun ilk 5 kaydı (rag.retrieve, aynı persona) ile özgün sorunun kalıpla bulunan
    ilk 5 kaydının Jaccard benzerliği; kalıp ve kalıp + Groq için.
  * Gecikme: çağrı süresi p50 / p95 (üretimdeki 2,5 sn zaman aşımı için).
  * Uçtan uca: eski 30 senaryo ve persona 45 Groq etiketleriyle yeniden üretilir; dayanak sorunu ve beklenen değer
    isabeti (kalıpla: dayanak 0, isabet 41/41).

Groq'a giden: söyleniş üretiminde özgün sentetik soru; sınıflandırmada üretimdeki istem (app/soru_anlama.istem,
maskelenmiş metin). Her çağrı harcama.json defterine yazılır; BUTCE_USD aşılacaksa çağrı yapılmaz. Sonuçlar her
çağrıdan sonra diske yazılır; yarıda kalırsa yeniden çalıştırınca kaldığı yerden devam eder.

    python docs/olcum/2026-10-12-soru-anlama/soru_anlama_olc.py --self-test
    python docs/olcum/2026-10-12-soru-anlama/soru_anlama_olc.py --hazirla        (API yok: sorular.json)
    python docs/olcum/2026-10-12-soru-anlama/soru_anlama_olc.py --parafraz       (Groq)
    python docs/olcum/2026-10-12-soru-anlama/soru_anlama_olc.py --siniflandir [--model openai/gpt-oss-20b]  (Groq)
    python docs/olcum/2026-10-12-soru-anlama/soru_anlama_olc.py --rapor          (API yok)
    python docs/olcum/2026-10-12-soru-anlama/soru_anlama_olc.py --uctan-uca      (API yok; sınıflandırma sonucunu kullanır)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KOK))
DIZIN = Path(__file__).resolve().parent
SORULAR = DIZIN / "sorular.json"
PARAFRAZ = DIZIN / "parafraz.json"
DEFTER = DIZIN / "harcama.json"
BUTCE_USD = 0.15
AZAMI_DENEME = 8
for akim in (sys.stdout, sys.stderr):
    if hasattr(akim, "reconfigure"):
        akim.reconfigure(encoding="utf-8")

# Kalıp etiketlerinin elle düzeltmesi (özgün soru kimliği → ihtiyaç / niyet). Gerekçe yanında.
ALTIN_DUZELTME: dict[str, dict] = {
    "E01": {"niyet": ["tanim", "tutar", "uygunluk"]},          # "bireysel traktör alımı destekleniyor mu"
    "E04": {"ihtiyac": ["arge"], "niyet": ["tarih", "tutar", "sure", "uygunluk"]},   # Eurostars Ar-Ge; ortak yurt dışında
    "E05": {"ihtiyac": ["girisim"]},                            # "ne kadar yatırım alabilirim": BiGG fonu, makine değil
    "E08": {"ihtiyac": ["ihracat", "dijital"], "niyet": ["tutar"]},   # "hâlâ yıllık 15.102 TL mi"
    "E13": {"ihtiyac": ["girisim"]},                            # "kafe açmak istiyorum"
    "E15": {"ihtiyac": ["tanitim", "ihracat"]},                 # Turquality ihracat markalaşma programı
    "E24": {"ihtiyac": ["girisim"]},                            # "BiGG Yatırım" program adı
    "P28": {"ihtiyac": ["girisim", "finansman"]},               # "markamla online satış" reklam talebi değil
    "P38": {"ihtiyac": ["ihracat"]},                            # Körfez'e satış; tanıtım talebi yok
    "P40": {"ihtiyac": ["tanitim", "ihracat"]},                 # pazaryeri reklamı; dijital dönüşüm değil
}

PARAFRAZ_SISTEM = (
    "Türkçe yazan bir küçük işletme sahibi gibi davran. Verilen soruyu AYNI anlamla, AYNI bilgi talebiyle, günlük "
    "konuşma diliyle 2 farklı biçimde yeniden yaz. Yasaklı kelimeleri ve köklerini KULLANMA; yerine eş anlamlı ya da "
    "dolaylı ifade kullan. Program, kurum ve yer adlarını koru. Sayıları koru. Soruya yeni bilgi ya da yeni talep "
    'ekleme. Yalnız şu JSON nesnesini döndür: {"yeniden": ["...", "..."]}')


def _modul(yol: str, ad: str):
    spec = importlib.util.spec_from_file_location(ad, KOK / yol)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _olcumler():
    return (_modul("docs/olcum/2026-10-11-yerel-danisman/yerel_olc.py", "yerel_olc"),
            _modul("docs/olcum/2026-10-12-persona/persona_olc.py", "persona_olc"))


def kalip_etiketleri(soru: str) -> tuple[list[str], list[str]]:
    from app.ihtiyac import soru_ihtiyaclari
    from app.yerel_danisman import niyetler
    return sorted(niyetler(soru) - {"liste"}), soru_ihtiyaclari(soru)


def yasakli_kelimeler(soru: str) -> list[str]:
    """Sorudaki kalıp eşleşmeleri (söylenişte kaçınılacak kelimeler), özgün yazımıyla."""
    from app.ihtiyac import SORU_KALIPLARI, _katla
    from app.yerel_danisman import _NIYET
    katli = _katla(soru)
    return sorted({m.group().strip() for k in (*SORU_KALIPLARI.values(), *_NIYET.values()) for m in k.finditer(katli)
                   if m.group().strip()})


def hazirla() -> list[dict]:
    yo, po = _olcumler()
    P1, s1 = yo.senaryolar()
    P2, s2 = po.senaryolar()
    sorular = []
    for onek, P, ss in (("E", P1, s1), ("P", P2, s2)):
        for s in ss:
            kimlik = f"{onek}{s['n']:02}"
            niyet, ihtiyac = kalip_etiketleri(s["soru"])
            altin = {"niyet": niyet, "ihtiyac": ihtiyac, **ALTIN_DUZELTME.get(kimlik, {})}
            sorular.append(dict(id=kimlik, persona=s["persona"], profil=P.get(s["persona"]) if s["persona"] else None,
                                soru=s["soru"], beklenen=s["beklenen"], tur=s["tur"],
                                altin={"niyet": sorted(altin["niyet"]), "ihtiyac": sorted(altin["ihtiyac"])},
                                yasakli=yasakli_kelimeler(s["soru"])))
    SORULAR.write_text(json.dumps(sorular, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(sorular)} özgün soru → {SORULAR.name}; elle düzeltilen altın etiket: {len(ALTIN_DUZELTME)}")
    return sorular


# ------------------------------------------------------------------ Groq çağrısı (bekleme ve defter)
def anahtar() -> str:
    deger = os.environ.get("GROQ_API_KEY", "")
    if not deger and (KOK / ".env").exists():
        for satir in (KOK / ".env").read_text(encoding="utf-8").splitlines():
            if satir.startswith("GROQ_API_KEY="):
                deger = satir.split("=", 1)[1].strip().strip('"').strip("'")
    return deger


def defter_oku() -> dict:
    if DEFTER.exists():
        return json.loads(DEFTER.read_text(encoding="utf-8"))
    return {"cagrilar": [], "toplam_usd": 0.0, "butce_usd": BUTCE_USD}


def defter_yaz(d: dict) -> None:
    d["toplam_usd"] = round(sum(c["usd"] for c in d["cagrilar"]), 6)
    DEFTER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


class BekleSinir(Exception):
    """Günlük kota ya da bütçe: çalışma durur, yeniden çalıştırınca kaldığı yerden sürer."""


def cagir(mesajlar: list[dict], model: str, api_key: str, defter: dict, etiket: str, *, tasima=None,
          uyku=time.sleep, cikti_siniri: int | None = None) -> tuple[str, float]:
    """Üretimdeki gövdeyle (app/soru_anlama.groq_cagir) çağrı; 429'da Retry-After kadar bekler. (içerik, süre)."""
    import httpx

    from app import soru_anlama
    tahmin = soru_anlama.maliyet_usd(model, sum(len(m["content"]) for m in mesajlar) // 3,
                                     cikti_siniri or soru_anlama.CIKTI_SINIR)
    if defter["toplam_usd"] + tahmin > BUTCE_USD:
        raise BekleSinir(f"bütçe: {defter['toplam_usd']:.4f} + {tahmin:.4f} > {BUTCE_USD} USD")
    govde = {"model": model, "messages": mesajlar, "temperature": 0,
             "max_completion_tokens": cikti_siniri or soru_anlama.CIKTI_SINIR, "response_format": {"type": "json_object"}}
    if model.startswith("openai/gpt-oss"):
        govde |= {"reasoning_effort": "low", "include_reasoning": False}
    ek = {"transport": tasima} if tasima is not None else {}
    with httpx.Client(timeout=60, trust_env=False, follow_redirects=False, **ek) as c:
        for deneme in range(AZAMI_DENEME):
            bas = time.perf_counter()
            r = c.post(soru_anlama.URL, headers={"Authorization": f"Bearer {api_key}"}, json=govde)
            sure = time.perf_counter() - bas
            if r.status_code == 429:
                govde_metni = r.text[:400]
                if re.search(r"per day|TPD|RPD", govde_metni):
                    raise BekleSinir(f"günlük kota: {govde_metni}")
                bekle = float(r.headers.get("retry-after") or 10)
                print(f"    429, {bekle:.0f} sn bekleniyor")
                uyku(min(bekle + 0.5, 90))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Groq HTTP {r.status_code}: {r.text[:300]}")
            veri = r.json()
            kul = veri.get("usage") or {}
            giris, cikis = int(kul.get("prompt_tokens", 0)), int(kul.get("completion_tokens", 0))
            defter["cagrilar"].append({"etiket": etiket, "model": model, "giris": giris, "cikis": cikis,
                                       "usd": soru_anlama.maliyet_usd(model, giris, cikis), "sure_sn": round(sure, 3)})
            defter_yaz(defter)
            return veri["choices"][0]["message"]["content"] or "", sure
    raise BekleSinir("art arda 429")


def parafraz(api_key: str | None = None, tasima=None, uyku=time.sleep) -> int:
    sorular = json.loads(SORULAR.read_text(encoding="utf-8"))
    sonuc = json.loads(PARAFRAZ.read_text(encoding="utf-8")) if PARAFRAZ.exists() else {}
    api_key = api_key if api_key is not None else anahtar()
    if not api_key:
        print("GROQ_API_KEY tanımlı değil; çağrı yapılmadı.")
        return 1
    defter = defter_oku()
    model = "openai/gpt-oss-120b"
    for s in sorular:
        if s["id"] in sonuc:
            continue
        mesaj = [{"role": "system", "content": PARAFRAZ_SISTEM},
                 {"role": "user", "content": f"SORU: {s['soru']}\nYASAKLI KELİMELER: {', '.join(s['yasakli']) or '-'}"}]
        try:
            icerik, _ = cagir(mesaj, model, api_key, defter, f"parafraz:{s['id']}", tasima=tasima, uyku=uyku,
                              cikti_siniri=1000)
            yeni = [x.strip() for x in json.loads(icerik).get("yeniden", []) if isinstance(x, str) and x.strip()][:2]
        except BekleSinir as e:
            print(f"durdu: {e}")
            break
        except (ValueError, RuntimeError) as e:
            print(f"  {s['id']}: atlandı ({type(e).__name__}: {str(e)[:120]})")
            continue
        sonuc[s["id"]] = yeni
        PARAFRAZ.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {s['id']}: {len(yeni)} söyleniş | toplam {defter['toplam_usd']:.4f} USD")
    print(f"söyleniş: {len(sonuc)}/{len(sorular)} soru; harcama {defter['toplam_usd']:.4f} USD")
    return 0


def tum_sorular() -> list[dict]:
    """Özgün sorular + söyleniş soruları (söyleniş: id 'E04a', özgünün altın etiketi ve personası)."""
    sorular = json.loads(SORULAR.read_text(encoding="utf-8"))
    paraf = json.loads(PARAFRAZ.read_text(encoding="utf-8")) if PARAFRAZ.exists() else {}
    tum = [dict(s, ozgun=s["id"], tip="ozgun") for s in sorular]
    for s in sorular:
        for harf, metin in zip("ab", paraf.get(s["id"], [])):
            tum.append(dict(s, id=s["id"] + harf, soru=metin, ozgun=s["id"], tip="soylenis", beklenen=[]))
    return tum


def sinif_dosyasi(model: str) -> Path:
    return DIZIN / f"siniflandirma_{model.split('/')[-1]}.jsonl"


def siniflandirmalar(model: str) -> dict[str, dict]:
    yol = sinif_dosyasi(model)
    if not yol.exists():
        return {}
    return {k["id"]: k for k in (json.loads(x) for x in yol.read_text(encoding="utf-8").splitlines() if x.strip())}


def siniflandir(model: str, api_key: str | None = None, tasima=None, uyku=time.sleep) -> int:
    from app import soru_anlama
    api_key = api_key if api_key is not None else anahtar()
    if not api_key:
        print("GROQ_API_KEY tanımlı değil; çağrı yapılmadı.")
        return 1
    yapilan = siniflandirmalar(model)
    defter = defter_oku()
    for s in tum_sorular():
        if s["id"] in yapilan:
            continue
        maskeli = soru_anlama.maskele(s["soru"])
        try:
            icerik, sure = cagir(soru_anlama.istem(maskeli), model, api_key, defter, f"sinif:{s['id']}",
                                 tasima=tasima, uyku=uyku)
        except BekleSinir as e:
            print(f"durdu: {e}")
            break
        try:
            niyet, ihtiyac = soru_anlama.ayristir(icerik)
            hata = None
        except ValueError as e:
            niyet, ihtiyac, hata = frozenset(), (), f"{type(e).__name__}"
        kayit = {"id": s["id"], "maskeli": maskeli, "niyet": sorted(niyet), "ihtiyac": list(ihtiyac),
                 "sure_sn": round(sure, 3), "hata": hata}
        with sinif_dosyasi(model).open("a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        print(f"  {s['id']:5} {sure:4.2f} sn n={kayit['niyet']} i={kayit['ihtiyac']} | {defter['toplam_usd']:.4f} USD")
    print(f"sınıflandırma ({model}): {len(siniflandirmalar(model))}/{len(tum_sorular())}; "
          f"harcama {defter_oku()['toplam_usd']:.4f} USD")
    return 0


# ------------------------------------------------------------------ ölçüm
def prf(tahmin: list[set], altin: list[set]) -> dict:
    dp = sum(len(t & a) for t, a in zip(tahmin, altin))
    yp = sum(len(t - a) for t, a in zip(tahmin, altin))
    yn = sum(len(a - t) for t, a in zip(tahmin, altin))
    k = dp / (dp + yp) if dp + yp else 1.0
    d = dp / (dp + yn) if dp + yn else 1.0
    return {"kesinlik": round(k, 3), "duyarlilik": round(d, 3), "f1": round(2 * k * d / (k + d), 3) if k + d else 0.0,
            "tam_eslesme": round(sum(t == a for t, a in zip(tahmin, altin)) / max(len(altin), 1), 3),
            "dogru": dp, "fazla": yp, "eksik": yn, "n": len(altin)}


def jaccard(a: list, b: list) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def _etiket(s: dict, k: dict | None):
    from app import soru_anlama
    if not k:
        return None
    return soru_anlama.Etiketler(soru_anlama._anahtar(s["soru"]), frozenset(k["niyet"]), tuple(k["ihtiyac"]), "olcum",
                                 True)


def yontem_etiketleri(s: dict, k: dict | None) -> dict[str, tuple[set, set]]:
    from app import soru_anlama
    from app.ihtiyac import soru_ihtiyaclari
    from app.yerel_danisman import niyetler
    kalip = (niyetler(s["soru"]) - {"liste"}, set(soru_ihtiyaclari(s["soru"])))
    with soru_anlama.baglam(_etiket(s, k)):
        birlesik = (niyetler(s["soru"]) - {"liste"}, set(soru_ihtiyaclari(s["soru"])))
    groq = (set(k["niyet"]), set(k["ihtiyac"])) if k else (set(), set())
    return {"kalip": kalip, "kalip+groq": birlesik, "yalniz_groq": groq}


def retrieve_idleri(s: dict, k: dict | None, limit: int = 5) -> list[int]:
    from app import rag, soru_anlama
    from app.models import FinancialProfile
    profil = FinancialProfile(**s["profil"]) if s.get("profil") else None
    with soru_anlama.baglam(_etiket(s, k)):
        return [t.id for t in rag.retrieve(s["soru"], limit=limit, profil_kaydi=profil)]


def uretimde(s: dict, k: dict | None) -> dict | None:
    """Üretim kuralı: programı ya da kurumu adıyla anan soru Groq'a gönderilmez (app/rag.soru_anlama_gerekli_mi)."""
    from app import rag
    return k if k is not None and rag.soru_anlama_gerekli_mi(s["soru"]) else None


def rapor(modeller: list[str]) -> dict:
    tum = tum_sorular()
    sonuc: dict = {"soru_sayisi": {"ozgun": sum(s["tip"] == "ozgun" for s in tum),
                                   "soylenis": sum(s["tip"] == "soylenis" for s in tum)}, "modeller": {}}
    ozgun_kayit = {s["id"]: retrieve_idleri(s, None) for s in tum if s["tip"] == "ozgun"}
    for model in modeller:
        siniflar = siniflandirmalar(model)
        if not siniflar:
            continue
        m: dict = {"siniflandirilan": len(siniflar), "hata": sum(1 for k in siniflar.values() if k.get("hata")),
                   "uretimde_gonderilmeyen": sum(1 for s in tum if s["id"] in siniflar and uretimde(s, {}) is None)}
        sureler = sorted(k["sure_sn"] for k in siniflar.values())
        m["gecikme_sn"] = {"p50": round(statistics.median(sureler), 3),
                           "p95": round(sureler[int(0.95 * (len(sureler) - 1))], 3), "en_cok": sureler[-1],
                           "2.5_sn_ustu": sum(x > 2.5 for x in sureler)}
        for tip in ("ozgun", "soylenis"):
            ss = [s for s in tum if s["tip"] == tip and s["id"] in siniflar]
            if not ss:
                continue
            et = [yontem_etiketleri(s, uretimde(s, siniflar[s["id"]])) for s in ss]
            altin_n = [set(s["altin"]["niyet"]) for s in ss]
            altin_i = [set(s["altin"]["ihtiyac"]) for s in ss]
            m[tip] = {y: {"ihtiyac": prf([e[y][1] for e in et], altin_i), "niyet": prf([e[y][0] for e in et], altin_n)}
                      for y in ("kalip", "kalip+groq", "yalniz_groq")}
            if tip == "soylenis":
                jk = [jaccard(retrieve_idleri(s, None), ozgun_kayit[s["ozgun"]]) for s in ss]
                jg = [jaccard(retrieve_idleri(s, uretimde(s, siniflar[s["id"]])), ozgun_kayit[s["ozgun"]]) for s in ss]
                m["kayit_ortusmesi"] = {"kalip": round(statistics.mean(jk), 3), "kalip+groq": round(statistics.mean(jg), 3),
                                        "iyilesen": sum(g > k for k, g in zip(jk, jg)),
                                        "kotulesen": sum(g < k for k, g in zip(jk, jg)), "n": len(ss)}
                m["ornekler"] = [
                    {"id": s["id"], "soru": s["soru"], "altin": s["altin"]["ihtiyac"], "kalip": sorted(e["kalip"][1]),
                     "kalip+groq": sorted(e["kalip+groq"][1])}
                    for s, e in zip(ss, et) if e["kalip"][1] != e["kalip+groq"][1]][:40]
        sonuc["modeller"][model] = m
    defter = defter_oku()
    sonuc["harcama_usd"] = defter["toplam_usd"]
    sonuc["cagri_sayisi"] = len(defter["cagrilar"])
    (DIZIN / "rapor.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    (DIZIN / "rapor.md").write_text(rapor_md(sonuc), encoding="utf-8")
    print(rapor_md(sonuc))
    return sonuc


def rapor_md(r: dict) -> str:
    sat = ["# Soru anlama (Groq) ölçümü — 2026-10-12", "",
           f"Özgün soru {r['soru_sayisi']['ozgun']}, söyleniş {r['soru_sayisi']['soylenis']}; Groq çağrısı "
           f"{r['cagri_sayisi']}, harcama {r['harcama_usd']:.4f} USD.", "",
           "Yöntemler üretim kuralıyla: program ya da kurum adı geçen soru Groq'a gönderilmez (o soruda Groq etiketi "
           "yok sayılır, `yalniz_groq` boştur); Groq'un niyet etiketleri kullanılmaz (`kalip+groq` niyeti = kalıp). "
           "Altın etiket: kalıp etiketi + 10 elle düzeltme (soru_anlama_olc.ALTIN_DUZELTME); kalıba yakın olduğu için "
           "özgün sorularda kalıp lehine yanlıdır. Karar ve uçtan uca sonuç: KARAR.md.", ""]
    for model, m in r["modeller"].items():
        g = m["gecikme_sn"]
        sat += [f"## {model}", "", f"Sınıflandırılan {m['siniflandirilan']} (biçim hatası {m['hata']}; program/kurum "
                f"adı geçtiği için üretimde gönderilmeyecek {m['uretimde_gonderilmeyen']}, bunlarda kalıp + Groq = kalıp); "
                f"gecikme p50 "
                f"{g['p50']} sn, p95 {g['p95']} sn, en çok {g['en_cok']} sn, 2,5 sn üstü {g['2.5_sn_ustu']}.", ""]
        for tip, ad in (("ozgun", "Özgün sorular"), ("soylenis", "Farklı söylenişler")):
            if tip not in m:
                continue
            sat += [f"### {ad}", "", "| yöntem | ihtiyaç K / D / F1 | ihtiyaç tam | fazla / eksik | niyet F1 | niyet tam |",
                    "|---|---|---|---|---|---|"]
            for y, v in m[tip].items():
                i, n = v["ihtiyac"], v["niyet"]
                sat.append(f"| {y} | {i['kesinlik']} / {i['duyarlilik']} / {i['f1']} | {i['tam_eslesme']} | "
                           f"{i['fazla']} / {i['eksik']} | {n['f1']} | {n['tam_eslesme']} |")
            sat.append("")
        if "kayit_ortusmesi" in m:
            o = m["kayit_ortusmesi"]
            sat += [f"Kayıt örtüşmesi (söyleniş ilk 5 kayıt ∩ özgün soru ilk 5 kayıt, Jaccard): kalıp {o['kalip']}, "
                    f"kalıp + Groq {o['kalip+groq']}; iyileşen {o['iyilesen']}, kötüleşen {o['kotulesen']} / {o['n']}.", ""]
    return "\n".join(sat)


def uctan_uca(model: str) -> int:
    """Eski 30 ve persona 45, Groq etiketleri bağlamdayken yeniden üretilir (API yok)."""
    from app import soru_anlama
    yo, po = _olcumler()
    siniflar = siniflandirmalar(model)
    sorular = {s["soru"]: s for s in json.loads(SORULAR.read_text(encoding="utf-8"))}
    bulunamayan = [s["id"] for s in sorular.values() if s["id"] not in siniflar]
    if bulunamayan:
        print(f"sınıflandırması olmayan özgün soru: {bulunamayan}; önce --siniflandir")
        return 1
    # calistir() bağlam kurmadan soruları sırayla işler; etiket, işlenen sorunun metniyle bulunur.
    def ek_ihtiyaclar(soru):
        s = sorular.get(soru)
        return tuple(siniflar[s["id"]]["ihtiyac"]) if s and uretimde(s, siniflar[s["id"]]) else ()

    def ek_niyetler(soru):
        s = sorular.get(soru)
        return frozenset(siniflar[s["id"]]["niyet"]) if s and soru_anlama.NIYET_KULLAN else frozenset()

    soru_anlama.ek_ihtiyaclar, soru_anlama.ek_niyetler = ek_ihtiyaclar, ek_niyetler
    ozet = {}
    for ad, P, ss in (("eski30", *yo.senaryolar()), ("persona45", *po.senaryolar())):
        out = DIZIN / "uctan_uca" / ad
        out.mkdir(parents=True, exist_ok=True)
        print(f"=== {ad}")
        sonuc = yo.calistir(P, ss, str(out))
        ozet[ad] = {"dayanak": sum(len(x["dayanak_sorunlari"]) for x in sonuc),
                    "isabet": f"{sum(len(x['isabet']) for x in sonuc)}/{sum(len(x['beklenen']) for x in sonuc)}",
                    "yasak_dil": sum(x["yasak_dil"] for x in sonuc)}
    (DIZIN / "uctan_uca" / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ self-test
def _self_test() -> int:
    import tempfile

    import httpx
    global DIZIN, SORULAR, PARAFRAZ, DEFTER, BUTCE_USD
    asil = (DIZIN, SORULAR, PARAFRAZ, DEFTER, BUTCE_USD)
    gecici = Path(tempfile.mkdtemp())
    DIZIN, SORULAR, PARAFRAZ, DEFTER = gecici, gecici / "s.json", gecici / "p.json", gecici / "h.json"
    try:
        SORULAR.write_text(json.dumps([dict(id="E01", persona=None, profil=None, soru="Yabancı alıcılara satmak "
                                            "istiyoruz", beklenen=[], tur="t", altin={"niyet": [], "ihtiyac": ["ihracat"]},
                                            yasakli=[])], ensure_ascii=False), encoding="utf-8")
        cagrilar, beklemeler = [], []
        sira = [httpx.Response(429, headers={"retry-after": "2"}, text="rate limit per minute"),
                httpx.Response(200, json={"choices": [{"message": {"content": '{"yeniden": ["Dış alıcıya satış", '
                                                                   '"Yurt dışı müşteri"]}'}}],
                                          "usage": {"prompt_tokens": 300, "completion_tokens": 80}}),
                httpx.Response(200, json={"choices": [{"message": {"content": '{"niyet": [], "ihtiyac": ["ihracat"]}'}}],
                                          "usage": {"prompt_tokens": 800, "completion_tokens": 30}})]

        def sunucu(r):
            cagrilar.append(json.loads(r.content))
            return sira.pop(0) if sira else httpx.Response(200, json={
                "choices": [{"message": {"content": '{"niyet": [], "ihtiyac": []}'}}], "usage": {}})
        t = httpx.MockTransport(sunucu)
        parafraz("k", tasima=t, uyku=beklemeler.append)
        paraf_ok = json.loads(PARAFRAZ.read_text(encoding="utf-8"))["E01"] == ["Dış alıcıya satış", "Yurt dışı müşteri"]
        siniflandir("openai/gpt-oss-120b", "k", tasima=t, uyku=beklemeler.append)
        s1 = siniflandirmalar("openai/gpt-oss-120b")
        n_cagri = len(cagrilar)
        siniflandir("openai/gpt-oss-120b", "k", tasima=t, uyku=beklemeler.append)   # devam: yeni çağrı yok
        devam_ok = len(cagrilar) == n_cagri
        defter = defter_oku()
        s = tum_sorular()
        BUTCE_USD = defter["toplam_usd"]   # bütçe doldu: çağrı yapılmaz
        PARAFRAZ.unlink()
        parafraz("k", tasima=t, uyku=beklemeler.append)
        butce_ok = len(cagrilar) == n_cagri
        uretim_govdesi = cagrilar[2]
        k = [("429'da Retry-After kadar beklenir", beklemeler and beklemeler[0] >= 2),
             ("söyleniş kaydedilir", paraf_ok),
             ("özgün + 2 söyleniş sınıflandırılır", set(s1) == {"E01", "E01a", "E01b"} and s1["E01"]["ihtiyac"] == ["ihracat"]),
             ("sınıflandırma üretim istemiyle", uretim_govdesi["messages"][0]["content"].startswith("Türkiye'deki devlet")
              and uretim_govdesi["temperature"] == 0 and uretim_govdesi.get("reasoning_effort") == "low"),
             ("kaldığı yerden devam", devam_ok),
             ("bütçe dolunca çağrı yok", butce_ok),
             ("defter tutulur", len(defter["cagrilar"]) == 4 and defter["toplam_usd"] > 0),
             ("söylenişler özgünün altın etiketini taşır", len(s) == 3 and s[1]["altin"] == s[0]["altin"]),
             ("P/R/F1", prf([{"a", "b"}, set()], [{"a"}, {"c"}]) == {"kesinlik": 0.5, "duyarlilik": 0.5, "f1": 0.5,
                                                                     "tam_eslesme": 0.0, "dogru": 1, "fazla": 1,
                                                                     "eksik": 1, "n": 2}),
             ("altın düzeltme anahtarları geçerli", all(set(v) <= {"niyet", "ihtiyac"} for v in ALTIN_DUZELTME.values())),
             ("yasaklı kelimeler", "ihracat" in " ".join(yasakli_kelimeler("İhracat için ne kadar kredi var?")))]
    finally:
        DIZIN, SORULAR, PARAFRAZ, DEFTER, BUTCE_USD = asil
    g = sum(1 for _, ok in k if ok)
    for ad, ok in k:
        print(f"  [{'OK' if ok else 'HATA'}] {ad}")
    print(f"self-test: {g}/{len(k)}")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    arg = sys.argv[1:]
    model = arg[arg.index("--model") + 1] if "--model" in arg else "openai/gpt-oss-120b"
    if "--self-test" in arg:
        sys.exit(_self_test())
    if "--hazirla" in arg:
        hazirla()
    elif "--parafraz" in arg:
        sys.exit(parafraz())
    elif "--siniflandir" in arg:
        sys.exit(siniflandir(model))
    elif "--rapor" in arg:
        rapor(["openai/gpt-oss-120b", "openai/gpt-oss-20b"])
    elif "--uctan-uca" in arg:
        sys.exit(uctan_uca(model))
    else:
        print(__doc__)
