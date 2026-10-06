"""Veritabanı satırlarını (Tesvik, FinancialProfile) skorlama motorunun
modellerine çevirir. Motorun kendisi için bkz. app/match_scoring.py."""
from __future__ import annotations

from app.match_scoring import CompanyProfile, IncentiveProgram
from app.nace_9903 import il_bolgesi

# Kullanıcının profilinde işaretleyebileceği hedef kitle özellikleri.
# Zorunlu hedef kitleli (exclusive) programlar yalnızca bu etiketlerden en az
# birini taşıyan işletmeye gösterilir.
OZELLIK_ETIKETLERI: dict[str, str] = {
    "kadin_girisimci": "Kadın girişimci / kadınların yönettiği işletme",
    "genc_girisimci": "Genç girişimci",
    "savunma_sanayii": "Savunma sanayii tedarikçisi",
    "mesleki_egitim": "Mesleki eğitim veren / çırak-stajyer çalıştıran işletme",
    "hukuk_burosu": "Hukuk bürosu / avukatlık",
    "basin_ilan": "Basın-yayın kuruluşu (gazete vb.)",
    "cay_ureticisi": "Çay üreticisi / çay işleyen",
    "kooperatif": "Kooperatif",
}

_TUTAR_NITELIGI_TURU = {
    "hibe": "hibe",
    "kredi_kefalet": "kefalet",
    "faiz_destegi": "faizsiz_kredi",
}


def company_from_profile(profil) -> CompanyProfile:
    """FinancialProfile -> CompanyProfile.

    `bolge` serbest metin; yalnızca tanınan bir il adıysa il olarak alınır.
    Aksi hâlde il bilinmiyor sayılır (yanlış il kısıtıyla elemekten iyidir)."""
    bolge = (profil.bolge or "").strip()
    return CompanyProfile(
        province=bolge if bolge and il_bolgesi(bolge) is not None else None,
        nace_codes=[profil.nace_kodu] if getattr(profil, "nace_kodu", None) else [],
        employees=profil.calisan_sayisi,
        annual_revenue=profil.yillik_ciro,
        tags=set(getattr(profil, "ozellikler", None) or []),
    )


def program_from_tesvik(t) -> IncentiveProgram:
    k = t.uygunluk_kriterleri or {}
    return IncentiveProgram(
        id=str(t.id),
        name=t.baslik or "",
        institution=t.kurum or "",
        support_type=_TUTAR_NITELIGI_TURU.get(k.get("tutar_niteligi"), "diger"),
        nace_codes=[n.nace_prefix for n in (getattr(t, "nace_kayitlari", None) or []) if not n.haric_mi],
        excluded_nace_codes=[n.nace_prefix for n in (getattr(t, "nace_kayitlari", None) or []) if n.haric_mi],
        eligible_provinces=list(k.get("bolge_kisitli") or []),
        eligible_regions=list(k.get("eligible_regions") or []),
        min_employees=k.get("min_employees"),
        max_employees=k.get("max_employees"),
        max_scale=k.get("max_olcek"),
        exclusive_target_group=bool(k.get("exclusive_target_group", False)),
        target_group_tags=set(k.get("target_group_tags") or []),
    )
