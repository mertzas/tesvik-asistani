"""9903 EK-3 listesindeki sütun kayması düzeltmesi (2026-10-12).

app/data/ek3_9903.json PDF'ten otomatik çıkarılmıştı; iki sütunlu tabloda uzun satırlar kaydı:
- tanım sütunu şart sütununa taştı: 55.1 "Oteller ... 50 oda ve üzeri (Otel, Tatil Köyü, Butik Otel ve Özel" |
  "Konaklama Tesisi desteklenir)"; 18 matbaacılık şartı "ve modernizasyon yatırımları desteklenir." parçasına indi;
- şart tanıma girdi: 82.2 "Sadece 6 ncı bölgede yapılan yatırımlar desteklenir" tanımda kaldığı için çağrı merkezi
  her bölgede "uygun" çıkıyordu;
- çok satırlı sayfa düzeninde komşu kodun metni yazıldı: 24.10.08 ferro alaşım, 35.11/35.12 elektrik dağıtımı,
  52.22.06 kılavuzluk, 01.47.01/03 su ürünlerinin "balık yemi tesisi" şartı.
Persona denemesinde (docs/olcum/2026-10-12-persona) butik otel ve matbaa yanıtlarında görüldü.

Her düzeltilmiş tanım ve şart, resmî metnin (Resmî Gazete 30.05.2025, 9903 sayılı Karar EK-3; metin
docs/olcum/2026-10-09-uygunluk/kaynak/177.txt) boşluk normalleştirilmiş hâlinde birebir geçmek zorundadır (self-test).
"X hariç" kapsam dışı alt kodları tanımda kalır (_haric_kod iki alanı da okur; şart sayılmaz).

Kullanım:
    python scripts/fix_ek3_9903_2026_10_12.py --self-test
    python scripts/fix_ek3_9903_2026_10_12.py            (kuru çalıştırma: değişiklikleri listeler)
    python scripts/fix_ek3_9903_2026_10_12.py --uygula   (yazar; idempotent)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
VERI = KOK / "app" / "data" / "ek3_9903.json"
KAYNAK = KOK / "docs" / "olcum" / "2026-10-09-uygunluk" / "kaynak" / "177.txt"

_KUMES = ("a) Damızlık kümes hayvanları yetiştiriciliğinin kuluçkahane ile entegre olması şartı aranır. "
          "b) 1, 2, 3, 4 ve 5. Bölgelerde asgari 200.000 adet/dönem et yönlü kümes hayvanları yetiştiriciliğinin "
          "kesimhane ile entegre olması şartı aranır. c) 6. Bölgede asgari 100.000 adet/dönem et yönlü kümes hayvanları "
          "yetiştiriciliğinin kesimhane ile entegre olması şartı aranır. d) 1, 2, 3, 4 ve 5. Bölgelerde asgari 200.000 "
          "adet/dönem yumurta yönlü kümes hayvanları yetiştiriciliği şartı aranır. e) 6. Bölgede asgari asgari 100.000 "
          "adet/dönem yumurta yönlü kümes hayvanları yetiştiriciliği şartı aranır. Ayrıca, tevsi ve komple yeni yatırım "
          "cinsindeki yatırımlar; yem tesisi ve/veya et yönlü kümes hayvanları yetiştiriciliği yatırımları ileri işleme "
          "ve/veya soğuk hava deposu, yumurta yönlü kümes hayvanları yetiştiriciliği yatırımları soğuk hava deposu ve/veya "
          "yumurta tasnif-paketleme yatırımları ile entegre edilebilir.")

# kod -> (tanım, şart). Elektrik üretimi (35.11/35.12) şartı D bölümü şartı olarak ayrıca saklıdır; tekrar yazılmaz.
DUZELTME: dict[str, tuple[str, str]] = {
    "01.47.01": ("Kümes hayvanlarının yetiştirilmesi (tavuk, hindi, ördek, kaz ve beç tavuğu vb.)", _KUMES),
    "01.47.03": ("Kümes hayvanlarından yumurta üretilmesi", _KUMES),
    "10.3": ("Sebze ve meyvelerin işlenmesi ve saklanması",
             "Sadece sarartma ve mumlama işlemi içeren meyve ve/veya sebze yatırımları desteklenmez."),
    "10.5": ("Süt ürünleri ve yenilebilir buz imalatı",
             "5 ton/gün altındaki kapasiteye sahip süt işleme yatırımları desteklenmez"),
    "10.61.01": ("Kahvaltılık tahıl ürünleri ile diğer taneli tahıl ürünlerinin imalatı (buğday, yulaf, mısır, çavdar "
                 "vb. ezmeleri ile mısır gevreği ve patlamış mısır dahil)", ""),
    "10.61.07": ("Ön pişirme yapılmış veya başka şekilde hazırlanmış tane halde hububat imalatı (bulgur dahil, mısır "
                 "hariç)", ""),
    "10.72": ("Peksimet, bisküvi, dayanıklı pastane ürünleri ve kek imalatı",
              "Kadayıf ve yufka üretimi konusundaki yatırımlar desteklenmez."),
    "15": ("Diğer malzemelerden deri ve ilgili ürünlerin imalatı",
           "Derinin tabaklanmasına yönelik yatırımlar sadece organize sanayi bölgelerinde teşvik edilir."),
    "16": ("Ağaç, ağaç ürünleri ve mantar ürünleri imalatı (mobilya hariç); saz, saman ve benzeri malzemelerden örülerek "
           "yapılan eşyaların imalatı 16.11.03 hariç", ""),
    "18": ("Kayıtlı medyanın basılması ve çoğaltılması",
           "Sabit yatırım tutarı 100 Milyon TL ve üzerindeki tevsi ve modernizasyon yatırımları desteklenir."),
    "22.2": ("Plastik ürünlerin imalatı", "Sabit yatırım tutarı 100 Milyon TL ve üzerindeki yatırımlar desteklenir."),
    "24.10.05": ("Sıcak haddelenmiş demir veya çelikten bar ve çubukların üretilmesi (inşaat demiri dahil)",
                 "Sadece parlatılmış çubuk üretimi desteklenir."),
    "24.10.08": ("Demir cevherinin doğrudan indirgenmesiyle elde edilen demirli ürünler ve diğer sünger demir ürünlerinin "
                 "imalatı ile elektroliz veya diğer kimyasal yöntemlerle istisnai saflıkta demir üretilmesi", ""),
    "24.10.12": ("Ferro alaşımların imalatı (ferro manganez, ferro silisyum, ferro siliko manganez, ferro krom ve "
                 "diğerleri)", "Yüksek karbonlu ferro manganez hariç."),
    "33.12.03": ("Motor ve türbinlerin onarım ve bakımı (hidrolik, rüzgar, gaz, su, buhar türbinleri) (gemi ve tekne "
                 "motorları, motorlu kara taşıtı ve motosiklet motorları hariç)", ""),
    "35.11": ("Yenilenemeyen kaynaklardan elektrik üretimi", ""),
    "35.12": ("Yenilenebilir kaynaklardan elektrik üretimi", ""),
    "35.14.06": ("Elektrik enerjisinin dağıtımı (üretim kaynağından veya iletim sisteminden son kullanıcıya iletim "
                 "sistemiyle taşınan elektrik enerjisi dağıtım sisteminin işletilmesi)", ""),
    "35.15.01": ("Elektrikli araçlar ve elektronik cihazlar için şarj istasyonlarının işletilmesi",
                 "Tebliğ ile belirlenecek şartları sağlayan yatırımlar desteklenir."),
    "35.22.01": ("Ana şebeke üzerinden gaz yakıtların dağıtımı (her çeşit gazlı yakıtın, ana boru sistemiyle dağıtımı ve "
                 "tedariki)", ""),
    "50.10.13": ("Kıyı sularında yolcuların feribotlarla, kruvaziyer gemilerle ve teknelerle taşınması (deniz otobüsleri "
                 "işletmeciliği dahil; uluslararası denizler ile göl ve nehirlerde yapılanlar hariç)",
                 "Gezinti amaçlı olanlar hariç"),
    "50.30.08": ("İç sularda yolcu taşımacılığı (nehir, kanal ve göllerde yapılanlar, vb.) (gezinti amaçlı olanlar dahil)",
                 "Gezinti amaçlı olanlar hariç"),
    "52.10.02": ("Frigorifik depolama ve antrepoculuk faaliyetleri (bozulabilir gıda ürünleri dahil dondurulmuş veya "
                 "soğutulmuş mallar için depolama)", "Sadece 1.000 m2 üzeri soğuk hava deposu yatırımları desteklenir."),
    "52.10.03": ("Hububat depolama ve antrepoculuk faaliyetleri (hububat silolarının işletilmesi vb.)",
                 "Sadece lisanslı depoculuk faaliyetleri desteklenir"),
    "52.22.06": ("Su yolu taşımacılığını destekleyici olarak liman ve su yollarının işletilmesi (limanların, iskelelerin, "
                 "rıhtımların, su yolu havuzlarının, deniz terminallerinin vb. işletilmesi) (deniz feneri, fener dubası "
                 "vb. işletilmesi hariç)", ""),
    "52.22.08": ("Deniz ve kıyı suları ile iç sularda kılavuzluk ve rıhtıma yanaştırma faaliyetleri (geminin "
                 "havuzlanması ve havuzdan çıkarılması dahil)", ""),
    "52.23.04": ("Havaalanı işletmeciliği (uçak pisti işletme, yolcu terminali ve havayolu şirketlerinin kendi bilet "
                 "satış hizmetleri dahil; havaalanı yer hizmetleri ve bilet acentelerinin faaliyetleri hariç)", ""),
    "55.1": ("Oteller ve benzeri konaklama yerleri",
             "50 oda ve üzeri (Otel, Tatil Köyü, Butik Otel ve Özel Konaklama Tesisi desteklenir)"),
    "55.90.01": ("Öğrenci ve işçi yurtları, pansiyonlar ve odası kiralanan evlerde yapılan konaklama faaliyetleri (tatil "
                 "amaçlı olanlar hariç)", "Sadece asgari 200 öğrenci kapasitesindeki Öğrenci yurtları desteklenir."),
    "82.2": ("Çağrı merkezlerinin faaliyetleri", "Sadece 6 ncı bölgede yapılan yatırımlar desteklenir."),
}


def _norm(metin: str) -> str:
    metin = re.sub(r"\s+", " ", metin.replace(" ", " ")).strip()
    return re.sub(r"(?<=\w)- (?=[a-zçğıöşü])", "-", metin)   # satır sonunda tireyle bölünen sözcük: "tasnif-\npaketleme"


def kaynak_metni() -> str:
    return _norm(KAYNAK.read_text(encoding="utf-8"))


def kaynakta_mi(parca: str, kaynak: str) -> bool:
    """Parça resmî metinde birebir geçiyor mu. Satır sonlarında sözcük bölünmesi ("tevsi\\nve") boşlukla normalleşir;
    iki sütunlu sayfada tanım ve şart arasına başka satır giren kalemlerde (01.47, 35.11) her cümle ayrı aranır."""
    if not parca:
        return True
    p = _norm(parca)
    if p in kaynak:
        return True
    return all(_norm(c) in kaynak for c in re.split(r"(?<=[.;])\s+(?=[a-eA-ZÇĞİÖŞÜ0-9])", p) if c.strip())


def degisiklikler(veri: dict) -> list[tuple[str, str, str, str, str]]:
    """(kod, eski tanım, eski şart, yeni tanım, yeni şart) — yalnız farklı olanlar."""
    out = []
    for k in veri["kayitlar"]:
        if k["kod"] in DUZELTME:
            t, s = DUZELTME[k["kod"]]
            if (k.get("tanim") or "") != t or (k.get("sartlar") or "") != s:
                out.append((k["kod"], k.get("tanim") or "", k.get("sartlar") or "", t, s))
    return out


def uygula(yaz: bool) -> int:
    veri = json.loads(VERI.read_text(encoding="utf-8"))
    d = degisiklikler(veri)
    for kod, et, es, yt, ys in d:
        print(f"{kod}\n  eski: {et} | {es}\n  yeni: {yt} | {ys}")
    print(f"{len(d)} kalem {'güncellendi' if yaz else 'güncellenecek (kuru çalıştırma; yazmak için --uygula)'}")
    if yaz and d:
        yeni = {kod: (yt, ys) for kod, _, _, yt, ys in d}
        for k in veri["kayitlar"]:
            if k["kod"] in yeni:
                k["tanim"], k["sartlar"] = yeni[k["kod"]]
        veri["not"] = (veri.get("not", "") + " Sütun kayması düzeltmesi 2026-10-12 "
                       "(scripts/fix_ek3_9903_2026_10_12.py; resmî metinle birebir doğrulandı).").strip()
        VERI.write_text(json.dumps(veri, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


def self_test() -> int:
    sonuc: list[tuple[str, bool]] = []
    kaynak = kaynak_metni()
    veri = json.loads(VERI.read_text(encoding="utf-8"))
    kodlar = {k["kod"] for k in veri["kayitlar"]}
    sonuc.append(("düzeltilen her kod EK-3 listesinde var", set(DUZELTME) <= kodlar))
    eksik = [f"{kod}:{alan}" for kod, (t, s) in DUZELTME.items()
             for alan, metin in (("tanım", t), ("şart", s)) if not kaynakta_mi(metin, kaynak)]
    sonuc.append((f"tüm tanım ve şartlar resmî metinde birebir geçiyor {eksik or ''}", not eksik))
    sonuc.append(("kaynak denetimi uydurma metni yakalar", not kaynakta_mi("Sadece 7. bölgede desteklenir.", kaynak)))
    sonuc.append(("otel şartı 50 oda", DUZELTME["55.1"][1].startswith("50 oda ve üzeri")))
    sonuc.append(("hariç alt kodlar tanımda kalır (şart sayılmaz)", "16.11.03 hariç" in DUZELTME["16"][0]
                  and DUZELTME["16"][1] == ""))
    sonuc.append(("elektrik üretimi şartı bölüm şartında, tekrar edilmez",
                  DUZELTME["35.11"][1] == "" and "Doğalgaza" in (veri.get("bolum_sartlari") or {}).get("D", "")))
    kopya = json.loads(json.dumps(veri))
    for k in kopya["kayitlar"]:
        if k["kod"] in DUZELTME:
            k["tanim"], k["sartlar"] = DUZELTME[k["kod"]]
    sonuc.append(("idempotent: uygulanmış veride değişiklik kalmaz", degisiklikler(kopya) == []))
    for ad, ok in sonuc:
        print(("GEÇTİ " if ok else "KALDI ") + ad)
    gecen = sum(ok for _, ok in sonuc)
    print(f"self-test: {gecen}/{len(sonuc)} geçti")
    return 0 if gecen == len(sonuc) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(uygula("--uygula" in sys.argv))
