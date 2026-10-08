"""Ana sayfa özeti (2026-10-08): kullanıcının "bana ne uygun, son tarih ne, sırada ne var" sorusunu tek çağrıda yanıtlar.

Önceki açılış ekranı SaaS sayaçlarını (kalan sorgu, aktif üye) gösteriyordu; eşleşen destekler uzun profil formunun
altındaydı. Bu modül yeni veri üretmez: profil, eşleştirme (app.matching), çağrılar (app.cagrilar), kontrol listeleri
(app.basvuru_listesi) ve İKAS bağlantısını birleştirir; "sıradaki adım" kuralları burada, test edilebilir biçimde durur.

    python -m app.ozet --self-test
"""
from __future__ import annotations

import sys
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_org
from app.models import BasvuruTakibi, FinancialProfile, IkasBaglanti, Organization, PlanType, Tesvik, get_db
from app.nace_9903 import BOLGE_ILLERI, il_bolgesi

router = APIRouter(tags=["ana sayfa"])

# Eşleşmeyi en çok etkileyen alanlar ve kullanıcıya gösterilecek gerekçe (sıra = önem).
TEMEL_ALANLAR: list[tuple[str, str, str]] = [
    ("sektor", "Sektör", "Hangi kurumun programlarının size açık olduğunu belirler."),
    ("bolge", "İl", "Yatırım teşvik bölgesi, kalkınma ajansı ve il bazlı tarım destekleri ile göre değişir."),
    ("sirket_turu", "Şirket türü", "Şahıs işletmesi ihracat ve TÜBİTAK desteklerinin çoğundan doğrudan yararlanamaz."),
    ("calisan_sayisi", "Çalışan sayısı", "KOBİ ölçeğini ve istihdam desteklerini belirler."),
    ("yillik_ciro", "Yıllık ciro", "KOBİ ölçeğini ve kredi/kefalet tavanlarını belirler."),
    ("hedefler", "Hedefler", "Yatırım, ihracat, Ar-Ge, istihdam hedefine göre programlar öne çıkar."),
]
EK_ALANLAR: list[tuple[str, str, str]] = [
    ("nace_kodu", "NACE kodu", "Sektöre özel programlarda daha kesin eşleşme sağlar."),
    ("kurulus_tarihi", "Kuruluş tarihi", "Genç işletme ve girişimci programları kuruluş yaşına bakar."),
]
YAKLASAN_GUN = 60
EN_COK = 5


def il_listesi() -> list[str]:
    """81 il, Türkçe alfabeye göre."""
    alfabe = "abcçdefgğhıijklmnoöprsştuüvyz"
    sira = {h: i for i, h in enumerate(alfabe)}

    def anahtar(il: str):
        kucuk = il.replace("İ", "i").replace("I", "ı").lower().replace("â", "a")
        return [sira.get(h, 100) for h in kucuk]
    return sorted({il for iller in BOLGE_ILLERI.values() for il in iller}, key=anahtar)


def _dolu(deger) -> bool:
    return deger not in (None, "", [], {}) and not (isinstance(deger, str) and deger == "genel")


def profil_durumu(p: FinancialProfile | None) -> dict:
    if p is None:
        return {"var": False, "tamamlanma": 0, "eksikler": [{"alan": a, "etiket": e, "neden": n}
                                                             for a, e, n in TEMEL_ALANLAR], "uyarilar": []}
    eksik = [{"alan": a, "etiket": e, "neden": n} for a, e, n in TEMEL_ALANLAR if not _dolu(getattr(p, a, None))]
    ek_eksik = [{"alan": a, "etiket": e, "neden": n} for a, e, n in EK_ALANLAR if not _dolu(getattr(p, a, None))]
    uyarilar = []
    if p.bolge and il_bolgesi(p.bolge) is None:
        uyarilar.append(f"'{p.bolge}' bir il adı olarak tanınmadı; il bazlı destekler eşleşmeyebilir. Listeden seçin.")
    puan = (len(TEMEL_ALANLAR) - len(eksik)) * 14 + (len(EK_ALANLAR) - len(ek_eksik)) * 8
    return {"var": True, "tamamlanma": min(100, puan), "eksikler": eksik + ek_eksik, "uyarilar": uyarilar}


def sonraki_adim(profil: dict, one_cikan: list[dict], basvurular: list[dict], yaklasan: list[dict]) -> dict:
    """Tek, somut öneri. Öncelik: profil yok > temel alan eksik > son başvurusu yakın ve listesi bitmemiş >
    hiç kontrol listesi yok > devam eden liste > profili ayrıntılandır."""
    if not profil["var"]:
        return {"metin": "İşletme profilinizi doldurun; size uygun destekleri hemen listeleyelim.",
                "eylem": "profil", "dugme": "Profili doldur"}
    temel_eksik = [e for e in profil["eksikler"] if e["alan"] in {a for a, _, _ in TEMEL_ALANLAR}]
    if temel_eksik:
        return {"metin": f"{temel_eksik[0]['etiket']} bilgisini ekleyin: {temel_eksik[0]['neden']}",
                "eylem": "profil", "dugme": "Profili tamamla"}
    takipte = {b["tesvik_id"]: b for b in basvurular}
    for c in yaklasan:
        b = takipte.get(c["tesvik_id"])
        # 0/0 liste (kayıtta şart/belge yok) tamamlanmış sayılmaz: başvuru hâlâ yapılmalı.
        if c["durum"] == "acik" and c["kalan_gun"] is not None and c["kalan_gun"] <= 30 and (
                b is None or b["toplam"] == 0 or b["tamamlanan"] < b["toplam"]):
            ne = "ön kayıt son gününe" if c.get("on_kayit_son") else "son başvuruya"
            return {"metin": f"{c['baslik']}: {ne} {c['kalan_gun']} gün kaldı. Kontrol listesini tamamlayın.",
                    "eylem": "liste", "tesvik_id": c["tesvik_id"], "dugme": "Kontrol listesini aç"}
    if one_cikan and not basvurular:
        e = one_cikan[0]
        return {"metin": f"En uygun destek: {e['baslik']}. Şartlarını ve belgelerini kontrol listesinde görün.",
                "eylem": "liste", "tesvik_id": e["id"], "dugme": "Kontrol listesini aç"}
    eksik_liste = [b for b in basvurular if b["tamamlanan"] < b["toplam"]]
    if eksik_liste:
        b = eksik_liste[0]
        return {"metin": f"{b['baslik']} için {b['toplam'] - b['tamamlanan']} madde kaldı.",
                "eylem": "liste", "tesvik_id": b["tesvik_id"], "dugme": "Devam et"}
    if not one_cikan:
        return {"metin": "Profilinize uyan açık program bulunamadı; hedeflerinizi ve sektörünüzü gözden geçirin.",
                "eylem": "profil", "dugme": "Profili düzenle"}
    return {"metin": "Uygun desteklerin tamamını ve tahmini tutarları inceleyin.", "eylem": "destekler",
            "dugme": "Uygun destekler"}


@router.get("/api/iller")
def iller():
    """Profil formundaki il listesi (9903 sayılı Karar EK-2'deki 81 il)."""
    return {"iller": il_listesi()}


@router.get("/api/ozet")
def ozet(current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    from app.basvuru_listesi import _yanit
    from app.cagrilar import program_cagrilari
    from app.matching import esles

    bugun = date.today()
    p = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    profil = profil_durumu(p)

    eslesmeler = esles(p, db) if p is not None else []
    one_cikan, yaklasan = [], []
    for e in eslesmeler:
        cagrilar = program_cagrilari(e.tesvik, bugun, kapanmis_en_cok=0)
        cagri = cagrilar[0] if cagrilar else None
        if len(one_cikan) < 3:
            one_cikan.append({"id": e.tesvik.id, "kurum": e.tesvik.kurum, "baslik": e.tesvik.baslik, "skor": e.skor,
                              "tesvil_tutari": e.tesvik.tesvil_tutari, "cagri": cagri})
        for c in cagrilar:
            ufuk = c["kalan_gun"] if c["kalan_gun"] is not None else 0
            if c["durum"] in ("acik", "yaklasan") and ufuk <= YAKLASAN_GUN:
                yaklasan.append({**c, "tesvik_id": e.tesvik.id, "baslik": e.tesvik.baslik, "kurum": e.tesvik.kurum})

    basvurular = []
    for k in (db.query(BasvuruTakibi).filter(BasvuruTakibi.org_id == current_org.id)
              .order_by(BasvuruTakibi.guncelleme.desc()).limit(EN_COK).all()):
        t = db.get(Tesvik, k.tesvik_id)
        if t is None:
            continue
        y = _yanit(t, k)
        basvurular.append({"tesvik_id": t.id, "baslik": t.baslik, "kurum": t.kurum, "tamamlanan": y["tamamlanan"],
                           "toplam": y["toplam"], "taslak_var": bool(k.taslak),
                           "cagri": (y["cagrilar"][0] if y["cagrilar"] and y["cagrilar"][0]["durum"] != "kapandi"
                                     else None)})
    # Kullanıcının takip ettiği başvuruların tarihleri de yaklaşanlara girer: program artık ilk eşleşmelerde
    # olmasa da (profil değişti, limit) son günü kaçmamalı. Tarayıcı denemesi 2026-10-08: takipteki 1501'in ön
    # kaydına 14 gün varken "sıradaki adım" eşleşme listesindeki 23 günlük çağrıyı gösteriyordu.
    listedeki = {c["tesvik_id"] for c in yaklasan}
    for b in basvurular:
        c = b["cagri"]
        if (c and b["tesvik_id"] not in listedeki and c["durum"] in ("acik", "yaklasan")
                and (c["kalan_gun"] or 0) <= YAKLASAN_GUN):
            yaklasan.append({**c, "tesvik_id": b["tesvik_id"], "baslik": b["baslik"], "kurum": b["kurum"]})
    yaklasan.sort(key=lambda c: (c["son_gun"] or "9999-12-31"))

    ikas = None
    b = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).first()
    if b is not None:
        o = b.son_ozet or {}
        ikas = {"durum": b.baglanti_durumu, "magaza": b.store_name, "siparis": o.get("siparis_sayisi"),
                "ciro": o.get("yillik_ciro"), "yurt_disi": o.get("yurt_disi_siparis")}

    from app.hazirlik import eihracat_sonucu, yol_haritasi

    e = eihracat_sonucu(p)
    adimlar = [a for a in yol_haritasi(p, db)["adimlar"] if not a["tamam"]]
    hazirlik = {
        # E-ihracat hesaplayıcısını öne çıkarma ölçütü: beyan edilen sektör/hedef ya da İKAS'ta yurt dışı sipariş.
        "eihracat_ilgili": bool(p is not None and (p.sektor in ("e-ticaret", "ihracat")
                                                  or {"ihracat", "e-ticaret"} & set(p.hedefler or [])
                                                  or (ikas or {}).get("yurt_disi"))),
        "eihracat": ({k: e[k] for k in ("simdi_tl", "hazirlikla_tl", "teyitle_tl", "aylik_bekleme_tl")}
                     if e else None),
        "ilk_adim": ({k: adimlar[0][k] for k in ("kod", "baslik", "program_sayisi")} if adimlar else None),
        "acik_adim_sayisi": len(adimlar),
    }

    return {
        "profil": profil,
        "hazirlik": hazirlik,
        "eslesme_sayisi": len(eslesmeler),
        "onizleme": current_org.plan == PlanType.FREE,
        "one_cikanlar": one_cikan,
        "yaklasan_son_basvurular": yaklasan[:EN_COK],
        "basvurular": basvurular,
        "ikas": ikas,
        "sonraki_adim": sonraki_adim(profil, one_cikan, basvurular, yaklasan),
    }


def _self_test() -> int:
    p_yok = profil_durumu(None)
    tam = FinancialProfile(sektor="e-ticaret", bolge="Konya", sirket_turu="limited", calisan_sayisi=5,
                           yillik_ciro=1e6, hedefler=["ihracat"], nace_kodu="47.91", kurulus_tarihi=date(2020, 1, 1))
    eksik = FinancialProfile(sektor="genel", bolge="Konyaa", calisan_sayisi=5)
    pd_tam, pd_eksik = profil_durumu(tam), profil_durumu(eksik)
    yaklasan = [{"tesvik_id": 7, "baslik": "İstihdamı Koruma", "durum": "acik", "kalan_gun": 12, "kapanis": "2026-10-20"}]
    k = [
        ("81 il, Türkçe sıralı", len(il_listesi()) == 81 and il_listesi()[0] == "Adana"
         and il_listesi().index("Çanakkale") < il_listesi().index("Denizli")
         and il_listesi().index("İstanbul") > il_listesi().index("Iğdır")),
        ("profil yok: %0 ve 6 temel eksik", p_yok["tamamlanma"] == 0 and len(p_yok["eksikler"]) == 6),
        ("tam profil %100", pd_tam["tamamlanma"] == 100 and not pd_tam["eksikler"]),
        ("'genel' sektör eksik sayılır, tanınmayan il uyarısı", pd_eksik["eksikler"][0]["alan"] == "sektor"
         and pd_eksik["uyarilar"] and "Konyaa" in pd_eksik["uyarilar"][0]),
        ("sıradaki adım: profil yok", sonraki_adim(p_yok, [], [], [])["eylem"] == "profil"),
        ("sıradaki adım: temel alan eksik", "Sektör" in sonraki_adim(pd_eksik, [], [], [])["metin"]),
        ("sıradaki adım: 30 gün içinde kapanan çağrı önce", sonraki_adim(pd_tam, [{"id": 1, "baslik": "X"}], [], yaklasan)
         == {"metin": "İstihdamı Koruma: son başvuruya 12 gün kaldı. Kontrol listesini tamamlayın.", "eylem": "liste",
             "tesvik_id": 7, "dugme": "Kontrol listesini aç"}),
        ("listesi tamamlanmışsa yakın çağrı atlanır", sonraki_adim(
            pd_tam, [{"id": 1, "baslik": "X"}], [{"tesvik_id": 7, "baslik": "İ", "tamamlanan": 3, "toplam": 3}], yaklasan)
         ["eylem"] == "destekler"),
        ("hiç liste yoksa en uygun desteğin listesi", sonraki_adim(pd_tam, [{"id": 1, "baslik": "X"}], [], [])
         ["tesvik_id"] == 1),
    ]
    for ad, ok in k:
        print(("  ✓ " if ok else "  ✗ ") + ad)
    gecen = sum(ok for _, ok in k)
    print(f"self-test: {gecen}/{len(k)} geçti")
    return 0 if gecen == len(k) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print("Kullanım: python -m app.ozet --self-test")
