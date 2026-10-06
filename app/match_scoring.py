"""Hibrit eşleştirme skorlama motoru (Match Scoring Engine).

İki aşamalı, deterministik ve saf (veritabanı/ağ erişimi yok) boru hattı:

  Aşama 1 - Katı eleme: il/bölge, çalışan sayısı ve zorunlu hedef kitle
            şartlarından biri sağlanmıyorsa program sonuç kümesinden TAMAMEN
            çıkar; skorlamaya hiç girmez.
  Aşama 2 - Ağırlıklı skor (0-100): sektör %45, bölge %25, ölçek/ciro %20,
            destek türü tercihi %10.

Bilinmeyen veri politikası (bilerek muhafazakâr):
  * Profilde il/çalışan/ciro YOKSA ve program bunu kısıtlıyorsa program
    ELENMEZ (yokluğun ihlal olduğu kanıtlanamaz) ama `unverified` listesinde
    belirtilir ve ilgili kriter nötr puan alır.
  * Zorunlu hedef kitle (`exclusive_target_group`) istisnadır: etiketler
    olumlu beyandır; profilde etiket yoksa işletme o kitleden DEĞİLDİR.

Sapma (spec dışı, bilerek): `strict_sector=True` (varsayılan) iken NACE
listesi olan bir program, işletmenin hiçbir koduyla eşleşmiyorsa elenir.
Aksi hâlde sektörü uyuşmayan program ölçek/bölge/destek puanlarıyla eşiği
geçebiliyordu. Kapatmak için `strict_sector=False`.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.kobi import SIRA as OLCEK_SIRASI, kobi_sinifi
from app.nace_9903 import il_bolgesi
from app.nace_hiyerarsi import SektorUyumu, exclusion_status, normalize_nace, sector_match
from app.urun_sektor_anahtarlari import kucult

SupportType = Literal["hibe", "faizsiz_kredi", "kredi", "kefalet", "diger"]

AGIRLIKLAR: dict[str, float] = {
    "sektor": 0.45,
    "bolge": 0.25,
    "olcek": 0.20,
    "destek_turu": 0.10,
}

BOLGE_ULUSAL_PUANI = 50.0
OLCEK_KISITSIZ_PUANI = 70.0     # program ölçek kısıtlamıyor: uyum bilgisi yok
OLCEK_BILINMIYOR_PUANI = 50.0   # profilde veri yok
SINIRDA_MIN_CARPAN = 0.5        # sert sınırda bile uygun; yalnızca yarı puan

_ASCII = str.maketrans("çğıöşü", "cgiosu")


def _katla(x: str) -> str:
    return kucult(x).strip().translate(_ASCII)


def _ilk_buyuk(metin: str) -> str:
    """str.capitalize() geri kalanı küçültüp "4. Bölge"yi bozuyordu."""
    return metin[:1].upper() + metin[1:]


def _nace_listesi(kodlar: list[str]) -> list[str]:
    sonuc = []
    for k in kodlar:
        n = normalize_nace(k)
        if n is None:
            raise ValueError(f"Geçersiz NACE kodu: {k!r}")
        if n not in sonuc:
            sonuc.append(n)
    return sonuc


# --------------------------------------------------------------------------
# Modeller
# --------------------------------------------------------------------------
class CompanyProfile(BaseModel):
    province: str | None = None
    region: int | None = Field(None, ge=1, le=6, description="Boşsa ilden türetilir")
    employees: int | None = Field(None, ge=0)
    annual_revenue: float | None = Field(None, ge=0)
    nace_codes: list[str] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set,
        description="Hedef kitle etiketleri: kadin_girisimci, savunma_sanayii, ...")
    preferred_support_types: list[SupportType] = Field(default_factory=list,
        description="Tercih sırasına göre")

    @field_validator("tags")
    @classmethod
    def _etiket_normalize(cls, v: set[str]) -> set[str]:
        return {_katla(t) for t in v}

    @field_validator("nace_codes")
    @classmethod
    def _nace_normalize(cls, v: list[str]) -> list[str]:
        return _nace_listesi(v)

    @property
    def effective_region(self) -> int | None:
        if self.region is not None:
            return self.region
        return il_bolgesi(self.province) if self.province else None


class IncentiveProgram(BaseModel):
    id: str
    name: str
    institution: str = ""
    support_type: SupportType = "diger"

    nace_codes: list[str] = Field(default_factory=list,
        description="Boş = yatay/sektör bağımsız program")
    excluded_nace_codes: list[str] = Field(default_factory=list,
        description="Programın açıkça dışladığı kollar (ör. 'imalat, tütün 12 hariç')")

    # Katı kısıtlar (boş = kısıt yok)
    eligible_provinces: list[str] = Field(default_factory=list)
    eligible_regions: list[int] = Field(default_factory=list)
    min_employees: int | None = Field(None, ge=0)
    max_employees: int | None = Field(None, ge=0)
    exclusive_target_group: bool = False
    target_group_tags: set[str] = Field(default_factory=set)
    max_scale: Literal["mikro", "kucuk", "orta"] | None = Field(
        None, description="Programa başvurabilecek EN BÜYÜK ölçek; 'orta' = KOBİ vasfı şart "
                          "(7 Ağustos 2025 KOBİ tanımı, bkz. app/kobi.py)")

    # Puanlama girdileri
    priority_provinces: list[str] = Field(default_factory=list)
    priority_regions: list[int] = Field(default_factory=list)
    min_revenue: float | None = Field(None, ge=0)
    max_revenue: float | None = Field(None, ge=0)
    ideal_min_employees: int | None = Field(None, ge=0)
    ideal_max_employees: int | None = Field(None, ge=0)
    ideal_min_revenue: float | None = Field(None, ge=0)
    ideal_max_revenue: float | None = Field(None, ge=0)

    @field_validator("target_group_tags")
    @classmethod
    def _etiket_normalize(cls, v: set[str]) -> set[str]:
        return {_katla(t) for t in v}

    @field_validator("nace_codes", "excluded_nace_codes")
    @classmethod
    def _nace_normalize(cls, v: list[str]) -> list[str]:
        return _nace_listesi(v)


class CriterionScore(BaseModel):
    score: float          # 0-100
    weight: float
    weighted: float       # score * weight


class ScoredMatch(BaseModel):
    program_id: str
    program_name: str
    institution: str = ""
    total_score: float
    breakdown: dict[str, CriterionScore]
    match_reasons: list[str]
    unverified: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Aşama 1: katı eleme
# --------------------------------------------------------------------------
def _il_kumesi(iller: list[str]) -> set[str]:
    return {_katla(i) for i in iller}


def _sektor_uyumu(profile: "CompanyProfile", program: "IncentiveProgram") -> SektorUyumu:
    """İşletmenin birden çok NACE kodu varsa programa en uyanı alınır."""
    if not profile.nace_codes:
        return sector_match(None, program.nace_codes)
    return max((sector_match(k, program.nace_codes) for k in profile.nace_codes),
              key=lambda u: u.skor)


def hard_filter(profile: CompanyProfile, program: IncentiveProgram, *,
                strict_sector: bool = True) -> tuple[list[str], list[str]]:
    """(eleme_sebepleri, doğrulanamayanlar). Sebep listesi boşsa program geçer."""
    sebepler: list[str] = []
    dogrulanamayan: list[str] = []

    # 1) İl / bölge
    if program.eligible_provinces or program.eligible_regions:
        il_ok = bolge_ok = False
        if profile.province:
            il_ok = _katla(profile.province) in _il_kumesi(program.eligible_provinces)
        bolge = profile.effective_region
        if bolge is not None:
            bolge_ok = bolge in program.eligible_regions
        if profile.province is None and bolge is None:
            dogrulanamayan.append("il/bölge (program kısıtlı, profilde il yok)")
        elif not (il_ok or bolge_ok):
            sebepler.append(
                f"il/bölge kapsam dışı ({profile.province or '-'}, "
                f"{bolge or '?'}. bölge)")

    # 2) Çalışan sayısı
    if program.min_employees is not None or program.max_employees is not None:
        if profile.employees is None:
            dogrulanamayan.append("çalışan sayısı (program kısıtlı, profilde yok)")
        else:
            if program.min_employees is not None and profile.employees < program.min_employees:
                sebepler.append(
                    f"çalışan sayısı {profile.employees} < asgari {program.min_employees}")
            if program.max_employees is not None and profile.employees > program.max_employees:
                sebepler.append(
                    f"çalışan sayısı {profile.employees} > azami {program.max_employees}")

    # 2b) Ölçek (KOBİ vasfı / azami ölçek)
    if program.max_scale is not None:
        olcek = kobi_sinifi(profile.employees, profile.annual_revenue)
        if olcek.sinif is None:
            dogrulanamayan.append("ölçek (KOBİ sınıfı belirlenemedi: çalışan/ciro eksik)")
        elif OLCEK_SIRASI[olcek.sinif] > OLCEK_SIRASI[program.max_scale]:
            if olcek.kesin:
                sebepler.append(f"ölçek uygun değil: {olcek.aciklama}; program en çok "
                                f"'{program.max_scale}' ölçeğine açık")
            else:
                dogrulanamayan.append(f"ölçek ({olcek.aciklama})")

    # 3) Zorunlu hedef kitle
    if program.exclusive_target_group:
        if not (profile.tags & program.target_group_tags):
            sebepler.append(
                "zorunlu hedef kitle dışında "
                f"(gerekli: {', '.join(sorted(program.target_group_tags)) or '-'})")

    # Açık dışlama: "imalat, ancak tütün (12) hariç" -> tütün işletmesi elenir.
    # İşletme kodu hariç koddan genişse (C vs 12) dalı bilinmiyor: elenmez, işaretlenir.
    if program.excluded_nace_codes and profile.nace_codes:
        durumlar = [exclusion_status(k, program.excluded_nace_codes) for k in profile.nace_codes]
        if "degil" not in durumlar and "belirsiz" not in durumlar:
            sebepler.append("işletmenin sektörü programdan açıkça hariç tutulmuş "
                            f"({', '.join(program.excluded_nace_codes)})")
        elif "belirsiz" in durumlar and "degil" not in durumlar:
            dogrulanamayan.append("hariç tutulan kol (işletme kodu daha geniş, alt dal bilinmiyor)")

    # Spec dışı: sektör-kilitli program, hiçbir NACE koduyla eşleşmiyor
    if strict_sector and program.nace_codes and profile.nace_codes:
        if _sektor_uyumu(profile, program).durum == "uyumsuz":
            sebepler.append("program sektörü işletmenin NACE kodlarıyla örtüşmüyor")
    elif program.nace_codes and not profile.nace_codes:
        dogrulanamayan.append("NACE kodu (program sektörlü, profilde kod girilmemiş)")

    return sebepler, dogrulanamayan


# --------------------------------------------------------------------------
# Aşama 2: skorlama
# --------------------------------------------------------------------------
def _sektor_puani(profile: CompanyProfile, program: IncentiveProgram
                  ) -> tuple[float, str]:
    u = _sektor_uyumu(profile, program)
    return round(u.skor * 100, 1), u.aciklama


def _bolge_puani(profile: CompanyProfile, program: IncentiveProgram
                 ) -> tuple[float, str]:
    bolge = profile.effective_region
    hedefli = bool(program.eligible_provinces or program.eligible_regions)
    oncelikli = False
    if profile.province and _katla(profile.province) in _il_kumesi(
            program.priority_provinces + program.eligible_provinces):
        oncelikli = True
    if bolge is not None and bolge in (program.priority_regions + program.eligible_regions):
        oncelikli = True
    if oncelikli and (hedefli or program.priority_provinces or program.priority_regions):
        yer = f"{bolge}. Bölge" if bolge else profile.province
        return 100.0, f"{yer} öncelikli kalkınma kapsamında"
    return BOLGE_ULUSAL_PUANI, "genel ulusal kapsam"


def _boyut_carpani(deger: float | None, sert_min: float | None,
                   sert_max: float | None, ideal_min: float | None,
                   ideal_max: float | None) -> float | None:
    """1.0 (ideal dilim) -> SINIRDA_MIN_CARPAN (sert sınır). None = ölçülemez.

    İdeal dilim verilmemişse iki taraflı sınırda orta %60'lık bant, tek
    taraflı sınırda sınırın ötesi tam puan sayılır."""
    if sert_min is None and sert_max is None:
        return None
    if deger is None:
        return -1.0  # işaret: veri yok
    lo = sert_min if sert_min is not None else float("-inf")
    hi = sert_max if sert_max is not None else float("inf")
    if ideal_min is None and ideal_max is None and lo > float("-inf") and hi < float("inf"):
        genislik = hi - lo
        ideal_min, ideal_max = lo + 0.2 * genislik, hi - 0.2 * genislik
    il = ideal_min if ideal_min is not None else lo
    ih = ideal_max if ideal_max is not None else hi
    if il <= deger <= ih:
        return 1.0
    if deger < il:
        if lo == float("-inf") or il <= lo:
            return 1.0
        d = min(1.0, (il - deger) / (il - lo))
    else:
        if hi == float("inf") or ih >= hi:
            return 1.0
        d = min(1.0, (deger - ih) / (hi - ih))
    return 1.0 - (1.0 - SINIRDA_MIN_CARPAN) * d


def _olcek_puani(profile: CompanyProfile, program: IncentiveProgram
                 ) -> tuple[float, str, list[str]]:
    carpanlar, bilinmeyen = [], []
    c = _boyut_carpani(profile.employees, program.min_employees, program.max_employees,
                       program.ideal_min_employees, program.ideal_max_employees)
    if c is not None:
        (bilinmeyen.append("çalışan sayısı") if c < 0 else carpanlar.append(c))
    r = _boyut_carpani(profile.annual_revenue, program.min_revenue, program.max_revenue,
                       program.ideal_min_revenue, program.ideal_max_revenue)
    if r is not None:
        (bilinmeyen.append("ciro") if r < 0 else carpanlar.append(r))
    if carpanlar:
        ort = sum(carpanlar) / len(carpanlar)
        ek = " (sınıra yakın)" if ort < 0.85 else ""
        return 100.0 * ort, f"ölçek hedef diliminde{ek}", bilinmeyen
    if bilinmeyen:
        return OLCEK_BILINMIYOR_PUANI, "ölçek verisi eksik", bilinmeyen
    return OLCEK_KISITSIZ_PUANI, "program ölçek kısıtı koymuyor", []


def _destek_puani(profile: CompanyProfile, program: IncentiveProgram
                  ) -> tuple[float, str]:
    tercih = profile.preferred_support_types
    if not tercih:
        return 50.0, "destek türü tercihi belirtilmemiş"
    if program.support_type in tercih:
        sira = tercih.index(program.support_type)
        return max(50.0, 100.0 - 25.0 * sira), f"tercih edilen tür: {program.support_type}"
    return 25.0, f"tercih edilmeyen tür: {program.support_type}"


def score_program(profile: CompanyProfile, program: IncentiveProgram,
                  dogrulanamayan: list[str] | None = None) -> ScoredMatch:
    sektor, s_ned = _sektor_puani(profile, program)
    bolge, b_ned = _bolge_puani(profile, program)
    olcek, o_ned, o_bil = _olcek_puani(profile, program)
    destek, d_ned = _destek_puani(profile, program)

    ham = {"sektor": sektor, "bolge": bolge, "olcek": olcek, "destek_turu": destek}
    kirilim = {
        k: CriterionScore(score=round(v, 1), weight=AGIRLIKLAR[k],
                          weighted=round(v * AGIRLIKLAR[k], 2))
        for k, v in ham.items()
    }
    toplam = round(sum(v * AGIRLIKLAR[k] for k, v in ham.items()), 1)
    return ScoredMatch(
        program_id=program.id, program_name=program.name,
        institution=program.institution, total_score=toplam,
        breakdown=kirilim,
        match_reasons=[_ilk_buyuk(x) for x in (s_ned, b_ned, o_ned, d_ned)],
        unverified=list(dogrulanamayan or []) + [f"{x} (ölçek puanı nötr)" for x in o_bil],
    )


def calculate_matches(profile: CompanyProfile, programs: list[IncentiveProgram], *,
                      min_score: float = 0.0, strict_sector: bool = True
                      ) -> list[ScoredMatch]:
    """Aşama 1 ile ele, Aşama 2 ile puanla, puana göre azalan sırala.

    Eşit puanda program adına göre sıralanır (deterministik çıktı)."""
    sonuc: list[ScoredMatch] = []
    for program in programs:
        sebepler, dogrulanamayan = hard_filter(profile, program,
                                               strict_sector=strict_sector)
        if sebepler:
            continue
        eslesme = score_program(profile, program, dogrulanamayan)
        if eslesme.total_score >= min_score:
            sonuc.append(eslesme)
    sonuc.sort(key=lambda m: (-m.total_score, m.program_name))
    return sonuc
