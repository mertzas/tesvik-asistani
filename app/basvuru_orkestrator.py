"""Deterministik e-ihracat başvuru doğrulama orkestratörü (10 adım, dış dil modeli yok).

Girdi: şirket profili + harcama dökümü (JSON). Çıktı üç bölüm: (1) adım adım denetim ve düzeltme raporu, (2) DYS'ye
yapıştırılacak resmî gerekçe metni, (3) otomasyona basılacak katı JSON. Her oran, tavan, şart ve hedef ülke listesi
veritabanındaki doğrulanmış kayıtlardan (5986 ve 5973 sayılı Karar kayıtları, 2026 üst limitleri) okunur; kayıtta
karşılığı olmayan kalem "Kapsam Dışı / İncelenmeli" işaretlenir, tahmin yapılmaz.

Mevzuat notu (girdi şablonundaki varsayımların düzeltmesi): e-ihracat kalemleri (dijital pazaryeri reklamı, sipariş
karşılama, pazaryeri komisyonu, çevrim içi mağaza, perakende site tanıtımı, E-İhracat Konsorsiyumu) 5986 sayılı
Karar kapsamındadır; 5973 sayılı Karar yurt dışı marka tescili (m.4), pazar araştırması (m.6), birim kira (m.11) ve
genel tanıtım (m.12) desteklerini kapsar. Hedef ülke ilavesi kayıtlarda yalnız 5986 m.4, m.5 ve m.6 için "%70"
olarak (20 puan) yazılıdır; başka kaleme ilave uygulanmaz.

Adımlar (fonksiyonlar): 1 ayristir · 2 mevzuat_esle · 3 kobi_ve_kosgeb · 4 hedef_ulke · 5 mukerrerlik_denetimi ·
6 dys_eksikleri · 7 senaryo_stres_testi · 8 onarim_rotalari · 9 gerekce_metni · 10 json_cikti.

Kullanım:
    python -m app.basvuru_orkestrator --self-test
    python -m app.basvuru_orkestrator --demo                 (A-D senaryoları, sentetik girdi)
    python -m app.basvuru_orkestrator --girdi girdi.json     (gerçek girdi; çıktı stdout)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date

MEVZUAT_DAYANAGI = ("5986 sayılı Cumhurbaşkanı Kararı (e-ihracat destekleri) ve 5973 sayılı Cumhurbaşkanı Kararı "
                    "(marka tescili, pazar araştırması, birim kira, tanıtım)")
ODEME_SURESI_GUN = 183   # "ödeme belgesi tarihinden itibaren en geç 6 ay" (kayıt 193 başvuru süresi; 5973 m.16 adımı)

# kalem türü → (kayıt başlığında aranan madde, kısa ad)
KALEM_PROGRAM = {
    "pazaryeri_reklam": (r"5986 sayılı Karar m\.4\)", "Dijital Pazaryeri Tanıtım (Reklam) Desteği"),
    "site_tanitim": (r"5986 sayılı Karar m\.5\)", "E-İhracat Tanıtım Desteği (Perakende E-Ticaret Sitesi statüsü)"),
    "siparis_karsilama": (r"5986 sayılı Karar m\.6\)", "Sipariş Karşılama (Fulfillment) Hizmeti Desteği"),
    "cevrimici_magaza": (r"5986 sayılı Karar m\.8\)", "Çevrim İçi Mağaza ve Hedef Ülke E-Ticaret Paydaşı Desteği"),
    "pazaryeri_komisyon": (r"5986 sayılı Karar m\.9\)", "Yurt Dışı Pazaryeri Komisyon Gideri Desteği"),
    "marka_tescil": (r"5973 sayılı Karar m\.4\)", "Yurt Dışı Marka Tescil Desteği"),
    "pazar_arastirma": (r"5973 sayılı Karar m\.6\)", "Yurt Dışı Pazar Araştırması Desteği"),
    "yurt_disi_depo": (r"5973 sayılı Karar m\.11\)", "Yurt Dışı Birim Kira Desteği"),
    "tanitim_genel": (r"5973 sayılı Karar m\.12\)", "Yurt Dışı Tanıtım ve Pazarlama Desteği"),
}
# Statüsüz şirketin yararlanabildiği 5986 kalemleri (kayıt 162: "Statüsüz şirketin yararlanabildiği kalemler: dijital
# pazaryeri reklamı, sipariş karşılama, pazaryeri komisyonu, (önceki yıl 1 milyon USD üzeri ihracatla) çevrim içi mağaza")
STATUSUZ_KALEMLER = {"pazaryeri_reklam", "siparis_karsilama", "pazaryeri_komisyon", "cevrimici_magaza"}
STATU_SARTLI = {"site_tanitim"}            # kayıt 196: "Destek yalnız statü sahiplerine açıktır"
MADRID_SARTLI = {"pazaryeri_reklam", "siparis_karsilama", "pazaryeri_komisyon"}   # kayıt 192-194 şart maddesi
ON_ONAY_SARTLI = {"pazaryeri_reklam", "siparis_karsilama", "pazaryeri_komisyon", "cevrimici_magaza", "site_tanitim"}

# Açıklamadan kalem türü (girdide "kalem" verilmemişse); eşleşmeyen kalem Kapsam Dışı / İncelenmeli olur.
_KALEM_KALIBI = (
    ("pazaryeri_komisyon", r"komisyon|referral fee|selling fee|transaction fee"),
    ("siparis_karsilama", r"fulfil|fba\b|sipari[sş] kar[sş]ılama|depolama hizmet|pick.?pack"),
    ("yurt_disi_depo", r"depo kira|warehouse rent|ofis kira|ma[gğ]aza kira"),
    ("marka_tescil", r"marka tescil|wipo|euipo|uspto|trademark"),
    ("pazar_arastirma", r"pazar ara[sş]t[ıi]rma"),
    ("pazaryeri_reklam", r"(amazon|etsy|ebay|walmart|trendyol|zalando|noon|allegro)\b.*(reklam|ads|sponsored)|"
                         r"(reklam|ads|sponsored).*(amazon|etsy|ebay|walmart|zalando|noon|allegro)"),
    ("site_tanitim", r"google ads|meta ads|facebook|instagram|tiktok|influencer|seo|site reklam"),
    ("cevrimici_magaza", r"mağaza açılış|store setup|çevrim ?içi mağaza|online store fee"),
)


@dataclass
class Program:
    kalem: str
    tesvik_id: int | None
    baslik: str
    oran: int                       # %
    hedef_oran: int | None          # hedef ülkede % (kayıtta açıkça yazılıysa)
    tavan_try: float | None         # 2026 yıllık üst limit (kayıttan)
    tavan_metni: str
    sartlar: list[str] = field(default_factory=list)


@dataclass
class Harcama:
    no: int
    aciklama: str
    kalem: str | None
    tutar: float
    para_birimi: str
    kdv_dahil: bool
    kdv_orani: float
    kur: float | None
    tarih: date | None
    ulke: str | None
    pazaryeri: str | None
    odeme: str                      # "sirket_banka" | "sirket_kart" | "sahis" | "nakit" | bilinmiyor
    tedarikci_iliskili: bool
    baska_destek: str | None
    tutar_try_kdv_haric: float | None = None
    durum: str = "UYGUN"
    notlar: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ ortak yardımcılar
def _tl(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _deger(metin: str) -> float:
    return float(metin.replace(".", "").replace(",", "."))


def _anonim(unvan: str | None) -> str:
    """KVKK: unvan yerine kararlı, geri çevrilemez kısa kimlik."""
    return "Şirket-" + hashlib.sha256((unvan or "anonim").encode("utf-8")).hexdigest()[:6].upper()


def _katla(s: str | None) -> str:
    tablo = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return (s or "").translate(tablo).lower()


def program_kaydindan(kalem: str, t) -> Program:
    """Kayıttan oran, hedef ülke oranı ve 2026 tavanı (yalnız metinde açıkça yazanlar)."""
    tutar = t.tesvil_tutari or ""
    oran = re.search(r"%\s*(\d+)", tutar)
    hedef = re.search(r"hedef ülkelerde %\s*(\d+)", tutar)
    tavan = re.search(r"2026[^;]*?(\d{1,3}(?:\.\d{3})+)\s*TL", tutar)
    sartlar = [m.get("metin", "") for m in t.kontrol_listesi or [] if m.get("tur") == "sart"]
    return Program(kalem, t.id, t.baslik, int(oran.group(1)) if oran else 0,
                   int(hedef.group(1)) if hedef else None,
                   _deger(tavan.group(1)) if tavan else None, tutar, sartlar)


def programlari_yukle(db) -> tuple[dict[str, Program], list[str], str]:
    """(kalem → Program, hedef ülke listesi, statüsüz kalem cümlesi) — veritabanından."""
    from app.models import Tesvik
    kayitlar = [t for t in db.query(Tesvik).all() if t.aktif_mi is not False]
    programlar = {}
    for kalem, (kalip, _) in KALEM_PROGRAM.items():
        t = next((x for x in kayitlar if re.search(kalip, x.baslik or "")), None)
        if t is not None:
            programlar[kalem] = program_kaydindan(kalem, t)
    hedef_listesi: list[str] = []
    for t in kayitlar:
        m = re.search(r"Hedef ülkeler \([^)]*\): ([^.]+)\.", t.detay or "")
        if m:
            hedef_listesi = [x.strip() for x in m.group(1).split(",") if x.strip()]
            break
    statusuz = ""
    for t in kayitlar:
        m = re.search(r"Statüsüz şirketin yararlanabildiği kalemler: [^.|]+", t.detay or "")
        if m:
            statusuz = m.group(0)
            break
    return programlar, hedef_listesi, statusuz


# ------------------------------------------------------------------ 1. Ayrıştırma ve temizleme
def ayristir(girdi: dict) -> tuple[dict, list[Harcama], list[str]]:
    rapor = []
    profil = dict(girdi.get("sirket") or {})
    profil["anonim_kimlik"] = _anonim(profil.pop("unvan", None))
    vkn = str(profil.pop("vergi_no", "") or "")
    if vkn and not re.fullmatch(r"\d{10}", vkn):
        rapor.append(f"Vergi numarası 10 haneli değil ({len(vkn)} hane): DYS kaydı reddedilir; düzeltin.")
    harcamalar = []
    for i, h in enumerate(girdi.get("harcamalar") or [], 1):
        tarih = date.fromisoformat(h["tarih"]) if h.get("tarih") else None
        x = Harcama(i, h.get("aciklama", ""), h.get("kalem"), float(h.get("tutar", 0)),
                    (h.get("para_birimi") or "TRY").upper(), bool(h.get("kdv_dahil", False)),
                    float(h.get("kdv_orani", 0.20)), h.get("kur"), tarih, h.get("ulke"), h.get("pazaryeri"),
                    h.get("odeme", "bilinmiyor"), bool(h.get("tedarikci_iliskili", False)), h.get("baska_destek"))
        if not x.kalem:
            x.kalem = next((k for k, kalip in _KALEM_KALIBI if re.search(kalip, x.aciklama, re.I)), None)
            if x.kalem:
                x.notlar.append(f"Kalem açıklamadan çıkarıldı: {x.kalem}.")
        if x.para_birimi != "TRY":
            if not x.kur:
                x.durum = "SARTLI"
                x.notlar.append(f"{x.para_birimi} tutar için ödeme tarihindeki TCMB döviz satış kuru girilmedi; TL "
                                "karşılığı hesaplanamadı.")
                x.tutar_try_kdv_haric = 0.0
                harcamalar.append(x)
                continue
            tutar_try = x.tutar * float(x.kur)
        else:
            tutar_try = x.tutar
        if x.kdv_dahil:
            tutar_try = tutar_try / (1 + x.kdv_orani)
            x.notlar.append(f"KDV (%{int(x.kdv_orani * 100)}) ayrıştırıldı; destek KDV hariç tutar üzerinden "
                            "hesaplandı (KDV esası kayıtta yazılı değil: İncelenmeli).")
        x.tutar_try_kdv_haric = round(tutar_try, 2)
        harcamalar.append(x)
    rapor.append(f"{len(harcamalar)} harcama ayrıştırıldı; toplam KDV hariç "
                 f"{_tl(sum(h.tutar_try_kdv_haric or 0 for h in harcamalar))} TL.")
    return profil, harcamalar, rapor


# ------------------------------------------------------------------ 2. Mevzuat eşleştirme
def mevzuat_esle(profil: dict, harcamalar: list[Harcama], programlar: dict[str, Program], statusuz: str,
                 bugun: date) -> list[str]:
    rapor = []
    sahis = profil.get("sirket_turu") == "sahis"
    konsorsiyum = bool(profil.get("konsorsiyum_uyesi"))
    statu = profil.get("statu")            # None | "perakende_site" | "pazaryeri" | "konsorsiyum"
    for h in harcamalar:
        if h.durum == "SARTLI" and h.tutar_try_kdv_haric == 0:
            continue
        p = programlar.get(h.kalem or "")
        if p is None:
            h.durum = "RET"
            h.notlar.append("Kapsam Dışı / İncelenmeli: bu gider kayıtlı e-ihracat ya da 5973 kalemleriyle eşleşmedi "
                            "(ör. kargo/navlun için kayıtlı bir destek kalemi yok).")
            continue
        if sahis and not konsorsiyum:
            h.durum = "RET"
            h.notlar.append("Şahıs işletmesi doğrudan yararlanamaz (kayıt şartı: \"Şirket ya da kooperatif olmak "
                            "(şahıs işletmesi yalnız E-İhracat Konsorsiyumu aracılığıyla, sınırlı süre)\").")
            continue
        if h.kalem in STATU_SARTLI and not statu:
            h.durum = "RET"
            h.notlar.append("Kendi sitenin yurt dışı tanıtımı statü ister (kayıt: \"Destek yalnız statü sahiplerine "
                            "açıktır\"). " + (statusuz + "." if statusuz else ""))
            continue
        if h.kalem == "cevrimici_magaza" and not statu and not profil.get("onceki_yil_ihracat_usd_1m_ustu"):
            h.durum = "SARTLI"
            h.notlar.append("Statüsüz şirkette çevrim içi mağaza kalemi önceki yıl 1 milyon USD üzeri ihracat ister "
                            "(kayıt 162); profilde teyit yok.")
        if h.kalem == "yurt_disi_depo" and not statu and re.search(r"depo|warehouse", h.aciklama, re.I):
            h.durum = "RET"
            h.notlar.append("E-ticaret deposu kirası 5986 statüsü (perakende site, pazaryeri ya da konsorsiyum) ister "
                            "(kayıt 190, 5973 m.11/5-A).")
            continue
        if h.kalem in MADRID_SARTLI and not profil.get("madrid_tescilli_marka"):
            h.durum = "SARTLI"
            h.notlar.append("Ön onay için WIPO Madrid Sistemi'ne taraf en az bir ülkede tescilli yurt dışı marka "
                            "gerekir; yoksa önce 5973 m.4 Yurt Dışı Marka Tescil Desteği.")
        if h.kalem in ON_ONAY_SARTLI:
            on_onay = profil.get("on_onay_tarihi", {}).get(h.kalem) if isinstance(profil.get("on_onay_tarihi"),
                                                                                     dict) else None
            if not on_onay:
                h.durum = "SARTLI" if h.durum != "RET" else h.durum
                h.notlar.append("Bu kalem için ön onay tarihi girilmedi; destek ön onaydan sonra başlar.")
            else:
                baslangic = date.fromisoformat(on_onay)
                baslangic = date(baslangic.year + (baslangic.month == 12), baslangic.month % 12 + 1, 1)
                if h.tarih and h.tarih < baslangic:
                    h.durum = "RET"
                    h.notlar.append(f"Harcama ({h.tarih:%d.%m.%Y}) destek başlangıcından ({baslangic:%d.%m.%Y}; ön "
                                    "onay tarihini izleyen ayın ilk günü) önce.")
                    continue
        if h.tarih and (bugun - h.tarih).days > ODEME_SURESI_GUN:
            h.durum = "RET"
            h.notlar.append(f"Ödeme belgesi tarihinden itibaren 6 aylık başvuru süresi geçmiş ({h.tarih:%d.%m.%Y}).")
    rapor.append("Kalem eşleştirmesi: " + "; ".join(
        f"#{h.no} {KALEM_PROGRAM.get(h.kalem or '', ('', 'Kapsam dışı'))[1]} → {h.durum}" for h in harcamalar) + ".")
    if konsorsiyum:
        rapor.append("Konsorsiyum üyesi: konsorsiyumun satış yaptığı ülkelerdeki pazaryerlerinde reklam, sipariş "
                     "karşılama ve komisyon desteği için ayrıca başvurulamaz (kayıt 192-194 dışlama şartı).")
    return rapor


# ------------------------------------------------------------------ 3. KOBİ ve KOSGEB
def kobi_ve_kosgeb(profil: dict, db=None) -> tuple[str, list[str]]:
    from app.kobi import AD, kobi_sinifi
    olcek = kobi_sinifi(profil.get("calisan_sayisi"), profil.get("yillik_ciro"))
    ad = AD.get(olcek.sinif, "belirlenemedi") if olcek.sinif else "belirlenemedi"
    rapor = [f"KOBİ ölçeği: {ad}" + ("" if olcek.kesin else " (bilanço/ciro eksik; kesin değil)") + "."]
    if db is not None:
        from app.models import Tesvik
        yurt_disi = [t for t in db.query(Tesvik).all() if t.kurum == "KOSGEB" and t.aktif_mi is not False
                     and re.search(r"yurt ?dışı|pazar", t.baslik or "", re.I)]
        rapor.append("KOSGEB'in güncel kayıtlarında yurt dışı pazar/e-ihracat desteği " + (
            "var: " + ", ".join(t.baslik for t in yurt_disi) if yurt_disi else
            "yok; şablondaki 'KOSGEB Yurt Dışı Pazar Destek Programı' kayıtlı güncel programlar arasında değil") + ".")
    return ad, rapor


# ------------------------------------------------------------------ 4. Hedef ülke
def hedef_ulke(harcamalar: list[Harcama], programlar: dict[str, Program], hedef_listesi: list[str]) -> list[str]:
    katli = {_katla(x) for x in hedef_listesi}
    rapor = []
    for h in harcamalar:
        p = programlar.get(h.kalem or "")
        if p is None or not h.ulke:
            continue
        listede = _katla(h.ulke) in katli
        if listede and p.hedef_oran:
            rapor.append(f"#{h.no} {h.ulke} hedef ülke listesinde; {p.baslik.split(' (')[0]} oranı %{p.oran} → "
                         f"%{p.hedef_oran} (+{p.hedef_oran - p.oran} puan, kayıttan).")
        elif listede:
            rapor.append(f"#{h.no} {h.ulke} hedef ülke listesinde, ama bu kalem için kayıtta hedef ülke oranı "
                         "yazılı değil; ilave uygulanmadı.")
    if not rapor:
        rapor.append("Hedef ülke ilavesi uygulanan harcama yok.")
    return rapor


# ------------------------------------------------------------------ 5. Mükerrerlik ve usulsüzlük
def mukerrerlik_denetimi(harcamalar: list[Harcama]) -> list[str]:
    rapor = []
    gorulen: dict[tuple, int] = {}
    for h in harcamalar:
        anahtar = (round(h.tutar, 2), h.para_birimi, h.tarih, _katla(h.aciklama)[:40])
        if anahtar in gorulen:
            h.durum = "RET"
            h.notlar.append(f"Mükerrer kayıt: #{gorulen[anahtar]} ile aynı tutar, tarih ve açıklama.")
        gorulen.setdefault(anahtar, h.no)
        if h.baska_destek:
            h.durum = "RET"
            h.notlar.append(f"Aynı gider {h.baska_destek} kapsamında desteklenmiş/başvurulmuş: kayıt şartı \"Aynı gider "
                            "için bu Karar dışında başka bir mevzuat/program kapsamında destek almamış olmalısınız\".")
        if h.odeme in ("sahis", "nakit"):
            h.durum = "SARTLI" if h.durum == "UYGUN" else h.durum
            h.notlar.append("Ödeme şirket banka hesabı ya da şirket kartından değil: kayıtta istenen ödeme belgesi "
                            "banka dekontu, kredi kartı ekstresi ya da hesap dökümüdür (İncelenmeli).")
        if h.tedarikci_iliskili:
            h.durum = "SARTLI" if h.durum == "UYGUN" else h.durum
            h.notlar.append("İlişkili taraftan alım: kayıtlarda bu konuda hüküm yok; incelemeci kuruluştan teyit edin "
                            "(İncelenmeli).")
    rapor.append(f"Mükerrerlik/usulsüzlük: {sum(1 for h in harcamalar if h.durum == 'RET')} ret, "
                 f"{sum(1 for h in harcamalar if h.durum == 'SARTLI')} şartlı harcama.")
    return rapor


# ------------------------------------------------------------------ 6. DYS prosedürü
def dys_eksikleri(profil: dict, programlar: dict[str, Program], kullanilan: set[str], db=None) -> list[str]:
    from app.hazirlik import ADIMLAR, program_adimlari
    gerekli: list[str] = []
    if db is not None:
        from app.models import Tesvik
        for kalem in kullanilan:
            p = programlar.get(kalem)
            t = db.get(Tesvik, p.tesvik_id) if p and p.tesvik_id else None
            if t is not None:
                gerekli += [k for k in program_adimlari(t) if k not in gerekli]
    profil_var = set(profil.get("hazirlik") or [])
    for bayrak, kod in (("madrid_tescilli_marka", "madrid_marka"), ("on_onay_tarihi", "on_onay"),
                        ("statu", "perakende_statusu"), ("birlik_uyesi", "birlik_uyeligi")):
        if profil.get(bayrak):
            profil_var.add(kod)
    eksik = [ADIMLAR[k].baslik for k in gerekli if k not in profil_var and k in ADIMLAR]
    if not profil.get("dys_yetkilendirme"):
        eksik.append("DYS yetkilendirme (şirket yetkilisi adına DYS kullanıcı yetkisi)")
    if not profil.get("imza_sirkuleri"):
        eksik.append("Güncel imza sirküleri")
    return eksik


# ------------------------------------------------------------------ 7. Senaryo stres testi
SENARYOLAR = {
    "A": {"ad": "Yalnız Amazon/Etsy satışı yapan mikro şahıs işletmesi",
          "girdi": {"sirket": {"unvan": "örnek-A", "sirket_turu": "sahis", "calisan_sayisi": 2, "yillik_ciro": 3e6,
                               "madrid_tescilli_marka": False},
                    "harcamalar": [{"aciklama": "Amazon sponsored products reklam", "tutar": 1200, "para_birimi": "USD",
                                    "kur": 41.5, "tarih": "2026-09-10", "ulke": "ABD", "odeme": "sirket_kart"},
                                   {"aciklama": "Etsy transaction fee komisyon", "tutar": 300, "para_birimi": "USD",
                                    "kur": 41.5, "tarih": "2026-09-20", "ulke": "ABD", "odeme": "sirket_kart"}]}},
    "B": {"ad": "Kendi ikas sitesinden doğrudan yurt dışına (D2C) satan marka",
          "girdi": {"sirket": {"unvan": "örnek-B", "sirket_turu": "limited", "calisan_sayisi": 5, "yillik_ciro": 6e6,
                               "madrid_tescilli_marka": True, "hazirlik": ["dys_kaydi", "kep", "e_imza"]},
                    "harcamalar": [{"aciklama": "Google Ads site reklamı Almanya", "tutar": 2000, "para_birimi": "EUR",
                                    "kur": 48.2, "tarih": "2026-08-15", "ulke": "Almanya", "odeme": "sirket_kart"},
                                   {"aciklama": "Uluslararası kargo navlun", "tutar": 45000, "para_birimi": "TRY",
                                    "tarih": "2026-08-20", "ulke": "Almanya", "odeme": "sirket_banka"}]}},
    "C": {"ad": "Pazaryerinde satan, hedef ülkede deposu olan karma işletme",
          "girdi": {"sirket": {"unvan": "örnek-C", "sirket_turu": "limited", "calisan_sayisi": 15,
                               "yillik_ciro": 20e6, "madrid_tescilli_marka": True,
                               "on_onay_tarihi": {"pazaryeri_reklam": "2026-05-12", "siparis_karsilama": "2026-05-12"},
                               "reklam_satis_try": {"pazaryeri_reklam": 900000},
                               "ulke_eticaret_satis_try": {"Almanya": 2500000},
                               "hazirlik": ["dys_kaydi", "kep", "e_imza", "birlik_uyeligi", "madrid_marka"],
                               "dys_yetkilendirme": True, "imza_sirkuleri": True},
                    "harcamalar": [{"aciklama": "Amazon.de sponsored ads", "tutar": 5000, "para_birimi": "EUR",
                                    "kur": 48.2, "tarih": "2026-07-03", "ulke": "Almanya", "odeme": "sirket_kart"},
                                   {"aciklama": "Amazon FBA fulfilment ücreti", "tutar": 6500, "para_birimi": "EUR",
                                    "kur": 48.2, "tarih": "2026-07-28", "ulke": "Almanya", "odeme": "sirket_banka"},
                                   {"aciklama": "Almanya depo kira", "tutar": 3000, "para_birimi": "EUR", "kur": 48.2,
                                    "tarih": "2026-08-01", "ulke": "Almanya", "odeme": "sirket_banka"},
                                   {"aciklama": "Amazon.de sponsored ads", "tutar": 5000, "para_birimi": "EUR",
                                    "kur": 48.2, "tarih": "2026-07-03", "ulke": "Almanya", "odeme": "sirket_kart"}]}},
    "D": {"ad": "Harcaması tavanı aşan, kuru eksik ve süresi geçmiş kalemleri olan sınır durum",
          "girdi": {"sirket": {"unvan": "örnek-D", "sirket_turu": "anonim", "calisan_sayisi": 120,
                               "yillik_ciro": 400e6, "madrid_tescilli_marka": True,
                               "on_onay_tarihi": {"pazaryeri_komisyon": "2025-12-01"},
                               "hazirlik": ["dys_kaydi", "kep", "e_imza", "birlik_uyeligi"]},
                    "harcamalar": [{"aciklama": "Amazon referral fee komisyon", "tutar": 200000, "para_birimi": "USD",
                                    "kur": 41.5, "tarih": "2026-06-30", "ulke": "ABD", "odeme": "sirket_banka"},
                                   {"aciklama": "Zalando komisyon", "tutar": 15000, "para_birimi": "EUR",
                                    "tarih": "2026-09-01", "ulke": "Almanya", "odeme": "sirket_banka"},
                                   {"aciklama": "eBay komisyon", "tutar": 50000, "para_birimi": "TRY",
                                    "tarih": "2026-02-10", "ulke": "ABD", "odeme": "sirket_banka",
                                    "baska_destek": "KOSGEB"}]}},
}


# ------------------------------------------------------------------ hesap (adım 2-4 sonrası)
def hesapla(profil: dict, harcamalar: list[Harcama], programlar: dict[str, Program],
            hedef_listesi: list[str]) -> tuple[list[dict], list[str]]:
    """Kalem başına deterministik hak ediş: esas × oran, tavanla sınırlanır (tavan aşılırsa tavan sabitlenir)."""
    katli = {_katla(x) for x in hedef_listesi}
    rapor = []
    kalemler = []
    gruplar: dict[tuple, list[Harcama]] = {}
    for h in harcamalar:
        if h.kalem in programlar:
            gruplar.setdefault((h.kalem, h.ulke if programlar[h.kalem].hedef_oran else None), []).append(h)
    for (kalem, ulke), hs in gruplar.items():
        p = programlar[kalem]
        uygun = [h for h in hs if h.durum != "RET"]
        esas = round(sum(h.tutar_try_kdv_haric or 0 for h in uygun), 2)
        notlar = []
        if kalem == "pazaryeri_reklam":
            satis = (profil.get("reklam_satis_try") or {}).get(kalem)
            if satis is not None and esas > 0.20 * satis:
                notlar.append(f"SRMO sınırı: esas gider reklamdan dönen satışın %20'si ile sınırlandı ({_tl(esas)} → "
                              f"{_tl(0.20 * satis)} TL).")
                esas = round(0.20 * satis, 2)
            elif satis is None and esas:
                notlar.append("Reklamdan dönen satış girilmedi; SRMO (%20) kontrolü yapılamadı.")
        hedefte = bool(ulke) and _katla(ulke) in katli and p.hedef_oran is not None
        oran = p.hedef_oran if hedefte else p.oran
        destek = round(esas * oran / 100, 2)
        if kalem == "siparis_karsilama" and ulke:
            satis = (profil.get("ulke_eticaret_satis_try") or {}).get(ulke)
            if satis is not None and destek > 0.10 * satis:
                notlar.append(f"Destek, {ulke}'daki e-ticaret satışının %10'u ile sınırlandı ({_tl(destek)} → "
                              f"{_tl(0.10 * satis)} TL).")
                destek = round(0.10 * satis, 2)
            elif satis is None and destek:
                notlar.append(f"{ulke}'daki e-ticaret satışı girilmedi; %10 sınırı kontrol edilemedi.")
        if p.tavan_try is not None and destek > p.tavan_try:
            notlar.append(f"Tavan aşıldı: hak ediş 2026 yıllık üst limitte ({_tl(p.tavan_try)} TL) sabitlendi.")
            destek = p.tavan_try
        durumlar = {h.durum for h in hs}
        onay = "RET" if not uygun else "SARTLI" if "SARTLI" in durumlar or notlar and any(
            "girilmedi" in n for n in notlar) else "UYGUN"
        for h in hs:
            notlar += [f"#{h.no}: {n}" for n in h.notlar]
        birimler = sorted({h.para_birimi for h in hs})
        if len(birimler) > 1:
            notlar.insert(0, "Çok para birimli kalem: orijinal tutar alanı TL karşılığıdır (satır ayrıntısı notta).")
        kalemler.append({
            "kalem_adi": KALEM_PROGRAM[kalem][1] + (f" — {ulke}" if ulke else ""),
            "harcama_tutari_orijinal": (round(sum(h.tutar for h in hs), 2) if len(birimler) == 1
                                        else round(sum(h.tutar_try_kdv_haric or 0 for h in hs), 2)),
            "harcama_para_birimi": birimler[0] if len(birimler) == 1 else "TRY",
            "harcama_tutari_try": esas,
            "destek_orani_yuzde": p.oran,
            "hedef_ulke_ilave_puani": (oran - p.oran) if hedefte else 0,
            "net_destek_orani": oran,
            "mevzuat_tavan_try": p.tavan_try or 0.0,
            "talep_edilen_hakedis_try": 0.0 if onay == "RET" else destek,
            "onay_durumu": onay,
            "not": " ".join(notlar) or "Kayıttaki şartlar sağlanıyor görünüyor; incelemeci kuruluş teyidi gerekir.",
        })
        rapor.append(f"{KALEM_PROGRAM[kalem][1]}{' (' + ulke + ')' if ulke else ''}: esas {_tl(esas)} TL × %{oran} = "
                     f"{_tl(0.0 if onay == 'RET' else destek)} TL → {onay}.")
    # kayıtla eşleşmeyen harcamalar da JSON'da görünür
    for h in harcamalar:
        if h.kalem not in programlar:
            kalemler.append({
                "kalem_adi": f"Kapsam Dışı / İncelenmeli: {h.aciklama}", "harcama_tutari_orijinal": h.tutar,
                "harcama_para_birimi": h.para_birimi, "harcama_tutari_try": h.tutar_try_kdv_haric or 0.0,
                "destek_orani_yuzde": 0, "hedef_ulke_ilave_puani": 0, "net_destek_orani": 0, "mevzuat_tavan_try": 0.0,
                "talep_edilen_hakedis_try": 0.0, "onay_durumu": "RET", "not": " ".join(h.notlar)})
    return kalemler, rapor


# ------------------------------------------------------------------ 8. Onarım
_ONARIM = (
    (r"Şahıs işletmesi doğrudan", "Limited/anonim şirkete geçin ya da E-İhracat Konsorsiyumu üyesi olun; harcamaları "
                                  "şirket kurulduktan ve ön onay alındıktan sonra şirket adına yapın."),
    (r"statü ister|statü sahiplerine", "Statü almadan yalnız statüsüz kalemlerden (pazaryeri reklamı, sipariş "
                                       "karşılama, pazaryeri komisyonu) yararlanabilirsiniz; site reklamını "
                                       "pazaryeri içi reklama kaydırın ya da statü başvurusu yapın."),
    (r"Madrid", "Önce 5973 m.4 Yurt Dışı Marka Tescil Desteği ile Madrid sistemine taraf bir ülkede marka tescili "
                "yaptırın; ardından ön onay başvurusu."),
    (r"ön onay tarihi girilmedi", "Kalem için ön onay başvurusu yapın; destek ön onay tarihini izleyen ayın ilk "
                                  "gününden sonraki harcamalara uygulanır."),
    (r"destek başlangıcından", "Ön onaydan önceki harcama kurtarılamaz; sonraki harcamaları başlangıç tarihinden sonra "
                               "yapın."),
    (r"6 aylık başvuru süresi", "Süresi geçen ödeme belgesi kurtarılamaz; sonraki ödemeler için çeyrek dönem "
                                "takvimine göre 6 ay içinde başvurun."),
    (r"Aynı gider", "Gideri yalnız bir programa sunun: diğer başvuruyu geri çekin ya da bu kalemden vazgeçin."),
    (r"Mükerrer kayıt", "Mükerrer satırı dökümden çıkarın."),
    (r"TCMB", "Ödeme tarihindeki TCMB döviz satış kurunu girin; TL karşılığı yeniden hesaplanır."),
    (r"banka dekontu", "Ödemeyi şirket banka hesabı ya da şirket kartından yapın; belgeyi dekont/ekstre ile tevsik "
                       "edin."),
    (r"Kapsam Dışı", "Bu gider için kayıtlı destek kalemi yok; başvuru paketinden çıkarın."),
    (r"SRMO", "Reklam bütçesini reklamdan dönen satışın %20'si içinde planlayın (SRMO ≤ %20, RDK ≥ 5)."),
    (r"Tavan aşıldı", "Tavanı aşan tutar desteklenmez; harcamayı sonraki yıla ya da başka uygun kaleme yayın."),
)


def onarim_rotalari(kalemler: list[dict]) -> list[str]:
    rotalar = []
    for k in kalemler:
        if k["onay_durumu"] == "UYGUN" and "sınırlandı" not in k["not"] and "Tavan" not in k["not"]:
            continue
        for kalip, rota in _ONARIM:
            if re.search(kalip, k["not"]) and (k["kalem_adi"], rota) not in [(r[0], r[1]) for r in rotalar]:
                rotalar.append((k["kalem_adi"], rota))
    return [f"{ad}: {rota}" for ad, rota in rotalar] or ["Onarım gerektiren kalem yok."]


# ------------------------------------------------------------------ 9. Gerekçe metni
def gerekce_metni(profil: dict, olcek: str, kalemler: list[dict]) -> str:
    uygun = [k for k in kalemler if k["onay_durumu"] != "RET"]
    toplam = sum(k["talep_edilen_hakedis_try"] for k in uygun)
    maddeler = sorted({m for k in uygun for m in re.findall(r"m\.\d+", _madde_bul(k["kalem_adi"]))})
    if not uygun:
        return ("Başvuru sahibi şirketin sunduğu harcamaların hiçbiri 5986 ve 5973 sayılı Kararlar kapsamında destek "
                "şartlarını sağlamamaktadır; başvuru yapılmamalı, düzeltme rotaları uygulanmalıdır.")
    return (f"{profil['anonim_kimlik']} ({olcek} ölçekli işletme), yurt dışı pazarlardaki e-ihracat faaliyetleri "
            f"kapsamında gerçekleştirdiği giderler için 5986 sayılı Cumhurbaşkanı Kararı ve uygulama Genelgesi ile, "
            f"ilgili olduğu ölçüde 5973 sayılı Cumhurbaşkanı Kararı hükümleri çerçevesinde destek talep etmektedir. "
            f"Talep edilen kalemler: {', '.join(k['kalem_adi'] for k in uygun)} (ilgili maddeler: "
            f"{', '.join(maddeler) or 'kayıtta belirtilen maddeler'}). Destek oranları Karar'da öngörülen temel oran "
            f"üzerinden, hedef ülke listesinde yer alan ülkelere yönelik giderlerde Karar'daki artırımlı oran "
            f"uygulanarak, 2026 yılı üst limitleri aşılmayacak şekilde hesaplanmıştır.\n\n"
            f"Toplam talep tutarı {_tl(toplam)} TL'dir. Giderler şirket adına düzenlenmiş fatura ve banka dekontu/kredi "
            f"kartı ekstresi ile tevsik edilmekte olup aynı giderler için başka bir mevzuat veya program kapsamında "
            f"destek talep edilmediği beyan edilir. Şartlı olarak işaretlenen kalemlere ilişkin eksik belgeler "
            f"başvuru ekinde tamamlanacaktır.")


def _madde_bul(kalem_adi: str) -> str:
    for kalip, ad in KALEM_PROGRAM.values():
        if kalem_adi.startswith(ad):
            return kalip.replace("\\", "")
    return ""


# ------------------------------------------------------------------ 10. JSON ve orkestrasyon
def calistir(girdi: dict, db, bugun: date | None = None) -> dict:
    bugun = bugun or date.today()
    programlar, hedef_listesi, statusuz = programlari_yukle(db)
    profil, harcamalar, r1 = ayristir(girdi)
    r2 = mevzuat_esle(profil, harcamalar, programlar, statusuz, bugun)
    olcek, r3 = kobi_ve_kosgeb(profil, db)
    r4 = hedef_ulke(harcamalar, programlar, hedef_listesi)
    r5 = mukerrerlik_denetimi(harcamalar)
    kalemler, r_hesap = hesapla(profil, harcamalar, programlar, hedef_listesi)
    eksik = dys_eksikleri(profil, programlar, {h.kalem for h in harcamalar if h.kalem in programlar}, db)
    r8 = onarim_rotalari(kalemler)
    metin = gerekce_metni(profil, olcek, kalemler)
    json_cikti = {
        "basvuru_meta": {"mevzuat_dayanagi": MEVZUAT_DAYANAGI,
                         "basvuru_turu": "Ödeme başvurusu (kalem bazında; ön onay gerektiren kalemlerde ön onay sonrası)",
                         "kobi_olcegi": olcek},
        "tesvik_kalemleri": kalemler,
        "toplam_talep_try": round(sum(k["talep_edilen_hakedis_try"] for k in kalemler), 2),
        "eksik_ve_tamamlanacak_evraklar": eksik,
    }
    return {"rapor": {"1 Ayrıştırma": r1, "2 Mevzuat eşleştirme": r2, "3 KOBİ ve KOSGEB": r3, "4 Hedef ülke": r4,
                      "5 Mükerrerlik ve usulsüzlük": r5, "Hesap": r_hesap, "6 DYS eksikleri": eksik or ["Eksik yok."],
                      "8 Onarım rotaları": r8},
            "gerekce": metin, "json": json_cikti}


def bicimle(sonuc: dict, senaryo: str = "") -> str:
    satir = [f"#### BÖLÜM 1: AJAN TARTIŞMASI VE DÜZELTME RAPORU{(' — ' + senaryo) if senaryo else ''}"]
    for adim, maddeler in sonuc["rapor"].items():
        satir.append(f"**{adim}**")
        satir += [f"- {m}" for m in maddeler]
    satir += ["", "#### BÖLÜM 2: RESMİ BAŞVURU GEREKÇE METNİ", sonuc["gerekce"], "",
              "#### BÖLÜM 3: RESMİ ENJEKSİYON JSON ŞEMASI", "```json",
              json.dumps(sonuc["json"], ensure_ascii=False, indent=2), "```"]
    return "\n".join(satir)


def stres_testi(db, bugun: date | None = None) -> dict[str, dict]:
    return {k: calistir(v["girdi"], db, bugun) for k, v in SENARYOLAR.items()}


def stres_ozeti(sonuclar: dict[str, dict]) -> list[str]:
    """7. adım: A-D sınır senaryolarının tek satırlık sonucu (kural setinin sınamasıdır; girdi şirketten bağımsız)."""
    satir = []
    for k, s in sonuclar.items():
        kal = s["json"]["tesvik_kalemleri"]
        durum = {d: sum(1 for x in kal if x["onay_durumu"] == d) for d in ("UYGUN", "SARTLI", "RET")}
        satir.append(f"Senaryo {k} ({SENARYOLAR[k]['ad']}): {durum['UYGUN']} uygun, {durum['SARTLI']} şartlı, "
                     f"{durum['RET']} ret; toplam talep {_tl(s['json']['toplam_talep_try'])} TL.")
    return satir


# ------------------------------------------------------------------ self-test
def _self_test() -> int:
    from types import SimpleNamespace as N
    bugun = date(2026, 10, 12)
    t192 = N(id=192, baslik="Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı Karar m.4)",
             tesvil_tutari="%50 (hedef ülkelerde %70); 2026 yıllık üst limit şirketler için 36.993.646 TL",
             kontrol_listesi=[{"tur": "sart", "metin": "Ön onay için Madrid"}])
    t194 = N(id=194, baslik="Yurt Dışı Pazaryeri Komisyon Gideri Desteği (5986 sayılı Karar m.9)",
             tesvil_tutari="%50; 2026 şirketler için yıllık 3.698.274 TL; 3 yıl", kontrol_listesi=[])
    progs = {"pazaryeri_reklam": program_kaydindan("pazaryeri_reklam", t192),
             "pazaryeri_komisyon": program_kaydindan("pazaryeri_komisyon", t194)}
    hedef = ["ABD", "Almanya"]
    sonuc = []
    p = progs["pazaryeri_reklam"]
    sonuc.append(("kayıttan oran/hedef oran/tavan", (p.oran, p.hedef_oran, p.tavan_try) == (50, 70, 36993646.0)))
    girdi = {"sirket": {"unvan": "X", "vergi_no": "123", "sirket_turu": "limited", "madrid_tescilli_marka": True,
                        "on_onay_tarihi": {"pazaryeri_reklam": "2026-05-12", "pazaryeri_komisyon": "2026-05-12"}},
             "harcamalar": [{"aciklama": "Amazon sponsored ads", "tutar": 1000, "para_birimi": "EUR", "kur": 50,
                             "tarih": "2026-07-01", "ulke": "Almanya", "odeme": "sirket_kart"},
                            {"aciklama": "Amazon sponsored ads", "tutar": 1000, "para_birimi": "EUR", "kur": 50,
                             "tarih": "2026-07-01", "ulke": "Almanya", "odeme": "sirket_kart"},
                            {"aciklama": "komisyon", "tutar": 10000, "para_birimi": "USD", "tarih": "2026-08-01"},
                            {"aciklama": "kargo navlun", "tutar": 5000, "para_birimi": "TRY", "tarih": "2026-08-01"}]}
    profil, hs, r1 = ayristir(girdi)
    sonuc.append(("vergi no hatası raporlanır, unvan anonim", any("10 haneli" in x for x in r1)
                  and profil["anonim_kimlik"].startswith("Şirket-")))
    sonuc.append(("kur yoksa TL hesaplanmaz, şartlı", hs[2].durum == "SARTLI" and hs[2].tutar_try_kdv_haric == 0))
    mevzuat_esle(profil, hs, progs, "", bugun)
    mukerrerlik_denetimi(hs)
    sonuc.append(("mükerrer satır ret", hs[1].durum == "RET" and any("Mükerrer" in n for n in hs[1].notlar)))
    sonuc.append(("kargo kapsam dışı", hs[3].durum == "RET" and "Kapsam Dışı" in hs[3].notlar[0]))
    kalemler, _ = hesapla(profil, hs, progs, hedef)
    reklam = next(k for k in kalemler if k["kalem_adi"].startswith("Dijital Pazaryeri"))
    sonuc.append(("hedef ülke %70: 50.000 TL × %70 = 35.000", reklam["net_destek_orani"] == 70
                  and reklam["hedef_ulke_ilave_puani"] == 20 and reklam["talep_edilen_hakedis_try"] == 35000.0))
    # tavan sabitleme
    hs2 = [Harcama(1, "komisyon", "pazaryeri_komisyon", 1e7, "TRY", False, 0.2, None, date(2026, 9, 1), "ABD",
                   None, "sirket_banka", False, None, 1e7)]
    k2, _ = hesapla({}, hs2, progs, hedef)
    sonuc.append(("tavan aşılınca tavan sabitlenir", k2[0]["talep_edilen_hakedis_try"] == 3698274.0
                  and "Tavan aşıldı" in k2[0]["not"]))
    # şahıs ret ve onarım rotası
    hs3 = [Harcama(1, "Amazon sponsored ads", "pazaryeri_reklam", 100, "TRY", False, 0.2, None, date(2026, 9, 1),
                   None, None, "sirket_kart", False, None, 100.0)]
    mevzuat_esle({"sirket_turu": "sahis"}, hs3, progs, "", bugun)
    k3, _ = hesapla({}, hs3, progs, hedef)
    sonuc.append(("şahıs işletmesi ret + konsorsiyum rotası", k3[0]["onay_durumu"] == "RET"
                  and any("Konsorsiyumu" in r for r in onarim_rotalari(k3))))
    # süre aşımı
    hs4 = [Harcama(1, "komisyon", "pazaryeri_komisyon", 100, "TRY", False, 0.2, None, date(2026, 1, 5), None, None,
                   "sirket_banka", False, None, 100.0)]
    mevzuat_esle({"sirket_turu": "limited", "madrid_tescilli_marka": True,
                  "on_onay_tarihi": {"pazaryeri_komisyon": "2025-11-01"}}, hs4, progs, "", bugun)
    sonuc.append(("6 aylık süre aşımı ret", hs4[0].durum == "RET"))
    # SRMO
    hs5 = [Harcama(1, "ads", "pazaryeri_reklam", 100000, "TRY", False, 0.2, None, date(2026, 9, 1), "Fas", None,
                   "sirket_kart", False, None, 100000.0)]
    k5, _ = hesapla({"reklam_satis_try": {"pazaryeri_reklam": 200000}}, hs5, progs, hedef)
    sonuc.append(("SRMO: esas satışın %20'si (40.000) × %50", k5[0]["harcama_tutari_try"] == 40000.0
                  and k5[0]["talep_edilen_hakedis_try"] == 20000.0))
    for ad, ok in sonuc:
        print(("GEÇTİ " if ok else "KALDI ") + ad)
    gecen = sum(ok for _, ok in sonuc)
    print(f"self-test: {gecen}/{len(sonuc)} geçti")
    return 0 if gecen == len(sonuc) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    from app.models import SessionLocal
    _db = SessionLocal()
    try:
        _stres = stres_testi(_db)
        _ozet = stres_ozeti(_stres)
        if "--demo" in sys.argv:
            for _k, _s in _stres.items():
                _s["rapor"]["7 Senaryo stres testi"] = _ozet
                print(f"\n\n=============== SENARYO {_k}: {SENARYOLAR[_k]['ad']} (sentetik girdi) ===============\n")
                print(bicimle(_s, f"Senaryo {_k}"))
        elif "--girdi" in sys.argv:
            _yol = sys.argv[sys.argv.index("--girdi") + 1]
            with open(_yol, encoding="utf-8") as _f:
                _s = calistir(json.load(_f), _db)
            _s["rapor"]["7 Senaryo stres testi"] = _ozet
            print(bicimle(_s))
        else:
            print(__doc__)
    finally:
        _db.close()
