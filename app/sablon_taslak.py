"""Yapay zekâsız başvuru ön taslağı ve taslak sihirbazı (2026-10-08).

Neden: Claude taslağı profili ABD'ye gönderdiği için açık rıza, PRO plan ve API anahtarı istiyordu. Taslağın çoğu
yapılandırılmış veridir (programın amacı, tutar/oran, başvuru yeri/dönemi, şartlar, belgeler, profil, İKAS toplamları).

Sürüm 2 (kullanıcı geri bildirimi 2026-10-08: "bu böyle olmaz"): cevapsız şablon baştan sona [DOLDURUN] tablosu
üretiyordu; taslak değil boş formdu. Artık:
  - sorular(t): programın türüne göre sihirbaz soruları (proje, gerekçe, çıktılar), önerilen faaliyet adımları,
    desteklenen gider kalemleri, kayıttaki destek oranı seçenekleri ve üst limit;
  - uret(..., cevaplar): cevapları cümlelere ve tablolara yerleştirir, bütçe toplamını ve talep edilebilecek desteği
    (toplam × kullanıcının seçtiği oran, kayıttaki üst limitle sınırlı) HESAPLAR; cevaplanmayan yerler kısa liste;
  - göstergeler önce programın türünden (Ar-Ge projesine kapasite/ihracat göstergesi gelmez);
  - kontrol listesindeki kurallar ("…desteklenmez") onay kutusu değil uyarı.
Hiçbir rakam tahmin edilmez: rakamlar kayıttan ya da kullanıcının cevabından gelir.

    python -m app.sablon_taslak --self-test
"""
from __future__ import annotations

import re
import sys

from app.basvuru_taslagi import BASLIK_NOTU, BOLUMLER, kart_ozeti
from app.form_sablonlari import form as resmi_form

MODEL_ADI = "sablon-v2"
D = "[DOLDURUN: {}]"
# Yüklem biçimleri ünlü uyumuyla hazır yazılır ("şirket" + "dir" → "şirkettir").
SIRKET = {"yok": "henüz şirketleşmemiş bir girişimdir", "sahis": "bir şahıs işletmesidir",
          "limited": "bir limited şirkettir", "anonim": "bir anonim şirkettir", "kooperatif": "bir kooperatiftir"}
HEDEF = {"yatirim": "yatırım", "ihracat": "ihracat", "arge": "Ar-Ge", "istihdam": "istihdam", "makine": "makine alımı",
         "sulama": "sulama sistemi", "hayvan": "hayvancılık", "organik": "organik tarım", "e-ticaret": "e-ticaret"}
# Profil formundaki sektör seçeneklerinin görünen adları (taslakta ham anahtar "arge" yazılıyordu).
SEKTOR = {"tarim": "tarım", "imalat": "imalat", "perakende": "perakende", "e-ticaret": "e-ticaret", "hizmet": "hizmet",
          "ihracat": "ihracat", "arge": "Ar-Ge"}
ON_ONAY = re.compile(r"ön\s+onay|müracaat tarihinden önce|harcamaya başlamadan", re.IGNORECASE)
KURAL = re.compile(r"desteklenmez|yararlanamaz|kapsam dışı|kabul edilmez|alınmaz|sunulabilir|en fazla \d+ proje",
                   re.IGNORECASE)
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

# Program türüne göre sihirbaz: gerekçe soruları (anahtar, etiket, ipucu), faaliyet adımları, çıktı soruları.
REHBER: dict[str, dict] = {
    "yatirim": {"gerekce": [("darbogaz", "Mevcut kapasite ve darboğazlar", "Hangi süreç ya da makinede darboğaz var, kapasite kullanım oranı"),
                            ("talep", "Karşılanamayan talep", "Reddedilen/ertelenen siparişler, talep artışı"),
                            ("cozum", "Yatırımın çözeceği sorun", "Verimlilik, kalite, maliyet etkisi")],
                "adimlar": ["Teklif ve proformaların toplanması", "Makine/ekipman tedariki", "Kurulum ve devreye alma",
                            "Kapasite/verimlilik artışının ölçülmesi"],
                "cikti": [("kapasite", "Kapasite artışı", "Mevcut → hedef (birim/yıl)")]},
    "ihracat": {"gerekce": [("pazar", "Hedef pazarlar ve seçim gerekçesi", "Ülkeler, pazar araştırması dayanağı"),
                            ("mevcut_ihracat", "Mevcut ihracat durumu", "Son yıl ihracat, başlıca alıcılar/kanallar"),
                            ("rekabet", "Rekabet avantajı", "Ürün, fiyat, sertifika, marka")],
                "adimlar": ["Pazar araştırması ve hedef ülke seçimi", "Tanıtım/fuar/pazaryeri faaliyetleri",
                            "Alıcı görüşmeleri ve sipariş", "İhracat sonuçlarının izlenmesi"],
                "cikti": [("ihracat", "İhracat hedefi", "Son yıl → hedef tutar ve pazarlar")]},
    "arge": {"gerekce": [("yenilik", "Teknolojik yenilik ve özgün değer", "Mevcut çözümlerden farkı"),
                         ("yontem", "Teknik riskler ve yöntem", "Belirsizlikler, deney/prototip planı"),
                         ("ticarilesme", "Ticarileşme", "Hedef müşteri, pazar, gelir modeli")],
             "adimlar": ["Literatür/patent taraması ve gereksinimler", "Tasarım ve prototip geliştirme", "Test ve doğrulama",
                         "Ticarileşme hazırlığı (fikri mülkiyet, pilot müşteri)"],
             "cikti": [("arge_cikti", "Ar-Ge çıktıları", "Prototip, patent/faydalı model başvurusu, teknoloji hazırlık seviyesi")]},
    "istihdam": {"gerekce": [("istihdam", "Korunacak/oluşturulacak istihdam", "Pozisyonlar ve kişi sayısı"),
                             ("durum", "İstihdamı etkileyen durum", "Talep düşüşü, finansman ihtiyacı, büyüme")],
                 "adimlar": ["İşe alım/istihdamın korunması planı", "SGK bildirgeleriyle izleme"],
                 "cikti": [("ilave_istihdam", "İstihdam etkisi", "İlave ya da korunan istihdam (kişi)")]},
    "girisim": {"gerekce": [("fikir", "İş fikri ve çözülen sorun", "Hedef müşteri ve ihtiyacı"),
                            ("ekip", "Ekip ve yetkinlik", "Kurucular, deneyim"),
                            ("model", "İş modeli", "Gelir kaynakları, ilk müşteriler")],
                "adimlar": ["Şirket kuruluşu / kayıtlar", "Ürün/hizmetin ilk sürümü", "İlk müşteriler ve satış", "Büyüme planı"],
                "cikti": [("girisim_cikti", "Girişim hedefleri", "Müşteri, gelir ve yatırım hedefi")]},
    "tarim": {"gerekce": [("uretim", "Üretim durumu", "Ürün, alan (dekar) ya da hayvan sayısı, ÇKS/TÜRKVET kaydı"),
                          ("amac", "Desteğin kullanım amacı", "Verim, kalite, maliyet, sertifikasyon")],
              "adimlar": ["Kayıtların (ÇKS/ÖKS/TÜRKVET) güncellenmesi", "Üretim/uygulama dönemi", "Başvuru ve belge teslimi"],
              "cikti": [("tarim_cikti", "Üretim etkisi", "Verim, alan ya da hayvan sayısı değişimi")]},
}
GENEL = {"gerekce": [("sorun", "Çözülecek sorun / karşılanacak ihtiyaç", "Neden şimdi?")],
         "adimlar": [], "cikti": [("genel_cikti", "Beklenen etki", "Ciro, verimlilik ya da istihdam etkisi")]}
BASLIK_TURU = [("girisim", r"Girişim|BiGG"), ("yatirim", r"Kapasite|Yatırım|makine|Dijital Dönüşüm|Hamle"),
               ("arge", r"Ar-?Ge|Araştırma|Teknoloji"), ("ihracat", r"ihracat|Rekabetçilik|Pazar"),
               ("istihdam", r"istihdam")]


def _tl(x) -> str:
    return f"{float(x):,.0f} TL".replace(",", ".")


def _tarih(iso: str | None) -> str:
    if not iso:
        return ""
    y, a, g = map(int, iso.split("-"))
    return f"{g} {AYLAR[a - 1]} {y}"


def _ay(yyyy_mm: str | None) -> str:
    """'2026-11' → 'Kasım 2026'; boş ya da bozuksa boş."""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", (yyyy_mm or "").strip())
    return f"{AYLAR[int(m.group(2)) - 1]} {m.group(1)}" if m and 1 <= int(m.group(2)) <= 12 else ""


def _tam_cumleler(metin: str) -> str:
    """Yalnız tamamlanmış cümleler: kazınmış özetlerin bir kısmı kelime ortasında kesik ("… geliştirilmiş, iyile")."""
    metin = (metin or "").replace(" […]", "").strip()
    if not metin or metin[-1] in ".!?…":
        return metin
    son = max(metin.rfind(". "), metin.rfind("! "), metin.rfind("? "))
    return metin[:son + 1] if son > 0 else ""


def program_hedefleri(t) -> set[str]:
    """Programın sektör etiketinden ve metninden gösterge anahtarları (yedek; tür önce başlıktan alınır)."""
    sektor = set((t.uygunluk_kriterleri or {}).get("sektorler") or [])
    metin = f"{t.baslik or ''} {t.kurum or ''}"
    h = set()
    if "arge" in sektor or re.search(r"Ar-?Ge|TÜBİTAK|TUBITAK", metin, re.IGNORECASE):
        h.add("arge")
    if "ihracat" in sektor or re.search(r"ihracat|e-ihracat", metin, re.IGNORECASE):
        h.add("ihracat")
    if re.search(r"istihdam", metin, re.IGNORECASE):
        h.add("istihdam")
    return h


def program_turleri(t) -> list[str]:
    """Rehber anahtarları, önem sırasıyla. Önce BAŞLIK, sonra kurum (tarım), en son sektör etiketi: sektör etiketleri
    ihtiyacı geniş kodlar (Kapasite Geliştirme'de "arge" var) ve tek başına Ar-Ge sorusu getiriyordu."""
    baslik = t.baslik or ""
    turler = [tur for tur, kalip in BASLIK_TURU if re.search(kalip, baslik, re.IGNORECASE)]
    if "girisim" in turler and "yatirim" in turler:
        turler.remove("yatirim")  # "Yatırım Tabanlı Girişimcilik": girişime sermaye yatırımı, makine/kapasite değil
    if re.search(r"Tarım", t.kurum or "", re.IGNORECASE):
        turler.append("tarim")
    if not turler:
        turler = sorted(program_hedefleri(t))
    return [x for x in dict.fromkeys(turler) if x in REHBER]


def oran_secenekleri(t) -> list[float]:
    """Kaydın tutar/formül metnindeki destek oranları (%): kullanıcı kendi durumuna uyanı seçer (1501: %75 ilk 5
    proje, %60 sonrası). Oran tahmin edilmez; metinde yoksa boş liste ve hesap yapılmaz."""
    metin = f"{t.tesvil_tutari or ''} {t.tutari_hesaplama_formulu or ''}"
    oranlar = {float(x.replace(",", ".")) for x in re.findall(r"%\s?(\d{1,3}(?:[.,]\d+)?)", metin)}
    return sorted((o for o in oranlar if 0 < o <= 100), reverse=True)


def gider_kalemleri(t) -> list[str]:
    """Formüldeki "Desteklenen giderler: a; b; c." listesi (tur18 biçimi); yoksa boş."""
    m = re.search(r"Desteklenen giderler:\s*(.+?)\.?$", t.tutari_hesaplama_formulu or "")
    return [x.strip() for x in m.group(1).split(";") if x.strip()] if m else []


def sorular(t) -> dict:
    """Sihirbaz tanımı: arayüz bu yapıdan form kurar."""
    turler = program_turleri(t)
    paket = [REHBER[x] for x in turler] or [GENEL]
    f = resmi_form(t.id)
    # Resmi form şablonu varsa (app/form_sablonlari.py) sorular formun kendi bölümleridir.
    gerekce = (list(f["bolumler"]) if f else
               list({k: (k, e, i) for p in paket for k, e, i in p["gerekce"]}.values()))
    cikti = list({k: (k, e, i) for p in paket for k, e, i in p["cikti"]}.values())
    return {"turler": turler,
            "gerekce": [{"anahtar": k, "etiket": e, "ipucu": i} for k, e, i in gerekce],
            "cikti": [{"anahtar": k, "etiket": e, "ipucu": i} for k, e, i in cikti],
            "faaliyet_onerileri": paket[0]["adimlar"],
            "gider_kalemleri": gider_kalemleri(t),
            "oran_secenekleri": oran_secenekleri(t),
            "ust_limit": t.tutari_max,
            "form": {"ad": f["ad"], "kaynak": f["kaynak"], "tablolar": f["tablolar"]} if f else None}


# ------------------------------------------------------------------------------------------------- bölümler
def _isletme(p: dict) -> str:
    sirketsiz = p.get("şirket türü") == "yok"
    tur = SIRKET.get(p.get("şirket türü") or "", None)
    il = p.get("bölge") or D.format("il")
    sektor, nace = p.get("sektör"), p.get("NACE kodu")
    alan = SEKTOR.get(sektor, sektor) if sektor and sektor != "genel" else D.format("sektör")
    nace_ek = f" (NACE {nace})" if nace else f" ({D.format('NACE kodu')})"
    calisan, ciro = p.get("çalışan sayısı"), p.get("yıllık ciro")
    if sirketsiz:
        # Şirketi olmayan girişimci (BiGG vb.): "işletmemiz", hasılat ve KOBİ ölçeği anlamsız; ölçek çalışan/ciro
        # sayısından hesaplanıp "mikro işletme" yazılıyordu ve aynı paragrafta "şirketleşmemiş" ile çelişiyordu.
        cumle = [f"Başvuru, {il} ilinde henüz şirket kurmamış bir girişimci tarafından yapılmaktadır.",
                 f"Kurulacak şirketin faaliyet alanı: {alan}{nace_ek}."]
        if calisan:
            cumle.append(f"Girişimde şu an çalışan kişi sayısı: {calisan}.")
        if ciro:
            cumle.append(f"Bugüne kadarki gelir (beyan): {_tl(ciro)}.")
    else:
        cumle = [f"İşletmemiz {il} ilinde faaliyet gösteren "
                 f"{tur if tur else D.format('şirket türü') + ' bir işletmedir'}.",
                 f"Faaliyet alanı: {alan}{nace_ek}."]
        kurulus = p.get("kuruluş tarihi")
        if kurulus:
            cumle.append(f"Kuruluş tarihi: {_tarih(kurulus)}.")
        # 0 geçerli bir cevaptır (gelirsiz yıl); yalnız None eksik sayılır.
        cumle.append(f"Çalışan sayısı: {calisan if calisan is not None else D.format('çalışan sayısı')}; "
                     f"son yıl net satış hasılatı: {_tl(ciro) if ciro is not None else D.format('yıllık ciro (TL)')}.")
        if p.get("KOBİ ölçeği"):
            cumle.append(f"Ölçek: {p['KOBİ ölçeği']}.")
    satirlar = [" ".join(cumle)]
    ikas = [(k, v) for k, v in p.items() if "İKAS" in k]
    if ikas:
        satirlar += ["", "E-ticaret mağaza kayıtlarına göre (resmi belgeyle — fatura, gümrük beyannamesi/ETGB — teyit "
                     "edilmelidir):"] + [f"- {k}: {v}" for k, v in ikas]
    return "\n".join(satirlar)


def _amac(t, p: dict, c: dict, s: dict) -> str:
    satir = [f"Başvurulan program: **{t.baslik}** ({t.kurum})."]
    amac = _tam_cumleler(kart_ozeti(t.ozet, 600))
    if amac:
        satir.append(f"Programın amacı (kurum metni): {amac}")
    satir.append("")
    if c.get("proje_adi"):
        satir.append(f"**Proje:** {c['proje_adi'].strip()}." + (f" {c['proje_ozeti'].strip()}" if c.get("proje_ozeti") else ""))
    else:
        satir.append(f"**Proje:** {D.format('projenin adı ve tek cümlelik tanımı')}")
    gerekce = c.get("gerekce") or {}
    if s.get("form"):
        # Resmi form: her bölüm formdaki başlığıyla, sırasıyla; boşsa formun açıklaması [DOLDURUN] ipucu olur.
        satir += ["", f"Aşağıdaki başlıklar **{s['form']['ad']}** bölümleridir; metni ilgili alanlara aktarın."]
        for q in s["gerekce"]:
            v = (gerekce.get(q["anahtar"]) or "").strip()
            satir += ["", f"### {q['etiket']}", "", v or D.format(q["ipucu"])]
        if s["form"]["tablolar"]:
            satir += ["", "Formda ayrıca doldurulacak tablolar:"] + [f"- {x}" for x in s["form"]["tablolar"]]
        return "\n".join(satir).strip()
    yanitli = [(q["etiket"], gerekce[q["anahtar"]].strip()) for q in s["gerekce"] if (gerekce.get(q["anahtar"]) or "").strip()]
    eksik = [q for q in s["gerekce"] if not (gerekce.get(q["anahtar"]) or "").strip()]
    satir += ["", *[f"**{e}:** {v}" for e, v in yanitli]]
    if eksik:
        satir += ["", "Gerekçede ayrıca şunları somutlayın:"] + [f"- {q['etiket']}: {D.format(q['ipucu'])}" for q in eksik]
    hedefler = [HEDEF.get(h, h) for h in (p.get("hedefler") or [])]
    if hedefler:
        sahip = "Girişimin" if p.get("şirket türü") == "yok" else "İşletmenin"
        satir += ["", f"{sahip} genel hedefleri: {', '.join(hedefler)}."]
    return "\n".join(x for x in satir).strip()


def _takvim(t, cagrilar: list[dict], c: dict, s: dict) -> str:
    satir = []
    canli = [x for x in cagrilar if x.get("durum") in ("acik", "yaklasan")]
    if canli:
        x = canli[0]
        if x.get("on_kayit_son"):
            satir.append(f"Başvuru dönemi: {x['ad']} — ön kayıt son günü {_tarih(x['on_kayit_son'])}, kapanış "
                         f"{_tarih(x.get('kapanis'))}.")
        elif x["durum"] == "yaklasan":
            satir.append(f"Başvuru dönemi: {x['ad']} — {_tarih(x.get('acilis'))} tarihinde açılıyor"
                         + (f", kapanış {_tarih(x['kapanis'])}." if x.get("kapanis") else "."))
        else:
            satir.append(f"Başvuru dönemi: {x['ad']} — son başvuru {_tarih(x['kapanis'])}." if x.get("kapanis")
                         else f"Başvuru dönemi: {x['ad']} — açık (son tarih duyurulmadı).")
    elif t.basvuru_suresi:
        satir.append(f"Başvuru zamanı: {t.basvuru_suresi}")
    if t.basvuru_yeri:
        satir.append(f"Başvuru yeri: {t.basvuru_yeri}")
    if t.destek_verilme_suresi:
        satir.append(f"Destek süresi: {t.destek_verilme_suresi}")
    if ON_ONAY.search(f"{t.basvuru_suresi or ''} {' '.join(map(str, t.basvuru_sartlari or []))}"):
        satir.append("**Önemli:** Bu programda ön onaydan/müracaattan önce yapılan harcama desteklenmez; harcamaları "
                     "başvurudan sonraya planlayın.")
    faaliyetler = [f for f in (c.get("faaliyetler") or []) if (f.get("ad") or "").strip()]
    if faaliyetler:
        satir += ["", "| Faaliyet | Başlangıç | Bitiş |", "|---|---|---|"]
        satir += [f"| {f['ad'].strip()} | {_ay(f.get('baslangic')) or '—'} | {_ay(f.get('bitis')) or '—'} |" for f in faaliyetler]
    elif s["faaliyet_onerileri"]:
        satir += ["", "Önerilen iş adımları (sihirbazda tarihlerini girin):"] + [f"- {a}" for a in s["faaliyet_onerileri"]]
    else:
        satir += ["", f"İş adımları ve takvim: {D.format('faaliyetler ve ayları')}"]
    return "\n".join(satir)


def _butce(t, c: dict, s: dict) -> str:
    satir = []
    if t.tesvil_tutari:
        satir.append(f"Programın destek tutarı/oranı: {t.tesvil_tutari}")
    if t.tutari_hesaplama_formulu:
        satir.append(f"Hesaplama: {t.tutari_hesaplama_formulu}")
    kalemler = []
    for k in c.get("butce") or []:
        try:
            tutar = float(k.get("tutar") or 0)
        except (TypeError, ValueError):
            continue
        if (k.get("kalem") or "").strip() and tutar > 0:
            kalemler.append((k["kalem"].strip(), tutar))
    if not kalemler:
        if s["gider_kalemleri"]:
            satir += ["", "Desteklenen gider türleri (bütçenizi bunlara göre kurun):"] + [f"- {g}" for g in s["gider_kalemleri"]]
        satir += ["", "Bütçe kalemlerini ve tutarlarını sihirbazda girin; toplam ve talep edilebilecek destek hesaplanır."]
        return "\n".join(satir)
    toplam = sum(x for _, x in kalemler)
    satir += ["", "| Gider kalemi | Tutar |", "|---|---|"] + [f"| {k} | {_tl(x)} |" for k, x in kalemler]
    satir.append(f"| **Toplam** | **{_tl(toplam)}** |")
    oran = c.get("destek_orani")
    if oran in s["oran_secenekleri"]:
        destek = toplam * oran / 100
        limit = s.get("ust_limit")
        sinirli = bool(limit) and destek > limit
        satir += ["", f"Talep edilebilecek destek (tahmini): {_tl(toplam)} × %{oran:g} = **{_tl(min(destek, limit) if sinirli else destek)}**"
                  + (f" (kayıttaki üst limit {_tl(limit)} ile sınırlandı)" if sinirli else "") + "."]
    elif s["oran_secenekleri"]:
        satir += ["", "Talep edilebilecek desteği hesaplamak için sihirbazda size uyan destek oranını seçin: "
                  + ", ".join(f"%{o:g}" for o in s["oran_secenekleri"]) + "."]
    satir.append("Kalem tutarlarını teklif/proformalarla belgeleyin; kesin tutarı kurum belirler.")
    return "\n".join(satir)


def _cikti(p: dict, c: dict, s: dict) -> str:
    cevap = c.get("ciktilar") or {}
    satir = []
    for q in s["cikti"]:
        v = (cevap.get(q["anahtar"]) or "").strip()
        satir.append(f"- **{q['etiket']}:** {v}" if v else f"- {q['etiket']}: {D.format(q['ipucu'])}")
    if "istihdam" not in s["turler"] and p.get("çalışan sayısı") is not None and (cevap.get("istihdam_notu") or "").strip():
        satir.append(f"- **İstihdam:** {cevap['istihdam_notu'].strip()}")
    satir.append(f"- Ölçüm yöntemi: {(cevap.get('olcum') or '').strip() or D.format('göstergelerin nasıl izleneceği (fatura, SGK bildirgesi, gümrük verisi)')}")
    return "\n".join(satir)


CEVAP_YAZISI = {"evet": "sağlıyor", "hayir": "SAĞLAMIYOR", "bilmiyorum": "emin değil"}


def _tur(m: dict) -> str:
    """Eski biçimli maddeler (tur=basvuru, kural kalıplı şart) yeni türlere çevrilir."""
    tur = m.get("tur")
    if tur == "basvuru":
        return "adim"
    if tur == "sart" and (m.get("kural") or KURAL.search(m.get("metin") or "")):
        return "kural"
    return tur


def belgeler_ve_kurallar(maddeler: list[dict]) -> str:
    """Kontrol listesi bölümü, kutular karışmadan: şartlar (cevapla), belgeler ve adımlar (onay kutusu), kurallar ve
    bilgiler (uyarı). Kaynakta doğrulanamamış madde "(kurumdan teyit edin)" notuyla."""
    if not maddeler:
        return ("## 6. Başvuru şartları, belgeler ve adımlar\n\nBu program için şart/belge bilgisi sistemimizde yok; "
                "kurumun resmi sayfasından kontrol edin.")

    def yaz(m: dict) -> str:
        return m["metin"] + (" (kurumdan teyit edin)" if m.get("dogrulandi") is False else "")

    grup = {t: [m for m in maddeler if _tur(m) == t] for t in ("sart", "belge", "adim", "kural", "bilgi")}
    satir = ["## 6. Başvuru şartları, belgeler ve adımlar", "", "Kontrol listenizden; kurumun güncel duyurusuyla teyit edin."]
    if grup["sart"]:
        satir += ["", "**Başvurabilir miyim? (şartlar)**"] + [
            f"- {yaz(m)} — {CEVAP_YAZISI.get(m.get('cevap'), 'cevaplanmadı')}" for m in grup["sart"]]
    if grup["belge"]:
        satir += ["", "**Hazırlanacak belgeler**"] + [f"- [{'x' if m.get('isaretli') else ' '}] {yaz(m)}" for m in grup["belge"]]
    if grup["adim"]:
        satir += ["", "**Başvuru adımları**"] + [f"- [{'x' if m.get('isaretli') else ' '}] {yaz(m)}" for m in grup["adim"]]
    if grup["kural"] or grup["bilgi"]:
        satir += ["", "**Bilmeniz gerekenler**"] + [f"- ⚠ {yaz(m)}" for m in grup["kural"]] + [f"- {yaz(m)}" for m in grup["bilgi"]]
    return "\n".join(satir)


# Başvuru biçimine göre taslağın yeri (docs/olcum/2026-10-09-uygunluk/KRITER_SEMASI.md; taslak denemesi: proje dışı
# programlarda kullanıcılar "metin bu başvuruya bir şey katmıyor" dedi, docs/olcum/2026-10-09-taslak-ajan/RAPOR.md).
BICIM_ACIKLAMA = {
    "kefalet": "Bu program bir kredi kefaletidir: başvuruyu kredi kullanacağınız bankaya yaparsınız, banka kefaleti KGF'ye "
               "iletir. Proje metni istenmez; bankanın istediği finansal belgeler gerekir.",
    "bildirim_prim": "Bu teşvik SGK'ya yapılan işe giriş ve aylık prim bildirimiyle uygulanır; proje ya da başvuru metni "
                     "yazılmaz. Uygunluk şartlarını ve işe alınacak kişilerin niteliğini kontrol edin.",
    "uretim_odeme": "Bu destek üretim/kayıt bilgilerinize göre (dekar, hayvan, ürün başına) ödenir; proje metni yazılmaz. "
                    "Kayıtlarınızı (ÇKS vb.) zamanında güncellemeniz yeterlidir.",
    "belge_etuys": "Bu teşvik, E-TUYS üzerinden yatırım teşvik belgesi başvurusuyla alınır; başvuru serbest metin değil, "
                   "yatırım bilgileri (cins, yer, tutar, makine listesi, istihdam) girilen yapılandırılmış formdur.",
    "kredi": "Bu bir kredi programıdır: başvuruda kredi tutarı, vade ve teminat bilgileri istenir; uzun proje metni zorunlu "
             "değildir. Aşağıdaki taslağı yalnız harcama planınızı toparlamak için kullanabilirsiniz.",
    "faiz_destegi": "Bu destek kullandığınız kredinin faizine yapılır: başvuruda kredi ve harcama bilgileri istenir; uzun "
                    "proje metni zorunlu değildir. Taslağı harcama planınızı toparlamak için kullanabilirsiniz.",
    "gider_on_onay": "Bu destek gider kalemleri bazında ön onay ve belgelerle geri ödemeyle işler; uzun proje metni istenmez. "
                     "Taslağı harcama planınızı (kalem, ülke, tutar) toparlamak için kullanabilirsiniz.",
}
TASLAK_YOK = {"kefalet", "bildirim_prim", "uretim_odeme", "belge_etuys"}


def taslak_kapsami(t) -> dict:
    """Taslak neye hazırlanıyor: gerekli mi, ne için, nereye girilir, ne değildir (arayüz ve Word başlığı)."""
    bicim = getattr(t, "basvuru_bicimi", None)
    f = resmi_form(t.id)
    if f:
        ilk, son = f["bolumler"][0][1], f["bolumler"][-1][1]
        ne_icin = f"{f['ad']} metin bölümleri ({ilk.split(' ')[0]} – {son.split(' ')[0]})"
    else:
        ne_icin = "kurumun başvuru formundaki proje/iş planı anlatımı (amaç ve gerekçe, faaliyetler ve takvim, bütçe, çıktılar)"
    # Resmi proje formu tanımlıysa (ör. Kapasite Geliştirme: faiz desteği ama II. Bölüm proje formu ister) form esastır.
    return {"gerekli": bool(f) or bicim not in TASLAK_YOK, "bicim": bicim, "aciklama": None if f else BICIM_ACIKLAMA.get(bicim),
            "ne_icin": ne_icin, "resmi_form": f["ad"] if f else None, "form_kaynak": f["kaynak"] if f else None,
            "nereye": (getattr(t, "basvuru_yeri", None) or "").strip() or None,
            "ne_degil": "Resmi form değildir: formun tabloları, ekleri ve imzalı belgeleri kurumun sisteminde ayrıca doldurulur."}


def uret(t, profil: dict, maddeler: list[dict], cagrilar: list[dict], cevaplar: dict | None = None) -> str:
    """Markdown taslak. profil: app.rag.profil_sozlugu (+ İKAS baglam_alanlari); cagrilar: program_cagrilari;
    cevaplar: sihirbaz (proje_adi, proje_ozeti, gerekce{}, faaliyetler[], butce[], destek_orani, ciktilar{})."""
    c, s = cevaplar or {}, sorular(t)
    govde = [_isletme(profil), _amac(t, profil, c, s), _takvim(t, cagrilar, c, s), _butce(t, c, s), _cikti(profil, c, s)]
    metin = "\n\n".join(f"## {b}\n\n{g}" for b, g in zip(BOLUMLER, govde))
    # Ayrı alıntı satırı: paneldeki mdToHtml alıntı içi italiği işlemiyor.
    k = taslak_kapsami(t)
    not_ = (f"> **Ne için:** {t.baslik} başvurusunda {k['ne_icin']}."
            + (f" **Nereye girilir:** {k['nereye']}." if k["nereye"] else "")
            + "\n>\n" + BASLIK_NOTU
            + "\n>\n> Bu taslak yapay zekâ kullanılmadan, kayıtlı verilerinizden ve sihirbaz cevaplarınızdan hazırlandı.")
    return f"{not_}\n\n{metin}\n\n{belgeler_ve_kurallar(maddeler)}\n"


def _self_test() -> int:
    from app.models import Tesvik

    t1501 = Tesvik(id=34, kurum="TUBITAK", baslik="1501 - TÜBİTAK Sanayi Ar-Ge Projeleri Destekleme Programı",
                   tesvil_tutari="Hibe: ilk 5 proje %75 (en fazla 20 M TL/proje), 6. ve sonrası %60 (en fazla 20 M TL)",
                   tutari_max=20_000_000,
                   tutari_hesaplama_formulu="Destek = uygun proje giderleri × %75 ya da × %60; proje başına en fazla 20 "
                                            "milyon TL. Desteklenen giderler: personel; seyahat; malzeme ve sarf.",
                   basvuru_sartlari=["Sermaye şirketi olmak", "Proje başvurusundan önce tamamlanmış Ar-Ge faaliyetleri desteklenmez"],
                   uygunluk_kriterleri={"sektorler": ["arge", "genel"]})
    p = {"sektör": "imalat", "bölge": "Konya", "çalışan sayısı": 12, "yıllık ciro": 4.5e6, "şirket türü": "limited",
         "NACE kodu": "10.71", "hedefler": ["yatirim", "ihracat"]}
    m = [{"tur": "sart", "metin": "Sermaye şirketi olmak", "isaretli": False},
         {"tur": "sart", "metin": "Proje başvurusundan önce tamamlanmış Ar-Ge faaliyetleri desteklenmez", "isaretli": False},
         {"tur": "belge", "metin": "Proje öneri formu", "isaretli": True}]
    cev = {"proje_adi": "Glutensiz ekmek üretim süreci", "proje_ozeti": "Raf ömrünü uzatan yeni bir fermantasyon süreci.",
           "gerekce": {"B2": "Katkısız raf ömrü 7 güne çıkar."},
           "faaliyetler": [{"ad": "Prototip", "baslangic": "2027-01", "bitis": "2027-06"}],
           "butce": [{"kalem": "Personel", "tutar": 2_000_000}, {"kalem": "Malzeme", "tutar": 500_000}],
           "destek_orani": 75.0, "ciktilar": {"arge_cikti": "Pilot üretim hattı ve faydalı model başvurusu"}}
    bos = uret(t1501, p, m, [])
    dolu = uret(t1501, p, m, [], cev)
    t1512 = Tesvik(id=174, kurum="TUBITAK", baslik="1512 - Girişimcilik Destek Programı (BiGG - Bireysel Genç Girişim)")
    # rag.profil_sozlugu şirketsiz profile de çalışan/ciroya göre "mikro işletme" ölçeği koyar.
    girisimci = uret(t1512, {"sektör": "arge", "bölge": "Ankara", "çalışan sayısı": 1, "yıllık ciro": 0.0,
                             "şirket türü": "yok", "NACE kodu": "62.01", "hedefler": ["arge"],
                             "KOBİ ölçeği": "mikro işletme [KOBİ Yönetmeliği]"}, [], [])
    gelirsiz = uret(t1501, {**p, "yıllık ciro": 0.0}, m, [])
    buyuk = uret(t1501, p, m, [], {**cev, "butce": [{"kalem": "Personel", "tutar": 40_000_000}]})
    k = [
        ("cevapsız taslakta boş tablo yok", "| [DOLDURUN" not in bos and "Önerilen iş adımları" in bos
         and "Desteklenen gider türleri" in bos),
        ("oran seçenekleri kayıttan (%75, %60)", sorular(t1501)["oran_secenekleri"] == [75.0, 60.0]),
        ("cevaplar metne girer", "**Proje:** Glutensiz ekmek üretim süreci." in dolu and "Katkısız raf ömrü" in dolu
         and "| Prototip | Ocak 2027 | Haziran 2027 |" in dolu),
        ("bütçe toplamı ve destek hesaplanır", "**2.500.000 TL**" in dolu and "= **1.875.000 TL**" in dolu),
        ("üst limit uygulanır", "= **20.000.000 TL** (kayıttaki üst limit 20.000.000 TL ile sınırlandı)" in buyuk),
        ("Ar-Ge projesine kapasite/ihracat göstergesi gelmez", "Kapasite artışı" not in bos and "İhracat hedefi" not in bos
         and "Ar-Ge çıktıları" in bos),
        ("kural uyarı olarak, onay kutusu değil", "- ⚠ Proje başvurusundan önce" in bos
         and "- [ ] Proje başvurusundan önce" not in bos and "- [x] Proje öneri formu" in bos),
        ("seçilmeyen oranla hesap yapılmaz", "Talep edilebilecek destek (tahmini)" not in uret(t1501, p, m, [], {**cev, "destek_orani": 50})),
        ("ek uyumu ve tam cümle", "bir limited şirkettir." in bos and _tam_cumleler("Bir. İki iyile") == "Bir."),
        ("girişim programında kapasite sorusu yok", program_turleri(Tesvik(kurum="TUBITAK",
                                                                           baslik="1812 - Yatırım Tabanlı Girişimcilik")) == ["girisim"]),
        ("ay biçimi", _ay("2027-01") == "Ocak 2027" and _ay("2027-13") == "" and _ay(None) == ""),
        ("resmi form bölümleri (1501 → AGY100 A-E)", sorular(t1501)["form"]["ad"].startswith("TÜBİTAK Proje Öneri")
         and [q["anahtar"] for q in sorular(t1501)["gerekce"]][:3] == ["A3", "B1", "B2"]
         and "### B.2 Projenin Teknoloji Düzeyi" in bos and "M011 Personel" in bos),
        ("form cevabı başlığının altına yazılır", "### B.4 Projenin Yenilikçi Yönleri" in uret(
            t1501, p, m, [], {**cev, "gerekce": {"B4": "Ülke için yeni ürün."}}) and "Ülke için yeni ürün." in uret(
            t1501, p, m, [], {**cev, "gerekce": {"B4": "Ülke için yeni ürün."}})),
        ("ciro 0 eksik sayılmaz", "son yıl net satış hasılatı: 0 TL." in gelirsiz and "yıllık ciro (TL)" not in gelirsiz),
        ("şirketsiz girişimde işletme/ölçek/hasılat dili yok", "henüz şirket kurmamış bir girişimci" in girisimci
         and "İşletmemiz" not in girisimci and "Ölçek:" not in girisimci and "hasılat" not in girisimci
         and "DOLDURUN: yıllık ciro" not in girisimci and "Girişimin genel hedefleri: Ar-Ge." in girisimci),
        ("sektör görünen adıyla", "faaliyet alanı: Ar-Ge (NACE 62.01)." in girisimci
         and "Faaliyet alanı: imalat (NACE 10.71)." in bos),
        ("taslak kapsamı: kefalette gerekmez, açıklamalı",
         taslak_kapsami(Tesvik(id=86, baslik="Nefes", basvuru_bicimi="kefalet"))["gerekli"] is False
         and "bankaya" in taslak_kapsami(Tesvik(id=86, baslik="Nefes", basvuru_bicimi="kefalet"))["aciklama"]),
        ("taslak kapsamı: resmi form varsa biçimden önce gelir (Kapasite Geliştirme, faiz desteği)",
         (lambda k: k["gerekli"] and k["aciklama"] is None and "2.11" in k["ne_icin"])(
             taslak_kapsami(Tesvik(id=8, baslik="Kapasite Geliştirme", basvuru_bicimi="faiz_destegi")))),
        ("taslak neye hazırlandığını ilk satırda söyler", bos.startswith("> **Ne için:**")),
    ]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in k)
    print(f"\nself-test: {gecen}/{len(k)} geçti")
    return 0 if gecen == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
