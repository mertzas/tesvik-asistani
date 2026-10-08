"""Başvuru kontrol listesi (2026-10-08): bulunan teşvik için şart, belge ve başvuru adımlarını işaretlenebilir liste
olarak sunar ve kullanıcının işaretlerini saklar. Evrak hazırlama desteğinin ilk adımı.

Maddeler kaydın kendi alanlarından üretilir (uydurma madde yok):
  sart    -> basvuru_sartlari   ("Şartı sağlıyorum")
  belge   -> gerekli_belgeler   ("Belge hazır")
  basvuru -> basvuru_yeri (+ basvuru_suresi)  ("Başvuruyu yaptım")
Madde anahtarı metnin özetidir: metin değişirse eski işaret düşer (yanlış madde işaretli görünmez).

Yazdırma/PDF tarayıcıda (window.print) yapılır; sunucuda PDF üretilmez.

    python -m app.basvuru_listesi --self-test
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import basvuru_taslagi
from app.cagrilar import program_cagrilari
from app.auth import get_current_org
from app.models import (BasvuruTakibi, FinancialProfile, IkasBaglanti, Organization, PlanType, Tesvik, get_db,
                        settings)
from app.rate_limit import org_hiz_siniri, sayac as hiz_sayaci

router = APIRouter(prefix="/api/basvuru-listesi", tags=["başvuru kontrol listesi"])

TUR_ETIKETI = {"sart": "Şart", "belge": "Belge", "basvuru": "Başvuru"}
EN_COK_MADDE = 100
GUNLUK_TASLAK_SINIRI = 5  # kuruluş başına; her taslak bir ücretli Claude çağrısı


def _anahtar(tur: str, metin: str) -> str:
    ozet = hashlib.sha1(" ".join(metin.split()).lower().encode("utf-8")).hexdigest()[:10]
    return f"{tur[0]}:{ozet}"


def _liste(deger) -> list[str]:
    if not deger:
        return []
    if isinstance(deger, str):  # eski kayıtlarda tek metin olabilir
        return [deger]
    return [str(x).strip() for x in deger if str(x).strip()]


def maddeler(t: Tesvik) -> list[dict]:
    """Kayıttan sıralı madde listesi: önce şartlar, sonra belgeler, en son başvuru adımı. Aynı metin bir kez."""
    sonuc, gorulen = [], set()

    def ekle(tur: str, metin: str):
        anahtar = _anahtar(tur, metin)
        if anahtar in gorulen:
            return
        gorulen.add(anahtar)
        sonuc.append({"anahtar": anahtar, "tur": tur, "metin": metin})

    for s in _liste(t.basvuru_sartlari):
        ekle("sart", s)
    for b in _liste(t.gerekli_belgeler):
        ekle("belge", b)
    if (t.basvuru_yeri or "").strip():
        metin = f"Başvuruyu yap: {t.basvuru_yeri.strip()}"
        if (t.basvuru_suresi or "").strip():
            metin += f" — {t.basvuru_suresi.strip()}"
        ekle("basvuru", metin)
    return sonuc[:EN_COK_MADDE]


def _yanit(t: Tesvik, kayit: BasvuruTakibi | None) -> dict:
    liste = maddeler(t)
    isaretli = set(kayit.isaretli or []) if kayit else set()
    for m in liste:
        m["isaretli"] = m["anahtar"] in isaretli
    return {
        "tesvik": {"id": t.id, "baslik": t.baslik, "kurum": t.kurum, "kaynak_url": t.kaynak_url,
                   "basvuru_yeri": t.basvuru_yeri, "basvuru_suresi": t.basvuru_suresi, "aktif_mi": t.aktif_mi},
        "maddeler": liste,
        "tamamlanan": sum(m["isaretli"] for m in liste),
        "toplam": len(liste),
        "takipte": kayit is not None,
        "guncelleme": kayit.guncelleme.isoformat() if kayit and kayit.guncelleme else None,
        "taslak": kayit.taslak if kayit else None,
        "taslak_tarihi": kayit.taslak_tarihi.isoformat() if kayit and kayit.taslak_tarihi else None,
        # Dönemsel çağrılar (app/cagrilar.py): açık/yaklaşan önce; yoksa boş liste ("tarih duyurulmadı").
        "cagrilar": program_cagrilari(t),
        "uyari": None if liste else ("Bu destek için şart/belge bilgisi henüz sistemde yok; kurumun resmi "
                                     "sayfasından kontrol edin."),
    }


def _tesvik(db: Session, tesvik_id: int) -> Tesvik:
    t = db.get(Tesvik, tesvik_id)
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teşvik bulunamadı")
    return t


def _kayit(db: Session, org: Organization, tesvik_id: int) -> BasvuruTakibi | None:
    return db.query(BasvuruTakibi).filter(BasvuruTakibi.org_id == org.id,
                                          BasvuruTakibi.tesvik_id == tesvik_id).first()


class IsaretGirdi(BaseModel):
    isaretli: list[str] = Field(default_factory=list, max_length=EN_COK_MADDE)


@router.get("")
def takip_edilenler(current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Kullanıcının kontrol listesi açtığı teşvikler, ilerlemeyle (en son güncellenen başta)."""
    kayitlar = (db.query(BasvuruTakibi).filter(BasvuruTakibi.org_id == current_org.id)
                .order_by(BasvuruTakibi.guncelleme.desc()).all())
    sonuc = []
    for k in kayitlar:
        t = db.get(Tesvik, k.tesvik_id)
        if t is None:
            continue
        y = _yanit(t, k)
        sonuc.append({"tesvik_id": t.id, "baslik": t.baslik, "kurum": t.kurum, "aktif_mi": t.aktif_mi,
                      "tamamlanan": y["tamamlanan"], "toplam": y["toplam"], "guncelleme": y["guncelleme"]})
    return {"listeler": sonuc}


@router.get("/{tesvik_id}")
def liste_getir(tesvik_id: int, current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    return _yanit(_tesvik(db, tesvik_id), _kayit(db, current_org, tesvik_id))


@router.get("/{tesvik_id}/docx", dependencies=[Depends(org_hiz_siniri(30))])
def liste_word(tesvik_id: int, current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Kontrol listesi + başvuru dönemleri + ön taslak tek Word dosyası (app/basvuru_docx.py). Yeni veri üretmez."""
    from urllib.parse import quote

    from fastapi.responses import Response

    from app.basvuru_docx import belge_olustur, dosya_adi
    t = _tesvik(db, tesvik_id)
    ascii_ad, utf8_ad = dosya_adi(t.baslik)
    return Response(
        content=belge_olustur(_yanit(t, _kayit(db, current_org, tesvik_id))),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_ad}\"; filename*=UTF-8''{quote(utf8_ad)}",
                 "Cache-Control": "no-store"})


@router.put("/{tesvik_id}", dependencies=[Depends(org_hiz_siniri(60))])
def isaretleri_kaydet(tesvik_id: int, girdi: IsaretGirdi, current_org: Organization = Depends(get_current_org),
                      db: Session = Depends(get_db)):
    """İşaretli madde anahtarlarını kaydeder (tam liste; işaret kaldırma = listeden çıkarma). İlk kayıt takibi başlatır."""
    t = _tesvik(db, tesvik_id)
    gecerli = {m["anahtar"] for m in maddeler(t)}
    bilinmeyen = sorted(set(girdi.isaretli) - gecerli)
    if bilinmeyen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Liste güncellenmiş olabilir; sayfayı yenileyip tekrar deneyin.")
    simdi = datetime.now(timezone.utc).replace(tzinfo=None)
    kayit = _kayit(db, current_org, tesvik_id)
    if kayit is None:
        kayit = BasvuruTakibi(org_id=current_org.id, tesvik_id=tesvik_id, olusturma=simdi)
        db.add(kayit)
    kayit.isaretli = sorted(set(girdi.isaretli))
    kayit.guncelleme = simdi
    db.commit()
    db.refresh(kayit)
    return _yanit(t, kayit)


@router.post("/{tesvik_id}/taslak")
def taslak_olustur(tesvik_id: int, yontem: str = Query("sablon", pattern="^(sablon|yapay_zeka)$"),
                   current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Başvuru ön taslağı. yontem=sablon (varsayılan, 2026-10-08): yapay zekâsız, kayıtlı verilerden şablonla
    (app/sablon_taslak.py); plan, rıza ve servis gerektirmez, veri yurt dışına çıkmaz. yontem=yapay_zeka: Claude ile
    (app/basvuru_taslagi.py); koşullar ücretli çağrıdan ÖNCE sırayla denetlenir: PRO+ plan, açık rıza (profil
    Anthropic'e/ABD'ye gider), kayıtlı profil, yapılandırılmış servis, günlük sınır."""
    if yontem == "sablon":
        return _sablon_taslak(tesvik_id, current_org, db)
    if current_org.plan == PlanType.FREE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Başvuru taslağı PRO ve üzeri planlarda kullanılabilir.")
    if not current_org.ai_yurtdisi_riza:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Taslak, işletme profilinizi yapay zekâ servisine (Anthropic, ABD) gönderir. "
                                   "Ayarlar bölümünden açık rızanızı verirseniz kullanabilirsiniz.")
    t = _tesvik(db, tesvik_id)
    profil_row = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    if profil_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Önce Profil & Öneriler bölümünden işletme profilinizi kaydedin.")
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Yapay zekâ servisi bu sunucuda yapılandırılmamış.")
    izin, _ = hiz_sayaci.izin_ver(f"taslak:{current_org.id}", GUNLUK_TASLAK_SINIRI, 86400)
    if not izin:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Günlük {GUNLUK_TASLAK_SINIRI} taslak sınırına ulaştınız; yarın tekrar deneyin.")

    from app.ikas_veri_esleme import baglam_alanlari
    from app.rag import profil_sozlugu
    kayit = _kayit(db, current_org, tesvik_id)
    profil = profil_sozlugu(profil_row)
    # Bağlı İKAS mağazası varsa sipariş toplamları (kişisel veri değil) taslağa girer: e-ihracat ve ciro
    # bölümleri [DOLDURUN] yerine mağazanın kendi verisiyle başlar (KVKK metninde belirtildi).
    ikas = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id,
                                         IkasBaglanti.baglanti_durumu == "bagli").first()
    profil.update(baglam_alanlari(ikas.son_ozet if ikas else None))
    try:
        metin, _kullanim = basvuru_taslagi.uret(t, profil, _yanit(t, kayit)["maddeler"])
    except basvuru_taslagi.TaslakHatasi as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    simdi = datetime.now(timezone.utc).replace(tzinfo=None)
    if kayit is None:
        kayit = BasvuruTakibi(org_id=current_org.id, tesvik_id=tesvik_id, isaretli=[], olusturma=simdi)
        db.add(kayit)
    kayit.taslak, kayit.taslak_tarihi, kayit.taslak_model = metin, simdi, settings.CLAUDE_MODEL[:60]
    kayit.guncelleme = simdi
    db.commit()
    db.refresh(kayit)
    return _yanit(t, kayit)


def _profil_ve_ikas(db: Session, org: Organization) -> dict | None:
    from app.ikas_veri_esleme import baglam_alanlari
    from app.rag import profil_sozlugu
    profil_row = db.query(FinancialProfile).filter(FinancialProfile.org_id == org.id).first()
    if profil_row is None:
        return None
    profil = profil_sozlugu(profil_row)
    ikas = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == org.id, IkasBaglanti.baglanti_durumu == "bagli").first()
    profil.update(baglam_alanlari(ikas.son_ozet if ikas else None))
    return profil


def _taslagi_kaydet(db: Session, org: Organization, t: Tesvik, kayit: BasvuruTakibi | None, metin: str,
                    model: str) -> dict:
    simdi = datetime.now(timezone.utc).replace(tzinfo=None)
    if kayit is None:
        kayit = BasvuruTakibi(org_id=org.id, tesvik_id=t.id, isaretli=[], olusturma=simdi)
        db.add(kayit)
    kayit.taslak, kayit.taslak_tarihi, kayit.taslak_model = metin, simdi, model[:60]
    kayit.guncelleme = simdi
    db.commit()
    db.refresh(kayit)
    return _yanit(t, kayit)


def _sablon_taslak(tesvik_id: int, org: Organization, db: Session) -> dict:
    from app import sablon_taslak
    t = _tesvik(db, tesvik_id)
    profil = _profil_ve_ikas(db, org)
    if profil is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Önce Profil & Öneriler bölümünden işletme profilinizi kaydedin.")
    kayit = _kayit(db, org, tesvik_id)
    metin = sablon_taslak.uret(t, profil, _yanit(t, kayit)["maddeler"], program_cagrilari(t))
    return _taslagi_kaydet(db, org, t, kayit, metin, sablon_taslak.MODEL_ADI)


@router.delete("/{tesvik_id}")
def takibi_birak(tesvik_id: int, current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    kayit = _kayit(db, current_org, tesvik_id)
    if kayit is not None:
        db.delete(kayit)
        db.commit()
    return {"mesaj": "Kontrol listesi kaldırıldı."}


def _self_test() -> int:
    t = Tesvik(id=1, baslik="Deneme", kurum="KOSGEB", basvuru_sartlari=["KOBİ olmak", "KOBİ  olmak"],
               gerekli_belgeler=["Başvuru Formu", "Taahhütname"], basvuru_yeri="KBS",
               basvuru_suresi="Sürekli açık")
    m = maddeler(t)
    kontroller = [
        ("tekrar eden şart bir kez", [x["tur"] for x in m] == ["sart", "belge", "belge", "basvuru"]),
        ("başvuru adımı yer + süre", m[-1]["metin"] == "Başvuruyu yap: KBS — Sürekli açık"),
        ("anahtar kararlı", maddeler(t)[1]["anahtar"] == m[1]["anahtar"] and m[1]["anahtar"].startswith("b:")),
        ("metin değişince anahtar değişir", _anahtar("belge", "Başvuru Formu (yeni)") != m[1]["anahtar"]),
        ("boş kayıtta madde yok + uyarı", maddeler(Tesvik(id=2)) == [] and bool(_yanit(Tesvik(id=2), None)["uyari"])),
        ("eski tek metin alanı da okunur", _liste("Tek belge") == ["Tek belge"]),
    ]
    for ad, ok in kontroller:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in kontroller)
    print(f"\nself-test: {gecen}/{len(kontroller)} geçti")
    return 0 if gecen == len(kontroller) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
