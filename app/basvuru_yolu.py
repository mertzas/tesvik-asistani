"""Başvuru yol haritası: bir teşvik bulunduktan sonra "bunu nasıl alırım?" sorusunun cevabı.

Yol haritası üç kaynaktan kurulur ve HİÇBİR ŞEY UYDURULMAZ:
  1. Teşvik kaydının kendi alanları (başvuru şartları, belgeler, yeri, süresi, ödeme süresi, aktiflik).
  2. Kuruma özgü genel süreç (hangi kapıdan başvurulur) - yalnız kamuya açık, kurum sayfalarında
     değişmeden duran bilgiler; ayrıntı ve tarih için daima resmi kaynağa yönlendirilir.
  3. Kullanıcının profili (çiftçi/KOBİ/girişimci, il) ve doğrulanmış il müdürlüğü iletişim satırları.

Kayıtta olmayan bilgi için "teyit edin" adımı eklenir; telefon/adres yalnızca doğrulanmış tablolardan gelir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (FinancialProfile, IlKosgebMudurlugu, IlTarimMudurlugu, KurumIletisim, Tesvik)

TARIM_KURUMLARI = {"tarım bakanlığı", "tarim bakanligi", "tkdk"}


def _kurum(t: Tesvik) -> str:
    return (t.kurum or "").strip().lower()


def _tarim_mi(t: Tesvik, profil: FinancialProfile | None) -> bool:
    if _kurum(t) in TARIM_KURUMLARI or "tarım" in _kurum(t):
        return True
    return bool(profil and (profil.sektor or "").lower() == "tarim" and (t.kategori or "").lower() == "tarim")


def _adim(baslik: str, aciklama: str, *, tur: str = "yap", link: str | None = None,
          liste: list[str] | None = None) -> dict:
    return {"baslik": baslik, "aciklama": aciklama, "tur": tur, "link": link, "liste": liste or []}


def _il_iletisim(db: Session, t: Tesvik, profil: FinancialProfile | None) -> dict | None:
    """Başvuru kapısı olan il müdürlüğünün DOĞRULANMIŞ iletişimi (yoksa None)."""
    il = ((profil.bolge if profil else None) or "").strip()
    if not il:
        return None
    if _tarim_mi(t, profil):
        r = db.query(IlTarimMudurlugu).filter(IlTarimMudurlugu.il_adi.ilike(il)).first()
        if r is None:
            return None
        if r.url_dogrulandi:
            return {"ad": f"{r.il_adi} Tarım ve Orman İl Müdürlüğü", "telefon": r.telefon, "adres": r.adres,
                    "dogrulama_tarihi": str(r.dogrulama_tarihi), "kaynak_url": r.kaynak_url}
        return {"ad": f"{r.il_adi} Tarım ve Orman İl Müdürlüğü", "telefon": None, "adres": None,
                "dogrulama_tarihi": None, "kaynak_url": r.kaynak_url}
    if _kurum(t) == "kosgeb":
        r = db.query(IlKosgebMudurlugu).filter(IlKosgebMudurlugu.il_adi.ilike(il)).first()
        if r is None:
            return None
        return {"ad": r.mudurluk_adi, "telefon": r.telefon, "adres": r.adres,
                "dogrulama_tarihi": str(r.dogrulama_tarihi), "kaynak_url": r.kaynak_url}
    return None


def _kurum_iletisim(db: Session, t: Tesvik) -> dict | None:
    k = db.query(KurumIletisim).filter(KurumIletisim.kurum == t.kurum).first()
    if k is None:
        return None
    return {"ad": k.kurum_tam_ad or k.kurum, "telefon": k.cagri_merkezi_no or k.genel_merkez_no,
            "adres": k.adres, "dogrulama_tarihi": str(k.dogrulama_tarihi), "kaynak_url": k.kaynak_url}


def _kurum_sureci(t: Tesvik, profil: FinancialProfile | None) -> tuple[list[dict], list[str]]:
    """Kuruma özgü genel süreç adımları ve ön hazırlık maddeleri."""
    kurum = _kurum(t)
    adimlar: list[dict] = []
    hazirlik: list[str] = []
    if _tarim_mi(t, profil):
        hazirlik += ["e-Devlet şifresi (başvuru ve ÇKS işlemleri e-Devlet üzerinden de yapılabilir)",
                     "Çiftçi Kayıt Sistemi (ÇKS) kaydı - yoksa önce İlçe Tarım Müdürlüğü'nden yaptırın",
                     "Arazi/parsel belgeleri (tapu veya kira sözleşmesi)"]
        adimlar.append(_adim("Çiftçi Kayıt Sistemi (ÇKS) kaydınızı kontrol edin",
                             "Tarımsal desteklerin çoğu ÇKS'ye kayıtlı olmayı şart koşar. Kaydınız ve parsel "
                             "bilgileriniz güncel değilse İlçe Tarım ve Orman Müdürlüğü'ne başvurarak güncelleyin."))
    elif kurum == "kosgeb":
        hazirlik += ["e-Devlet şifresi (KOSGEB sistemine e-Devlet ile girilir)",
                     "Girişim/işletme bilgi formu ve vergi levhası, (varsa) faaliyet belgesi"]
        adimlar.append(_adim("KOSGEB'e girişimci/işletme olarak kaydolun",
                             "Destek başvuruları KOSGEB'in çevrimiçi sistemi üzerinden yapılır; önce işletme "
                             "kaydınızı oluşturun ve bilgilerinizin güncel olduğunu kontrol edin."))
    elif kurum in ("tübitak", "tubitak"):
        hazirlik += ["TÜBİTAK çevrimiçi başvuru sistemine kullanıcı hesabı",
                     "Proje önerisi (amaç, yöntem, iş paketleri, bütçe)"]
        adimlar.append(_adim("Proje önerinizi hazırlayın",
                             "TÜBİTAK destekleri proje bazlıdır; öneri çağrı duyurusundaki şablon ve "
                             "takvime göre hazırlanıp çevrimiçi sistemden yüklenir."))
    elif kurum == "kgf":
        hazirlik += ["Çalıştığınız banka(lar)ın KGF kefaletli kredi sunduğunu teyit edin",
                     "Güncel mali tablolar (bilanço/gelir tablosu) ve vergi levhası"]
        adimlar.append(_adim("Bankanıza başvurun",
                             "KGF kredi vermez, kredi için kefalet sağlar. Başvuruyu KGF'nin protokollü olduğu "
                             "bankaya yaparsınız; teminat yetersizse banka KGF kefaletiyle devam eder."))
    elif "hazine" in kurum or "ticaret" in kurum or "sanayi" in kurum:
        hazirlik += ["e-Devlet şifresi / kurumun çevrimiçi sistemi için yetkilendirme",
                     "Yatırım/proje tutarı, fizibilite veya iş planı"]
    return adimlar, hazirlik


def _aciklik_adimi(t: Tesvik) -> dict | None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bitis = t.bitis_tarihi.replace(tzinfo=None) if t.bitis_tarihi is not None else None
    if t.aktif_mi is False:
        return _adim("Program kapalı görünüyor", t.durum_notu or "Bu program şu an başvuruya kapalı olabilir; "
                     "yenilenip yenilenmeyeceğini kurumdan sorun.", tur="uyari")
    if bitis is not None and bitis < now:
        return _adim("Son başvuru tarihi geçmiş görünüyor",
                     f"Kayıttaki bitiş tarihi {bitis:%d.%m.%Y}. Yeni dönem için kurum duyurularını takip edin.",
                     tur="uyari")
    if t.aktif_mi is None:
        return _adim("Önce programın hâlâ açık olduğunu teyit edin",
                     "Bu programın başvuruya açık olduğu henüz tarafımızca doğrulanmadı. Başvuru hazırlığına "
                     "başlamadan resmi sayfadan veya kurum çağrı merkezinden teyit alın.", tur="uyari",
                     link=t.kaynak_url)
    return None


def basvuru_yolu(t: Tesvik, profil: FinancialProfile | None, db: Session,
                 eksik_kriterler: list[str] | None = None) -> dict:
    """Seçilen teşvik için kişiselleştirilmiş, sıralı başvuru yol haritası."""
    adimlar: list[dict] = []
    uyarilar: list[str] = []

    aciklik = _aciklik_adimi(t)
    if aciklik:
        adimlar.append(aciklik)

    kurum_adimlari, hazirlik = _kurum_sureci(t, profil)

    sartlar = list(t.basvuru_sartlari or [])
    if sartlar or eksik_kriterler:
        aciklama = "Başvurmadan önce aşağıdaki şartları sağladığınızdan emin olun."
        if eksik_kriterler:
            aciklama += " Profilinize göre aşağıdakiler eksik veya belirsiz görünüyor - önce bunları giderin."
        adimlar.append(_adim("Uygunluğunuzu doğrulayın", aciklama, tur="kontrol",
                             liste=[*(f"Eksik/belirsiz: {e}" for e in (eksik_kriterler or [])), *sartlar]))
    else:
        adimlar.append(_adim("Uygunluk şartlarını resmi kaynaktan okuyun",
                             "Bu program için şart listesi sistemimizde işlenmedi; çağrı/mevzuat metnindeki "
                             "kimlere açık olduğu ve hariç tutulanlar bölümünü okuyun.", tur="kontrol",
                             link=t.kaynak_url))

    adimlar.extend(kurum_adimlari)

    belgeler = list(t.gerekli_belgeler or [])
    if belgeler or hazirlik:
        adimlar.append(_adim("Belgeleri toplayın",
                             "Başvuru dosyanız için aşağıdaki belgeleri hazırlayın; eksik belge başvurunun "
                             "reddine veya gecikmesine yol açar.", tur="belge", liste=[*hazirlik, *belgeler]))
    else:
        adimlar.append(_adim("Gerekli belgeleri kurumdan öğrenin",
                             "Belge listesi sistemimizde işlenmedi; resmi kaynaktaki başvuru kılavuzundan veya "
                             "kurumdan öğrenin.", tur="belge", link=t.kaynak_url))

    kapi = t.basvuru_yeri
    iletisim = _il_iletisim(db, t, profil) or _kurum_iletisim(db, t)
    if kapi or iletisim:
        aciklama = f"Başvuru yeri: {kapi}." if kapi else "Başvuru için ilgili kurumla iletişime geçin."
        if t.basvuru_suresi:
            aciklama += f" Başvuru dönemi: {t.basvuru_suresi}."
        adimlar.append(_adim("Başvurunuzu yapın", aciklama, tur="basvuru", link=t.kaynak_url))
    else:
        adimlar.append(_adim("Başvuru kapısını teyit edin",
                             "Başvurunun nereye/nasıl yapılacağı sistemimizde işlenmedi. Resmi kaynaktaki "
                             "başvuru bölümünü izleyin." + (f" Dönem: {t.basvuru_suresi}." if t.basvuru_suresi else ""),
                             tur="basvuru", link=t.kaynak_url))

    sonuc = "Başvurunuz değerlendirilir; eksik varsa kurum sizden tamamlamanızı ister."
    if t.destek_verilme_suresi:
        sonuc += f" Tahmini ödeme/sonuçlanma süresi: {t.destek_verilme_suresi}."
    if t.tutari_hesaplama_formulu:
        sonuc += f" Tutar: {t.tutari_hesaplama_formulu}"
    adimlar.append(_adim("Sonucu bekleyin ve takip edin", sonuc, tur="takip"))

    if not t.kaynak_url:
        uyarilar.append("Bu kayıt için resmi kaynak bağlantısı yok; bilgileri kuruma sorarak teyit edin.")
    uyarilar.append("Tarihler, tutarlar ve şartlar değişebilir; başvurudan önce resmi kaynağı kontrol edin. "
                    "Bu rehber bilgilendirme amaçlıdır, başvuru garantisi vermez.")

    for i, a in enumerate(adimlar, 1):
        a["no"] = i

    return {
        "tesvik_id": t.id,
        "baslik": t.baslik,
        "kurum": t.kurum,
        "aktif_mi": t.aktif_mi,
        "adimlar": adimlar,
        "iletisim": iletisim,
        "kurum_iletisim": _kurum_iletisim(db, t),
        "kaynak_url": t.kaynak_url,
        "uyarilar": uyarilar,
    }
