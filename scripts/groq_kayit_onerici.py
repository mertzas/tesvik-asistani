"""Groq ile kamu mevzuat metninden kayıt ÖNERİSİ (geliştirme aracı; 2026-10-12, tur39).

Kapsam (Mert, 2026-10-12): Groq yalnız resmî kurum sayfalarının metnini okur; kullanıcı, kuruluş ya da ikas verisi bu
araca hiç girmez ve uygulamanın çalışma anı yolu (app/llm_saglayici.py, yalnız iç ağ) değişmez. Bu betik veritabanındaki
kullanıcı tablolarını okumaz; girdisi yalnız `gorevler.json` (resmî URL + çıkarılacak bilgi tarifi).

Akış: resmî URL → metin (tur21 doğrulayıcısının indirme/önbelleği) → Groq (openai/gpt-oss-120b, JSON çıktı, sıcaklık 0)
→ `oneri/<gorev>.json` → `kayit/<slug>.json` → doğrulayıcı (scripts/fix_veri_2026_10_12_tur39.py --dogrula) her alıntıyı
resmî metinde birebir arar; geçmeyen madde düşer, geçmeyen kayıt eklenmez. Model yalnız öneri üretir, karar vermez.

Maliyet: model fiyatı GroqCloud model sayfasından (2026-10-12): giriş 0,15 USD / 1M token, çıkış 0,60 USD / 1M token.
Her çağrının token kullanımı ve tutarı `harcama.json` defterine yazılır; BUTCE_USD aşılacaksa çağrı yapılmaz.

    python scripts/groq_kayit_onerici.py --self-test
    python scripts/groq_kayit_onerici.py                 (dry-run: görevler, kaynak boyutu, tahmini maliyet)
    python scripts/groq_kayit_onerici.py --calistir      (GROQ_API_KEY gerekir; .env ya da ortam değişkeni)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
DIZIN = KOK / "docs/olcum/2026-10-12-tur39"
GOREVLER = DIZIN / "gorevler.json"
DEFTER = DIZIN / "harcama.json"
MODEL = "openai/gpt-oss-120b"
URL = "https://api.groq.com/openai/v1/chat/completions"
FIYAT_GIRIS, FIYAT_CIKIS = 0.15, 0.60          # USD / 1M token (GroqCloud model sayfası, 2026-10-12)
BUTCE_USD = 1.00
# Groq ücretsiz katmanı (on_demand) dakika başına 8.000 token sayar ve istekte giriş + max_completion_tokens
# toplamına bakar (2026-10-12: 27.046 token istenince HTTP 413). Kaynak penceresi bu sınıra göre seçilir.
TPM_SINIR = 8000
KAYNAK_SINIR = 10_000                          # karakter; Türkçe mevzuatta ~3 karakter/token → ~3.400 token
PENCERE = 700                                  # anahtar kelimenin iki yanında alınan karakter
CIKTI_SINIR = 2800

SISTEM = (
    "Sen Türk resmî mevzuat ve kurum sayfalarından yapılandırılmış veri çıkaran bir ayrıştırıcısın. Kurallar: "
    "(1) Yalnız verilen KAYNAK METNİ kullan; genel bilgini kullanma. (2) Her 'alinti' alanı kaynak metinde kelimesi "
    "kelimesine geçen bir parça olmalı (10-300 karakter); harf, noktalama ve sayı değiştirme. (3) Metinde olmayan "
    "sayı, oran, tarih, tutar yazma; bilmiyorsan alanı boş bırak ya da maddeyi koyma. (4) 'metin' alanları sade "
    "Türkçe, kısa; ama içindeki her sayı aynı maddenin alıntısında da geçmeli. (5) Yalnız istenen JSON nesnesini döndür.")

SEMA = (
    '{"slug": "...", "kurum": "...", "baslik": "...", "ozet": "2-4 cümle", "kaynak_url": "<verilen URL>", '
    '"aktif_mi": true|false|null, "durum": {"metin": "...", "alinti": "birebir", "kaynak_url": "<URL>"}, '
    '"basvuru_bicimi": "proje|kredi|faiz_destegi|kefalet|bildirim_prim|uretim_odeme|belge_etuys|gider_on_onay|'
    'hisse_fon|gotuyu_hibe|diger", "bolge_kisitli": [], "sektorler": ["genel|arge|ihracat|imalat|e-ticaret|tarim|'
    'hizmet"], "tesvil_tutari": "yalnız alıntılı sayılar", "basvuru_yeri": "...", "basvuru_suresi": "...", '
    '"kontrol_listesi": [{"tur": "sart|kural|bilgi|belge|adim", "metin": "...", "alinti": "birebir", '
    '"kaynak_url": "<URL>"}], "cagrilar": [], "alintilar": [{"iddia": "...", "alinti": "birebir", "kaynak_url": '
    '"<URL>"}]}')


def _tur39():
    spec = importlib.util.spec_from_file_location("tur39", KOK / "scripts/fix_veri_2026_10_12_tur39.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def anahtar() -> str:
    deger = os.environ.get("GROQ_API_KEY", "")
    if not deger and (KOK / ".env").exists():
        for satir in (KOK / ".env").read_text(encoding="utf-8").splitlines():
            if satir.startswith("GROQ_API_KEY="):
                deger = satir.split("=", 1)[1].strip().strip('"').strip("'")
    return deger


def maliyet(giris: int, cikis: int) -> float:
    return round(giris / 1e6 * FIYAT_GIRIS + cikis / 1e6 * FIYAT_CIKIS, 6)


def defter_oku() -> dict:
    if DEFTER.exists():
        return json.loads(DEFTER.read_text(encoding="utf-8"))
    return {"model": MODEL, "fiyat_usd_1m": [FIYAT_GIRIS, FIYAT_CIKIS], "cagrilar": [], "toplam_usd": 0.0}


def defter_yaz(d: dict) -> None:
    d["toplam_usd"] = round(sum(c["usd"] for c in d["cagrilar"]), 6)
    DEFTER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def kaynak_metni(gorev: dict, metin_al) -> str:
    """Görevin resmî kaynak metinleri; uzunsa anahtar kelimelerin çevresi."""
    parcalar = []
    for url in gorev["kaynaklar"]:
        metin, hata = metin_al(url)
        if hata:
            raise RuntimeError(f"kaynak indirilemedi: {url}: {hata}")
        metin = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", metin))
        if gorev.get("bolumler"):
            # Madde sınırları: [başlangıç deseni, bitiş deseni] çiftleri; bitiş, başlangıçtan sonraki ilk eşleşme.
            dilim = []
            for bas, son in gorev["bolumler"]:
                b = re.search(bas, metin)
                e = re.compile(son).search(metin, b.end()) if b else None
                if not (b and e):
                    raise RuntimeError(f"bölüm bulunamadı: {bas} … {son}")
                dilim.append(metin[b.start():e.start()])
            metin = "\n…\n".join(dilim)
        elif len(metin) > KAYNAK_SINIR // len(gorev["kaynaklar"]) and gorev.get("anahtar"):
            pencere = []
            for m in re.finditer(gorev["anahtar"], metin, re.I):
                pencere.append((max(0, m.start() - PENCERE), m.end() + PENCERE))
            birlesik = []
            for a, b in sorted(pencere):
                if birlesik and a <= birlesik[-1][1]:
                    birlesik[-1] = (birlesik[-1][0], max(b, birlesik[-1][1]))
                else:
                    birlesik.append((a, b))
            metin = "\n…\n".join(metin[a:b] for a, b in birlesik) or metin
        parcalar.append(f"=== KAYNAK URL: {url}\n{metin[: KAYNAK_SINIR // len(gorev['kaynaklar'])]}")
    return "\n\n".join(parcalar)


def istem(gorev: dict, kaynak: str) -> list[dict]:
    return [{"role": "system", "content": SISTEM},
            {"role": "user", "content": (
                f"GÖREV: {gorev['tarif']}\nslug: {gorev['slug']}\nBUGÜN: {date.today().isoformat()}\n"
                f"Çıktı şeması (alan adları aynen): {SEMA}\n"
                "Her kaynak_url alanına alıntının geçtiği KAYNAK URL'yi yaz.\n\n" + kaynak)}]


def groq_cagir(mesajlar: list[dict], api_key: str, tasima=None) -> tuple[dict, int, int]:
    import requests
    govde = {"model": MODEL, "messages": mesajlar, "temperature": 0, "max_completion_tokens": CIKTI_SINIR,
             "response_format": {"type": "json_object"}}
    post = tasima or requests.post
    r = post(URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
             json=govde, timeout=180)
    if getattr(r, "status_code", 200) >= 400:
        raise RuntimeError(f"Groq HTTP {r.status_code}: {r.text[:300]}")
    veri = r.json()
    icerik = veri["choices"][0]["message"]["content"]
    kul = veri.get("usage") or {}
    return json.loads(icerik), int(kul.get("prompt_tokens", 0)), int(kul.get("completion_tokens", 0))


def cakisan_kayitlar(gorev: dict, kayitlar: list[tuple]) -> list[int]:
    """Görevin kaynağı olan kanuna (mevzuat.gov.tr 1.5.<no>) zaten bağlı kayıtların kimlikleri. Tur38'de KKYDP mevcut
    78/80'in kopyası olarak eklenmişti (2026-10-12); aynı kanuna bağlı kayıt varsa görev çalıştırılmaz, mevcut kayıt
    genişletilmelidir. `kayitlar`: (id, başlık, kaynak_url) — teşvik kataloğu, kullanıcı verisi değil."""
    nolar = {m for u in gorev.get("kaynaklar", []) for m in re.findall(r"1\.5\.(\d{4})\b", u)}
    if not nolar:
        return []
    desen = re.compile(r"\b(?:" + "|".join(sorted(nolar)) + r")(?:\s*sayılı|SayiliKanun|\.pdf)", re.I)
    return [i for i, baslik, url in kayitlar if desen.search(f"{baslik or ''} {url or ''}")]


def _katalog() -> list[tuple]:
    sys.path.insert(0, str(KOK))
    from app.models import SessionLocal, Tesvik
    db = SessionLocal()
    try:
        return [(t.id, t.baslik, t.kaynak_url) for t in db.query(Tesvik).all()]
    finally:
        db.close()


def calistir(gercek: bool, tasima=None, api_key: str | None = None, katalog: list[tuple] | None = None) -> int:
    tur39 = _tur39()
    gorevler = json.loads(GOREVLER.read_text(encoding="utf-8"))
    (DIZIN / "oneri").mkdir(parents=True, exist_ok=True)
    (DIZIN / "kayit").mkdir(parents=True, exist_ok=True)
    defter = defter_oku()
    api_key = api_key if api_key is not None else anahtar()
    if gercek and not api_key:
        print("GROQ_API_KEY tanımlı değil (.env ya da ortam değişkeni). Çağrı yapılmadı.")
        return 1
    toplam_tahmin = 0.0
    for g in gorevler:
        hedef = DIZIN / "oneri" / f"{g['slug']}.json"
        if hedef.exists():
            print(f"  atlandı (öneri var): {g['slug']}")
            continue
        cakisan = cakisan_kayitlar(g, katalog if katalog is not None else _katalog())
        if cakisan:
            print(f"  atlandı (aynı kanuna bağlı kayıt var: {cakisan}; mevcut kaydı genişletin): {g['slug']}")
            continue
        kaynak = kaynak_metni(g, tur39.tur21.metin_al)
        mesaj = istem(g, kaynak)
        tahmini_giris = sum(len(m["content"]) for m in mesaj) // 3
        tahmin = maliyet(tahmini_giris, CIKTI_SINIR)
        if tahmini_giris + CIKTI_SINIR > TPM_SINIR:
            print(f"  atlandı: {g['slug']} ~{tahmini_giris + CIKTI_SINIR:,} token > dakika sınırı {TPM_SINIR:,}; "
                  "anahtar kelimeyi daraltın")
            continue
        toplam_tahmin += tahmin
        print(f"  {g['slug']}: kaynak {len(kaynak):,} karakter, ~{tahmini_giris:,} token, en çok {tahmin:.4f} USD")
        if not gercek:
            continue
        if defter["toplam_usd"] + tahmin > BUTCE_USD:
            print(f"  BÜTÇE: {defter['toplam_usd']:.4f} + {tahmin:.4f} > {BUTCE_USD} USD; durdu.")
            return 1
        oneri, giris, cikis = groq_cagir(mesaj, api_key, tasima)
        usd = maliyet(giris, cikis)
        defter["cagrilar"].append({"zaman": datetime.now().isoformat(timespec="seconds"), "gorev": g["slug"],
                                   "giris_token": giris, "cikis_token": cikis, "usd": usd})
        defter_yaz(defter)
        oneri["slug"] = g["slug"]
        hedef.write_text(json.dumps(oneri, ensure_ascii=False, indent=2), encoding="utf-8")
        (DIZIN / "kayit" / f"{g['slug']}.json").write_text(json.dumps(oneri, ensure_ascii=False, indent=2),
                                                           encoding="utf-8")
        print(f"    → {giris} + {cikis} token, {usd:.5f} USD (toplam {defter['toplam_usd']:.4f})")
        time.sleep(1)
    if not gercek:
        print(f"Tahmini en çok toplam: {toplam_tahmin:.4f} USD (bütçe {BUTCE_USD} USD). Çalıştırmak için --calistir.")
    return 0


def _self_test() -> int:
    import tempfile

    class _Yanit:
        status_code = 200

        def __init__(self, icerik):
            self._i = icerik

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(self._i)}}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 200}}

    giden = {}

    def sahte_post(url, headers, json, timeout):   # noqa: A002
        giden.update(url=url, govde=json, yetki=headers["Authorization"])
        return _Yanit({"baslik": "X", "kontrol_listesi": []})

    sonuc = [("maliyet: 1M giriş + 1M çıkış = 0,75 USD", maliyet(1_000_000, 1_000_000) == 0.75)]
    oneri, g, c = groq_cagir([{"role": "user", "content": "x"}], "test-anahtar", sahte_post)
    sonuc.append(("Groq gövdesi: model, sıcaklık 0, JSON çıktı", giden["govde"]["model"] == MODEL
                  and giden["govde"]["temperature"] == 0 and giden["govde"]["response_format"]["type"] == "json_object"))
    sonuc.append(("yalnız api.groq.com", giden["url"].startswith("https://api.groq.com/")))
    sonuc.append(("token kullanımı okunur", (g, c) == (1000, 200) and oneri["baslik"] == "X"))
    m = istem({"tarif": "t", "slug": "s"}, "=== KAYNAK URL: https://www.gib.gov.tr/x\nmetin")
    sonuc.append(("istemde kullanıcı verisi alanı yok", "profil" not in json.dumps(m, ensure_ascii=False).lower()
                  and "kaynak url" in m[1]["content"].lower()))
    with tempfile.TemporaryDirectory() as d:
        global DEFTER
        eski = DEFTER
        DEFTER = Path(d) / "h.json"
        try:
            dft = defter_oku()
            dft["cagrilar"].append({"usd": 0.4})
            dft["cagrilar"].append({"usd": 0.3})
            defter_yaz(dft)
            sonuc.append(("defter toplamı", defter_oku()["toplam_usd"] == 0.7))
        finally:
            DEFTER = eski
    sonuc.append(("anahtar sohbete/çıktıya yazılmaz (yalnız başlıkta)", "test-anahtar" not in json.dumps(oneri)))
    uzun = "x " * 40_000 + "ihracat teslimi " + "y " * 40_000
    kes = kaynak_metni({"kaynaklar": ["u"], "anahtar": "ihracat teslim"}, lambda u: (uzun, None))
    tahmini = sum(len(m["content"]) for m in istem({"tarif": "t", "slug": "s"}, kes)) // 3
    bol = kaynak_metni({"kaynaklar": ["u"], "bolumler": [["Madde 11 –", "Madde 12 –"]]},
                       lambda u: ("giriş Madde 11 – ihracat istisnası metni Madde 12 – sonrası", None))
    sonuc.append(("madde sınırıyla kesim", "ihracat istisnası" in bol and "sonrası" not in bol and "giriş" not in bol))
    sonuc.append(("istek ücretsiz katmanın dakika sınırına sığar", tahmini + CIKTI_SINIR <= TPM_SINIR
                  and "ihracat teslimi" in kes))
    katalog = [(335, "Ar-Ge ve Tasarım Personeli Gelir Vergisi Stopajı Teşviki (5746 sayılı Kanun m.3/2)", ""),
               (281, "Prim desteği", "https://www.sanayi.gov.tr/assets/pdf/mevzuat/5746SayiliKanun.pdf#madde-3"),
               (9, "Başka", "https://www.mevzuat.gov.tr/mevzuatmetin/1.5.57461.pdf")]
    sonuc.append(("aynı kanuna bağlı kayıt varsa görev atlanır",
                  cakisan_kayitlar({"kaynaklar": ["https://www.mevzuat.gov.tr/mevzuatmetin/1.5.5746.pdf"]}, katalog)
                  == [335, 281]
                  and cakisan_kayitlar({"kaynaklar": ["https://www.mevzuat.gov.tr/mevzuatmetin/1.5.3065.pdf"]},
                                       katalog) == []))
    for ad, ok in sonuc:
        print(("GEÇTİ " if ok else "KALDI ") + ad)
    gecen = sum(ok for _, ok in sonuc)
    print(f"self-test: {gecen}/{len(sonuc)} geçti")
    return 0 if gecen == len(sonuc) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    sys.exit(calistir("--calistir" in sys.argv))
