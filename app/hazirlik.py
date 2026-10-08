"""Hazırlık yol haritası: "uygun değilsiniz" yerine "uygun olmak için şu adımlar" (2026-10-08).

İki kaynaktan çıkar, ikisi de kayıtlara dayanır (uydurma süre/maliyet yok):
  1. Şirket türü karşı-olgusu: profil şahıs/şirketsizse aynı profil "limited" olsaydı eşleşmeye giren programlar
     (app/matching.esles ile; engel mantığı uygunluk_engeli ve kayıtlardaki sirket_turleri listesi).
  2. Eşleşen programların ön şartları: şart/belge/başvuru yeri metninde geçen kayıt ve belge gereklilikleri
     (ihracatçı birliği, DYS, Madrid marka tescili, e-imza, KEP, ÇKS, yatırım teşvik belgesi, SGK/vergi borcu)
     ile KOSGEB programlarının tümünde aranan KOSGEB veri tabanı kaydı.
Her adım, gerektiren programları (id, başlık) listeler; kullanıcı "tamam" işaretlediğinde
financial_profiles.hazirlik["durumlar"] içinde saklanır.

    python -m app.hazirlik --self-test
"""
import re
import sys
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_org
from app.eticaret_destek_hesaplayici import KALEMLER, EihracatDurumu, EihracatGirdisi, hesapla, sozluk
from app.models import FinancialProfile, Organization, get_db

router = APIRouter()


@dataclass(frozen=True)
class Adim:
    kod: str
    baslik: str
    nasil: str
    kalip: str | None = None      # şart/belge metninde aranan düzenli ifade
    kurum: str | None = None      # bu kurumun bütün programlarında gerekli


ADIMLAR: dict[str, Adim] = {a.kod: a for a in (
    Adim("sirket", "Limited/anonim şirkete geçiş",
         "Şirket kuruluşu ticaret sicili (MERSİS) üzerinden yapılır; şahıs işletmesinin varlık ve sözleşmelerinin "
         "devrini mali müşavirinizle planlayın. E-ihracatta geçici yol: E-İhracat Konsorsiyumu (5986 Genelge m.33/7)."),
    Adim("kosgeb_kaydi", "KOSGEB veri tabanı kaydı ve KOBİ Bilgi Beyannamesi",
         "KOSGEB e-Hizmetler (e-Devlet ile giriş) üzerinden işletme kaydı ve onaylı KOBİ Bilgi Beyannamesi.",
         r"KOSGEB\s+veri\s*taban|KOBİ\s+Bilgi\s+Beyannamesi", kurum="KOSGEB"),
    Adim("birlik_uyeligi", "İhracatçı birliği üyeliği",
         "Ürün grubunuzun ihracatçı birliğine üye olun; 5973 ve 5986 başvuruları üyesi olunan birliğin genel "
         "sekreterliğine yapılır.",
         # "Bakanlıkça görevlendirilen İhracatçı Birliği" (5973 m.6) üyelik şartı değildir; yalnız üyelik bağlamı.
         r"ihracatçı\s+birliğ\w*\s+üye|üyesi\s+olunan\s+ihracatçı\s+birliğ"),
    Adim("dys_kaydi", "Ticaret Bakanlığı DYS kaydı",
         "Destek Yönetim Sistemi'ne (DYS) şirket kaydı; MERSİS bilgileri ve NACE kodu güncel olmalı.",
         r"\bDYS\b|Destek\s+Yönetim\s+Sistemi"),
    Adim("madrid_marka", "Yurt dışı marka tescili (Madrid Sistemi)",
         "Madrid Sistemi'ne taraf en az bir ülkede marka tescili; masrafın bir kısmı 5973 m.4 Yurt Dışı Marka Tescil "
         "Desteği ile karşılanabilir.", r"Madrid"),
    Adim("perakende_statusu", "Perakende E-Ticaret Sitesi statüsü",
         "Başvuru E-İhracat Sekretaryasına; şartlar 5986 Genelgesi m.7 (önceki yıl ≥ 500.000 USD ihracat vb.).",
         r"Perakende\s+E-Ticaret\s+Sitesi\s+statü"),
    Adim("on_onay", "Harcamadan önce ön onay",
         "Bu programlarda ön onay tarihinden önce yapılan harcama desteklenmez; harcamayı planlamadan başvurun.",
         r"ön\s+onay"),
    Adim("e_imza", "Elektronik imza (e-imza)", "Yetkili kişi adına nitelikli elektronik sertifika edinin.",
         r"e-?imza|elektronik\s+imza"),
    Adim("kep", "Kayıtlı elektronik posta (KEP) adresi", "Şirket adına bir KEP hizmet sağlayıcısından KEP adresi alın.",
         r"\bKEP\b"),
    Adim("cks", "Çiftçi Kayıt Sistemi (ÇKS) kaydı", "İl/ilçe tarım ve orman müdürlüğünde ÇKS kaydı ve güncellemesi.",
         r"ÇKS|Çiftçi\s+Kayıt"),
    Adim("yatirim_tesvik_belgesi", "Yatırım teşvik belgesi",
         "Yatırıma başlamadan önce Sanayi ve Teknoloji Bakanlığı E-TUYS üzerinden belge başvurusu.",
         r"[Yy]atırım\s+[Tt]eşvik\s+[Bb]elgesi"),
    Adim("borc_durumu", "SGK prim ve vergi borcu durumu",
         "Vadesi geçmiş SGK/vergi borcu olmadığını (ya da yapılandırıldığını) gösteren yazıları hazırlayın.",
         r"SGK\s+(?:prim\s+)?borc|vergi\s+borc|vadesi\s+geçmiş"),
)}


ILGILI_SKOR = 0.5
SEKTOR_ONCELIGI = {"tarim": ("cks",)}


def _metin(t) -> str:
    return " ".join(str(x) for x in (t.basvuru_sartlari or [], t.gerekli_belgeler or [], t.basvuru_yeri or "",
                                       t.basvuru_suresi or ""))


def program_adimlari(t) -> list[str]:
    metin = _metin(t)
    return [a.kod for a in ADIMLAR.values()
            if (a.kurum and t.kurum == a.kurum) or (a.kalip and re.search(a.kalip, metin, re.IGNORECASE))]


def _kopya(p: FinancialProfile, **degisen) -> FinancialProfile:
    """Oturuma eklenmeyen (transient) kopya: karşı-olgu eşleştirmesi veritabanına yazılmaz."""
    alanlar = {c.name: getattr(p, c.name) for c in FinancialProfile.__table__.columns if c.name not in ("id", "org_id")}
    return FinancialProfile(**{**alanlar, **degisen})


def yol_haritasi(p: FinancialProfile | None, db: Session, en_cok_program: int = 200) -> dict:
    from app.matching import esles

    if p is None:
        return {"adimlar": [], "eslesme_sayisi": 0}
    durumlar = (p.hazirlik or {}).get("durumlar", {})
    eslesmeler = esles(p, db, limit=en_cok_program)
    gerek: dict[str, list] = {}
    for e in eslesmeler:
        for kod in program_adimlari(e.tesvik):
            gerek.setdefault(kod, []).append(e.tesvik)
    acilan = []
    if p.sirket_turu in ("sahis", "yok"):
        mevcut = {e.tesvik.id for e in eslesmeler}
        # Yalnız gerçekten ilgili programlar sayılır: skoru ILGILI_SKOR altında kalanlar yalnız "genel" sektör
        # etiketiyle eşleşir (persona denemesi 2026-10-08: buğday çiftçisine "şirkete geçin, 11 program açılır"
        # deniyordu; 11'i de 0,30 skorlu TÜBİTAK sanayi Ar-Ge programıydı).
        acilan = [e.tesvik for e in esles(_kopya(p, sirket_turu="limited"), db, limit=en_cok_program)
                  if e.tesvik.id not in mevcut and e.skor >= ILGILI_SKOR]
        if acilan:
            gerek["sirket"] = acilan
    adimlar = []
    for kod, programlar in gerek.items():
        a = ADIMLAR[kod]
        adimlar.append({
            "kod": kod, "baslik": a.baslik, "nasil": a.nasil, "tamam": bool(durumlar.get(kod)),
            "acar" if kod == "sirket" else "gerekli": [{"id": t.id, "baslik": t.baslik, "kurum": t.kurum,
                                                       "tutari_max": t.tutari_max} for t in programlar],
            "program_sayisi": len(programlar),
        })
    # Önce tamamlanmamışlar; sektörün temel kaydı (tarımda ÇKS: hububat, hayvancılık vb. ödemelerin ön şartı) ve
    # "sirket" (en çok kapıyı açar) en başta; sonra gerektiren program sayısı.
    oncelikli = SEKTOR_ONCELIGI.get(p.sektor, ()) + ("sirket",)
    adimlar.sort(key=lambda x: (x["tamam"], oncelikli.index(x["kod"]) if x["kod"] in oncelikli else len(oncelikli),
                                -x["program_sayisi"], x["baslik"]))
    return {"adimlar": adimlar, "eslesme_sayisi": len(eslesmeler)}


# ----------------------------------------------------------------------------------------------- API
class EihracatBilgisi(BaseModel):
    giderler: dict[str, float] = Field(default_factory=dict, description="KALEMLER kodu -> yıllık TL")
    yurt_disi_satis_tl: float | None = Field(None, ge=0, le=1e12)
    hedef_ulke_payi: float = Field(0.0, ge=0, le=1)
    turk_urun_payi: float = Field(1.0, ge=0, le=1)
    onceki_yil_ihracat_usd: float | None = Field(None, ge=0, le=1e12)
    perakende_statusu: bool | None = None


class HazirlikGirdisi(BaseModel):
    durumlar: dict[str, bool | None] = Field(default_factory=dict, description="adım kodu -> true/false; null = bilinmiyor")
    eihracat: EihracatBilgisi | None = None


def _dogrula(g: HazirlikGirdisi) -> None:
    bilinmeyen = [k for k in g.durumlar if k not in ADIMLAR] + \
        [k for k in (g.eihracat.giderler if g.eihracat else {}) if k not in KALEMLER]
    if bilinmeyen:
        raise HTTPException(status_code=422, detail=f"Tanınmayan alan: {', '.join(bilinmeyen)}")
    if g.eihracat and any(v < 0 or v > 1e12 for v in g.eihracat.giderler.values()):
        raise HTTPException(status_code=422, detail="Gider tutarları 0 ile 1 trilyon TL arasında olmalı")


def eihracat_sonucu(p: FinancialProfile | None) -> dict | None:
    h = (p.hazirlik or {}) if p is not None else {}
    e = h.get("eihracat")
    if not e or not e.get("giderler"):
        return None
    d = h.get("durumlar", {})
    durum = EihracatDurumu(
        sirket_turu=p.sirket_turu, birlik_uyesi=d.get("birlik_uyeligi"), madrid_marka=d.get("madrid_marka"),
        onceki_yil_ihracat_usd=e.get("onceki_yil_ihracat_usd"), perakende_statusu=e.get("perakende_statusu"))
    girdi = EihracatGirdisi(giderler=e["giderler"], yurt_disi_satis_tl=e.get("yurt_disi_satis_tl"),
                            hedef_ulke_payi=e.get("hedef_ulke_payi") or 0.0,
                            turk_urun_payi=1.0 if e.get("turk_urun_payi") is None else e["turk_urun_payi"])
    return sozluk(hesapla(girdi, durum))


def _yanit(p: FinancialProfile | None, db: Session) -> dict:
    return {"hazirlik": (p.hazirlik or {}) if p else {}, "yol_haritasi": yol_haritasi(p, db),
            "eihracat": eihracat_sonucu(p),
            "kalemler": [{"kod": k.kod, "etiket": k.etiket, "madde": k.madde, "aciklama": k.aciklama}
                         for k in KALEMLER.values()]}


def _profil(db: Session, org: Organization) -> FinancialProfile | None:
    return db.query(FinancialProfile).filter(FinancialProfile.org_id == org.id).first()


@router.get("/api/hazirlik")
def hazirlik_getir(current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    return _yanit(_profil(db, current_org), db)


@router.put("/api/hazirlik")
def hazirlik_kaydet(girdi: HazirlikGirdisi, current_org: Organization = Depends(get_current_org),
                    db: Session = Depends(get_db)):
    _dogrula(girdi)
    p = _profil(db, current_org)
    if p is None:
        raise HTTPException(status_code=409, detail="Önce işletme profilinizi kaydedin.")
    mevcut = dict(p.hazirlik or {})
    durumlar = {**mevcut.get("durumlar", {}), **girdi.durumlar}
    mevcut["durumlar"] = {k: v for k, v in durumlar.items() if v is not None}
    if girdi.eihracat is not None:
        mevcut["eihracat"] = girdi.eihracat.model_dump()
    p.hazirlik = mevcut          # JSON sütunu: yeni nesne atanmalı (yerinde değişiklik izlenmez)
    db.commit()
    return _yanit(p, db)


def _self_test() -> int:
    from app.models import Tesvik

    t_kosgeb = Tesvik(id=1, kurum="KOSGEB", baslik="Girişimci", basvuru_sartlari=["KOBİ olmak"])
    t_tic = Tesvik(id=2, kurum="Ticaret Bakanlığı", baslik="Reklam",
                   basvuru_sartlari=["Bir ihracatçı birliğine üye olmak", "Ticaret Bakanlığı Destek Yönetim Sistemi "
                                     "(DYS) kaydı", "Ön onay için WIPO Madrid Sistemi'ne taraf ülkede marka",
                                     "Destekten önce ön onay alınmalı"])
    t_tarim = Tesvik(id=3, kurum="Tarım ve Orman Bakanlığı", baslik="Mazot", basvuru_sartlari=["ÇKS kaydı"])
    t_m6 = Tesvik(id=4, kurum="Ticaret Bakanlığı", baslik="Pazar Araştırması",
                  basvuru_yeri="Bakanlıkça görevlendirilen İhracatçı Birliği Genel Sekreterliğine DYS üzerinden")
    t_uye = Tesvik(id=5, kurum="Ticaret Bakanlığı", baslik="Marka",
                   basvuru_yeri="Üyesi olunan İhracatçı Birliği Genel Sekreterliğine DYS üzerinden")
    p = FinancialProfile(sektor="e-ticaret", sirket_turu="sahis", hazirlik={"durumlar": {"dys_kaydi": True}})
    k = _kopya(p, sirket_turu="limited")
    k_ = [
        ("KOSGEB kurum kuralı", program_adimlari(t_kosgeb) == ["kosgeb_kaydi"]),
        ("Ticaret: birlik, DYS, Madrid, ön onay", program_adimlari(t_tic) == ["birlik_uyeligi", "dys_kaydi",
                                                                             "madrid_marka", "on_onay"]),
        ("ÇKS kalıbı", program_adimlari(t_tarim) == ["cks"]),
        ("görevlendirilen birlik üyelik şartı sayılmaz (5973 m.6)", program_adimlari(t_m6) == ["dys_kaydi"]),
        ("'üyesi olunan İhracatçı Birliği' (büyük İ) üyelik şartıdır", program_adimlari(t_uye) == ["birlik_uyeligi",
                                                                                               "dys_kaydi"]),
        ("karşı-olgu kopyası değişir, asıl profil değişmez", k.sirket_turu == "limited" and p.sirket_turu == "sahis"
         and k.hazirlik == p.hazirlik and k.id is None),
        ("her adımın açıklaması dolu", all(a.baslik and a.nasil for a in ADIMLAR.values())),
        ("hesaplayıcının adım kodları katalogda", {"sirket", "birlik_uyeligi", "madrid_marka", "perakende_statusu"}
         <= set(ADIMLAR)),
    ]
    for ad, ok in k_:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in k_)
    print(f"\nself-test: {gecen}/{len(k_)} geçti")
    return 0 if gecen == len(k_) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
