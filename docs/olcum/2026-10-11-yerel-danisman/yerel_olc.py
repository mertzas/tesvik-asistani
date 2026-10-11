"""Yerel danışman değerlendirmesi (2026-10-11): 30 senaryo, gerçek veritabanı, dış çağrı YOK (ücretsiz).

Her senaryo için:
  yanit_NN.md   kullanıcının göreceği yerel danışman yanıtı
  kaynak_NN.md  yanıtın dayanabileceği her şey: kayıtların tüm alanları, uygunluk kriterleri, kontrol listesi
                maddeleri (alıntılarıyla), çağrılar, 9903 notları, elenen blokları, iletişim tabloları
  ozet.json     otomatik ölçümler: dayanak denetimi (yanıttaki her URL/TL/oran/tarih/telefon kaynakta mı), garanti
                dili, sorumluluk reddi, eski ölçümün beklenen değer isabeti, süre
Bağımsız uzman değerlendirmesi (alt ajanlar) bu dosyaları okur: degerlendirme_*.json.

    python docs/olcum/2026-10-11-yerel-danisman/yerel_olc.py --self-test
    python docs/olcum/2026-10-11-yerel-danisman/yerel_olc.py            (üretir + ölçer)
"""
import importlib.util
import inspect
import json
import os
import re
import sys
import time
from datetime import date

KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, KOK)
OUT = os.path.dirname(os.path.abspath(__file__))
for akim in (sys.stdout, sys.stderr):
    if hasattr(akim, "reconfigure"):
        akim.reconfigure(encoding="utf-8")

YASAK = re.compile(r"garanti (ederim|ediyorum|veriyorum|veririm)|kesinlikle (alırsınız|kabul edilir|onaylanır)|"
                   r"kesin(likle)? onaylan|hak kazanırsınız|%100 hibe", re.I)

# Ek personalar (C_olcum.P'ye ek): profil alanları, ajans, kooperatif, kadın girişimci.
EK_P = {
    "yasli_ltd": dict(sektor="genel", bolge="İzmir", calisan_sayisi=6, yillik_ciro=8e6, nace_kodu="46.90",
                      sirket_turu="limited", hedefler=["finansman"], kurucu_yasi=52),
    "genc_sahis": dict(sektor="genel", bolge="Eskişehir", calisan_sayisi=1, yillik_ciro=9e5, nace_kodu="96.02",
                       sirket_turu="sahis", hedefler=["finansman"], kurucu_yasi=26),
    "organik_sertifikasiz": dict(sektor="tarim", bolge="Aydın", calisan_sayisi=2, yillik_ciro=1.2e6,
                                 arazi_buyuklugu_dekar=60, urun_turu="incir", tarim_kategori="meyve",
                                 sirket_turu="sahis", hedefler=["organik_tarim"], sertifikalar=["hicbiri"]),
    "girisim_ortakli": dict(sektor="arge", bolge="Ankara", calisan_sayisi=0, yillik_ciro=0, nace_kodu="62.01",
                            sirket_turu="yok", trl=3, hedefler=["arge"], baska_sirkette_ortak=True),
    "kooperatif": dict(sektor="tarim", bolge="Erzurum", calisan_sayisi=8, yillik_ciro=15e6, nace_kodu="10.51",
                       sirket_turu="kooperatif", hedefler=["yatirim", "makine"]),
    "kadin_ltd": dict(sektor="hizmet", bolge="Gaziantep", calisan_sayisi=5, yillik_ciro=4e6, nace_kodu="74.10",
                      sirket_turu="limited", hedefler=["finansman", "dijital"], ozellikler=["kadin_girisimci"]),
    "ankara_imalat": dict(sektor="imalat", bolge="Ankara", calisan_sayisi=35, yillik_ciro=90e6, nace_kodu="28.22",
                          sirket_turu="anonim", hedefler=["yatirim", "makine", "dijital"]),
}
EK_SENARYO = [
    ("yasli_ltd", "Halkbank İlk Adım Kredisi'ne başvurabilir miyim?", "yas_eleme"),
    ("genc_sahis", "Genç girişimciler için uygun kredi ya da kefalet var mı?", "yas_uygun"),
    ("organik_sertifikasiz", "Organik tarım desteğinden yararlanabilir miyim, dekar başına ne veriliyor?", "sertifika"),
    ("girisim_ortakli", "BiGG Yatırım'a (1812) başvurabilir miyim?", "ortaklik"),
    ("kooperatif", "Süt işleme tesisimize makine almak istiyoruz; hangi hibe ve krediler var?", "paket"),
    ("kadin_ltd", "Kadın girişimci olarak hangi kredi ve destekleri alabilirim?", "hedef_kitle"),
    ("ankara_imalat", "Ankara'da fabrikamıza yeni CNC hattı ve dijital dönüşüm yatırımı yapacağız; hangi destekleri "
                      "birlikte kullanabiliriz?", "paket"),
    ("ankara_imalat", "Ankara Kalkınma Ajansı'nın şu an açık bir programı var mı, son başvuru ne zaman?", "ajans"),
    (None, "TKDK IPARD hibesi nedir, kimler başvurabilir?", "bilgi"),
    ("ciftci", "Hububat için 2026 yılında dekar başına ne kadar destek ödenecek?", "tutar"),
]


def _modul(yol, ad):
    spec = importlib.util.spec_from_file_location(ad, os.path.join(KOK, yol))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def senaryolar():
    c = _modul("docs/olcum/2026-10-07-denetim2/C_olcum.py", "c_olcum")
    pa = _modul("docs/olcum/2026-10-09-prompt-ajan/prompt_ajan.py", "prompt_ajan")
    s = [dict(n=i, persona=p, soru=q, beklenen=b, tur="olcum") for i, (p, q, b, _k) in enumerate(c.SORULAR, 1)]
    # Tuzak senaryoları (manipülasyon, garanti, veride olmayan program, tarih, bölge, triyaj). Kayıt metnine
    # yerleştirilen talimat denemesi senaryosu dış model içindir; yerel danışman kayıt metnini yorumlamaz.
    for p, q, mod, d in pa.YENI:
        s.append(dict(n=len(s) + 1, persona=p, soru=q, beklenen=[], tur=d or mod))
    for p, q, tur in EK_SENARYO:
        s.append(dict(n=len(s) + 1, persona=p, soru=q, beklenen=[], tur=tur))
    return {**c.P, **EK_P}, s


def kaynak_metni(soru, kayitlar, profil, h, bugun, kod: bool = True, yanit: str | None = None) -> str:
    """Yanıtın dayanabileceği bütün veriler. kod=True: dayanak denetimi için koddaki sabit metinler de eklenir;
    değerlendiriciye giden dosyada (kod=False) yoktur. `yanit` verilirse yanıtta adı geçmeyen aday kayıtlar tek
    satırla (başlık, kurum, durum, kriterler) yazılır; değerlendirici "eksik program" sorusunu yine yanıtlayabilir."""
    from app import rag, yerel_danisman
    from app.basvuru_listesi import maddeler
    from app.cagrilar import program_cagrilari
    parca = [f"BUGÜN: {bugun.isoformat()}", f"SORU: {soru}"]
    for t in kayitlar:
        if yanit is not None and (t.baslik or "") not in yanit:
            parca.append(f"ADAY (yanıtta yok) KAYIT {t.id}: {t.baslik} — {t.kurum}; aktif_mi={t.aktif_mi}; "
                         f"kriterler={json.dumps(t.uygunluk_kriterleri or {}, ensure_ascii=False)}; "
                         f"tutar={(t.tesvil_tutari or '')[:200]}")
            continue
        parca.append("=" * 60 + f"\nKAYIT {t.id}\n" + rag._tesvik_detay_metni(t))
        parca.append(f"Uygunluk kriterleri (yapılandırılmış): {json.dumps(t.uygunluk_kriterleri or {}, ensure_ascii=False)}")
        if t.durum_notu:
            parca.append(f"Durum notu: {t.durum_notu}")
        for m in maddeler(t):
            parca.append(f"- [{m['tur']}] {m['metin']}" + (f" | alıntı: {m['alinti']}" if m.get("alinti") else "")
                         + (f" | kaynak: {m['kaynak_url']}" if m.get("kaynak_url") else ""))
        for c in program_cagrilari(t, bugun, kapanmis_en_cok=3):
            parca.append(f"ÇAĞRI: {json.dumps(c, ensure_ascii=False)}")
        if t.id in h.notlar:
            parca.append(f"9903 ÖN DEĞERLENDİRME: {h.notlar[t.id]}")
    if h.elenen:
        parca.append("EK BLOKLAR:\n" + h.elenen)
    sozluk = {"bölge": profil.bolge} if profil is not None and profil.bolge else None
    parca += [rag._kurum_iletisim_metni(kayitlar), rag._il_iletisim_metni(sozluk), rag._kosgeb_il_iletisim_metni(sozluk)]
    if kod:
        from app import girisim
        parca.append("SABİT METİNLER (kod): " + inspect.getsource(yerel_danisman) + inspect.getsource(girisim))
    return "\n".join(x for x in parca if x)


def calistir():
    from app import dayanak, rag, yerel_danisman
    from app.models import FinancialProfile, SessionLocal, Tesvik
    bugun = date.today()
    P, ss = senaryolar()
    db = SessionLocal()
    tum = db.query(Tesvik).all()
    sonuc = []
    for sc in ss:
        profil = FinancialProfile(**P[sc["persona"]]) if sc["persona"] else None
        bas = time.perf_counter()
        h = rag._hazirla(sc["soru"], False, profil)
        yanit = rag._yerel(sc["soru"], h, profil) if (h.matches or yerel_danisman.adi_gecen_programlar(sc["soru"], tum)) \
            else rag.BULUNAMADI_METNI
        sure = time.perf_counter() - bas
        adi_gecen = yerel_danisman.adi_gecen_programlar(sc["soru"], tum)
        # Yanıtın kullandığı kayıtların aynısı: adıyla anılanlar, yoksa kurumuyla anılanlar, sonra arama sonuçları.
        kurumlar = yerel_danisman.kurum_odagi(sc["soru"], tum) if not adi_gecen else set()
        kurum_kayit = [t for t in tum if t.kurum in kurumlar] + yerel_danisman.tutar_gecen_kayitlar(sc["soru"], tum)
        zorunlu = yerel_danisman.zorunlu_adaylar(profil, tum) + yerel_danisman.kurulus_adaylari(profil, sc["soru"], tum)
        kayitlar = [db.get(Tesvik, i) for i in dict.fromkeys(
            [t.id for t in adi_gecen] + [t.id for t in kurum_kayit] + [t.id for t in h.matches] + [t.id for t in zorunlu])]
        # tutarı boş kaydın yanıtta gösterilen önceki (devredilen) program kaydı
        kayitlar += [r for r in (yerel_danisman.devredilen_kayit(t, tum) for t in list(kayitlar))
                     if r is not None and r not in kayitlar]
        kaynak = kaynak_metni(sc["soru"], kayitlar, profil, h, bugun)
        sorunlar = dayanak.denetle(yanit, kaynak, sc["soru"], bugun)
        isabet = [b for b in sc["beklenen"] if b.lower() in yanit.lower()]
        k = dict(n=sc["n"], persona=sc["persona"], soru=sc["soru"], tur=sc["tur"], sure_sn=round(sure, 2),
                 kayitlar=[t.id for t in kayitlar], dayanak_sorunlari=sorunlar, yasak_dil=bool(YASAK.search(yanit)),
                 sorumluluk_reddi=yerel_danisman.SORUMLULUK_REDDI in yanit or yanit == rag.BULUNAMADI_METNI,
                 beklenen=sc["beklenen"], isabet=isabet,
                 profil=P[sc["persona"]] if sc["persona"] else None, uzunluk=len(yanit))
        sonuc.append(k)
        with open(os.path.join(OUT, f"yanit_{sc['n']:02}.md"), "w", encoding="utf-8") as f:
            f.write(f"<!-- persona: {sc['persona']} | soru: {sc['soru']} -->\n{yanit}\n")
        with open(os.path.join(OUT, f"kaynak_{sc['n']:02}.md"), "w", encoding="utf-8") as f:
            f.write(f"PERSONA: {json.dumps(k['profil'], ensure_ascii=False)}\n"
                    f"{kaynak_metni(sc['soru'], kayitlar, profil, h, bugun, kod=False, yanit=yanit)}\n")
        print(f"[{sc['n']:2}] {sc['persona'] or '-':20} {sc['tur']:12} {sure:5.2f} sn  kayıt={k['kayitlar'][:6]} "
              f"dayanak={len(sorunlar)} isabet={len(isabet)}/{len(sc['beklenen'])}")
    db.close()
    json.dump(sonuc, open(os.path.join(OUT, "ozet.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    toplam_dayanak = sum(len(x["dayanak_sorunlari"]) for x in sonuc)
    print(f"\nsenaryo {len(sonuc)} | dayanak sorunu {toplam_dayanak} | yasak dil {sum(x['yasak_dil'] for x in sonuc)} | "
          f"sorumluluk reddi eksik {sum(not x['sorumluluk_reddi'] for x in sonuc)} | "
          f"beklenen isabet {sum(len(x['isabet']) for x in sonuc)}/{sum(len(x['beklenen']) for x in sonuc)} | "
          f"süre ort {sum(x['sure_sn'] for x in sonuc) / len(sonuc):.2f} sn, en çok {max(x['sure_sn'] for x in sonuc):.2f} sn")
    return sonuc


def _self_test() -> int:
    P, ss = senaryolar()
    k = [("30 senaryo", len(ss) == 30),
         ("numaralar sıralı ve tekil", [s["n"] for s in ss] == list(range(1, 31))),
         ("her personanın profili var", all(s["persona"] is None or s["persona"] in P for s in ss)),
         ("yeni profil alanları sınanıyor", any(p.get("kurucu_yasi") for p in P.values())
          and any(p.get("baska_sirkette_ortak") for p in P.values()) and any(p.get("sertifikalar") for p in P.values())),
         ("yasak dil kalıbı", bool(YASAK.search("başvurunuz kesinlikle onaylanır")) and not YASAK.search("teyit edin"))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.exit(_self_test() if "--self-test" in sys.argv else (calistir() and 0))
