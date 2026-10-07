"""Aşama 3 ölçümü.

  python asama3_olcum.py baglam   -> 15 soru, LLM'siz: retrieve + bağlam denetimi (ücretsiz)
  python asama3_olcum.py model    -> persona başına 1 gerçek Claude çağrısı (10 çağrı, ÜCRETLİ)
  python asama3_olcum.py model 3  -> yalnızca 3. soru

Çıktılar: scratchpad/asama3/{baglam_ozet.json, cevap_NN.md, model_ozet.json}
Salt okunur: veritabanına yazmaz.
"""
import json, os, re, sys, time
from app import rag
from app.models import SessionLocal, FinancialProfile, Tesvik
from app.girisim import girisim_modu_mu

SP = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SP, "asama3"); os.makedirs(OUT, exist_ok=True)

PERSONA = {
 "1 Konya ciftci": dict(sektor="tarim", bolge="Konya", calisan_sayisi=3, yillik_ciro=2.5e6, arazi_buyuklugu_dekar=180, urun_turu="buğday", hedefler=["makine", "hayvan"], sirket_turu="sahis"),
 "2 Izmir tekstil": dict(sektor="imalat", bolge="İzmir", calisan_sayisi=12, yillik_ciro=60e6, nace_kodu="13.20", hedefler=["yatirim", "ihracat"], sirket_turu="limited"),
 "3 Ankara girisim": dict(sektor="arge", bolge="Ankara", calisan_sayisi=0, yillik_ciro=0, nace_kodu="62.01", sirket_turu="yok", trl=4, hedefler=["arge"]),
 "4 Van otel": dict(sektor="hizmet", bolge="Van", calisan_sayisi=25, yillik_ciro=30e6, nace_kodu="55.10", hedefler=["yatirim"], sirket_turu="anonim"),
 "5 Trabzon eticaret": dict(sektor="e-ticaret", bolge="Trabzon", calisan_sayisi=3, yillik_ciro=4e6, nace_kodu="47.91", hedefler=["ihracat"], sirket_turu="limited"),
 "6 Istanbul SaaS": dict(sektor="arge", bolge="İstanbul", calisan_sayisi=12, yillik_ciro=20e6, nace_kodu="62.01", sirket_turu="limited", trl=8, hedefler=["ihracat", "arge"]),
 "7 Bursa buyuk imalat": dict(sektor="imalat", bolge="Bursa", calisan_sayisi=400, yillik_ciro=2e9, nace_kodu="29.10", sirket_turu="anonim", hedefler=["yatirim", "arge"]),
 "8 Hatay mikro": dict(sektor="hizmet", bolge="Hatay", calisan_sayisi=4, yillik_ciro=3e6, nace_kodu="56.10", sirket_turu="sahis", hedefler=["istihdam"]),
 "9 Ekmek 10.71 Konya": dict(sektor="imalat", bolge="Konya", calisan_sayisi=30, yillik_ciro=80e6, nace_kodu="10.71", sirket_turu="limited", hedefler=["yatirim"]),
 "10 Hatay NACEsiz hizmet": dict(sektor="hizmet", bolge="Hatay", calisan_sayisi=2, yillik_ciro=1e6, sirket_turu="sahis", hedefler=["finansman"]),
}
# (persona, soru). İlk 10 = persona başına 1 gerçek çağrı; 11-15 yalnızca bağlam denetimi.
SORULAR = [
 ("1 Konya ciftci", "180 dekar buğday ekiyorum, traktör ve mibzer almak istiyorum; mazot-gübre desteği de alabilir miyim?"),
 ("2 Izmir tekstil", "Yeni dokuma hattı için makine yatırımı yapıp Almanya'ya ihracata başlayacağız. Hangi teşviklere başvurabiliriz, vergi indirimi var mı?"),
 ("3 Ankara girisim", "Şirketim yok, yapay zekâ tabanlı bir yazılım fikrim var, prototip aşamasındayım. Hangi hibelere başvurabilirim?"),
 ("4 Van otel", "Van'da 40 odalı otelimize 30 oda ekleyeceğiz; yatırım teşvik belgesi alabilir miyiz, SGK ve faiz desteği var mı?"),
 ("5 Trabzon eticaret", "Fındık ürünlerimizi Amazon üzerinden yurt dışına satmak istiyoruz; e-ihracat desteği, pazaryeri komisyonu ve reklam desteği var mı?"),
 ("6 Istanbul SaaS", "SaaS ürünümüzü ABD'ye satıyoruz; bulut sunucu, dijital reklam ve App Store komisyonları için hangi destekler var? 5448 sayılı Karar hâlâ geçerli mi?"),
 ("7 Bursa buyuk imalat", "400 çalışanlı otomotiv parça üreticisiyiz; elektrikli araç aktarma organı için 500 milyon TL yatırım planlıyoruz. Hangi program, hangi oranlar?"),
 ("8 Hatay mikro", "Hatay'da 4 kişilik restoranımız var, 3 kişi daha işe alacağız; istihdam ve SGK desteği nedir?"),
 ("9 Ekmek 10.71 Konya", "Yeni ekmek üretim hattı için makine alacağım ve ürün geliştirme yapacağım; yatırım teşvik belgesi alabilir miyim?"),
 ("10 Hatay NACEsiz hizmet", "İşletme sermayesi için uygun faizli kredi veya kefalet desteği arıyorum, ne önerirsiniz?"),
 ("6 Istanbul SaaS", "KOSGEB Girişimci Destek Programı bana uygun mu?"),
 ("2 Izmir tekstil", "1507 TÜBİTAK başvurusu için şartlar neler, kaç TL hibe alınır?"),
 ("4 Van otel", "2012/3305 sayılı Bölgesel Teşvik uygulamasından yararlanabilir miyim?"),
 ("1 Konya ciftci", "Hayvancılığa geçmek istiyorum, 50 baş süt ineği için hibe var mı?"),
 ("7 Bursa buyuk imalat", "Büyük işletmeyiz, KOSGEB'den yararlanamıyoruz; Ar-Ge merkezi ve TÜBİTAK 1501 için ne yapmalıyız?"),
]

db = SessionLocal()
DB_URLS = {t.kaynak_url for t in db.query(Tesvik).all() if t.kaynak_url}
DB_BASLIK = {t.id: t.baslik for t in db.query(Tesvik).all()}
AKTIF = {t.id: t.aktif_mi for t in db.query(Tesvik).all()}


def _profil(ad):
    return FinancialProfile(**PERSONA[ad])


def baglam_denetimi():
    ozet = []
    for n, (ad, soru) in enumerate(SORULAR, 1):
        p = _profil(ad)
        matches = rag.retrieve(soru, limit=rag.CEVAP_KAYIT_SAYISI, profil_kaydi=p)
        notlar = {i: u.metin() for i, u in rag.profil_9903_degerlendirmesi(matches, p).items()}
        elenen = rag.elenen_9903_metni(soru, p)
        eski = rag.eski_sistem_notu(soru)
        if eski and rag.ESKI_SISTEM_NOTU not in elenen:
            elenen = (elenen + "\n" if elenen else "") + eski
        girisim = girisim_modu_mu(p, soru)
        baglam = rag._baglam_metni(matches, rag.profil_sozlugu(p), notlar, elenen)
        kapali = [m.id for m in matches if m.aktif_mi is False]
        gurultu = [m.id for m in matches if "Buradasınız" in rag._tesvik_detay_metni(m)
                   or "Çerez" in rag._tesvik_detay_metni(m)]
        satir = dict(n=n, persona=ad, soru=soru, idler=[m.id for m in matches],
                     basliklar=[DB_BASLIK[m.id][:45] for m in matches], notlar=notlar, elenen_var=bool(elenen),
                     girisim=girisim, baglam_kar=len(baglam), tahmini_token=len(baglam) // 3,
                     kapali_kayit=kapali, gurultulu_kayit=gurultu)
        ozet.append(satir)
        print(f"\n[{n:2}] {ad} | {soru[:70]}")
        print(f"     kayıt={len(matches)} bağlam={len(baglam)} kar (~{len(baglam)//3} tok) girişim={girisim} "
              f"elenen={'var' if elenen else '-'} kapalı={kapali} gürültü={gurultu}")
        for m in matches:
            print(f"       {m.id:4} {DB_BASLIK[m.id][:60]}" + (f"  <9903: {notlar[m.id][:40]}>" if m.id in notlar else ""))
    json.dump(ozet, open(os.path.join(OUT, "baglam_ozet.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ gerçek model
KAYIT = []


def _kaydedici_kur():
    import anthropic
    Orig = anthropic.Anthropic

    class Kayitci(Orig):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            orig = self.messages.create

            def create(**kw):
                t0 = time.time()
                r = orig(**kw)
                u = getattr(r, "usage", None)
                KAYIT.append(dict(api_sure_sn=round(time.time() - t0, 1), stop=getattr(r, "stop_reason", None),
                                  giris_token=getattr(u, "input_tokens", None),
                                  cikis_token=getattr(u, "output_tokens", None),
                                  sistem_kar=len(kw.get("system", "")),
                                  mesaj_kar=len(kw["messages"][0]["content"])))
                return r
            self.messages.create = create
    anthropic.Anthropic = Kayitci


_SAYI = re.compile(r"(?<![\w.])(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(?:TL|₺|%|milyon|bin)|%\s*\d+(?:[.,]\d+)?")


def _sayilar(metin):
    return {re.sub(r"\s+", "", m.group(0).replace("₺", "TL")) for m in _SAYI.finditer(metin)}


def model_olcumu(secim=None):
    _kaydedici_kur()
    ozet = []
    hedef = SORULAR[:10] if secim is None else [SORULAR[secim - 1]]
    for ad, soru in hedef:
        n = SORULAR.index((ad, soru)) + 1
        p = _profil(ad)
        matches = rag.retrieve(soru, limit=rag.CEVAP_KAYIT_SAYISI, profil_kaydi=p)
        notlar = {i: u.metin() for i, u in rag.profil_9903_degerlendirmesi(matches, p).items()}
        elenen = rag.elenen_9903_metni(soru, p)
        baglam = rag._baglam_metni(matches, rag.profil_sozlugu(p), notlar, elenen)
        KAYIT.clear()
        t0 = time.time()
        cevap = rag.answer(soru, rag.profil_sozlugu(p), llm_kullan=True, profil_kaydi=p)
        sure = round(time.time() - t0, 1)
        k = KAYIT[-1] if KAYIT else {}
        # Ücretli yanıt önce diske (metrik hesabı çökerse kaybolmasın).
        with open(os.path.join(OUT, f"ham_{n:02}.md"), "w", encoding="utf-8") as f:
            f.write(cevap)
        urls = set(re.findall(r"https?://[^\s)\]>*]+", cevap))
        uydurma_url = sorted(u.rstrip(".,") for u in urls if u.rstrip(".,") not in DB_URLS)
        baglam_sayilar = _sayilar(baglam) | _sayilar(soru)
        suphe_sayilar = sorted(_sayilar(cevap) - baglam_sayilar)
        baglam_disi_program = sorted(b[:50] for i, b in DB_BASLIK.items()
                                     if i not in [m.id for m in matches] and len(b) > 12 and b in cevap)
        girisim = girisim_modu_mu(p, soru)
        basliklar = (["BÖLÜM 1", "BÖLÜM 2", "BÖLÜM 3", "BÖLÜM 4"] if girisim
                     else ["### 1.", "### 2.", "### 3.", "### 4.", "### 5."])
        eksik_baslik = [b for b in basliklar if b not in cevap]
        kapali_onerildi = [m.id for m in matches if m.aktif_mi is False and DB_BASLIK[m.id][:25] in cevap
                           and not re.search(r"(kapalı|artık aktif değil|geçmiş|sona er)", cevap, re.I)]
        satir = dict(n=n, persona=ad, soru=soru, llm_mi=cevap != rag._liste_formati(matches), sure_sn=sure, **k,
                     cevap_kar=len(cevap), girisim=girisim, eksik_baslik=eksik_baslik, uydurma_url=uydurma_url,
                     suphe_sayilar=suphe_sayilar, baglam_disi_program=baglam_disi_program,
                     kapali_onerildi=kapali_onerildi, kesildi="uzunluk sınırında kesildi" in cevap)
        ozet.append(satir)
        with open(os.path.join(OUT, f"cevap_{n:02}.md"), "w", encoding="utf-8") as f:
            f.write(f"# [{n}] {ad}\n\n**Soru:** {soru}\n\n**Bağlam kayıtları:** "
                    + ", ".join(f"{m.id} {DB_BASLIK[m.id][:40]}" for m in matches)
                    + f"\n\n**Ölçüm:** {json.dumps({k2: v for k2, v in satir.items() if k2 not in ('soru', 'persona')}, ensure_ascii=False)}\n\n---\n\n"
                    + cevap)
        print(f"\n[{n:2}] {ad}: llm={satir['llm_mi']} {sure}s stop={k.get('stop')} in={k.get('giris_token')} "
              f"out={k.get('cikis_token')} cevap={len(cevap)} kar | eksik başlık={eksik_baslik} "
              f"uydurma_url={len(uydurma_url)} şüpheli sayı={len(suphe_sayilar)} bağlam dışı program={baglam_disi_program} "
              f"kapalı önerildi={kapali_onerildi} kesildi={satir['kesildi']}")
        if suphe_sayilar:
            print("     şüpheli sayılar:", suphe_sayilar[:15])
        if uydurma_url:
            print("     uydurma url:", uydurma_url[:5])
    yol = os.path.join(OUT, "model_ozet.json")
    eski = json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else []
    eski = [e for e in eski if e["n"] not in {o["n"] for o in ozet}] + ozet
    json.dump(sorted(eski, key=lambda e: e["n"]), open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    mod = sys.argv[1] if len(sys.argv) > 1 else "baglam"
    if mod == "baglam":
        baglam_denetimi()
    elif mod == "model":
        model_olcumu(int(sys.argv[2]) if len(sys.argv) > 2 else None)
