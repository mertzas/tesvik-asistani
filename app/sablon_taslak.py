"""Yapay zekâsız başvuru ön taslağı (2026-10-08): kayıt + profil + çağrı + İKAS verisinden kurallarla Markdown.

Neden: Claude taslağı profili ABD'ye gönderdiği için açık rıza, PRO plan ve API anahtarı istiyordu. Taslağın çoğu zaten
yapılandırılmış veridir (programın amacı, tutar/oran, başvuru yeri/dönemi, şartlar, belgeler, profil, İKAS toplamları).
Bu modül aynı bölümleri (app/basvuru_taslagi.BOLUMLER) aynı uyarı notu ve belgeler bölümüyle üretir; veri olmayan her
yer "[DOLDURUN: …]" kalır, hiçbir rakam türetilmez ya da tahmin edilmez. Ağ yok, ücret yok, veri yurt dışına çıkmaz.
Yapay zekâ taslağı isteğe bağlı "metni yapay zekâyla yaz" seçeneği olarak kalır.

    python -m app.sablon_taslak --self-test
"""
from __future__ import annotations

import re
import sys

from app.basvuru_taslagi import BASLIK_NOTU, BOLUMLER, belgeler_bolumu, kart_ozeti

MODEL_ADI = "sablon-v1"
D = "[DOLDURUN: {}]"
# Yüklem biçimleri ünlü uyumuyla hazır yazılır ("şirket" + "dir" → "şirkettir").
SIRKET = {"yok": "henüz şirketleşmemiş bir girişimdir", "sahis": "bir şahıs işletmesidir",
          "limited": "bir limited şirkettir", "anonim": "bir anonim şirkettir", "kooperatif": "bir kooperatiftir"}
HEDEF = {"yatirim": "yatırım", "ihracat": "ihracat", "arge": "Ar-Ge", "istihdam": "istihdam", "makine": "makine alımı",
         "sulama": "sulama sistemi", "hayvan": "hayvancılık", "organik": "organik tarım", "e-ticaret": "e-ticaret"}
ON_ONAY = re.compile(r"ön\s+onay|müracaat tarihinden önce|harcamaya başlamadan", re.IGNORECASE)


def _tl(x) -> str:
    return f"{float(x):,.0f} TL".replace(",", ".")


def _tarih(iso: str | None) -> str:
    if not iso:
        return ""
    y, a, g = map(int, iso.split("-"))
    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    return f"{g} {aylar[a - 1]} {y}"


def _tam_cumleler(metin: str) -> str:
    """Yalnız tamamlanmış cümleler: kazınmış özetlerin bir kısmı kelime ortasında kesik ("… geliştirilmiş, iyile")."""
    metin = (metin or "").replace(" […]", "").strip()
    if not metin or metin[-1] in ".!?…":
        return metin
    son = max(metin.rfind(". "), metin.rfind("! "), metin.rfind("? "))
    return metin[:son + 1] if son > 0 else ""


# Program türüne göre yönlendirici gerekçe soruları ve faaliyet adımları (rakam yok; [DOLDURUN] ipucu). Yapay zekâ
# taslağıyla karşılaştırmada (docs/olcum/2026-10-08-taslak-karsilastirma) asıl fark buydu: model programa özgü
# sorular soruyordu ("darboğaz ve kapasite kullanım oranı", "karşılanamayan talep").
REHBER: dict[str, tuple[list[str], list[str]]] = {
    "yatirim": (["Mevcut kapasite kullanım oranı ve darboğazlar: " + D.format("hangi süreç/makinede, oran"),
                 "Karşılanamayan talep: " + D.format("reddedilen/ertelenen siparişler, talep artışı"),
                 "Yatırımın çözeceği sorun: " + D.format("verimlilik, kalite, maliyet")],
                ["Teklif ve proformaların toplanması", "Makine/ekipman tedariki", "Kurulum ve devreye alma",
                 "Kapasite/verimlilik artışının ölçülmesi"]),
    "ihracat": (["Hedef pazarlar ve seçim gerekçesi: " + D.format("ülkeler, pazar araştırması dayanağı"),
                 "Mevcut ihracat durumu: " + D.format("son yıl ihracat, başlıca alıcılar/kanallar"),
                 "Rekabet avantajı: " + D.format("ürün, fiyat, sertifika, marka")],
                ["Pazar araştırması ve hedef ülke seçimi", "Tanıtım/fuar/pazaryeri faaliyetleri",
                 "Alıcı görüşmeleri ve sipariş", "İhracat sonuçlarının izlenmesi"]),
    "arge": (["Teknolojik yenilik ve özgün değer: " + D.format("mevcut çözümlerden farkı"),
              "Teknik riskler ve yöntem: " + D.format("belirsizlikler, deney/prototip planı"),
              "Ticarileşme: " + D.format("hedef müşteri, pazar, gelir modeli")],
             ["Literatür/patent taraması ve gereksinimler", "Tasarım ve prototip geliştirme", "Test ve doğrulama",
              "Ticarileşme hazırlığı (fikri mülkiyet, pilot müşteri)"]),
    "istihdam": (["Korunacak/oluşturulacak istihdam: " + D.format("pozisyonlar ve kişi sayısı"),
                  "İstihdamı etkileyen durum: " + D.format("talep düşüşü, finansman ihtiyacı, büyüme")],
                 ["İşe alım/istihdamın korunması planı", "SGK bildirgeleriyle izleme"]),
    "girisim": (["İş fikri ve çözülen sorun: " + D.format("hedef müşteri ve ihtiyacı"),
                 "Ekip ve yetkinlik: " + D.format("kurucular, deneyim"),
                 "İş modeli: " + D.format("gelir kaynakları, ilk müşteriler")],
                ["Şirket kuruluşu / kayıtlar", "Ürün/hizmetin ilk sürümü", "İlk müşteriler ve satış", "Büyüme planı"]),
    "tarim": (["Üretim durumu: " + D.format("ürün, alan (dekar) ya da hayvan sayısı, ÇKS/TÜRKVET kaydı"),
               "Desteğin kullanım amacı: " + D.format("verim, kalite, maliyet, sertifikasyon")],
              ["Kayıtların (ÇKS/ÖKS/TÜRKVET) güncellenmesi", "Üretim/uygulama dönemi", "Başvuru ve belge teslimi"]),
}


BASLIK_TURU = [("girisim", r"Girişim|BiGG"), ("yatirim", r"Kapasite|Yatırım|makine|Dijital Dönüşüm|Hamle"),
               ("arge", r"Ar-?Ge|Araştırma|Teknoloji"), ("ihracat", r"ihracat|Rekabetçilik|Pazar"),
               ("istihdam", r"istihdam")]


def program_turleri(t) -> list[str]:
    """Rehber anahtarları, önem sırasıyla. Önce BAŞLIK (programın türü), yoksa kurum (tarım), en son sektör etiketi:
    sektör etiketleri ihtiyacı geniş kodlar (Kapasite Geliştirme'de "arge" var) ve tek başına Ar-Ge sorusu
    getiriyordu (tarayıcı/ölçüm 2026-10-08)."""
    baslik = t.baslik or ""
    turler = [tur for tur, kalip in BASLIK_TURU if re.search(kalip, baslik, re.IGNORECASE)]
    if "girisim" in turler and "yatirim" in turler:
        turler.remove("yatirim")  # "Yatırım Tabanlı Girişimcilik": girişime sermaye yatırımı, makine/kapasite değil
    if re.search(r"Tarım", t.kurum or "", re.IGNORECASE):
        turler.append("tarim")
    if not turler:
        turler = sorted(program_hedefleri(t))
    return [x for x in dict.fromkeys(turler) if x in REHBER]


def program_hedefleri(t) -> set[str]:
    """Programın türünden çıkan gösterge anahtarları (profil hedefinden bağımsız): Ar-Ge programına Ar-Ge çıktısı,
    ihracat programına ihracat göstergesi. Tarayıcı denemesi 2026-10-08: 1501 taslağında Ar-Ge çıktısı yoktu."""
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


def _isletme(p: dict) -> str:
    tur = SIRKET.get(p.get("şirket türü") or "", None)
    cumle = [f"İşletmemiz {p.get('bölge') or D.format('il')} ilinde faaliyet gösteren "
             f"{tur if tur else D.format('şirket türü') + ' bir işletmedir'}."]
    sektor = p.get("sektör")
    nace = p.get("NACE kodu")
    cumle.append(f"Faaliyet alanı: {sektor if sektor and sektor != 'genel' else D.format('sektör')}"
                 + (f" (NACE {nace})" if nace else f" ({D.format('NACE kodu')})") + ".")
    kurulus = p.get("kuruluş tarihi")
    cumle.append(f"Kuruluş tarihi: {_tarih(kurulus) if kurulus else D.format('kuruluş tarihi')}.")
    calisan, ciro = p.get("çalışan sayısı"), p.get("yıllık ciro")
    cumle.append(f"Çalışan sayısı: {calisan if calisan is not None else D.format('çalışan sayısı')}; "
                 f"son yıl net satış hasılatı: {_tl(ciro) if ciro else D.format('yıllık ciro (TL)')}.")
    if p.get("KOBİ ölçeği"):
        cumle.append(f"Ölçek: {p['KOBİ ölçeği']}.")
    satirlar = [" ".join(cumle), "", f"Ana ürün ve hizmetler: {D.format('ürün/hizmetler ve başlıca müşteri grupları')}"]
    ikas = [(k, v) for k, v in p.items() if "İKAS" in k]
    if ikas:
        satirlar += ["", "E-ticaret mağaza kayıtlarına göre (resmi belgeyle — fatura, gümrük beyannamesi/ETGB — teyit "
                     "edilmelidir):"] + [f"- {k}: {v}" for k, v in ikas]
    return "\n".join(satirlar)


def _amac(t, p: dict) -> str:
    satir = [f"Başvurulan program: **{t.baslik}** ({t.kurum})."]
    amac = _tam_cumleler(kart_ozeti(t.ozet, 600))
    if amac:
        satir.append(f"Programın amacı (kurum metni): {amac}")
    hedefler = [HEDEF.get(h, h) for h in (p.get("hedefler") or [])]
    satir += ["", f"İşletmenin bu başvurudaki hedefi: {', '.join(hedefler) if hedefler else D.format('hedef')}.",
              f"Proje: {D.format('projenin adı ve tek cümlelik tanımı')}",
              f"Gerekçe: {D.format('çözülecek sorun ya da karşılanacak ihtiyaç; neden şimdi')}",
              f"Programla uyum: {D.format('projenin programın amacına nasıl hizmet ettiği')}"]
    sorular = [s for tur in program_turleri(t) for s in REHBER[tur][0]]
    if sorular:
        satir += ["", "Gerekçeyi şu başlıklarla somutlayın:"] + [f"- {s}" for s in sorular]
    return "\n".join(satir)


def _takvim(t, cagrilar: list[dict]) -> str:
    satir = []
    canli = [c for c in cagrilar if c.get("durum") in ("acik", "yaklasan")]
    if canli:
        c = canli[0]
        if c.get("on_kayit_son"):
            satir.append(f"Başvuru dönemi: {c['ad']} — ön kayıt son günü {_tarih(c['on_kayit_son'])}, kapanış "
                         f"{_tarih(c.get('kapanis'))}.")
        elif c["durum"] == "yaklasan":
            satir.append(f"Başvuru dönemi: {c['ad']} — {_tarih(c.get('acilis'))} tarihinde açılıyor"
                         + (f", kapanış {_tarih(c['kapanis'])}." if c.get("kapanis") else "."))
        else:
            satir.append(f"Başvuru dönemi: {c['ad']} — son başvuru {_tarih(c['kapanis'])}." if c.get("kapanis")
                         else f"Başvuru dönemi: {c['ad']} — açık (son tarih duyurulmadı).")
    elif t.basvuru_suresi:
        satir.append(f"Başvuru zamanı: {t.basvuru_suresi}")
    else:
        satir.append(f"Başvuru dönemi: {D.format('kurumun güncel duyurusundaki tarih')}")
    if t.basvuru_yeri:
        satir.append(f"Başvuru yeri: {t.basvuru_yeri}")
    if t.destek_verilme_suresi:
        satir.append(f"Destek süresi: {t.destek_verilme_suresi}")
    metin = " ".join(filter(None, [t.basvuru_suresi or "", " ".join(map(str, t.basvuru_sartlari or []))]))
    if ON_ONAY.search(metin):
        satir.append("**Önemli:** Bu programda ön onaydan/müracaattan önce yapılan harcama desteklenmez; harcamaları "
                     "başvurudan sonraya planlayın.")
    turler = program_turleri(t)
    adimlar = REHBER[turler[0]][1] if turler else [D.format(f"faaliyet {i}") for i in (1, 2, 3)]  # yalnız birincil tür
    satir += ["", "| Faaliyet | Başlangıç | Bitiş | Sorumlu |", "|---|---|---|---|"]
    satir += [f"| {a} | {D.format('ay/yıl')} | {D.format('ay/yıl')} | {D.format('kişi/birim')} |" for a in adimlar]
    return "\n".join(satir)


def _butce(t) -> str:
    satir = []
    if t.tesvil_tutari:
        satir.append(f"Programın destek tutarı/oranı: {t.tesvil_tutari}")
    if t.tutari_hesaplama_formulu:
        satir.append(f"Hesaplama: {t.tutari_hesaplama_formulu}")
    if not satir:
        satir.append(f"Programın destek oranı ve üst limiti: {D.format('kurumun güncel tutar/oran bilgisi')}")
    satir += ["", "| Gider kalemi | Tutar (TL) | Açıklama |", "|---|---|---|"]
    satir += [f"| {D.format(f'kalem {i}')} | {D.format('tutar')} | {D.format('teklif/proforma dayanağı')} |" for i in (1, 2, 3)]
    satir += [f"| **Toplam** | {D.format('toplam')} | |", "",
              "Talep edilen destek, programın oranını ve üst limitini aşamaz; kalem tutarlarını teklif/proformalarla "
              "belgeleyin."]
    return "\n".join(satir)


def _cikti(p: dict, t=None) -> str:
    hedefler = list(p.get("hedefler") or [])
    hedefler += sorted(program_hedefleri(t) - set(hedefler)) if t is not None else []
    gosterge = {
        "istihdam": f"İlave istihdam: {D.format('kişi')} (mevcut {p.get('çalışan sayısı', D.format('kişi'))})",
        "ihracat": f"İhracat: son yıl {D.format('tutar ve döviz')} → hedef {D.format('tutar')}; hedef pazarlar "
                   f"{D.format('ülkeler')}",
        "yatirim": f"Kapasite: mevcut {D.format('birim/yıl')} → hedef {D.format('birim/yıl')}",
        "makine": f"Verimlilik: makine yatırımıyla {D.format('ölçülebilir artış, ör. birim maliyet/çevrim süresi')}",
        "arge": f"Ar-Ge çıktıları: {D.format('prototip, patent/faydalı model başvurusu, yayın')}"
                + (f"; mevcut teknoloji hazırlık seviyesi {p['TRL (teknoloji hazırlık seviyesi)']}"
                   if p.get("TRL (teknoloji hazırlık seviyesi)") else ""),
        "e-ticaret": f"Çevrim içi satış: {D.format('sipariş/ciro hedefi')}",
        "sulama": f"Su tasarrufu ve verim: {D.format('dekar başına verim/su kullanımı')}",
        "hayvan": f"Hayvan varlığı ve üretim: {D.format('baş sayısı, süt/et üretimi')}",
        "organik": f"Organik sertifikalı alan: {D.format('dekar')}",
    }
    satir = [f"- {gosterge[h]}" for h in hedefler if h in gosterge]
    satir.append(f"- Ciro/verimlilik etkisi: {D.format('ölçülebilir hedef ve süre')}")
    satir.append(f"- Ölçüm yöntemi: {D.format('göstergelerin nasıl izleneceği (fatura, SGK bildirgesi, gümrük verisi)')}")
    return "\n".join(satir)


def uret(t, profil: dict, maddeler: list[dict], cagrilar: list[dict]) -> str:
    """Markdown taslak. profil: app.rag.profil_sozlugu (+ İKAS baglam_alanlari); cagrilar: app.cagrilar.program_cagrilari."""
    govde = [_isletme(profil), _amac(t, profil), _takvim(t, cagrilar), _butce(t), _cikti(profil, t)]
    metin = "\n\n".join(f"## {b}\n\n{g}" for b, g in zip(BOLUMLER, govde))
    # Ayrı alıntı satırı: paneldeki mdToHtml alıntı içi italiği işlemiyor (tarayıcı denemesi 2026-10-08).
    not_ = BASLIK_NOTU + "\n>\n> Bu taslak yapay zekâ kullanılmadan, kayıtlı verilerinizden şablonla hazırlandı."
    return f"{not_}\n\n{metin}\n\n{belgeler_bolumu(maddeler)}\n"


def _self_test() -> int:
    from app.models import Tesvik

    t = Tesvik(id=7, kurum="KOSGEB", baslik="İstihdamı Koruma Destek Programı",
               ozet="İmalat sanayinde istihdamın korunması için KOBİ ve büyük işletmelere kredi desteği sağlanır.",
               tesvil_tutari="Kredi faiz desteği; azami 12 destek puanı", basvuru_yeri="KOSGEB",
               basvuru_sartlari=["Destekten önce ön onay alınmalı"])
    p = {"sektör": "imalat", "bölge": "Bursa", "çalışan sayısı": 45, "yıllık ciro": 120e6, "şirket türü": "limited",
         "kuruluş tarihi": "2009-04-01", "NACE kodu": "25.62", "hedefler": ["istihdam", "ihracat"],
         "yurt dışına teslim edilen siparişler (İKAS)": "12 sipariş (%3.0); ülkeler: DE"}
    c = [{"ad": "2026-2 dönemi", "durum": "acik", "acilis": "2026-09-01", "kapanis": "2026-10-31", "on_kayit_son": None}]
    m = [{"metin": "Başvuru formu", "isaretli": False}]
    s = uret(t, p, m, c)
    bos = uret(Tesvik(id=1, kurum="KGF", baslik="X"), {}, [], [])
    k = [
        ("beş bölüm + belgeler, sırayla", all(s.index(f"## {b}") < s.index(f"## {BOLUMLER[i + 1]}") for i, b in
                                              enumerate(BOLUMLER[:-1])) and "## 6. Hazırlanacak belgeler" in s),
        ("profil olguları metinde, ek uyumu doğru", all(x in s for x in ("Bursa", "bir limited şirkettir.", "NACE 25.62", "1 Nisan 2009",
                                                        "120.000.000 TL", "45"))),
        ("çağrı tarihi ve ön onay uyarısı", "31 Ekim 2026" in s and "ön onaydan" in s),
        ("İKAS verisi kaynağıyla", "E-ticaret mağaza kayıtlarına göre" in s and "12 sipariş" in s),
        ("hedefe göre gösterge", "İlave istihdam" in s and "İhracat: son yıl" in s),
        ("boş profilde rakam uydurulmaz", "[DOLDURUN: il]" in bos and "[DOLDURUN: yıllık ciro (TL)]" in bos
         and not re.search(r"\d{2,}\.\d{3} TL", bos)),
        ("yapay zekâ kullanılmadığı yazılı", "yapay zekâ kullanılmadan" in s and "_Bu taslak" not in s),
        ("kesik kurum metni tam cümleye indirilir", _tam_cumleler("Birinci cümle tamam. İkinci cümle iyile") ==
         "Birinci cümle tamam." and _tam_cumleler("tek kesik parça iyile") == ""),
        ("program türüne göre gerekçe soruları ve faaliyet adımları",
         "darboğazlar" in uret(Tesvik(id=8, kurum="KOSGEB", baslik="Kapasite Geliştirme Destek Programı"), {}, [], [])
         and "Makine/ekipman tedariki" in uret(Tesvik(id=8, kurum="KOSGEB", baslik="Kapasite Geliştirme"), {}, [], [])
         and "| [DOLDURUN: faaliyet 1]" in uret(Tesvik(id=1, kurum="KGF", baslik="Genel Kefalet"), {}, [], [])
         and "Teknolojik yenilik" not in uret(Tesvik(id=8, kurum="KOSGEB", baslik="Kapasite Geliştirme Destek Programı",
                                                     uygunluk_kriterleri={"sektorler": ["imalat", "arge"]}), {}, [], [])),
        ("girişim programında kapasite sorusu yok", program_turleri(Tesvik(
            kurum="TUBITAK", baslik="1812 - Yatırım Tabanlı Girişimcilik Destek Programı")) == ["girisim", "arge"]
         or program_turleri(Tesvik(kurum="TUBITAK", baslik="1812 - Yatırım Tabanlı Girişimcilik")) == ["girisim"]),
        ("Ar-Ge programına Ar-Ge çıktısı eklenir", "Ar-Ge çıktıları" in uret(
            Tesvik(id=34, kurum="TUBITAK", baslik="1501 Sanayi Ar-Ge", uygunluk_kriterleri={"sektorler": ["arge"]}),
            {"hedefler": ["yatirim"]}, [], [])),
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
