"""Kendi sunucumuzdaki model ölçümü (2026-10-11): LLM_SAGLAYICI=ozel_sunucu yolunun gerçek bir açık ağırlıklı
modelle uçtan uca denemesi. Üçüncü taraf servis YOK; model iç ağda (bu ölçümde aynı makinede Ollama) çalışır.

Her senaryo için rag._llm_cevap çağrılır (üretimdeki yolun aynısı: bağlam, sistem istemi, dayanak denetimi) ve
şunlar kaydedilir: süre, modelin yanıtı dayanak denetiminden geçti mi (geçmediyse kullanıcı yerel danışmanı görür),
geçmediyse sorunlar, ham yanıt. Sonuç: ozet.json + model_NN.md.

    LLM_SAGLAYICI=ozel_sunucu LLM_BASE_URL=http://127.0.0.1:11434/v1 LLM_MODEL=gemma4:latest LLM_ZAMAN_ASIMI_SN=900 \
        python docs/olcum/2026-10-11-ozel-model/ozel_model_olc.py 1 6 11 15 23
    python docs/olcum/2026-10-11-ozel-model/ozel_model_olc.py --self-test
"""
import importlib.util
import json
import logging
import os
import sys
import time
from datetime import date

KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, KOK)
OUT = os.path.dirname(os.path.abspath(__file__))
for akim in (sys.stdout, sys.stderr):
    if hasattr(akim, "reconfigure"):
        akim.reconfigure(encoding="utf-8")


def _yerel_olc():
    spec = importlib.util.spec_from_file_location(
        "yerel_olc", os.path.join(KOK, "docs/olcum/2026-10-11-yerel-danisman/yerel_olc.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def calistir(numaralar: list[int]) -> list[dict]:
    from app import dayanak, llm_saglayici, rag
    from app.models import FinancialProfile
    s = llm_saglayici.saglayici()
    if not llm_saglayici.etkin_mi(s):
        raise SystemExit("ozel_sunucu yapılandırılmamış ya da adres iç ağda değil (LLM_SAGLAYICI/LLM_BASE_URL/LLM_MODEL)")
    P, ss = _yerel_olc().senaryolar()
    yol = os.path.join(OUT, "ozet.json")
    sonuc = json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else []
    sonuc = [x for x in sonuc if x["n"] not in numaralar]
    bugun = date.today()
    for sc in (x for x in ss if x["n"] in numaralar):
        profil = FinancialProfile(**P[sc["persona"]]) if sc["persona"] else None
        h = rag._hazirla(sc["soru"], True, profil)
        sozluk = rag.profil_sozlugu(profil) if profil is not None else None
        baglam = rag._baglam_metni(h.matches, sozluk, h.notlar, h.elenen, bugun=bugun)
        bas = time.perf_counter()
        hata, ham, sorunlar = None, "", []
        try:
            ham, bilgi = llm_saglayici.tamamla(rag.SISTEM_PROMPTU + (rag.GIRISIM_PROMPT_EKI if h.girisim else ""),
                                               f"BAĞLAM:\n{baglam}\n\nKULLANICI SORUSU: {sc['soru']}",
                                               max_tokens=rag.LLM_MAX_TOKENS)
            cevap = rag.analiz_ayikla(ham)
            sorunlar = dayanak.denetle(cevap, baglam, sc["soru"], bugun)
        except llm_saglayici.LLMHatasi as e:
            hata, bilgi, cevap = str(e), {}, ""
        sure = round(time.perf_counter() - bas, 1)
        k = dict(n=sc["n"], soru=sc["soru"], persona=sc["persona"], model=s.model, sure_sn=sure, hata=hata,
                 gecti=bool(cevap) and not sorunlar and not hata, dayanak_sorunlari=sorunlar,
                 giris_token=bilgi.get("giris"), cikis_token=bilgi.get("cikis"), uzunluk=len(cevap))
        sonuc.append(k)
        with open(os.path.join(OUT, f"model_{sc['n']:02}.md"), "w", encoding="utf-8") as f:
            f.write(f"<!-- model: {s.model} | soru: {sc['soru']} | süre: {sure} sn | geçti: {k['gecti']} -->\n"
                    f"{cevap or hata}\n")
        print(f"[{sc['n']:2}] {sure:6.1f} sn  geçti={k['gecti']}  sorun={len(sorunlar)}  hata={hata}", flush=True)
        json.dump(sorted(sonuc, key=lambda x: x["n"]), open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return sonuc


def _self_test() -> int:
    from app import llm_saglayici
    os.environ.pop("LLM_SAGLAYICI", None)
    k = [("varsayılan yerelde model etkin değil", not llm_saglayici.etkin_mi()),
         ("30 senaryo okunur", len(_yerel_olc().senaryolar()[1]) == 30)]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout)
    calistir([int(x) for x in sys.argv[1:]] or list(range(1, 31)))
