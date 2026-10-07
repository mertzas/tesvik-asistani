"""Denetim 2 / Aşama C — danışman yanıt kalitesi, kör karşılaştırma (ÜCRETLİ: soru başına 1 Claude çağrısı).

  python docs/olcum/2026-10-07-denetim2/C_olcum.py          -> 12 çağrı
  python docs/olcum/2026-10-07-denetim2/C_olcum.py 5        -> yalnızca 5. soru

Her yanıt ÖNCE diske yazılır (C_ham_NN.md), sonra metrikler (C_cevap_NN.md, C_ozet.json).
"beklenen" değerleri Aşama A'da canlı kaynaktan doğrulanmış rakamlardır (A_fark_tablosu.json);
yanıtta geçip geçmediği otomatik işaretlenir, kalan sayılar elle incelenir.
"""
import json, os, re, sys, time
from app import rag
from app.models import SessionLocal, FinancialProfile, Tesvik
from app.girisim import girisim_modu_mu

OUT = os.path.dirname(os.path.abspath(__file__))
P = {
 "ciftci": dict(sektor="tarim", bolge="Konya", calisan_sayisi=3, yillik_ciro=2.5e6, arazi_buyuklugu_dekar=180, urun_turu="buğday", tarim_kategori="tahil_baklagil", hedefler=["makine", "hayvan"], sirket_turu="sahis"),
 "tekstil": dict(sektor="imalat", bolge="İzmir", calisan_sayisi=12, yillik_ciro=60e6, nace_kodu="13.20", hedefler=["yatirim", "ihracat", "arge"], sirket_turu="limited"),
 "girisim": dict(sektor="arge", bolge="Ankara", calisan_sayisi=0, yillik_ciro=0, nace_kodu="62.01", sirket_turu="yok", trl=4, hedefler=["arge"]),
 "otel": dict(sektor="hizmet", bolge="Van", calisan_sayisi=25, yillik_ciro=30e6, nace_kodu="55.10", hedefler=["yatirim"], sirket_turu="anonim"),
 "eticaret": dict(sektor="e-ticaret", bolge="Trabzon", calisan_sayisi=3, yillik_ciro=4e6, nace_kodu="47.91", hedefler=["ihracat"], sirket_turu="limited"),
 "saas": dict(sektor="arge", bolge="İstanbul", calisan_sayisi=12, yillik_ciro=20e6, nace_kodu="62.01", sirket_turu="limited", trl=8, hedefler=["ihracat", "arge", "finansman"]),
 "buyuk": dict(sektor="imalat", bolge="Bursa", calisan_sayisi=400, yillik_ciro=2e9, nace_kodu="29.10", sirket_turu="anonim", hedefler=["istihdam", "yatirim"]),
 "restoran": dict(sektor="hizmet", bolge="Hatay", calisan_sayisi=4, yillik_ciro=3e6, nace_kodu="56.10", sirket_turu="sahis", hedefler=["istihdam"]),
 "hatay_nacesiz": dict(sektor="hizmet", bolge="Hatay", calisan_sayisi=2, yillik_ciro=1e6, sirket_turu="sahis", hedefler=["finansman"]),
}
# (persona, soru, beklenen rakam/ifadeler [kaynak: A_fark_tablosu kayıt id])
SORULAR = [
 ("ciftci", "Traktör ve mibzer almak istiyorum; Kırsal Kalkınma hibesinin oranı ve üst limiti nedir, bireysel traktör alımı destekleniyor mu?", ["%50", "%70", "30.000.000", "100.000", "traktör"], 78),
 ("ciftci", "Tarlama damla sulama kuracağım; tasarruflu sulama hibesi oranı ve hibeye esas üst tutar ne kadar?", ["%50", "%70", "10.000.000", "2026"], 80),
 ("tekstil", "1507 TÜBİTAK KOBİ Ar-Ge programında proje bütçesi üst sınırı ve destek oranı nedir, çağrı açık mı?", ["3.500.000", "%75", "2026"], 44),
 ("tekstil", "Almanya'daki bir ortakla Eurostars'a başvurabilir miyiz; çağrı açık mı, ulusal bütçe ve proje süresi nedir?", ["4.000.000", "36 ay", "2026/2"], 48),
 ("girisim", "BiGG'den ne kadar yatırım alabilirim, şartları neler ve şirket kurmadan başvurabilir miyim?", ["1.350.000", "600.000", "ortaklık"], 174),
 ("girisim", "Şirket kurmadan KOSGEB Girişimci Destek Programı'ndan yararlanabilir miyim?", ["işletme", "KOSGEB"], 1),
 ("otel", "Van'daki otel yatırımı için teşvik belgesinde SGK işveren desteği kaç yıl, faiz desteği var mı, asgari yatırım tutarı ne?", ["12 yıl", "%100", "6.000.000", "MADDE 18"], 180),
 ("eticaret", "Pazaryeri üyelik gideri desteği hâlâ yıllık 15.102 TL mi, hangi Karar geçerli?", ["5973", "2573", "mülga"], 163),
 ("saas", "KOSGEB Yapay Zekâ Kredisi ne kadar, vadesi ve ödemesiz dönemi nedir?", ["500.000", "5.000.000", "24 ay", "12 ay"], 2),
 ("buyuk", "KOSGEB İstihdamı Koruma Destek Programı 2026-2 döneminde büyük işletme için kredi üst limiti ve başvuru tarihleri nedir?", ["150", "1 Eylül", "31 Ekim", "%37"], 7),
 ("restoran", "Restoranıma 3 kişi daha alacağım; 4447 sayılı Kanun işveren prim teşviki kaç ay sürer, şartları neler?", ["54 ay", "6 ay", "31.12.2026", "ilave"], 185),
 ("hatay_nacesiz", "TOBB Nefes Kredisi 2026 kredi ve kefalet limiti ne kadar?", ["3.000.000", "2.400.000"], 86),
]

db = SessionLocal()
DB_BASLIK = {t.id: t.baslik for t in db.query(Tesvik).all()}
KAYIT = []


def _kaydedici_kur():
    import anthropic
    Orig = anthropic.Anthropic

    class Kayitci(Orig):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            orig = self.messages.create

            def create(**kw):
                t0 = time.time(); r = orig(**kw); u = getattr(r, "usage", None)
                KAYIT.append(dict(api_sure_sn=round(time.time() - t0, 1), stop=getattr(r, "stop_reason", None),
                                  giris_token=getattr(u, "input_tokens", None), cikis_token=getattr(u, "output_tokens", None)))
                return r
            self.messages.create = create
    anthropic.Anthropic = Kayitci


_SAYI = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?)\s*(?:TL|₺|%|milyon|bin|ay|yıl|gün)|%\s*\d+(?:,\d+)?")


def _sayilar(m):
    return {re.sub(r"\s+", "", x.group(0).replace("₺", "TL")) for x in _SAYI.finditer(m)}


def _norm(s):
    return s.replace(" ", "").lower()


def _prompt(n):
    """Uygulamanın modele göndereceği birebir sistem promptu + kullanıcı mesajı (rag.answer ile aynı dallanma)."""
    pad, soru, _, _ = SORULAR[n - 1]
    p = FinancialProfile(**P[pad]); profil = rag.profil_sozlugu(p)
    h = rag._hazirla(soru, True, p)
    if h.girisim:
        sistem = rag.SISTEM_PROMPTU + rag.GIRISIM_PROMPT_EKI
        baglam = rag._baglam_metni(h.matches, profil, h.notlar, h.elenen)
    else:
        sistem = rag.SISTEM_PROMPTU
        baglam = rag._baglam_metni(h.matches, profil, h.notlar, h.elenen) if (h.notlar or h.elenen) \
            else rag._baglam_metni(h.matches, profil)
    return sistem, f"BAĞLAM:\n{baglam}\n\nKULLANICI SORUSU: {soru}"


def dump(secim=None):
    """API bakiyesi yokken: promptları C_prompt_NN.md'ye yaz; yanıt dışarıda üretilip C_ham_NN.md'ye konur, sonra `skor N`."""
    for n in range(1, len(SORULAR) + 1):
        if secim and n != secim:
            continue
        sistem, kullanici = _prompt(n)
        with open(os.path.join(OUT, f"C_prompt_{n:02}.md"), "w", encoding="utf-8") as f:
            f.write(f"<<SYSTEM>>\n{sistem}\n\n<<USER>>\n{kullanici}\n")
        print(f"[{n:2}] prompt yazıldı: sistem {len(sistem)} kar, kullanıcı {len(kullanici)} kar, girişim={'GIRISIM' in sistem[-800:] or 'girişim' in sistem[len(rag.SISTEM_PROMPTU):].lower()}")


def calistir(secim=None, kaynak="api"):
    """kaynak='api': gerçek çağrı. kaynak='oturum': C_ham_NN.md'deki hazır yanıtı puanla (çağrı yok)."""
    if kaynak == "api":
        _kaydedici_kur()
    ozet = []
    for n, (pad, soru, beklenen, kid) in enumerate(SORULAR, 1):
        if secim and n != secim:
            continue
        p = FinancialProfile(**P[pad])
        matches = rag.retrieve(soru, limit=rag.CEVAP_KAYIT_SAYISI, profil_kaydi=p)
        h = rag._hazirla(soru, True, p)
        baglam = rag._baglam_metni(h.matches, rag.profil_sozlugu(p), h.notlar, h.elenen)
        KAYIT.clear(); t0 = time.time()
        if kaynak == "api":
            cevap = rag.answer(soru, rag.profil_sozlugu(p), llm_kullan=True, profil_kaydi=p)
            with open(os.path.join(OUT, f"C_ham_{n:02}.md"), "w", encoding="utf-8") as f:
                f.write(cevap)
        else:
            cevap = open(os.path.join(OUT, f"C_ham_{n:02}.md"), encoding="utf-8").read().strip()
        sure = round(time.time() - t0, 1)
        k = KAYIT[-1] if KAYIT else {}
        k["kaynak"] = "claude API" if kaynak == "api" else "oturum içi model (API bakiyesi yok; aynı prompt+bağlam)"
        cn = _norm(cevap)
        bulunan = [b for b in beklenen if _norm(b) in cn]
        eksik = [b for b in beklenen if _norm(b) not in cn]
        baglam_sayi = _sayilar(baglam) | _sayilar(soru)
        suphe = sorted(_sayilar(cevap) - baglam_sayi)
        hedef_baglamda = kid in [m.id for m in matches]
        satir = dict(n=n, persona=pad, kayit=kid, kayit_baslik=DB_BASLIK.get(kid, "?")[:50], hedef_baglamda=hedef_baglamda,
                     girisim=girisim_modu_mu(p, soru), llm=cevap != rag._liste_formati(h.matches), sure_sn=sure, **k,
                     cevap_kar=len(cevap), beklenen_bulunan=bulunan, beklenen_eksik=eksik, baglam_disi_sayilar=suphe,
                     bilgi_yok=len(re.findall(r"elimde yok|bağlamda (yok|geçmiyor)|bilgim yok|teyit ed", cevap, re.I)),
                     kesildi="uzunluk sınırında kesildi" in cevap)
        ozet.append(satir)
        with open(os.path.join(OUT, f"C_cevap_{n:02}.md"), "w", encoding="utf-8") as f:
            f.write(f"# [{n}] {pad} — hedef kayıt {kid} {DB_BASLIK.get(kid,'?')[:60]}\n\n**Soru:** {soru}\n\n**Bağlam:** "
                    + ", ".join(f"{m.id} {DB_BASLIK[m.id][:35]}" for m in matches)
                    + f"\n\n**Ölçüm:** {json.dumps({x: y for x, y in satir.items() if x not in ('persona',)}, ensure_ascii=False)}\n\n---\n\n" + cevap)
        print(f"[{n:2}] {pad:13} kayıt {kid:3} bağlamda={hedef_baglamda} llm={satir['llm']} {sure}s in={k.get('giris_token')} out={k.get('cikis_token')} "
              f"| beklenen {len(bulunan)}/{len(beklenen)} eksik={eksik} | bağlam dışı sayı={suphe[:6]} | bilgi-yok ifadesi={satir['bilgi_yok']}")
    yol = os.path.join(OUT, "C_ozet.json")
    eski = json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else []
    eski = [e for e in eski if e["n"] not in {o["n"] for o in ozet}] + ozet
    json.dump(sorted(eski, key=lambda e: e["n"]), open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "dump":
        dump(int(args[1]) if len(args) > 1 else None)
    elif args and args[0] == "skor":
        calistir(int(args[1]) if len(args) > 1 else None, kaynak="oturum")
    else:
        calistir(int(args[0]) if args else None)
