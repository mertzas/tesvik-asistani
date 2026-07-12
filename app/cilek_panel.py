"""
Çilek Üretim Yönetim Paneli - API Router

Tek bir agregat endpoint (GET /api/cilek/panel/{parsel_id}) tüm dashboard'u
tek çağrıda döner - kırsalda zayıf mobil bağlantıda çiftçinin telefonunun
6 ayrı istek atmasını önlemek içindir. Ayrıca IoT/sensör cihazlarının ve
manuel giriş formlarının veri POST edebileceği ingestion endpoint'leri var.

Tum endpoint'ler mevcut get_current_org ile multi-tenant izolasyonu takip
eder; bir organizasyon baska bir organizasyonun parseline erisemez.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models import Organization, get_db
from app.auth import get_current_org
from app.models_cilek import (
    Parsel, SensorOkuma, FertigasyonTank, SulamaDongusu,
    Ilaclama, PazarFiyati, HasatKaydi, SogukZincirOkuma, GiderKalemi,
    SensorTipi, TankTipi, KaliteSinifi, PazarKaynagi, GiderKategorisi,
)
from app.schemas_cilek import (
    ParselCreate, ParselResponse,
    SensorOkumaCreate,
    IlaclamaCreate,
    PazarFiyatiCreate,
    HasatKaydiCreate,
    SogukZincirOkumaCreate,
    GiderKalemiCreate,
    CilekPaneliResponse,
)
from app.cilek_engine import (
    toprak_nemi_karti, toprak_ec_karti, don_riski_hesapla, mantar_riski_hesapla,
    erken_uyari_hesapla,
    fertigasyon_paneli, hasat_kilidi_durumu, pazar_paneli,
    hasat_performansi_bugun, soguk_zincir_durumu, finansal_saglik_hesapla,
)
from app.gubre_rehberi import gubre_dozaj_oneri_getir

router = APIRouter(prefix="/api/cilek", tags=["cilek-paneli"])


def _parsel_getir(db: Session, parsel_id: int, org: Organization) -> Parsel:
    parsel = db.query(Parsel).filter(Parsel.id == parsel_id, Parsel.org_id == org.id).first()
    if parsel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parsel bulunamadı")
    return parsel


# ============ PARSEL YÖNETİMİ ============

@router.post("/parseller", response_model=ParselResponse)
def parsel_olustur(
    request: ParselCreate,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    parsel = Parsel(
        org_id=current_org.id,
        ad=request.ad,
        ortam_tipi=request.ortam_tipi,
        alan_dekar=request.alan_dekar,
        cesit=request.cesit,
        dikim_tarihi=request.dikim_tarihi,
        enlem=request.enlem,
        boylam=request.boylam,
    )
    db.add(parsel)
    db.commit()
    db.refresh(parsel)
    return parsel


@router.get("/parseller", response_model=list[ParselResponse])
def parsel_listele(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    return db.query(Parsel).filter(Parsel.org_id == current_org.id, Parsel.aktif == True).all()  # noqa: E712


# ============ ANA PANEL (agregat) ============

@router.get("/panel/{parsel_id}", response_model=CilekPaneliResponse)
def panel_getir(
    parsel_id: int,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    parsel = _parsel_getir(db, parsel_id, current_org)

    toprak_nemi = toprak_nemi_karti(db, parsel_id)
    toprak_ec = toprak_ec_karti(db, parsel_id)
    don_riski = don_riski_hesapla(db, parsel)
    mantar_riski = mantar_riski_hesapla(db, parsel)
    erken_uyari = erken_uyari_hesapla(parsel)
    fertigasyon = fertigasyon_paneli(db, parsel_id)
    hasat_kilidi = hasat_kilidi_durumu(db, parsel_id)
    pazar = pazar_paneli(db)
    hasat_performansi = hasat_performansi_bugun(db, parsel_id)
    soguk_zincir = soguk_zincir_durumu(db, current_org.id)
    finansal_saglik = finansal_saglik_hesapla(db, parsel_id)
    gubre_onerisi = gubre_dozaj_oneri_getir(parsel.dikim_tarihi, parsel.alan_dekar)

    kritik_uyarilar = []
    if don_riski.risk_seviyesi == "kritik":
        kritik_uyarilar.append(don_riski.mesaj)
    if mantar_riski.risk_seviyesi == "kritik":
        kritik_uyarilar.append(mantar_riski.mesaj)
    if hasat_kilidi.kilitli:
        kritik_uyarilar.append(hasat_kilidi.mesaj)
    if erken_uyari.kullanilabilir and erken_uyari.don_riski_bekleniyor_mu:
        kritik_uyarilar.append(erken_uyari.mesaj)
    for tank in fertigasyon.tanklar:
        if tank.risk_seviyesi == "kritik":
            kritik_uyarilar.append(f"{tank.tank_tipi.upper()} tankı kritik seviyede düşük (%{tank.doluluk_yuzde:.0f}).")
    for depo in soguk_zincir:
        if depo.risk_seviyesi == "kritik":
            kritik_uyarilar.append(f"{depo.depo_adi}: {depo.mesaj}")

    return CilekPaneliResponse(
        parsel_id=parsel.id,
        parsel_ad=parsel.ad,
        ortam_tipi=parsel.ortam_tipi.value,
        guncelleme_zamani=datetime.now(timezone.utc),
        kritik_uyarilar=kritik_uyarilar,
        toprak_nemi=toprak_nemi,
        toprak_ec=toprak_ec,
        don_riski=don_riski,
        mantar_riski=mantar_riski,
        erken_uyari=erken_uyari,
        fertigasyon=fertigasyon,
        gubre_onerisi=gubre_onerisi,
        hasat_kilidi=hasat_kilidi,
        pazar=pazar,
        hasat_performansi=hasat_performansi,
        soguk_zincir=soguk_zincir,
        finansal_saglik=finansal_saglik,
    )


@router.get("/gubre-rehberi/{parsel_id}")
def gubre_rehberi_getir(
    parsel_id: int,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Parselin güncel fenolojik evresine göre gübre dozaj önerisi döner."""
    parsel = _parsel_getir(db, parsel_id, current_org)
    return gubre_dozaj_oneri_getir(parsel.dikim_tarihi, parsel.alan_dekar)


@router.get("/gubre-rehberi/{parsel_id}/tum-sezon")
def gubre_rehberi_tum_sezon(
    parsel_id: int,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Tüm sezon boyunca evre-evre gübre planını döner - önceden planlama için."""
    from app.gubre_rehberi import tum_evreleri_listele
    parsel = _parsel_getir(db, parsel_id, current_org)
    evreler = []
    for evre in tum_evreleri_listele():
        alan = parsel.alan_dekar
        evreler.append({
            "evre": evre.ad,
            "gun_araligi": evre.gun_araligi,
            "n_kg_da": evre.n_kg_da,
            "p2o5_kg_da": evre.p2o5_kg_da,
            "k2o_kg_da": evre.k2o_kg_da,
            "cao_kg_da": evre.cao_kg_da,
            "toplam_n_kg": round(evre.n_kg_da * alan, 2) if alan else None,
            "toplam_p2o5_kg": round(evre.p2o5_kg_da * alan, 2) if alan else None,
            "toplam_k2o_kg": round(evre.k2o_kg_da * alan, 2) if alan else None,
            "toplam_cao_kg": round(evre.cao_kg_da * alan, 2) if alan else None,
            "haftalik_uygulama_sikligi": evre.haftalik_uygulama_sikligi,
            "aciklama": evre.aciklama,
            "dikkat": evre.dikkat or None,
        })
    return {"parsel_id": parsel.id, "alan_dekar": parsel.alan_dekar, "evreler": evreler}


# ============ 1. SENSÖR VERİSİ GİRİŞİ (IoT cihazları için) ============

@router.post("/sensor-okuma", status_code=status.HTTP_201_CREATED)
def sensor_okuma_ekle(
    request: SensorOkumaCreate,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    _parsel_getir(db, request.parsel_id, current_org)  # yetki/varlık kontrolü

    try:
        sensor_tipi = SensorTipi(request.sensor_tipi)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Geçersiz sensör tipi: {request.sensor_tipi}")

    okuma = SensorOkuma(
        parsel_id=request.parsel_id,
        sensor_tipi=sensor_tipi,
        deger=request.deger,
        birim=request.birim,
        kaynak=request.kaynak,
    )
    db.add(okuma)
    db.commit()
    return {"status": "ok", "id": okuma.id}


# ============ 2. FERTİGASYON / TANK GÜNCELLEME ============

@router.put("/fertigasyon-tank/{tank_id}")
def tank_doluluk_guncelle(
    tank_id: int,
    doluluk_litre: float,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    tank = (
        db.query(FertigasyonTank)
        .join(Parsel, Parsel.id == FertigasyonTank.parsel_id)
        .filter(FertigasyonTank.id == tank_id, Parsel.org_id == current_org.id)
        .first()
    )
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank bulunamadı")

    tank.doluluk_litre = doluluk_litre
    tank.son_guncelleme = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok"}


# ============ 3. İLAÇLAMA KAYDI (PHI kilidi için) ============

@router.post("/ilaclama", status_code=status.HTTP_201_CREATED)
def ilaclama_ekle(
    request: IlaclamaCreate,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    _parsel_getir(db, request.parsel_id, current_org)

    kayit = Ilaclama(
        parsel_id=request.parsel_id,
        ilac_adi=request.ilac_adi,
        etken_madde=request.etken_madde,
        uygulama_tarihi=request.uygulama_tarihi,
        phi_gun=request.phi_gun,
        doz=request.doz,
        uygulayan=request.uygulayan,
        hedef=request.hedef,
    )
    db.add(kayit)
    db.commit()
    return {"status": "ok", "id": kayit.id, "mesaj": f"PHI süresi ({request.phi_gun} gün) boyunca parsel hasada kilitli olacak."}


# ============ 4. PAZAR FİYATI GİRİŞİ ============

@router.post("/pazar-fiyati", status_code=status.HTTP_201_CREATED)
def pazar_fiyati_ekle(
    request: PazarFiyatiCreate,
    current_org: Organization = Depends(get_current_org),  # auth zorunlu (herkes fiyat yazamasın)
    db: Session = Depends(get_db),
):
    try:
        kaynak = PazarKaynagi(request.kaynak)
        kalite = KaliteSinifi(request.kalite_sinifi)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    kayit = PazarFiyati(
        tarih=request.tarih,
        kaynak=kaynak,
        kalite_sinifi=kalite,
        bolge=request.bolge,
        fiyat_kg=request.fiyat_kg,
        hacim_kg=request.hacim_kg,
    )
    db.add(kayit)
    db.commit()
    return {"status": "ok", "id": kayit.id}


# ============ 5. HASAT KAYDI + SOĞUK ZİNCİR ============

@router.post("/hasat", status_code=status.HTTP_201_CREATED)
def hasat_ekle(
    request: HasatKaydiCreate,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    _parsel_getir(db, request.parsel_id, current_org)

    kalite = None
    if request.kalite_sinifi:
        try:
            kalite = KaliteSinifi(request.kalite_sinifi)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Geçersiz kalite sınıfı: {request.kalite_sinifi}")

    kayit = HasatKaydi(
        parsel_id=request.parsel_id,
        tarih=request.tarih,
        isci_adi=request.isci_adi,
        toplanan_kasa=request.toplanan_kasa,
        kasa_agirlik_kg=request.kasa_agirlik_kg,
        sure_saat=request.sure_saat,
        saatlik_ucret=request.saatlik_ucret,
        kalite_sinifi=kalite,
    )
    db.add(kayit)
    db.commit()
    return {"status": "ok", "id": kayit.id}


@router.post("/soguk-zincir", status_code=status.HTTP_201_CREATED)
def soguk_zincir_ekle(
    request: SogukZincirOkumaCreate,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    kayit = SogukZincirOkuma(
        org_id=current_org.id,
        depo_adi=request.depo_adi,
        sicaklik=request.sicaklik,
        hedef_sicaklik_min=request.hedef_sicaklik_min,
        hedef_sicaklik_max=request.hedef_sicaklik_max,
        parti_no=request.parti_no,
    )
    db.add(kayit)
    db.commit()
    return {"status": "ok", "id": kayit.id}


# ============ 6. GİDER KAYDI (mikro finansal sağlık) ============

@router.post("/gider", status_code=status.HTTP_201_CREATED)
def gider_ekle(
    request: GiderKalemiCreate,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    _parsel_getir(db, request.parsel_id, current_org)

    try:
        kategori = GiderKategorisi(request.kategori)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Geçersiz gider kategorisi: {request.kategori}")

    kayit = GiderKalemi(
        parsel_id=request.parsel_id,
        kategori=kategori,
        tutar=request.tutar,
        tarih=request.tarih,
        aciklama=request.aciklama,
    )
    db.add(kayit)
    db.commit()
    return {"status": "ok", "id": kayit.id}
