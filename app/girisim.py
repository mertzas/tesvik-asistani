"""Girişim (startup) modu: HUKS ön skoru ve danışman için girişim-özel bağlam (saf fonksiyonlar).

HUKS = "Hibe Uygunluk & Kazanım Skoru", 4 bileşen x 25 puan. Skor burada, KODDA ve profil
verisinden hesaplanır; LLM'e hesaplatılmaz (aksi hâlde model eksik veriyi tahminle doldurur).
Verisi olmayan bileşen puanlanmaz ve "değerlendirilemedi" olarak raporlanır; toplam, yalnızca
değerlendirilebilen bileşenler üzerinden verilir (ör. 52/75).

Bileşen kuralları sezgiseldir ve ÖN skor niteliğindedir; hukuki uygunluk, program bazında
başvuru şartlarından (veritabanı kayıtları) ve resmî uygulama esaslarından teyit edilmelidir.
Ekip & Ar-Ge niteliği bileşeni profilde karşılığı olmadığı için hiçbir zaman puanlanmaz;
danışman yalnızca kullanıcının yazdıklarından nitel yorum yapar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.urun_sektor_anahtarlari import kucult

SIRKET_TURLERI: dict[str, str] = {
    "yok": "henüz şirket kurulmadı",
    "sahis": "şahıs işletmesi",
    "limited": "limited şirket",
    "anonim": "anonim şirket",
    "kooperatif": "kooperatif",
}
SERMAYE_SIRKETLERI = {"limited", "anonim"}
AGIRLIK = 25

# Veritabanında olmayan, spec'te adı geçen programlar: danışman bunları uydurmak yerine
# "sistemde kayıt yok, resmî kaynaktan bakın" demeli.
VERITABANINDA_OLMAYAN_PROGRAMLAR = (
    "KOSGEB Yurt Dışı Pazar Destek Programı",
    "TTGV programları",
    "Kalkınma Ajansı proje teklif çağrıları",
)
# Doğrulanmış mevzuat notu: danışman "5448 bilişim destekleri" diye sorulursa güncel
# Karar'a yönlendirsin (kaynak: 10962 sayılı Karar MADDE 49-50, R.G. 27/2/2026).
MEVZUAT_NOTU = ("Ticaret Bakanlığı bilişim/SaaS hizmet ihracatı destekleri 1/1/2026'dan itibaren 10962 sayılı "
                "Karar kapsamındadır; 5447 (E-Turquality) ve 5448 sayılı Kararlar yürürlükten kaldırılmıştır. "
                "KOSGEB Ar-Ge/Ür-Ge/İnovasyon ve KOBİGEL programları yürürlükten kaldırılmıştır (kayıtları "
                "'kapalı' olarak sistemde).")

_ASCII = str.maketrans("çğıöşü", "cgiosu")
_GIRISIM_SORU = re.compile(
    r"\b(girisim\w*|startup|start-up|bigg|1812|1512|prototip\w*|mvp\b|fikir asamas\w*|"
    r"sirketles\w*|tohum\w*|kulucka\w*|teknogirisim\w*|trl\b)")


def _katla(m: str | None) -> str:
    return kucult(m or "").translate(_ASCII)


@dataclass(frozen=True)
class Bilesen:
    ad: str
    puan: int | None            # None = değerlendirilemedi
    gerekce: str

    @property
    def degerlendirildi(self) -> bool:
        return self.puan is not None


@dataclass
class HUKS:
    bilesenler: list[Bilesen] = field(default_factory=list)

    @property
    def puan(self) -> int:
        return sum(b.puan for b in self.bilesenler if b.puan is not None)

    @property
    def azami(self) -> int:
        return AGIRLIK * sum(1 for b in self.bilesenler if b.degerlendirildi)

    @property
    def normalize(self) -> int | None:
        return round(100 * self.puan / self.azami) if self.azami else None

    @property
    def eksikler(self) -> list[str]:
        return [b.ad for b in self.bilesenler if not b.degerlendirildi]

    def metin(self) -> str:
        satirlar = [f"HUKS ÖN SKORU (sistem hesapladı, profil verisinden): {self.puan}/{self.azami} "
                    f"değerlendirilebilen puan"
                    + (f" (100'e oranla {self.normalize})" if self.normalize is not None else "")
                    + (f"; değerlendirilemeyen bileşenler: {', '.join(self.eksikler)}" if self.eksikler else "")]
        for b in self.bilesenler:
            durum = f"{b.puan}/{AGIRLIK}" if b.degerlendirildi else "değerlendirilemedi"
            satirlar.append(f"- {b.ad}: {durum} — {b.gerekce}")
        return "\n".join(satirlar)


def _yas_yil(kurulus: date | None, bugun: date | None = None) -> float | None:
    if kurulus is None:
        return None
    bugun = bugun or date.today()
    return max(0.0, (bugun - kurulus).days / 365.25)


def _nace_statu(profil: Any, bugun: date | None) -> Bilesen:
    ad = "NACE kodu & şirket statüsü"
    tur = getattr(profil, "sirket_turu", None)
    nace = getattr(profil, "nace_kodu", None)
    if tur is None:
        return Bilesen(ad, None, "şirket türü profilde yok (henüz kurulmadı / şahıs / Ltd. / A.Ş.)")
    yas = _yas_yil(getattr(profil, "kurulus_tarihi", None), bugun)
    notlar = []
    if tur == "yok":
        puan, temel = 10, ("şirketleşmemiş: şirketleşme öncesi programlar (ör. TÜBİTAK 1812 BiGG) hedeflenebilir; "
                           "sermaye şirketi şartı arayan sanayi Ar-Ge programları (ör. 1507, 1501) şu an kapalı")
    elif tur in SERMAYE_SIRKETLERI:
        puan, temel = 25, f"{SIRKET_TURLERI[tur]}: sermaye şirketi şartı arayan programlara açık"
    elif tur == "sahis":
        puan, temel = 15, ("şahıs işletmesi: KOSGEB programlarına açık; sermaye şirketi şartı arayan TÜBİTAK "
                           "sanayi programları için şirket dönüşümü gerekir")
    else:
        puan, temel = 15, f"{SIRKET_TURLERI.get(tur, tur)}: program bazında statü şartı teyit edilmeli"
    if not nace and tur != "yok":
        puan -= 5
        notlar.append("NACE kodu girilmemiş; sektör eşleşmesi belirsiz")
    if yas is not None:
        notlar.append(f"şirket yaşı ~{yas:.1f} yıl" + (" (0-3 yaş pencereli girişimci programları için uygun aralık)"
                                                      if yas <= 3 else " (0-3 yaş şartlı girişimci destekleri kapalı olabilir)"))
    return Bilesen(ad, max(0, puan), temel + ("; " + "; ".join(notlar) if notlar else ""))


def _trl(profil: Any) -> Bilesen:
    ad = "Teknoloji hazırlık seviyesi (TRL)"
    trl = getattr(profil, "trl", None)
    if trl is None:
        return Bilesen(ad, None, "TRL profilde yok (1-3 fikir/araştırma, 4-6 prototip/doğrulama, 7-9 ticarileşme)")
    if trl <= 3:
        return Bilesen(ad, 12, f"TRL {trl}: fikir/araştırma aşaması; şirketleşme öncesi ve erken aşama çağrıları "
                               "hedeflenir, sanayi Ar-Ge programlarında prototip hedefi tanımlanmalı")
    if trl <= 6:
        return Bilesen(ad, 25, f"TRL {trl}: prototip/doğrulama aşaması; Ar-Ge hibe programlarının çekirdek aralığı")
    return Bilesen(ad, 15, f"TRL {trl}: ticarileşme aşaması; Ar-Ge hibesi yerine yatırım, ihracat ve pazarlama "
                           "destekleri daha uygun olabilir")


def _finans(profil: Any) -> Bilesen:
    ad = "Finansal & nakit akışı uyumu"
    ciro = getattr(profil, "yillik_ciro", None)
    tur = getattr(profil, "sirket_turu", None)
    if ciro is None and tur != "yok":
        return Bilesen(ad, None, "yıllık ciro profilde yok; hibeler harcama sonrası ödendiği için ön finansman gücü ölçülemedi")
    if tur == "yok" or not ciro:
        return Bilesen(ad, 5, "gelir yok: hibe harcama yapılıp belgelendikten sonra ödenir, ön finansman öz kaynaktan "
                              "karşılanmalı; şirketleşme öncesi hibeler (ör. BiGG) nakit avantajlıdır")
    giderler = getattr(profil, "giderler", None) or {}
    toplam = giderler.get("toplam") if isinstance(giderler, dict) else None
    puan, notlar = 15, [f"yıllık ciro {ciro:,.0f} TL".replace(",", ".")]
    if isinstance(toplam, (int, float)) and toplam > 0:
        if ciro - toplam > 0:
            puan, ek = 25, "gider toplamı ciro altında, ön finansman kapasitesi var"
        else:
            puan, ek = 10, "giderler ciroyu aşıyor; harcama-sonrası ödeme modeli nakit riski taşır"
        notlar.append(ek)
    if getattr(profil, "ilk_yil_mi", None):
        puan = max(5, puan - 5)
        notlar.append("ilk yıl/kuruluş giderleri nakit akışını zorlar")
    return Bilesen(ad, puan, "; ".join(notlar))


def _ekip() -> Bilesen:
    return Bilesen("Ekip & Ar-Ge niteliği", None,
                   "ekip ve proje niteliği verisi sistemde yok; danışman yalnızca sorudaki bilgiden nitel yorum "
                   "yapar, puan vermez")


def huks(profil: Any, bugun: date | None = None) -> HUKS:
    return HUKS([_nace_statu(profil, bugun), _trl(profil), _finans(profil), _ekip()])


# Girişim modu eşikleri: TRL 7+ ürün pazara çıkmış/ticarileşmiş demektir (TRL 8-9 pazarda ürün);
# 3 yaşını geçmiş bir sermaye şirketi erken aşama sayılmaz (BiGG/tohum programlarının da hedefi değil).
GIRISIM_TRL_UST = 6
GIRISIM_YAS_UST_YIL = 3.0


def girisim_modu_mu(profil: Any, soru: str, bugun: date | None = None) -> bool:
    """Girişim modu: şirketleşmemiş profil, erken TRL (≤6), 3 yaşından genç şirket veya girişim
    dilinde soru. Ölçüm 2026-10-07: `trl is not None` kuralı TRL 8, 12 çalışan, 20 M TL cirolu
    SaaS firmasını da girişim moduna (HUKS + 4 bölüm) sokuyordu."""
    if profil is not None:
        if getattr(profil, "sirket_turu", None) == "yok":
            return True
        trl = getattr(profil, "trl", None)
        if trl is not None and trl <= GIRISIM_TRL_UST:
            return True
        yas = _yas_yil(getattr(profil, "kurulus_tarihi", None), bugun)
        if yas is not None and yas <= GIRISIM_YAS_UST_YIL:
            return True
    return bool(_GIRISIM_SORU.search(_katla(soru)))


def girisim_baglam_metni(profil: Any, bugun: date | None = None) -> str:
    skor = huks(profil, bugun) if profil is not None else None
    parcalar = ["GİRİŞİM MODU BİLGİLERİ"]
    if skor is not None:
        parcalar.append(skor.metin())
    parcalar.append("SİSTEMDE KAYDI OLMAYAN PROGRAMLAR (bunlar için oran/limit/şart VERME; resmî kaynaktan "
                    "teyit istemekle yetin): " + "; ".join(VERITABANINDA_OLMAYAN_PROGRAMLAR))
    parcalar.append("MEVZUAT NOTU (doğrulanmış): " + MEVZUAT_NOTU)
    return "\n".join(parcalar)


GIRISIM_PROMPT_EKI = """

GİRİŞİM MODU (bağlamda "GİRİŞİM MODU BİLGİLERİ" bloğu varsa bu bölüm geçerlidir): Kullanıcı \\
bir girişim/erken aşama projesi için soruyor. Yukarıdaki 5 başlık yerine aşağıdaki 4 BÖLÜM \\
şablonunu kullan; tüm genel kurallar (UYDURMA YASAK, AKTİFLİK, SİSTEM ÖN DEĞERLENDİRMESİ, NET \\
ELEME, ÇİFT YÖNLÜ ANALİZ) aynen geçerlidir.

#### BÖLÜM 1: Girişim Uygunluk & Risk Özeti
- Mevcut durum: şirketleşme, NACE, TRL, sektör (profilden; yoksa "bilinmiyor").
- Kazanım skoru: bağlamdaki HUKS ÖN SKORUNU aynen aktar (puan/azami ve değerlendirilemeyen \\
bileşenler); kendin skor hesaplama veya değerlendirilemeyen bileşene puan verme. Skoru düşüren \\
ve yükselten faktörleri bileşen gerekçelerinden yaz. Ekip bileşeni için yalnızca kullanıcının \\
yazdıklarına dayanan nitel yorum yap.
- Kritik diskalifiye riskleri: bağlamdaki başvuru şartlarından (ör. sermaye şirketi, daha önce \\
destek almış olma, ortaklık yasağı) ve genel ilkelerden (vergi/SGK borcu, başvuru öncesi \\
harcama, mükerrer başvuru); genel ilkeyi genel ilke olarak etiketle.

#### BÖLÜM 2: Eşleşen Teşvik Matrisi
Bağlamdaki programları şu tabloyla ver: | Destek Programı | Kurum | Destek Türü (Hibe/Kredi/\\
Kefalet) | Üst Limit | Destek Oranı | Kritik Şart |. Bir hücre bağlamda yoksa "bağlamda yok" \\
yaz; ASLA tahmini rakam yazma. "SİSTEMDE KAYDI OLMAYAN PROGRAMLAR" listesindekileri tabloya \\
koyma; kullanıcı sorduysa adıyla anıp resmî kaynağa yönlendir.

#### BÖLÜM 3: Detaylı Finansal & Bütçe Analizi
- Personel, hizmet/makine/bulut, reklam kalemleri: yalnızca bağlamda geçen tavan, oran ve \\
kalem bilgileriyle; brüt asgari ücret çarpanı, yerli malı şartı, bulut limiti gibi değerler \\
bağlamda yoksa "uygulama esaslarından teyit edin" de.
- Nakit akışı uyarısı: hibelerin harcama+belge sonrası ödendiğini ve ön finansman gerektiğini \\
anlat; ödeme süresini (ay) ancak bağlamda geçiyorsa yaz, yoksa tahmin etme. Profildeki ciro/\\
gider verisinden kaba bir ön finansman değerlendirmesi yapabilirsin, varsayımlarını belirt.

#### BÖLÜM 4: Adım Adım Başvuru Yol Haritası
1. Şimdi: sisteme kayıt (bağlamdaki başvuru yeri/sistem adları), evrak, şirketleşme kararı.
2. Kritik tarihler: bağlamdaki çağrı dönemi/son başvuru bilgisi; yoksa "çağrı takvimini \\
kurumun sayfasından teyit edin".
3. Mükerrerlikten kaçınma: aynı harcama/fatura iki kuruma sunulamaz (genel ilke); hangi \\
harcamanın hangi programa gideceğini yalnızca bağlamdaki desteklenen kalemlere göre planla.

Asla "garanti onay" vaadi verme; hakem/komite değerlendirmesinin öznel elenme riskini açıkça \\
yaz. Şirket türü, kuruluş tarihi, TRL, faturalanmış harcama geçmişi gibi kritik parametreler \\
eksikse varsayma, BÖLÜM 1'de doğrudan sor."""
