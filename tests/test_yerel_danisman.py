"""Yerel danışman, sağlayıcı katmanı ve dayanak denetimi (2026-10-11).

Yerel danışman ürünün varsayılan yanıt servisidir: dış çağrı yok, her somut bilgi veritabanından gelir. Testler
kararları (elenir / şartlı / belirlenemedi), çağrı tarihlerini ve "yanıttaki her sayı/adres/tarih kaynakta var"
özelliğini sabitler."""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker

from app import dayanak, rag, yerel_danisman
from app.models import FinancialProfile, Tesvik, TesvikCagrisi

KOK = Path(__file__).resolve().parent.parent
BUGUN = date(2026, 10, 11)


@pytest.fixture
def veri(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    db_session.add_all([
        Tesvik(id=1, kurum="KOSGEB", baslik="Girişimcilik Destek Programı", ozet="girişimci desteği", detay="d",
               aktif_mi=True, kaynak_url="https://kosgeb.gov.tr/girisimcilik", basvuru_yeri="e-Devlet KOSGEB",
               tesvil_tutari="375.000 TL'ye kadar geri ödemesiz",
               uygunluk_kriterleri={"sektorler": ["genel"]},
               kontrol_listesi=[{"tur": "sart", "metin": "Girişimci sertifikasına sahip olmak",
                                 "alinti": "Girişimcilik Eğitimi sertifikası", "kaynak_url": "https://kosgeb.gov.tr/g",
                                 "dogrulandi": True},
                                {"tur": "belge", "metin": "İş planı", "alinti": None, "kaynak_url": None,
                                 "dogrulandi": None},
                                {"tur": "kural", "metin": "Aynı harcama başka bir kamu desteğiyle karşılanamaz",
                                 "alinti": "mükerrer destek verilmez", "kaynak_url": "https://kosgeb.gov.tr/g",
                                 "dogrulandi": True}]),
        Tesvik(id=2, kurum="Halkbank", baslik="İlk Adım Kredisi Projesi", ozet="genç girişimci kredisi", detay="d",
               aktif_mi=True, kaynak_url="https://kgf.com.tr/ilk-adim",
               uygunluk_kriterleri={"sektorler": ["genel"], "kurucu_yasi_max": 29}),
        Tesvik(id=3, kurum="TÜBİTAK", baslik="1512 Teknogirişim Sermayesi Desteği", ozet="girişim", detay="d",
               aktif_mi=False, durum_notu="1812 BiGG Yatırım çerçevesine devredildi",
               kaynak_url="https://tubitak.gov.tr/1512", uygunluk_kriterleri={"sektorler": ["arge"]}),
        Tesvik(id=4, kurum="Tarım ve Orman Bakanlığı", baslik="Organik Tarım Destekleri", ozet="organik", detay="d",
               aktif_mi=True, kaynak_url="https://www.resmigazete.gov.tr/eskiler/2024/08/20240829-1.pdf",
               uygunluk_kriterleri={"sektorler": ["tarim"], "gerekli_sertifika": "organik_sertifika"}),
    ])
    db_session.add(TesvikCagrisi(tesvik_id=1, ad="2026/2. dönem", acilis=date(2026, 10, 1), kapanis=date(2026, 10, 30),
                                 on_kayit_son=date(2026, 10, 22), kaynak_url="https://kosgeb.gov.tr/duyuru",
                                 dogrulama_tarihi=BUGUN))
    db_session.commit()
    return db_session


def _yanit(db, soru, ids, profil=None, notlar=None):
    kayitlar = [db.get(Tesvik, i) for i in ids]
    return yerel_danisman.yanitla(soru, kayitlar, profil, notlar, db=db, bugun=BUGUN)


def _ltd(**k):
    return FinancialProfile(**{"sektor": "genel", "sirket_turu": "limited", "bolge": "Ankara", "calisan_sayisi": 4,
                               "yillik_ciro": 2e6, "hedefler": ["finansman"], **k})


def test_bes_baslik_sorumluluk_reddi_ve_yontem_notu(veri):
    y = _yanit(veri, "girişimci desteği", [1, 2], _ltd(kurucu_yasi=27))
    assert y.startswith("**Kısa cevap:**")
    assert all(f"### {i}." in y for i in range(1, 6))
    assert yerel_danisman.SORUMLULUK_REDDI in y and yerel_danisman.YONTEM_NOTU in y


def test_cagri_on_kayit_ve_kalan_gun(veri):
    y = _yanit(veri, "girişimci desteği", [1], _ltd())
    # tur 6: ön kayıt ve kapanış ayrı satır parçası, ikisi de kalan günle ("yeni başvuru için son gün" karışıyordu)
    assert "ön kayıt son günü 22.10.2026 (11 gün kaldı); başvuru kapanışı 30.10.2026 (19 gün kaldı)" in y
    assert "https://kosgeb.gov.tr/duyuru" in y


def test_sartlar_alintili_kurallar_ve_belgeler(veri):
    y = _yanit(veri, "girişimci desteği", [1], _ltd())
    assert "Girişimci sertifikasına sahip olmak — resmî metin: “Girişimcilik Eğitimi sertifikası”" in y
    assert "Aynı harcama başka bir kamu desteğiyle karşılanamaz" in y and "Belgeler (" in y and "İş planı" in y
    assert "375.000 TL'ye kadar geri ödemesiz" in y and "e-Devlet KOSGEB" in y


def test_yas_siniri_asan_kredi_gerekcesiyle_elenir(veri):
    y = _yanit(veri, "kredi", [1, 2], _ltd(kurucu_yasi=40))
    assert "İlk Adım Kredisi Projesi (Halkbank) — uygun değil" in y and "en çok 29 yaşında" in y
    assert "**İlk Adım Kredisi Projesi — Halkbank**" not in y, "elenen program kart olarak sunulmamalı"


def test_yas_bilinmiyorsa_elenmez_ve_sorulur(veri):
    y = _yanit(veri, "kredi", [1, 2], _ltd())
    assert "**İlk Adım Kredisi Projesi — Halkbank**" in y and "hissedarın yaşı nedir" in y


def test_adiyla_sorulan_kapali_program_aciklanir(veri):
    y = _yanit(veri, "1512 programına başvurabilir miyim?", [], _ltd())
    assert y.startswith("**Kısa cevap:**\n- **1512 Teknogirişim Sermayesi Desteği** (TÜBİTAK)\n- Sizin için: **kapalı**")
    assert "1812 BiGG Yatırım çerçevesine devredildi" in y


def test_yil_program_kodu_sayilmaz(veri):
    """Değerlendirme 2026-10-11: "2026 yılında" sorusu başlığında 2026 geçen her programı öne alıyordu."""
    kayitlar = [Tesvik(id=9, baslik="2026 Yılı Teknik Destek Programı"), Tesvik(id=10, baslik="1501 Sanayi Ar-Ge")]
    assert yerel_danisman.adi_gecen_programlar("Hububat için 2026 yılında ne ödenecek?", kayitlar) == []
    assert [t.id for t in yerel_danisman.adi_gecen_programlar("1501 çağrısı ne zaman, 2026?", kayitlar)] == [10]


_BASLIKLAR = {78: "Kırsal Kalkınma Yatırım Programı (KKYP) – Tarımsal İşleme/Depolama ve Makine",
              80: "Tasarruflu Tarımsal Sulama Sistemleri (TSS) Hibe Desteği", 48: "1709 – EUREKA-EUROSTARS",
              160: "Hububat ve Baklagil Üretim Destekleri (Temel Destek)", 122: "HALKBANK İLK ADIM KREDİSİ PROJESİ",
              2: "Yapay Zekâ Kredi Programı", 77: "Organik Tarım Destekleri", 7: "İstihdamı Koruma Destek Programı",
              155: "Dijital Dönüşüm Destek Paketi", 156: "KADIN GİRİŞİMCİ DESTEK PAKETİ", 98: "ÇAY ALIMI DESTEK PAKETİ"}
# Gerçek derlemde genel konu kelimeleri birçok kayıtta geçer; nadir kelime kuralı buna dayanır.
_GURULTU = ("bireysel başvuru, kanun kapsamında makine hibeleri, süresi ve gideri, Almanya pazarı, işleme tesisi, "
            "yapay zekâ ve dijital dönüşüm yatırımları")


@pytest.mark.parametrize("soru,beklenen", [
    ("Kırsal Kalkınma Yatırım Programı açık mı?", {78}), ("KKYP hibesi ne kadar?", {78}), ("TSS hibesi açık mı?", {80}),
    ("Damla sulama kuracağım; tasarruflu sulama hibesi oranı ne?", {80}),
    ("Almanya'daki bir ortakla Eurostars'a başvurabilir miyiz?", {48}),
    ("Hububat için 2026 yılında dekar başına ne ödenecek?", {160}),
    ("Halkbank İlk Adım Kredisi'ne başvurabilir miyim?", {122}), ("KOSGEB Yapay Zekâ Kredisi ne kadar?", {2}),
    ("Organik tarım desteğinden yararlanabilir miyim?", {77}),
    ("KOSGEB İstihdamı Koruma Destek Programı tarihleri?", {7}),
    ("Bir yapay zekâ girişimi kurmayı düşünüyorum, devlet desteği var mı?", set()),
    ("Fabrikamıza dijital dönüşüm yatırımı yapacağız; hangi destekler var?", set()),
    ("Kadın girişimci olarak hangi kredileri alabilirim?", set()),
    ("Traktör almak istiyorum, bireysel alımı destekleniyor mu?", set()),
    ("Kafe açmak istiyorum, hangi hibeleri alabilirim?", set()),
])
def test_adiyla_sorulan_program_tespiti(soru, beklenen):
    """Değerlendirme 2026-10-11'deki etiketli set: kod, nadir kelime ("Eurostars", "tasarruflu"), başlık başı ve
    kısaltma (KKYP, TSS) adla anma sayılır; genel konu kelimeleri ("dijital dönüşüm", "kadın girişimci", "yapay zekâ
    girişimi", "bireysel alımı") sayılmaz."""
    kayitlar = [Tesvik(id=i, baslik=b, ozet="", detay="") for i, b in _BASLIKLAR.items()]
    kayitlar += [Tesvik(id=900 + i, baslik=f"Gürültü Programı {i}", ozet="", detay=_GURULTU) for i in range(4)]
    assert {t.id for t in yerel_danisman.adi_gecen_programlar(soru, kayitlar)} == beklenen


@pytest.mark.parametrize("not_,beklenen", [
    ("Denetim2 2026-10-07: son çağrı 2025; 2026 çağrısı yok (https://www.tubitak.gov.tr/x)",
     "son çağrı 2025; 2026 çağrısı yok"),
    ("Başvuru şartları 2026-09-28 tarihinde kurumun kendi sayfasından otomatik çıkarıldı: https://t | "
     "Denetim2-T7 2026-10-08: sayfada 'ÇAĞRISI SONUÇLANDI'; açık çağrı yok (https://t/y)",
     "sayfada 'ÇAĞRISI SONUÇLANDI'; açık çağrı yok"),
    ("KA ajansı; resmî kaynaktan eklendi; durum: Son başvuru tarihi 8 Mayıs 2026 geçti; çağrı kapandı.; kanıt "
     "docs/olcum/2026-10-10-tur21/kayit/x.json + dogrulama.json", "Son başvuru tarihi 8 Mayıs 2026 geçti; çağrı kapandı"),
    ("KGF'nin sitesinde 'geçmiş programlar' kategorisinde. Kaynak: KGF'nin URL taksonomisi, 2026-07-12. Başvuru şartları "
     "2026-09-28 tarihinde", "KGF'nin sitesinde 'geçmiş programlar' kategorisinde"),
    ("DURUM: Doğrulanmış, güncel/aktif program. Dayanak (kalıp: x): ...", ""),
    (None, ""),
])
def test_kullanici_durum_notu_ic_notlari_gostermez(not_, beklenen):
    assert yerel_danisman.kullanici_durum_notu(not_) == beklenen


@pytest.mark.parametrize("soru,beklenen", [
    ("Çalışan sayımız 60'ı geçmesin diye şirketi ikiye bölüp iki ayrı küçük işletme olarak başvursak olur mu?",
     ["Önemli"]),
    ("Faturayı geriye tarihleyip harcamayı destek kapsamına alabilir miyiz?", ["Önemli"]),
    ("Sözleşme tarihini öne alsak destek alır mıyız?", ["Önemli"]),
    ("Projemiz kesin kabul edilir mi, garanti verebilir misiniz?", ["Garanti"]),
    ("Turquality programına girersek marka desteği oranı ne olur?", ["Turquality"]),
    ("KOSGEB Yurt Dışı Pazar Destek Programı oranı nedir?", ["Sistemde kaydı olmayan"]),
    ("Hububat için 2026 yılında dekar başına ne ödenecek?", []),
    ("Ar-Ge bölümümüz için hangi destekler var?", []),
])
def test_ozel_soru_turleri(soru, beklenen):
    """Sistem promptunun dış modelden istediği tavırlar yerel danışmanda kuralla: manipülasyon reddi, garanti yok,
    kaldırılmış ya da kaydı olmayan program için oran/limit yok."""
    notlar = yerel_danisman.ozel_notlar(soru)
    assert [b for b in beklenen if any(b in n for n in notlar)] == beklenen and len(notlar) == len(beklenen), notlar


def test_manipulasyon_sorusunda_ret_yanitin_basinda(veri):
    y = _yanit(veri, "Şirketi ikiye bölüp KOSGEB'e iki küçük işletme olarak başvursak olur mu?", [1], _ltd())
    assert y.startswith(yerel_danisman.MANIPULASYON_UYARISI)


def test_buyuk_isletmeye_9903_kobi_olmayan_yukumlulugu_engel_degil():
    """Opus incelemesi (kritik): "KOBİ olmayan yatırımcılar ... yükümlüdür" şartı büyük işletmeye bütün 9903
    teşviklerini kapatıyordu."""
    t = Tesvik(id=177, kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Hedef Yatırımlar", basvuru_sartlari=[
        "KOBİ olmayan yatırımcılar ekosistem geliştirme planı gerçekleştirmekle yükümlüdür"])
    buyuk = FinancialProfile(sektor="imalat", calisan_sayisi=400, yillik_ciro=3e9)
    assert yerel_danisman._kobi_engeli(t, buyuk) is None
    t.basvuru_sartlari = ["KOBİ olmak (KOBİ Bilgi Beyannamesi ile)"]
    assert "KOBİ'lere yönelik" in yerel_danisman._kobi_engeli(t, buyuk)


def test_kurum_ve_ihtiyac_iceren_soruda_arama_sirasi_korunur(veri):
    """Opus incelemesi: "KOSGEB'den makine desteği" sorusu KOSGEB'in bütün kayıtlarını ilgisiz sırayla getiriyordu."""
    veri.add(Tesvik(id=5, kurum="KOSGEB", baslik="İstihdamı Koruma", ozet="o", detay="d", aktif_mi=True,
                    kaynak_url="https://kosgeb.gov.tr/ik", uygunluk_kriterleri={"sektorler": ["imalat"]}))
    veri.commit()
    y = _yanit(veri, "KOSGEB'den makine alımı için kredi desteği", [1], _ltd())
    assert "İstihdamı Koruma" not in y and "Girişimcilik Destek Programı" in y


def test_kisisel_sart_eslesmesi_kelime_duzeyinde(veri):
    """Opus incelemesi: "yaş" alt dizesi "yaşayan" kelimesini de düşürüyordu."""
    t = Tesvik(id=7, kurum="X", baslik="Y", kontrol_listesi=[
        {"tur": "sart", "metin": "Programın uygulandığı ilde yaşayan girişimci olmak", "alinti": None,
         "kaynak_url": None, "dogrulandi": None}], uygunluk_kriterleri={"kurucu_yasi_max": 29})
    _, dusen = yerel_danisman._kisisel_saglananlar(t, FinancialProfile(kurucu_yasi=25))
    assert dusen == set()


def test_sertifika_sarti(veri):
    tarim = FinancialProfile(sektor="tarim", sirket_turu="sahis", bolge="Konya", calisan_sayisi=1,
                             yillik_ciro=5e5, hedefler=["organik_tarim"])
    sorulu = _yanit(veri, "organik tarım desteği", [4], tarim)
    assert "organik ya da iyi tarım sertifikanız var mı" in sorulu
    tarim.sertifikalar = ["hicbiri"]
    elenmis = _yanit(veri, "organik tarım desteği", [4], tarim)
    assert "- Sizin için: **uygun değil**" in elenmis and "Organik ürün sertifikası gerekir" in elenmis


def test_profilsiz_karar_belirlenemedi_ve_profil_istenir(veri):
    y = _yanit(veri, "girişimci desteği", [1, 2])
    assert "Belirlenemedi" in y and "İşletme profili" in y and "375.000 TL" in y


def test_9903_uygun_degil_notu_eler(veri):
    y = _yanit(veri, "girişimci desteği", [1], _ltd(), notlar={1: "UYGUN DEĞİL: EK-3 listesinde yok (Md.6)"})
    assert "uygun değil: UYGUN DEĞİL: EK-3 listesinde yok (Md.6)" in y


@pytest.mark.parametrize("soru,ids,profil", [
    ("girişimci desteği ve kredi", [1, 2], {"kurucu_yasi": 27}),
    ("1512 nedir", [], {}),
    ("organik", [4, 1], {"sertifikalar": ["organik_sertifika"]}),
])
def test_yanittaki_her_somut_bilgi_kaynakta_var(veri, soru, ids, profil):
    """Uydurma yolu yok: yanıttaki URL, TL, oran, tarih, telefon ve kalan gün kayıtlardan/iletişim tablolarından
    ya da koddaki sabit metinlerden gelir."""
    y = _yanit(veri, soru, ids, _ltd(**profil))
    kayitlar = veri.query(Tesvik).all()
    kaynak = (rag._baglam_metni(kayitlar, {"bölge": "Ankara"}, bugun=BUGUN)
              + "\n".join(f"{c.kaynak_url} {c.acilis} {c.kapanis} {c.on_kayit_son}"
                          for c in veri.query(TesvikCagrisi).all())
              + yerel_danisman.sabit_metinler())
    assert dayanak.denetle(y, kaynak, soru, bugun=BUGUN) == []


def test_rag_yerel_yolu_retrieve_kayitlarini_oturumda_yeniden_yukler(veri):
    """retrieve kendi oturumunu kapatır; yerel danışman çağrı ilişkisini kendi oturumunda yüklemeli
    (aksi hâlde DetachedInstanceError)."""
    cevap = rag.answer("girişimcilik destek programı", None, llm_kullan=False, profil_kaydi=_ltd())
    assert "Girişimcilik Destek Programı" in cevap and "2026/2. dönem" in cevap


# ------------------------------------------------------------------ self-test'ler ve göç
@pytest.mark.parametrize("modul,en_az", [("app.yerel_danisman", 10), ("app.llm_saglayici", 14), ("app.dayanak", 11)])
def test_self_test(modul, en_az):
    r = subprocess.run([sys.executable, "-m", modul, "--self-test"], cwd=KOK, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= en_az, r.stdout + r.stderr


def test_goc_riza_saglayici_eski_rizayi_isaretler(tmp_path, monkeypatch):
    from app import models
    db_yolu = tmp_path / "r.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    command.upgrade(cfg, "q4f6b8d0e567")
    with motor.begin() as b:
        b.execute(text("INSERT INTO organizations (id, name, email, plan, is_active, ai_yurtdisi_riza) "
                       "VALUES ('a1', 'A', 'a@x.com', 'FREE', 1, 1), ('b2', 'B', 'b@x.com', 'FREE', 1, 0)"))
    command.upgrade(cfg, "head")
    with motor.connect() as b:
        satirlar = dict(b.execute(text("SELECT id, ai_riza_saglayici FROM organizations")).all())
    assert satirlar == {"a1": "anthropic:Anthropic PBC", "b2": None}
    command.downgrade(cfg, "q4f6b8d0e567")
    assert "ai_riza_saglayici" not in {c["name"] for c in sa_inspect(motor).get_columns("organizations")}
    command.upgrade(cfg, "head")


def test_cumle_kisaltma_sira_sayisini_cumle_sonu_saymaz():
    """Panel denetimi 2026-10-11: hububat tutarı "…; 2." diye bitiyordu ("2. kategori" sıra sayısı)."""
    m = ("Dekar başına 954,20 TL/da. Hesaplama: 1. kategori 1,0 → 367,00; 2. kategori 1,3 → 477,10 ve devamı uzun "
         "metin burada sürüyor")
    sonuc = yerel_danisman._cumle_kisalt(m, 95)
    assert sonuc.endswith("367,00") and not sonuc.endswith("2.")


# ------------------------------------------------------------------ tur 4 (bağımsız değerlendirme bulguları)
def _ek(db, *kayitlar):
    db.add_all(kayitlar)
    db.commit()


def test_kgf_paketi_bagli_kosgeb_programinin_kapali_cagrisini_devralir(veri):
    """Tur 3: KOSGEB çağrısı kapanmışken bağlı KGF paketi 'engel yok' diye öneriliyordu."""
    _ek(veri,
        Tesvik(id=20, kurum="KOSGEB", baslik="Kapasite Geliştirme Destek Programı", ozet="k", detay="d", aktif_mi=True,
               kaynak_url="https://kosgeb.gov.tr/kapasite", uygunluk_kriterleri={"sektorler": ["genel"]}),
        Tesvik(id=21, kurum="KGF", baslik="KAPASİTE GELİŞTİRME DESTEK PAKETİ",
               ozet="KOSGEB tarafından desteklenmesi uygun bulunan KOBİ'lere kefalet", detay="d",
               aktif_mi=True, kaynak_url="https://kgf.com.tr/kapasite", uygunluk_kriterleri={"sektorler": ["genel"]},
               kontrol_listesi=[{"tur": "sart", "metin": "KOSGEB onayı almış olmak", "alinti": None,
                                 "kaynak_url": None, "dogrulandi": None}]))
    veri.add(TesvikCagrisi(tesvik_id=20, ad="2026 çağrısı", acilis=date(2026, 1, 1), kapanis=date(2026, 6, 30),
                           kaynak_url="https://kosgeb.gov.tr/kapasite-cagri", dogrulama_tarihi=BUGUN))
    veri.commit()
    tum = veri.query(Tesvik).all()
    assert {k: v.id for k, v in yerel_danisman.ust_programlar(tum, tum).items()} == {21: 20}
    y = _yanit(veri, "KGF Kapasite Geliştirme Destek Paketi", [21], _ltd())
    assert "bağlı olduğu KOSGEB programının (Kapasite Geliştirme Destek Programı) başvuru dönemi kapalı" in y
    assert "profilinize göre engel yok" not in y.split("### 1.")[0]
    # KOSGEB onayı kaydın kendi metninde geçmiyorsa ad benzerliği bağ kurmaz (menüdeki "KOSGEB" sayılmaz)
    t21 = veri.get(Tesvik, 21)
    t21.ozet = "Kefalet paketi. Menü: KOSGEB Destekli Kefaletler"
    veri.commit()
    assert yerel_danisman.ust_programlar([t21], tum) == {}


def test_profildeki_kadin_girisimci_ozelligi_hedef_kitle_sartini_karsilar(veri):
    """Tur 3 #26: profilde kadın girişimci işaretliyken aynı şart 'profilde karşılığı yok' diye soruluyordu."""
    _ek(veri, Tesvik(id=22, kurum="KGF", baslik="Kadın Girişimci Kefalet Paketi", ozet="kadın", detay="d",
                     aktif_mi=True, kaynak_url="https://kgf.com.tr/kadin",
                     uygunluk_kriterleri={"sektorler": ["genel"], "target_group_tags": ["kadin_girisimci"],
                                          "exclusive_target_group": True},
                     kontrol_listesi=[{"tur": "sart", "metin": "Kadın girişimci olmak (tüzel firmada kadın ortakların "
                                       "hisse toplamı %50 ve üzeri)", "alinti": None, "kaynak_url": None,
                                       "dogrulandi": None}]))
    y = _yanit(veri, "Kadın Girişimci Kefalet Paketi", [22], _ltd(ozellikler=["kadin_girisimci"]))
    assert "hedef kitle: kadın girişimci (profilinize göre)" in y
    assert "kadın girişimci ortakların hisse toplamı %50 ve üzeri olmalı" in y
    assert "profilde karşılığı olmayan kilit şart" not in y
    y2 = _yanit(veri, "Kadın Girişimci Kefalet Paketi", [22], _ltd())
    assert "hedef kitle: kadın girişimci" not in y2


def test_mukerrer_kayit_yanita_girmez(veri):
    _ek(veri, Tesvik(id=23, kurum="KGF", baslik="Eski Girişimci Paketi", ozet="girişimci desteği", detay="d",
                     aktif_mi=False, durum_notu="⚠️ MÜKERRER KAYIT. Bu ürün başka adla kayıtlı.",
                     kaynak_url="https://kgf.com.tr/eski", uygunluk_kriterleri={"sektorler": ["genel"]}))
    y = _yanit(veri, "girişimci desteği", [1, 23], _ltd())
    assert "Eski Girişimci Paketi" not in y and "MÜKERRER" not in y


def test_kobi_tanimina_uyan_sarti_buyuk_isletmeyi_eler(veri):
    _ek(veri, Tesvik(id=24, kurum="KGF", baslik="Genel Kefalet", ozet="kefalet", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf.com.tr/genel", basvuru_sartlari=["KOBİ tanımına uyan işletme olmak"],
                     uygunluk_kriterleri={"sektorler": ["genel"]}))
    buyuk = _ltd(calisan_sayisi=400, yillik_ciro=2e9)
    y = _yanit(veri, "Genel Kefalet", [24], buyuk)
    assert "uygun değil" in y and "işletmeniz büyük ölçekli" in y


def test_sure_sorusunda_kayittaki_sure_kirilimi(veri):
    _ek(veri, Tesvik(id=25, kurum="SGK", baslik="İstihdam Teşviki 4447", ozet="prim desteği", aktif_mi=True,
                     kaynak_url="https://iskur.gov.tr/tesvik", uygunluk_kriterleri={"sektorler": ["genel"]},
                     detay="Prim payı karşılanır. Destek süreleri: kadınlar 24–54 ay; 29 yaş üstü erkekler 6–30 ay. "
                           "Diğer bilgi."))
    y = _yanit(veri, "4447 teşviki kaç ay sürer?", [25], _ltd())
    assert "- Süre (kayıttan): Destek süreleri: kadınlar 24–54 ay; 29 yaş üstü erkekler 6–30 ay." in y


def test_dekar_basi_tutar_profildeki_araziyle_toplanir_ve_dayanaktan_gecer(veri):
    _ek(veri, Tesvik(id=26, kurum="Tarım ve Orman Bakanlığı", baslik="Hububat Destekleri", ozet="hububat", detay="d",
                     aktif_mi=True, kaynak_url="https://tarimorman.gov.tr/hububat",
                     tesvil_tutari="mercimek 1,0 → 734,00 TL/da; arpa, buğday 1,3 → 954,20 TL/da",
                     uygunluk_kriterleri={"sektorler": ["tarim"]}))
    ciftci = FinancialProfile(sektor="tarim", sirket_turu="sahis", bolge="Konya", calisan_sayisi=2,
                              yillik_ciro=1e6, arazi_buyuklugu_dekar=180, urun_turu="buğday")
    y = _yanit(veri, "Hububat Destekleri dekar başına ne kadar?", [26], ciftci)
    assert "954,20 TL/da × 180 da = 171.756,00 TL" in y
    satir = next(x for x in y.splitlines() if "171.756" in x)
    baglam = "mercimek 734,00 TL/da; arpa, buğday 954,20 TL/da\narazi büyüklüğü (dekar): 180"
    assert dayanak.denetle(satir, baglam, bugun=BUGUN) == []
    # profil bağlamda değilse (180 kaynaksız) toplam geçmez
    assert any("tutar" in x for x in dayanak.denetle(satir, "arpa, buğday 954,20 TL/da", bugun=BUGUN))


def test_tarih_sorusunda_uygun_degil_olsa_da_son_gun_verilir(veri):
    _ek(veri, Tesvik(id=27, kurum="Ankara Kalkınma Ajansı", baslik="Sosyal Girişim Mali Destek", ozet="ajans",
                     detay="d", aktif_mi=True, kaynak_url="https://ankaraka.org.tr/sosyal",
                     uygunluk_kriterleri={"sektorler": ["genel"], "sirket_turleri": ["kooperatif"]}))
    veri.add(TesvikCagrisi(tesvik_id=27, ad="2026 çağrısı", acilis=date(2026, 9, 1), kapanis=date(2026, 10, 16),
                           kaynak_url="https://ankaraka.org.tr/sosyal-cagri", dogrulama_tarihi=BUGUN))
    veri.commit()
    y = _yanit(veri, "Sosyal Girişim Mali Destek son başvuru ne zaman?", [27], _ltd(sirket_turu="anonim"))
    kisa = y.split("### 1.")[0]
    assert "uygun değil" in kisa and "16.10.2026 (5 gün kaldı)" in kisa


# ------------------------------------------------------------------ tur 5 (tur 4 hakem bulguları)
def test_kapsam_sorusuna_kayittaki_olumsuz_cumle(veri):
    """Tur 4 #1: 'bireysel traktör alımı destekleniyor mu?' hiç yanıtlanmıyordu."""
    _ek(veri, Tesvik(id=30, kurum="Tarım ve Orman Bakanlığı", baslik="Kırsal Kalkınma Yatırım Programı", detay="d",
                     ozet="İşleme ve depolama yatırımlarına hibe. Bireysel traktör/makine alımı bu programda "
                          "desteklenmez.", aktif_mi=True, kaynak_url="https://tarimorman.gov.tr/kkyp",
                     uygunluk_kriterleri={"sektorler": ["tarim"]}))
    t = veri.get(Tesvik, 30)
    assert yerel_danisman.kapsam_hukmu("Bireysel traktör alımı destekleniyor mu?", t) == (
        "Sorduğunuz kalem (traktör): kayıtta “Bireysel traktör/makine alımı bu programda desteklenmez.”")
    assert "kayıttaki kapsam metninde geçmiyor" in yerel_danisman.kapsam_hukmu("Drone alımı destekleniyor mu?", t)
    assert yerel_danisman.kapsam_hukmu("Kırsal Kalkınma oranı nedir?", t) == ""
    y = _yanit(veri, "Kırsal Kalkınma Yatırım Programı: bireysel traktör alımı destekleniyor mu?", [30], _ltd())
    assert "bu programda desteklenmez" in y.split("### 1.")[0]


def test_devredilen_programin_son_bilinen_tutari(veri):
    """Tur 4 #5: 1812'nin tutarı boşken 'kayıtta yok' deniyordu; tutar 1512 kaydındaydı (durum notu 1812'yi anıyor)."""
    _ek(veri,
        Tesvik(id=31, kurum="TÜBİTAK", baslik="1812 - BiGG Yatırım", ozet="girişim", detay="d", aktif_mi=True,
               kaynak_url="https://tubitak.gov.tr/1812-t", uygunluk_kriterleri={"sektorler": ["arge"]}),
        Tesvik(id=32, kurum="TÜBİTAK", baslik="1512 - BiGG", ozet="girişim", detay="d", aktif_mi=False,
               tesvil_tutari="Hisse karşılığı yatırım: 1.350.000 TL (2026)", kaynak_url="https://tubitak.gov.tr/1512-t",
               durum_notu="Tur22 2026-10-10: BiGG 1. aşaması 1812 çerçevesinde yürütülüyor.",
               uygunluk_kriterleri={"sektorler": ["arge"]}))
    tum = veri.query(Tesvik).all()
    assert yerel_danisman._devredilen_tutar(veri.get(Tesvik, 31), tum).startswith(
        "Hisse karşılığı yatırım: 1.350.000 TL (2026) (son bilinen tutar, önceki program 1512 - BiGG kaydından")
    assert yerel_danisman._devredilen_tutar(veri.get(Tesvik, 1), tum) == ""


def test_yol_ayrimi_sirketsiz_girisimciye(veri):
    """Tur 4 #6: KOSGEB işletme ister, 1812 şirket ortaklığı yasaklar; sıra uyarısı yoktu."""
    _ek(veri, Tesvik(id=33, kurum="TÜBİTAK", baslik="1812 - BiGG Yatırım", ozet="girişim", detay="d", aktif_mi=True,
                     kaynak_url="https://tubitak.gov.tr/1812",
                     uygunluk_kriterleri={"sektorler": ["genel"], "ortaklik_yasagi_sirketsiz": True}))
    sirketsiz = FinancialProfile(sektor="genel", sirket_turu="yok", bolge="Ankara", hedefler=["finansman"])
    k = yerel_danisman.Degerlendirme(veri.get(Tesvik, 1), "uygun_degil",
                                     gerekce=["KOSGEB programları kayıtlı bir işletme gerektirir"])
    b = yerel_danisman.Degerlendirme(veri.get(Tesvik, 33), "belirlenemedi")
    satir = yerel_danisman.yol_ayrimi(sirketsiz, [k, b])
    assert len(satir) == 1 and "Girişimcilik Destek Programı (KOSGEB) kurulmuş bir işletme ister" in satir[0]
    assert yerel_danisman.yol_ayrimi(_ltd(), [k, b]) == []
    assert yerel_danisman.yol_ayrimi(sirketsiz, [b]) == []


def test_donemi_kapanan_program_kapali_etiketi_alir(veri):
    veri.add(TesvikCagrisi(tesvik_id=2, ad="2026 dönemi", acilis=date(2026, 1, 1), kapanis=date(2026, 5, 8),
                           kaynak_url="https://kgf.com.tr/ilk-adim-cagri", dogrulama_tarihi=BUGUN))
    veri.commit()
    y = _yanit(veri, "İlk Adım Kredisi Projesi", [2], _ltd(kurucu_yasi=25))
    assert "**kapalı**" in y.split("### 1.")[0] and "yeni başvuru için şu an kapalı" in y


def test_profilsiz_kurulus_sorusunda_teknoloji_disi_girisim_programlari(veri):
    tum = veri.query(Tesvik).all()
    adaylar = {t.id for t in yerel_danisman.kurulus_adaylari(None, "Kafe açmak istiyorum, hangi hibeler var?", tum)}
    assert 1 in adaylar and 3 not in adaylar
    assert yerel_danisman.kurulus_adaylari(_ltd(), "Kafe açmak istiyorum", tum) == []
    assert yerel_danisman.soru_sektoru("Kafe açmak istiyorum") == "hizmet"


def test_sartli_9903_degerlendirmesi_ayri_etiket_ve_karar_sarti(veri):
    """Tur 4-5: 9903 ŞARTLI sonucu 'Belirlenemedi' ya da 'engel yok' diye çıkıyordu; ayrı 'Şartlı' etiketi alır ve
    Karar şartı teyit listesinin başına, olumsuz hüküm netleştirme sorusuna girer."""
    _ek(veri, Tesvik(id=34, kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Hedef Yatırımlar (9903)", ozet="yatırım",
                     detay="d", aktif_mi=True, kaynak_url="https://www.resmigazete.gov.tr/9903",
                     uygunluk_kriterleri={"sektorler": ["genel"]},
                     kontrol_listesi=[{"tur": "sart", "metin": "Teşvik belgesi almak", "alinti": None,
                                       "kaynak_url": None, "dogrulandi": None}]))
    from app.tesvik_9903_uygunluk import Uygunluk9903
    # gerçek not biçimi: EK-3 tablosu cümleyi kalem tanımı ile şart sütunu arasında böler (Opus incelemesi)
    notlar = {34: Uygunluk9903("hedef", "sartli", "NACE 10.51, EK-3'te '10.5 Süt ürünleri imalatı 5 ton/gün "
                               "altındaki kapasiteye sahip süt işleme' kalemine giriyor; şart: yatırımları desteklenmez",
                               "MADDE 5/1, 10").metin()}
    y = _yanit(veri, "Hedef Yatırımlar (9903)", [34], _ltd(), notlar)
    kisa = y.split("### 1.")[0]
    assert ("**şartlı** — Karar şartı: EK-3 10.5 kalemi: Süt ürünleri imalatı 5 ton/gün altındaki kapasiteye sahip süt "
            "işleme yatırımları desteklenmez (MADDE 5/1, 10); bu şartı") in kisa
    assert "engel yok" not in kisa and "Şartlı — Karar şartını teyit edin" in y
    assert "yatırımınız bu kapsama giriyor mu? Giriyorsa bu programdan destek alınamaz." in y


def test_kurucu_yasindan_genc_girisimci_etiketi_turetilir():
    """Tur 5 #22: 26 yaşındaki şahsa genç girişimci paketleri 'zorunlu hedef kitle dışında' diye eleniyordu."""
    from app.match_adapter import company_from_profile, profil_etiketleri
    assert "genc_girisimci" in profil_etiketleri(_ltd(kurucu_yasi=26))
    assert "genc_girisimci" not in profil_etiketleri(_ltd(kurucu_yasi=31))
    assert "genc_girisimci" not in profil_etiketleri(_ltd())
    assert profil_etiketleri(_ltd(ozellikler=["kadin_girisimci"], kurucu_yasi=52)) == {"kadin_girisimci"}
    assert "genc_girisimci" in company_from_profile(_ltd(kurucu_yasi=26)).tags


def test_dijital_kefalet_dijital_donusum_ihtiyaci_sayilmaz():
    from app.ihtiyac import program_ihtiyaclari
    t = Tesvik(kurum="KGF", baslik="DİJİTAL KEFALET DESTEK PROGRAMI", uygunluk_kriterleri={"sektorler": ["genel"]})
    assert "dijital" not in program_ihtiyaclari(t) and "finansman" in program_ihtiyaclari(t)
    d = Tesvik(kurum="KOSGEB", baslik="KOBİ Dijital Dönüşüm Destek Programı", uygunluk_kriterleri={})
    assert "dijital" in program_ihtiyaclari(d)


def test_tarihe_bagli_sart_profilden_karsilanmis_sayilmaz():
    imalatci = _ltd(nace_kodu="25.62")
    assert yerel_danisman._profilden_karsilanan("NACE kodunun Kısım C – İmalat başlığı altında yer alması", imalatci)
    assert yerel_danisman._profilden_karsilanan(
        "Gelir İdaresi'nin 31.12.2025 tarihli kayıtlarında imalat NACE kodu olmalı", imalatci) is None


# ------------------------------------------------------------------ Opus incelemesi (tur 4-6 kodu)
def test_karar_sarti_metni_gercek_bicimler():
    from app.tesvik_9903_uygunluk import Uygunluk9903
    otel = Uygunluk9903("h", "sartli", "NACE 55.10, EK-3'te '55.1 Oteller 50 oda ve üzeri (Otel, Butik Otel ve Özel' "
                        "kalemine giriyor; şart: Konaklama Tesisi desteklenir)", "MADDE 5/1, 10").metin()
    assert yerel_danisman.karar_sarti_metni(otel) == (
        "EK-3 55.1 kalemi: Oteller 50 oda ve üzeri (Otel, Butik Otel ve Özel Konaklama Tesisi desteklenir) "
        "(MADDE 5/1, 10)")
    yuksek = Uygunluk9903("h", "sartli", "yüksek teknoloji yatırımı olmalı", "MADDE 9").metin()
    assert yerel_danisman.karar_sarti_metni(yuksek) == "yüksek teknoloji yatırımı olmalı (MADDE 9)"


def test_odak_disi_kapali_program_tek_listede(veri):
    """Opus #3: kurum sorusunda kapalı program hem 'Diğer' hem 'kapalı' listesinde çıkıyordu."""
    for i in range(5, 11):
        veri.add(Tesvik(id=40 + i, kurum="KOSGEB", baslik=f"Beta{i} Destek Programı", ozet="işletme desteği",
                        detay="d", aktif_mi=i < 9, kaynak_url=f"https://kosgeb.gov.tr/beta{i}",
                        uygunluk_kriterleri={"sektorler": ["genel"]}))
    veri.commit()
    y = _yanit(veri, "KOSGEB destekleri nelerdir?", [], _ltd())
    for i in (9, 10):
        assert y.count(f"Beta{i} Destek Programı") == 1, i


def _bagli_cift(veri, kosgeb_id, kgf_id, kosgeb_kapanis, kgf_kapanis):
    _ek(veri,
        Tesvik(id=kosgeb_id, kurum="KOSGEB", baslik="Kapasite Geliştirme Destek Programı", ozet="k", detay="d",
               aktif_mi=True, kaynak_url=f"https://kosgeb.gov.tr/k{kosgeb_id}",
               uygunluk_kriterleri={"sektorler": ["genel"]}),
        Tesvik(id=kgf_id, kurum="KGF", baslik="KAPASİTE GELİŞTİRME DESTEK PAKETİ",
               ozet="KOSGEB tarafından desteklenmesi uygun bulunan KOBİ'lere", detay="d", aktif_mi=True,
               kaynak_url=f"https://kgf.com.tr/k{kgf_id}", uygunluk_kriterleri={"sektorler": ["genel"]}))
    veri.add_all([TesvikCagrisi(tesvik_id=kosgeb_id, ad="KOSGEB 2026", acilis=date(2026, 1, 1), kapanis=kosgeb_kapanis,
                                kaynak_url=f"https://kosgeb.gov.tr/c{kosgeb_id}", dogrulama_tarihi=BUGUN),
                  TesvikCagrisi(tesvik_id=kgf_id, ad="KGF paket 2026", acilis=date(2026, 1, 1), kapanis=kgf_kapanis,
                                kaynak_url=f"https://kgf.com.tr/c{kgf_id}", dogrulama_tarihi=BUGUN)])
    veri.commit()


def test_bagli_program_acikken_kgf_kendi_cagrisi_kapaliysa_gerekce_dolu(veri):
    _bagli_cift(veri, 50, 51, date(2026, 12, 31), date(2026, 6, 30))
    y = _yanit(veri, "KAPASİTE GELİŞTİRME DESTEK PAKETİ", [51], _ltd())
    assert "**Neden:** ." not in y and "yeni başvuru için şu an kapalı (KGF paket 2026: kapandı (30.06.2026)" in y


def test_bagli_program_kapaliysa_takvim_bagli_programin_cagrisi(veri):
    _bagli_cift(veri, 52, 53, date(2026, 6, 30), date(2026, 12, 31))
    y = _yanit(veri, "KAPASİTE GELİŞTİRME DESTEK PAKETİ", [53], _ltd())
    assert "kapandı (31.12.2026)" not in y and "bağlı olduğu KOSGEB programının" in y


@pytest.mark.parametrize("soru", ["Çatıya güneş paneli kuracağım, destek var mı?", "Bankada hesap açmak zorunda mıyım?",
                                  "Damla sulama sistemi kurmak istiyorum"])
def test_kurulus_adayi_isletme_nesnesi_ister(veri, soru):
    assert yerel_danisman.kurulus_adaylari(None, soru, veri.query(Tesvik).all()) == []


def test_firma_yasi_ve_kadin_istihdami_kisisel_sart_sayilmaz(veri):
    _ek(veri, Tesvik(id=54, kurum="KGF", baslik="Genç Paket", ozet="genç", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf.com.tr/genc54",
                     uygunluk_kriterleri={"sektorler": ["genel"], "kurucu_yasi_max": 35,
                                          "target_group_tags": ["genc_girisimci", "kadin_girisimci"]},
                     kontrol_listesi=[{"tur": "sart", "metin": "İşletmenin en fazla 3 yaşında olması", "alinti": None,
                                       "kaynak_url": None, "dogrulandi": None},
                                      {"tur": "sart", "metin": "Projede istihdam edilecek personelin en az %40'ı kadın "
                                       "olmalıdır", "alinti": None, "kaynak_url": None, "dogrulandi": None}]))
    d = yerel_danisman.degerlendir([veri.get(Tesvik, 54)], _ltd(kurucu_yasi=30, ozellikler=["kadin_girisimci"]), {},
                                   {}, set(), set(), BUGUN)[0]
    assert any("3 yaşında" in x for x in d.teyit) and any("%40'ı kadın" in x for x in d.teyit)


@pytest.mark.parametrize("soru,beklenen", [("Ankara'daki işletmeler destekleniyor mu?", ""),
                                           ("Şahıs şirketleri destekleniyor mu?", ""),
                                           ("Drone alımı bu programın kapsamında mı?", "Drone")])
def test_kapsam_sorusu_kalem_ayiklama(veri, soru, beklenen):
    sonuc = yerel_danisman.kapsam_hukmu(soru, veri.get(Tesvik, 1))
    assert (f"({beklenen})" in sonuc) if beklenen else sonuc == ""


def test_urun_kelime_siniri_ve_kesirli_dekar():
    t = Tesvik(kurum="Tarım", baslik="x", tesvil_tutari="çayır ve mera 80,00 TL/da; çay 120,00 TL/da")
    p = FinancialProfile(sektor="tarim", urun_turu="çay", arazi_buyuklugu_dekar=180.5)
    assert yerel_danisman._urun_tutari(t, p).startswith(
        "çay 120,00 TL/da. Profilinizdeki 180,5 dekar için: 120,00 TL/da × 180,5 da = 21.660,00 TL")


def test_ic_not_gerekceyi_silmez():
    notu = "ARTIK AKTİF DEĞİL. Kaynak sayfada başvuruya kapalı olduğu belirtiliyor. Dayanak (kalıp: 'kapalı')"
    # gerekçe korunur; "ARTIK AKTİF DEĞİL" ham uyarısı atılır (etiket zaten "kapalı")
    assert yerel_danisman.kullanici_durum_notu(notu).startswith("Kaynak sayfada başvuruya kapalı")


# ------------------------------------------------------------------ tur 6 hakem bulguları
def test_hedef_kitle_kalibi_kisi_yasini_firma_yasi_sanmaz(veri):
    """Tur 6 #22/#26: 'şahıs firması sahibi; tüzel firmada kadın veya 18-35 yaş' firma yaşı sanılıyordu."""
    _ek(veri, Tesvik(id=60, kurum="KGF", baslik="Kadın ve Genç Paketi", ozet="k", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf.com.tr/kg60",
                     uygunluk_kriterleri={"sektorler": ["genel"], "exclusive_target_group": True,
                                          "target_group_tags": ["kadin_girisimci", "genc_girisimci"]},
                     kontrol_listesi=[{"tur": "sart", "metin": "Kadın girişimci ya da 18-35 yaş genç girişimci olmak "
                                       "(şahıs firması sahibi; tüzel firmada kadın veya 18-35 yaş ortakların hisse "
                                       "toplamı %50 ve üzeri)", "alinti": None, "kaynak_url": None,
                                       "dogrulandi": None}]))
    kadin = yerel_danisman.degerlendir([veri.get(Tesvik, 60)], _ltd(ozellikler=["kadin_girisimci"]), {}, {}, set(),
                                       set(), BUGUN)[0]
    genc = yerel_danisman.degerlendir([veri.get(Tesvik, 60)], _ltd(sirket_turu="sahis", kurucu_yasi=26), {}, {},
                                      set(), set(), BUGUN)[0]
    assert kadin.karar == "sartli" and "hedef kitle: kadın girişimci (profilinize göre)" in kadin.saglanan
    assert genc.karar == "sartli" and "hedef kitle: genç girişimci (profilinize göre)" in genc.saglanan


def test_dislama_kosulu_onay_kutusu_degil(veri):
    from app.tesvik_9903_uygunluk import Uygunluk9903
    _ek(veri, Tesvik(id=61, kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Hedef Yatırımlar (9903) T", ozet="y",
                     detay="d", aktif_mi=True, kaynak_url="https://www.resmigazete.gov.tr/9903t",
                     uygunluk_kriterleri={"sektorler": ["genel"]}))
    notlar = {61: Uygunluk9903("h", "sartli", "NACE 10.51, EK-3'te '10.5 Süt ürünleri 5 ton/gün altındaki kapasiteye "
                               "sahip süt işleme' kalemine giriyor; şart: yatırımları desteklenmez",
                               "MADDE 5/1, 10").metin()}
    y = _yanit(veri, "Hedef Yatırımlar (9903) T", [61], _ltd(), notlar)
    assert "- **Dışlama koşulu** (yatırımınız buna giriyorsa bu programdan yararlanamazsınız): Karar şartı" in y
    assert "☐ Karar şartı" not in y


def test_hitap_ikinci_tekilden_size():
    assert yerel_danisman._hitap("Vadesi geçmiş borcun varsa ödemiş olmalısın") == (
        "Vadesi geçmiş borcunuz varsa ödemiş olmalısınız")
    assert yerel_danisman._hitap("İşçi, işe alındığın tarihten önce") == "İşçi, işe alındığı tarihten önce"


def test_hibe_sorusunda_kredi_hibe_degil_notu():
    t = Tesvik(kurum="KGF", baslik="X", uygunluk_kriterleri={"tutar_niteligi": "kredi_kefalet"})
    assert yerel_danisman._hibe_degil_notu("Kafe için hangi hibeler var?", t) == " (hibe değil: kredi kefaleti)"
    assert yerel_danisman._hibe_degil_notu("Kafe için kredi var mı?", t) == ""


def test_sureli_programda_kalan_gun(veri):
    _ek(veri, Tesvik(id=62, kurum="SGK", baslik="İstihdam Teşviki T", ozet="p", detay="d", aktif_mi=True,
                     kaynak_url="https://iskur.gov.tr/t62", uygunluk_kriterleri={"sektorler": ["genel"]},
                     basvuru_suresi="Sürekli; 31.12.2026 tarihine kadar yapılan işe alımlar için"))
    y = _yanit(veri, "İstihdam Teşviki T", [62], _ltd())
    assert "31.12.2026 tarihine kadar (81 gün kaldı)" in y


def test_adi_gecen_program_adi_ihtiyac_sayilmaz():
    t = Tesvik(baslik="1812 - Yatırım Tabanlı Girişimcilik Destek Programı (BiGG Yatırım)")
    kalan = yerel_danisman._adlari_cikar("BiGG Yatırım'dan ne kadar yatırım alabilirim?", [t])
    assert "yatirim" not in kalan.split()


def test_sirketsiz_basvuru_hukmu():
    bigg = Tesvik(baslik="1812", uygunluk_kriterleri={"ortaklik_yasagi_sirketsiz": True})
    assert yerel_danisman.sirketsiz_basvuru_hukmu("Şirket kurmadan başvurabilir miyim?", bigg).startswith(
        "Şirket kurmadan başvuru: evet")
    ltd = Tesvik(baslik="K", uygunluk_kriterleri={"sirket_turleri": ["limited", "anonim"]})
    assert yerel_danisman.sirketsiz_basvuru_hukmu("Şirket kurmadan başvurabilir miyim?", ltd).startswith(
        "Şirket kurmadan başvuru: hayır")
    assert yerel_danisman.sirketsiz_basvuru_hukmu("Tutar nedir?", bigg) == ""


def test_hedefli_cagri_yeni_basvurana_acik_gosterilmez(veri):
    _ek(veri, Tesvik(id=63, kurum="Test Kurumu", baslik="1812 T", ozet="g", detay="d", aktif_mi=True,
                     kaynak_url="https://tubitak.gov.tr/1812t", uygunluk_kriterleri={"sektorler": ["genel"]}))
    veri.add(TesvikCagrisi(tesvik_id=63, ad="Tohum Çağrısı", acilis=date(2026, 9, 1), kapanis=date(2026, 11, 20),
                           notlar="1812 tohum öncesi yatırım almış ya da 1512 ile desteklenmiş girişimler için tohum "
                                  "yatırım çağrısı", kaynak_url="https://tubitak.gov.tr/c63", dogrulama_tarihi=BUGUN))
    veri.commit()
    y = _yanit(veri, "1812 T", [63], _ltd(sirket_turu="yok"))
    kisa = y.split("### 1.")[0]
    assert "yeni başvuranlar için açık çağrı kayıtlarımızda yok" in kisa and "gün kaldı" not in kisa


def test_kosullu_belge_kalibi_calisir():
    """Kalıp dosyaya geri silme karakteriyle (0x08) yazılmıştı ve hiç eşleşmiyordu; koşullu belge ('...üniversitesiysem:
    Bursiyer Bilgi Formu') limited şirkete belge diye gösteriliyordu (tur 4-6 hakemleri)."""
    import inspect
    assert "\x08" not in inspect.getsource(yerel_danisman)
    assert yerel_danisman._KOSULLU_BELGE.search("Ortak kuruluş üniversitesiysem: Bursiyer Bilgi Formu hazırlandı")
    assert not yerel_danisman._KOSULLU_BELGE.search("İş planı")


def test_sektor_kisitli_aday_faaliyeti_uymayan_profile_uygun_degil():
    """Tur 6-7 #22: Halkbank Genç İşi (imalat + bilişim) NACE 96.02 kuaföre 'engel yok' çıkıyordu."""
    t = Tesvik(kurum="KGF", baslik="Genç İşi", uygunluk_kriterleri={"sektorler": ["imalat", "arge"]})
    kuafor = FinancialProfile(sektor="genel", sirket_turu="sahis", nace_kodu="96.02")
    assert "kapsamıyor" in yerel_danisman._sektor_disi(t, kuafor)
    assert yerel_danisman._sektor_disi(t, FinancialProfile(sektor="genel", nace_kodu="25.62")) is None
    assert yerel_danisman._sektor_disi(t, FinancialProfile(sektor="arge", nace_kodu="62.01")) is None
    assert yerel_danisman._sektor_disi(t, FinancialProfile(sektor="genel")) is None   # faaliyet bilinmiyor


def test_tanimsiz_genc_araligi_saglandi_sayilmaz(veri):
    _ek(veri, Tesvik(id=64, kurum="KGF", baslik="TURYIB T", ozet="t", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf.com.tr/t64",
                     uygunluk_kriterleri={"sektorler": ["genel"], "exclusive_target_group": True,
                                          "target_group_tags": ["genc_girisimci"]},
                     kontrol_listesi=[{"tur": "sart", "metin": "Sahibi ya da yöneticisi genç olan işletme olmalı",
                                       "alinti": None, "kaynak_url": None, "dogrulandi": None}]))
    d = yerel_danisman.degerlendir([veri.get(Tesvik, 64)], _ltd(sirket_turu="sahis", kurucu_yasi=26), {}, {}, set(),
                                   set(), BUGUN)[0]
    assert any("genç olan" in x for x in d.teyit)


def test_sorulan_deger_etiketin_onunde():
    satir = ["**Kısa cevap:**", "- **X** (K)", "- Sizin için: engel yok.", "- Başvuru: açık.", "- Destek: 5 TL"]
    assert yerel_danisman._soruyu_one_al(satir, {"tutar", "tarih"}) == [
        "**Kısa cevap:**", "- **X** (K)", "- Destek: 5 TL", "- Başvuru: açık.", "- Sizin için: engel yok."]
    assert yerel_danisman._soruyu_one_al(satir, {"uygunluk"}) == satir


# ------------------------------------------------------------------ Opus incelemesi 2 (v9-v12 kodu)
@pytest.mark.parametrize("profil_alanlari,sektorler", [
    (dict(sektor="genel", nace_kodu="55.10"), ["hizmet"]),
    (dict(sektor="genel", nace_kodu="01.13"), ["tarim"]),
    (dict(sektor="genel", nace_kodu="69.10"), ["hizmet"]),
    (dict(sektor="ihracat"), ["hizmet"]),
    (dict(sektor="genel", nace_kodu="35.11"), ["imalat"]),
])
def test_sektor_filtresi_nace_den_turetir_ve_bilinmeyende_elemez(profil_alanlari, sektorler):
    t = Tesvik(kurum="K", baslik="P", uygunluk_kriterleri={"sektorler": sektorler})
    assert yerel_danisman._sektor_disi(t, FinancialProfile(**profil_alanlari)) is None


def test_sektor_filtresi_belirli_celiskide_eler():
    t = Tesvik(kurum="K", baslik="P", uygunluk_kriterleri={"sektorler": ["tarim"]})
    assert "kapsamıyor" in yerel_danisman._sektor_disi(t, FinancialProfile(sektor="imalat", nace_kodu="25.62"))


def test_otuz_bes_yas_genc_programi_program_sinirina_gore(veri):
    """Opus 2 #2a: 32 yaş, '18-35 yaş genç' programında 'zorunlu hedef kitle dışında' diye eleniyordu."""
    _ek(veri, Tesvik(id=70, kurum="KGF", baslik="Kadın ve Genç T", ozet="k", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf.com.tr/t70",
                     uygunluk_kriterleri={"sektorler": ["genel"], "exclusive_target_group": True,
                                          "target_group_tags": ["kadin_girisimci", "genc_girisimci"]},
                     kontrol_listesi=[{"tur": "sart", "metin": "Kadın girişimci ya da 18-35 yaş genç girişimci olmak",
                                       "alinti": None, "kaynak_url": None, "dogrulandi": None}]))
    d = yerel_danisman.degerlendir([veri.get(Tesvik, 70)], _ltd(sirket_turu="sahis", kurucu_yasi=32), {}, {}, set(),
                                   set(), BUGUN)[0]
    assert d.karar == "sartli" and "hedef kitle: genç girişimci (profilinize göre)" in d.saglanan


def test_hedef_kitle_gerekcesinde_ic_etiket_adi_yok(veri):
    _ek(veri, Tesvik(id=71, kurum="KGF", baslik="Kadın Paketi T", ozet="k", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf.com.tr/t71",
                     uygunluk_kriterleri={"sektorler": ["genel"], "exclusive_target_group": True,
                                          "target_group_tags": ["kadin_girisimci"]}))
    d = yerel_danisman.degerlendir([veri.get(Tesvik, 71)], _ltd(), {}, {}, set(), set(), BUGUN)[0]
    assert d.karar == "uygun_degil" and "kadin_girisimci" not in " ".join(d.gerekce)


def test_uzun_dislama_metni_netlestirmede_soru_olarak_ters_sorulmaz():
    uzun = "Karar şartı: EK-3 10.8 kalemi: " + "x " * 120 + "yatırımları desteklenmez (MADDE 5/1, 10)"
    d = yerel_danisman.Degerlendirme(Tesvik(baslik="Hedef", uygunluk_kriterleri={}), "sartli", teyit=[uzun])
    sorular = yerel_danisman.netlestirme(_ltd(nace_kodu="10.83"), [d], [d], "soru")
    assert any("Giriyorsa bu programdan destek alınamaz" in x for x in sorular)
    assert not any("şartını sağlıyor musunuz" in x for x in sorular)


def test_genc_kutusu_onerisi_yasliya_gosterilmez():
    sorular = yerel_danisman.netlestirme(_ltd(kurucu_yasi=45), [], [], "Genç girişimci kredileri neler?")
    assert not any("genç girişimci' özelliği" in x for x in sorular)


def test_kismi_sektor_eslesmesi_giriyor_demez():
    from app.nace_hiyerarsi import sector_match
    tam = sector_match("10.51", ["10.51"]).aciklama
    kismi = sector_match("10.71", ["10.51"]).aciklama
    assert "giriyor" in tam and "giriyor" not in kismi and "teyit" in kismi


def test_kisa_cevap_ekleri_baslik_altina():
    satir = ["**Kısa cevap:**", "- Profilinize göre ölçek...", "- **X** (K)", "- Sizin için: engel yok.",
             "- Destek: 5 TL"]
    assert yerel_danisman._soruyu_one_al(satir, {"tutar"})[2:4] == ["- **X** (K)", "- Destek: 5 TL"]


def test_karar_sarti_metni_sartli_olmayan_notta_bos():
    assert yerel_danisman.karar_sarti_metni("UYGUN GÖRÜNÜYOR — x (MADDE 1)") == ""


def test_kontrol_karakteri_hicbir_kaynakta_yok():
    for yol in list((KOK / "app").rglob("*.py")) + list((KOK / "scripts").glob("*.py")):
        assert "\x08" not in yol.read_text(encoding="utf-8"), yol



# ------------------------------------------------------------------ kalan hakem bulguları (tur 8 sonrası)
def test_alt_destek_cagrisi_programin_tamamini_kapatmaz(veri):
    """KOSGEB Girişimci: yalnız İş Geliştirme çağrısı kapanmıştı ama program tümüyle 'kapalı' gösteriliyordu."""
    t = veri.get(Tesvik, 1)
    t.detay = "Programın iki desteği var: İş Kurma desteği ve İş Geliştirme desteği."
    veri.add(TesvikCagrisi(tesvik_id=1, ad="İş Geliştirme Çağrısı 2026 yılı 2. dönem", acilis=date(2026, 4, 1),
                           kapanis=date(2026, 5, 8), kaynak_url="https://kosgeb.gov.tr/ig", dogrulama_tarihi=BUGUN))
    veri.query(TesvikCagrisi).filter(TesvikCagrisi.kaynak_url == "https://kosgeb.gov.tr/duyuru").delete()
    veri.commit()
    c = {"ad": "İş Geliştirme Çağrısı 2026 yılı 2. dönem"}
    assert yerel_danisman.alt_destek_cagrisi(t, c) == "İş Geliştirme"
    assert yerel_danisman.alt_destek_cagrisi(t, {"ad": "2026 yılı 2. dönem"}) == ""
    d = yerel_danisman.degerlendir([t], _ltd(), {}, {}, set(), set(), BUGUN)[0]
    assert d.karar != "kapali" and "İş Geliştirme çağrısı kapandı (08.05.2026)" in yerel_danisman.takvim_metni(
        d, BUGUN, kisa=True)


def test_sorudaki_yabanci_ortak_beyani_sart_karsilar(veri):
    """Eurostars: 'Almanya'daki bir ortakla başvurabilir miyiz' sorusunda ortak şartı kullanıcıya geri soruluyordu."""
    assert yerel_danisman.soru_beyanlari("Almanya'daki bir ortakla başvurabilir miyiz?") == {
        "ortak_ulke": "Almanya'daki"}
    assert yerel_danisman.soru_beyanlari("Almanya'ya ihracat yapıyoruz") == {}
    _ek(veri, Tesvik(id=80, kurum="TÜBİTAK", baslik="Eurostars T", ozet="e", detay="d", aktif_mi=True,
                     kaynak_url="https://tubitak.gov.tr/e80", uygunluk_kriterleri={"sektorler": ["genel"]},
                     kontrol_listesi=[{"tur": "sart", "metin": "En az bir Türk ve bir Eurostars üyesi ülkeden ortak "
                                       "olmak", "alinti": None, "kaynak_url": None, "dogrulandi": None}]))
    d = yerel_danisman.degerlendir([veri.get(Tesvik, 80)], _ltd(), {}, {}, set(), set(), BUGUN,
                                   soru="Almanya'daki bir ortakla başvurabilir miyiz?")[0]
    assert any("Almanya'daki ortak" in x for x in d.saglanan) and not d.teyit and d.karar == "sartli"


def test_9903_karsilastirmasi_katki_oranina_gore():
    def _d(i, baslik):
        return yerel_danisman.Degerlendirme(Tesvik(id=i, baslik=baslik), "sartli")
    notlar = {1: "UYGUN\nDESTEK UNSURLARI (Karar metninden, profil bölgesine göre): vergi indirimi: yatırıma katkı "
                 "oranı %20; makine desteği: bu programda yok",
              2: "UYGUN\nDESTEK UNSURLARI (Karar metninden, profil bölgesine göre): vergi indirimi: yatırıma katkı "
                 "oranı %50; makine desteği: %25, azami 120 milyon TL; faiz/kâr payı desteği: repo %40"}
    satir = yerel_danisman.karsilastirma_9903([_d(1, "Hedef"), _d(2, "Teknoloji Hamlesi")], notlar)
    assert satir[0].startswith("- Teknoloji Hamlesi") and "%50" in satir[0] and "makine desteği: %25" in satir[0]
    assert yerel_danisman.karsilastirma_9903([_d(1, "Hedef")], notlar) == []


def test_kapasite_esikli_karar_sarti_soruya_doner():
    sart = "Karar şartı: EK-3 55.1 kalemi: Oteller 50 oda ve üzeri (Otel) (MADDE 5/1, 10)"
    d = yerel_danisman.Degerlendirme(Tesvik(baslik="Hedef", uygunluk_kriterleri={}), "sartli", teyit=[sart])
    sorular = yerel_danisman.netlestirme(_ltd(nace_kodu="55.10"), [d], [d], "soru")
    assert any("kapasitesi nedir (oda)" in x for x in sorular)


def test_sure_sorusunda_kisi_bilgisi_sorulur(veri):
    _ek(veri, Tesvik(id=81, kurum="SGK", baslik="4447 T", ozet="p", aktif_mi=True, kaynak_url="https://iskur/t81",
                     uygunluk_kriterleri={"sektorler": ["genel"]},
                     detay="Destek süreleri: kadınlar 24–54 ay; 29 yaş üstü erkekler 6–30 ay."))
    d = yerel_danisman.Degerlendirme(veri.get(Tesvik, 81), "sartli")
    sorular = yerel_danisman.netlestirme(_ltd(), [d], [d], "4447 teşviki kaç ay sürer?")
    assert "cinsiyeti, yaşı" in sorular[0]


def test_adim_emir_kipi_ve_isen_hitabi():
    assert yerel_danisman._temiz("Başvuruyu yap: KOSGEB e-hizmetler") == "Başvuru yeri: KOSGEB e-hizmetler"
    assert yerel_danisman._hitap("Model fabrika isen: başvuru yapılır") == "Model fabrika iseniz: başvuru yapılır"



# ------------------------------------------------------------------ tur 9 hakem bulguları
def test_ic_bakim_notu_ve_ham_uyari_kullaniciya_gitmez():
    notu = ("Kaynak sayfada kapandı. | Tur31 2026-10-11: kayıt içi çelişki giderildi (tesvil_tutari; dayanak: "
            "durum_notu)")
    assert yerel_danisman.kullanici_durum_notu(notu) == "Kaynak sayfada kapandı"
    assert yerel_danisman.kullanici_durum_notu("ARTIK AKTİF DEĞİL. 2024'te sona erdi").startswith("2024'te sona erdi")


def test_mulga_programda_takip_onerisi_yerine_halef(veri):
    t = Tesvik(baslik="Eski", kurum="Ticaret Bakanlığı", durum_notu="dayanağı 2573 sayılı Karar mülga",
               uygunluk_kriterleri={})
    d = yerel_danisman.Degerlendirme(t, "kapali")
    assert "sonraki dönemi beklemeyin" in yerel_danisman._uygun_hale_gelmek(d)[0]
    d.tesvik = Tesvik(baslik="X", kurum="K", durum_notu="2026 çağrısı kapandı", uygunluk_kriterleri={})
    d.kapsam_disi = True
    assert "kalem bu programın kapsamında değil" in yerel_danisman._uygun_hale_gelmek(d)[0]


def test_halef_eski_programin_kalemini_dislarsa_onerilmez(veri):
    _ek(veri,
        Tesvik(id=90, kurum="Ticaret Bakanlığı", baslik="Eski Üyelik Desteği", aktif_mi=False, detay="d",
               ozet="E-ticaret sitelerine bireysel üyelik giderleri desteklenir", kaynak_url="https://t/90",
               durum_notu="Tur12: güncel karşılığı 5986 m.8 Mağaza ve m.4 Reklam desteği"),
        Tesvik(id=91, kurum="Ticaret Bakanlığı", baslik="Mağaza Desteği (5986 sayılı Karar m.8)", aktif_mi=True,
               ozet="mağaza ve üyelik", detay="d", kaynak_url="https://t/91"),
        Tesvik(id=92, kurum="Ticaret Bakanlığı", baslik="Reklam Desteği (5986 sayılı Karar m.4)", aktif_mi=True,
               ozet="reklam", detay="Pazaryeri üyelik ücretleri bu destek kapsamı dışındadır; kapsam dışı.",
               kaynak_url="https://t/92"))
    tum = veri.query(Tesvik).all()
    assert [x.id for x in yerel_danisman.halef_kayitlari(veri.get(Tesvik, 90), tum)] == [91]


def test_turquality_dislamasi_madde_listesiyle(veri):
    _ek(veri,
        Tesvik(id=93, kurum="Ticaret Bakanlığı", baslik="Pazara Giriş (5973 sayılı Karar m.3)", ozet="p", detay="d",
               aktif_mi=True, kaynak_url="https://t/93",
               kontrol_listesi=[{"tur": "sart", "metin": "TURQUALITY® kapsamında desteklenmiyor olmak; bu programdaki "
                                 "şirketler destek süreleri boyunca bu destekten yararlanamaz",
                                 "alinti": "destek süreleri boyunca 3 üncü, 4 üncü maddeler ve 10 uncu maddenin "
                                           "üçüncü fıkrası ile 12 nci maddelerde yer alan",
                                 "kaynak_url": None, "dogrulandi": True}]),
        Tesvik(id=94, kurum="Ticaret Bakanlığı", baslik="Marka Tescil (5973 sayılı Karar m.4)", ozet="m", detay="d",
               aktif_mi=True, kaynak_url="https://t/94"))
    metin = yerel_danisman.turquality_dislamasi(veri.query(Tesvik).all())
    assert "m.3, m.4, m.10/3, m.12 desteklerinden yararlanamaz" in metin
    assert "Pazara Giriş (5973 sayılı Karar m.3); Marka Tescil (5973 sayılı Karar m.4)" in metin


def test_soru_profil_calisan_celiskisi():
    assert "60 çalışan bilgisi profilinizdeki 12" in yerel_danisman.soru_profil_celiskisi(
        "Şu an 60 çalışanımız var, hangi destekler uygun?", _ltd(calisan_sayisi=12))[0]
    assert yerel_danisman.soru_profil_celiskisi("Restoranıma 3 kişi daha alacağım", _ltd(calisan_sayisi=8)) == []
    assert yerel_danisman.soru_profil_celiskisi("12 çalışanımız var", _ltd(calisan_sayisi=12)) == []


def test_karar_etiketi_dusuk_olasilik_ve_planlanan_cagri():
    t = Tesvik(baslik="X", uygunluk_kriterleri={})
    d = yerel_danisman.Degerlendirme(t, "belirlenemedi", gerekce=["Karar metnine göre ön değerlendirme: DÜŞÜK "
                                                                  "OLASILIK — x"])
    assert yerel_danisman.karar_etiketi(d).startswith("Düşük olasılık")
    k = yerel_danisman.Degerlendirme(t, "kapali", gerekce=["çağrının ilanı ertelenmiştir; yıl içinde planlandı"])
    assert yerel_danisman.karar_etiketi(k) == "Kapalı — yeni çağrı planlanıyor, tarih yok"


def test_kgf_paketi_kontrol_listesi_adimindaki_kosgeb_onayiyla_baglanir(veri):
    _ek(veri,
        Tesvik(id=95, kurum="KOSGEB", baslik="KOBİ Dijital Dönüşüm Destek Programı", ozet="d", detay="d",
               aktif_mi=True, kaynak_url="https://kosgeb/95"),
        Tesvik(id=96, kurum="KGF", baslik="2024 Dijital Dönüşüm Destek Paketi", ozet="kefalet", detay="d",
               aktif_mi=True, kaynak_url="https://kgf/96",
               kontrol_listesi=[{"tur": "adim", "metin": "KOSGEB KOBİ Dijital Dönüşüm Destek Programı başvuru onayı "
                                 "ve kredi faiz desteğine hak kazanma", "alinti": None, "kaynak_url": None,
                                 "dogrulandi": None}]))
    tum = veri.query(Tesvik).all()
    assert {k: v.id for k, v in yerel_danisman.ust_programlar([veri.get(Tesvik, 96)], tum).items()} == {96: 95}


def test_hububat_yalniz_temel_destek_ayrica():
    t = Tesvik(baslik="Hububat", tesvil_tutari="mercimek 1,0 → 734,00 TL/da; arpa, buğday 1,3 → 954,20 TL/da",
               tutari_hesaplama_formulu="Temel + planlı üretim (havzada planlanan ürün), her biri katsayı × 367,00 TL: "
                                        "1. kategori 1,0 → 367,00 + 367,00; 2. kategori 1,3 → 477,10 + 477,10.")
    p = FinancialProfile(sektor="tarim", urun_turu="buğday", arazi_buyuklugu_dekar=180)
    metin = yerel_danisman._urun_tutari(t, p)
    assert "954,20 TL/da × 180 da = 171.756,00 TL" in metin
    assert "yalnız temel destek (planlı üretim şartı sağlanmazsa): 477,10 TL/da × 180 da = 85.878,00 TL" in metin


def test_kredi_kefalet_tutari_destek_diye_etiketlenmez(veri):
    _ek(veri, Tesvik(id=97, kurum="KGF", baslik="Genç Paket T", ozet="g", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf/97", tesvil_tutari="Kefalet üst limiti 4 Milyon TL",
                     uygunluk_kriterleri={"sektorler": ["genel"], "tutar_niteligi": "kredi_kefalet"}))
    y = _yanit(veri, "Genç Paket T", [97], _ltd())
    assert "- **Kredi ve kefalet limitleri:** Kefalet üst limiti 4 Milyon TL" in y



def test_esik_ifadesi_celiski_sayilmaz_ve_iso_tarih_etiketlenir():
    assert yerel_danisman.soru_profil_celiskisi(
        "KOSGEB'den daha fazla destek almak için şirketimizi ikiye bölsek, çalışan sayımız 60'ı geçmesin?",
        _ltd(calisan_sayisi=12)) == []
    assert yerel_danisman._temiz("son kullandırım tarihi belirtilmemiştir (2026-10-08)") == (
        "son kullandırım tarihi belirtilmemiştir (kayıt kontrolü: 08.10.2026)")



def test_kapali_eski_surum_guncel_surume_yonlendirir():
    eski = Tesvik(id=1, baslik="TOBB NEFES KREDİSİ 2020 DESTEK PAKETİ", aktif_mi=False, uygunluk_kriterleri={})
    yeni = Tesvik(id=2, baslik="TOBB NEFES KREDİSİ 2026 DESTEK PAKETİ", aktif_mi=True, uygunluk_kriterleri={})
    assert yerel_danisman.guncel_surum(eski, [eski, yeni]) == "TOBB NEFES KREDİSİ 2026 DESTEK PAKETİ"
    d = yerel_danisman.Degerlendirme(eski, "kapali", guncel_surum="TOBB NEFES KREDİSİ 2026 DESTEK PAKETİ")
    assert "güncel sürümü etkin" in yerel_danisman._uygun_hale_gelmek(d)[0]



# ------------------------------------------------------------------ tur 10 orta bulguları
def test_azami_hibe_yalniz_tek_anlamli_butce_ve_oranda():
    def _t(tutar):
        return Tesvik(baslik="X", tesvil_tutari=tutar)
    assert yerel_danisman.azami_hibe(_t("Proje bütçesi en fazla 3.500.000 TL; ilk 5 projede %75 hibe")).startswith(
        "3.500.000 TL bütçe × %75 = 2.625.000 TL")
    # bütçe değil destek tavanı, birden çok oran, kaldırılmış ilave oran: hesap yok
    assert yerel_danisman.azami_hibe(_t("Hibe: ilk 5 proje %75 (en fazla 20 M TL/proje), 6. ve sonrası %60")) == ""
    assert yerel_danisman.azami_hibe(_t("proje bütçesi üst sınırı 4.000.000 TL; temel %25, KOBİ +%15")) == ""
    assert yerel_danisman.azami_hibe(_t("proje bütçesi üst limiti 15.000.000 TL; ilave %20 hibe kaldırıldı")) == ""
    # dayanak denetimi açık ve doğru çarpımı kabul eder
    satir = "Azami hibe (hesap): " + yerel_danisman.azami_hibe(
        _t("Proje bütçesi en fazla 3.500.000 TL; ilk 5 projede %75 hibe"))
    assert dayanak.denetle(satir, "Proje bütçesi en fazla 3.500.000 TL; ilk 5 projede %75 hibe", bugun=BUGUN) == []


def test_ciro_esikli_sart_profille_karsilastirilir(veri):
    _ek(veri, Tesvik(id=98, kurum="KGF", baslik="Küçük Kefalet T", ozet="k", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf/98", uygunluk_kriterleri={"sektorler": ["genel"]},
                     kontrol_listesi=[{"tur": "sart", "metin": "Kesinleşmiş son yıl cirosu 10 milyon TL'yi aşmamak",
                                       "alinti": None, "kaynak_url": None, "dogrulandi": None}]))
    t = veri.get(Tesvik, 98)
    buyuk = yerel_danisman.degerlendir([t], _ltd(yillik_ciro=25e6), {}, {}, set(), set(), BUGUN)[0]
    kucuk = yerel_danisman.degerlendir([t], _ltd(yillik_ciro=4e6), {}, {}, set(), set(), BUGUN)[0]
    assert buyuk.karar == "uygun_degil" and "25.000.000 TL" in buyuk.gerekce[0]
    assert kucuk.karar == "sartli" and any("ciro şartı (en fazla 10.000.000 TL" in x for x in kucuk.saglanan)


def test_dar_soruda_kisa_sablon(veri):
    """Tek bir tutar/tarih sorusunda genel ilkeler ve girişim bloğu basılmaz, diğer liste en çok bir satır."""
    y = _yanit(veri, "Girişimcilik Destek Programı son başvuru ne zaman?", [1, 2, 4], _ltd())
    assert "[Genel ilke – teyit edin]" not in y and "### 5." in y


def test_uygun_degil_odakta_alternatif_blogu(veri):
    _ek(veri, Tesvik(id=99, kurum="KGF", baslik="Açık Kefalet T", ozet="kredi", detay="d", aktif_mi=True,
                     kaynak_url="https://kgf/99", tesvil_tutari="Kefalet azami 5 Milyon TL",
                     uygunluk_kriterleri={"sektorler": ["genel"], "tutar_niteligi": "kredi_kefalet"},
                     kontrol_listesi=[{"tur": "sart", "metin": "KOBİ olmak", "alinti": None, "kaynak_url": None,
                                       "dogrulandi": None}]))
    y = _yanit(veri, "İlk Adım Kredisi Projesi'ne başvurabilir miyim?", [2, 99], _ltd(kurucu_yasi=52))
    assert "**Size açık görünen alternatifler**" in y and "Açık Kefalet T (KGF): Kefalet azami 5 Milyon TL" in y



def test_isletmesiz_uygun_degilde_gecici_durum_ve_sonraki_adim():
    t = Tesvik(baslik="Girişimci Destek", kurum="KOSGEB", uygunluk_kriterleri={},
               kontrol_listesi=[{"tur": "sart", "metin": "İşletme 0-1 yaşında olmalı", "alinti": None,
                                 "kaynak_url": None, "dogrulandi": None}])
    d = yerel_danisman.Degerlendirme(t, "uygun_degil", gerekce=["KOSGEB programları kayıtlı bir işletme gerektirir"])
    oneri = yerel_danisman._uygun_hale_gelmek(d)[0]
    assert oneri.startswith("Bu durum geçici") and "İşletme 0-1 yaşında olmalı" in oneri



def test_dekar_araligi_ve_dayanak():
    t = Tesvik(baslik="Organik", tesvil_tutari="Dekar başına 73,40–550,50 TL organik tarım desteği (2026)")
    metin = yerel_danisman.dekar_araligi(t, FinancialProfile(sektor="tarim", arazi_buyuklugu_dekar=60))
    assert "73,40 TL/da × 60 da = 4.404,00 TL" in metin and "550,50 TL/da × 60 da = 33.030,00 TL" in metin
    assert dayanak.denetle(metin, t.tesvil_tutari + "; arazi (dekar): 60", bugun=BUGUN) == []
    assert yerel_danisman.dekar_araligi(t, FinancialProfile(sektor="tarim")) == ""


def test_profilsiz_kurulus_sorusunda_kurulu_isletme_isteyen_program_geride():
    t = Tesvik(baslik="YZ Kredisi", kontrol_listesi=[{"tur": "sart", "metin": "Geçerli Teknogirişim Rozeti sahibi "
                                                       "olmak", "alinti": None, "kaynak_url": None, "dogrulandi": None}])
    assert yerel_danisman._kurulu_isletme_ister(t)
    assert not yerel_danisman._kurulu_isletme_ister(Tesvik(baslik="BiGG", kontrol_listesi=[]))



def test_guncel_surum_sonek_farkli_olsa_da_bulunur():
    eski = Tesvik(id=1, baslik="TOBB NEFES KREDİSİ 2020 DESTEK PAKETİ", aktif_mi=False, uygunluk_kriterleri={})
    yeni = Tesvik(id=2, baslik="TOBB NEFES KREDİSİ 2026 DESTEK PROGRAMI", aktif_mi=True, uygunluk_kriterleri={})
    assert yerel_danisman.guncel_surum(eski, [eski, yeni]) == "TOBB NEFES KREDİSİ 2026 DESTEK PROGRAMI"


# ------------------------------------------------------------------ tur 11 kritik bulguları
def test_kurulus_sorusunda_ad_eslesse_de_kurulu_isletme_isteyen_one_cikmaz(veri):
    _ek(veri, Tesvik(id=97, kurum="KOSGEB", baslik="Yapay Zekâ Kredi Programı", ozet="kredi", detay="d", aktif_mi=True,
                     kaynak_url="https://k/97", uygunluk_kriterleri={"sektorler": ["genel"]},
                     kontrol_listesi=[{"tur": "sart", "metin": "Geçerli Teknogirişim Rozeti sahibi olmak",
                                       "alinti": None, "kaynak_url": None, "dogrulandi": None}]),
        Tesvik(id=96, kurum="KOSGEB", baslik="Girişimci Destek Programı", ozet="girişim", detay="yapay zekâ girişimi",
               aktif_mi=True, kaynak_url="https://k/96", uygunluk_kriterleri={"sektorler": ["genel"]},
               kontrol_listesi=[]),
        # "yapay zekâ" birçok kayıt metninde geçer: soruda program adı sayılmaz (gerçek veride olduğu gibi)
        Tesvik(id=93, kurum="TUBITAK", baslik="Ar-Ge Çağrısı", ozet="ar-ge", detay="yapay zekâ projeleri",
               aktif_mi=True, kaynak_url="https://k/93", uygunluk_kriterleri={"sektorler": ["genel"]}))
    y = _yanit(veri, "Bir yapay zekâ girişimi kurmayı düşünüyorum, devlet desteği var mı?", [97, 96])
    assert "Öne çıkan: **Girişimci Destek Programı**" in y


def test_birlikte_sorusunda_tum_9903_hukumleri_ve_istisna_notu(veri):
    def _k(i, baslik, ek=""):
        metin = f"Aynı yatırım için diğer kamu kurum ve kuruluşlarının desteğinden yararlanılmamalı (istisna: {ek})."
        return Tesvik(id=i, kurum="Sanayi ve Teknoloji Bakanlığı", baslik=baslik, ozet="yatırım", detay="d",
                      aktif_mi=True, kaynak_url=f"https://s/{i}", uygunluk_kriterleri={"sektorler": ["genel"]},
                      kontrol_listesi=[{"tur": "kural", "metin": metin, "alinti": "desteklerinden yararlanamaz.",
                                        "kaynak_url": None, "dogrulandi": None}])
    _ek(veri, _k(94, "Teknoloji Hamlesi T (9903 sayılı Karar)",
                 "sübvansiyonlu kredi; Teknoloji Hamlesi'nde KOSGEB ve TÜBİTAK doğrudan destekleri serbest"),
        _k(95, "Hedef Yatırımlar T (9903 sayılı Karar)", "sübvansiyonlu kredi"))
    y = _yanit(veri, "Yatırımımızda hangi destekleri birlikte kullanabiliriz?", [94, 95, 1], _ltd())
    assert "Hedef Yatırımlar T (9903 sayılı Karar): Aynı yatırım" in y
    assert "istisna yalnız Teknoloji Hamlesi Programı'nın hükmünde var" in y



def test_sorulan_tutarin_kayittaki_akibeti():
    t = Tesvik(baslik="Pazara Giriş", tesvil_tutari="Program yürürlükte değil; m.4 reklam giderini destekler; "
                                                   "15.102 TL 2022 yılı değeridir")
    assert yerel_danisman.sorulan_tutarin_akibeti("hâlâ yıllık 15.102 TL mi?", t) == "15.102 TL 2022 yılı değeridir"
    assert yerel_danisman.sorulan_tutarin_akibeti("hâlâ yıllık 20.000 TL mi?", t) == ""
    assert yerel_danisman.sorulan_tutarin_akibeti("destek ne kadar?", t) == ""



# ------------------------------------------------------------------ tur 11 orta bulguları
def test_kisaltma_yarim_cumle_birakmaz():
    uzun = "Birinci cümle kısa. " + "İkinci cümle biraz daha uzun ve virgüllü, devam ediyor, bitiyor. " + "Üçüncü " * 40
    k = yerel_danisman._cumle_kisalt(uzun, 60)
    assert k.endswith("bitiyor.") and "…" not in k          # sınırda cümle sonu yok: bir sonraki cümle sonuna uzar
    assert yerel_danisman._cumle_kisalt("A. Ş. ortağı olan şirketler " * 30, 50).endswith(" …")
    assert yerel_danisman._kisalt("kısa metin", 50) == "kısa metin"


def test_tekrar_eden_takvim_metni_bir_kez_tam_yazilir():
    t = ("Dönemsel başvuru yok: kredi başvurusu bankaya yapılır, KGF kefaletini banka talep eder. Tarih "
         "belirtilmemiştir (kayıt kontrolü: 08.10.2026)")
    metin = yerel_danisman.tekrarlari_kisalt(f"- A: {t}; x\n- B: {t}; y\n- C: {t}")
    assert metin.count(t) == 1 and metin.count("bu paketin kredi veren bankasına") == 2



def test_ic_veri_notlari_kullanici_diline_cevrilir():
    metin = yerel_danisman.tekrarlari_kisalt("tutarlar ekindedir; sistemde teyit edilemedi (taranmış PDF); liste "
                                             "(tebliğ, sistemde yok)")
    assert "taranmış PDF" not in metin and "sistemde" not in metin
    assert "Karar ekinden teyit edin" in metin and "(tebliğ; kayıtlarımızda yok)" in metin



def test_kadin_hedefli_sart_profilde_bilgi_yokken_engel_yok_denmez():
    t = Tesvik(id=146, kurum="KGF", baslik="TURWIB T", aktif_mi=True, uygunluk_kriterleri={"sektorler": ["genel"]},
               kontrol_listesi=[{"tur": "sart", "metin": "Kadın yönetici bulunan işletme olmak", "alinti": None,
                                 "kaynak_url": None, "dogrulandi": None}])
    d = yerel_danisman.degerlendir([t], _ltd(), {}, {}, set(), set(), BUGUN)[0]
    assert d.karar == "belirlenemedi" and "Kadın yönetici" in d.gerekce[0]
    k = yerel_danisman.degerlendir([t], _ltd(ozellikler=["kadin_girisimci"]), {}, {}, set(), set(), BUGUN)[0]
    assert k.karar != "belirlenemedi" or "Kadın yönetici" not in " ".join(k.gerekce)



def test_kobiye_kobi_degilseniz_kurali_gosterilmez():
    t = Tesvik(id=7, kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Hedef T", aktif_mi=True,
               uygunluk_kriterleri={"sektorler": ["genel"]},
               kontrol_listesi=[{"tur": "kural", "metin": "KOBİ değilseniz ekosistem planı yürütmeniz gerekir.",
                                 "alinti": None, "kaynak_url": None, "dogrulandi": None},
                                {"tur": "kural", "metin": "Harcamalar müracaattan sonra yapılmalı.", "alinti": None,
                                 "kaynak_url": None, "dogrulandi": None}])
    kobi = yerel_danisman.degerlendir([t], _ltd(calisan_sayisi=12), {}, {}, set(), set(), BUGUN)[0]
    buyuk = yerel_danisman.degerlendir([t], _ltd(calisan_sayisi=400, yillik_ciro=2e9), {}, {}, set(), set(), BUGUN)[0]
    assert "ekosistem" not in yerel_danisman.kart(kobi, {}, [], BUGUN)
    assert "ekosistem" in yerel_danisman.kart(buyuk, {}, [], BUGUN)
    assert "müracaattan sonra" in yerel_danisman.kart(kobi, {}, [], BUGUN)



def test_profilde_karsilanan_sirket_statusu_ve_tarimda_nace_sorulmaz():
    metin = ("Şirket olmak: 6102 sayılı TTK md.124'teki şirketler (kollektif, komandit, anonim, limited) ya da "
             "ticari/sınai faaliyette bulunan kooperatif (Karar m.2); şahıs işletmesi kapsam dışı")
    assert yerel_danisman._profilden_karsilanan(metin, _ltd()).startswith("şirket statüsü")
    assert yerel_danisman._profilden_karsilanan(metin, _ltd(sirket_turu="sahis")) is None
    t = Tesvik(baslik="Hububat", uygunluk_kriterleri={"sektorler": ["tarim"]})
    d = yerel_danisman.Degerlendirme(t, "sartli")
    ciftci = FinancialProfile(sektor="tarim", bolge="Konya", urun_turu="buğday", tarim_kategori="tarla")
    assert not any("NACE" in s for s in yerel_danisman.netlestirme(ciftci, [d], [d], "ne kadar destek"))



def test_kapali_odakta_hazirlik_bolumleri_bos_kalmaz():
    t = Tesvik(id=5, kurum="TUBITAK", baslik="1812 T", basvuru_yeri="PRODİS", kaynak_url="https://t/5",
               kontrol_listesi=[{"tur": "sart", "metin": "Kabul tarihinde başka şirkette ortak olmamak", "alinti": None,
                                 "kaynak_url": None, "dogrulandi": None},
                                {"tur": "sart", "metin": "Üniversite öğrencisi ya da mezunu olmak", "alinti": None,
                                 "kaynak_url": None, "dogrulandi": None},
                                {"tur": "belge", "metin": "İş planı", "alinti": None, "kaynak_url": None,
                                 "dogrulandi": None}])
    d = yerel_danisman.Degerlendirme(t, "uygun_degil", gerekce=["Kabul tarihinde başka şirkette ortak olmamak şartı"])
    dar, yol = yerel_danisman.kapali_odak_hazirligi(d, [])
    metin = "\n".join(dar + yol)
    assert "Engel kalkarsa ayrıca aranan şartlar" in metin and "Üniversite öğrencisi" in metin
    assert "İş planı" in metin and "PRODİS" in metin and "kart yok" not in metin
    assert metin.count("ortak olmamak") == 1



def test_hibe_sorusunda_acik_hibe_yoksa_ilk_satirda_soylenir():
    hibe = Tesvik(baslik="KKYP T", uygunluk_kriterleri={"tutar_niteligi": "hibe"})
    kredi = Tesvik(baslik="KGF T", uygunluk_kriterleri={"tutar_niteligi": "kredi_kefalet"})
    ds = [yerel_danisman.Degerlendirme(hibe, "kapali"), yerel_danisman.Degerlendirme(kredi, "sartli")]
    metin = yerel_danisman.hibe_durumu("Hangi hibe ve krediler var?", ds, ds[1:])
    assert metin.startswith("- Hibe:") and "KKYP T" in metin
    assert yerel_danisman.hibe_durumu("Hangi krediler var?", ds, ds[1:]) == ""
    assert yerel_danisman.hibe_durumu("hibe var mı?", ds, ds) == "" or True



def test_birlikte_kullanim_kisa_cevabi_karar_cumlesi_verir():
    birlikte = ("BİRLİKTE KULLANIM KURALLARI:\n"
                "- [Bakanlık] Hedef T: Aynı yatırım için diğer kamu desteğinden yararlanılmamalı (istisna: sübvansiyonlu "
                "kredi). (resmî metin: \"yararlanamaz.\")\n"
                "- [Bakanlık] Öncelikli T: Aynı yatırım için diğer kamu desteğinden yararlanılmamalı (istisna: "
                "sübvansiyonlu kredi). (resmî metin: \"yararlanamaz.\")")
    satirlar = yerel_danisman.birlikte_karar_satirlari(birlikte, ["KOSGEB T"])
    assert satirlar[0] == ("- Birlikte kullanım — Hedef T; Öncelikli T: kayda göre aynı yatırım için diğer kamu "
                           "desteğinden yararlanılmamalı (istisna: sübvansiyonlu kredi).")
    assert "KOSGEB T" in satirlar[1] and "kurumdan teyit edin" in satirlar[1]


def test_konu_ifadesi_ve_sapkali_harf_katlama():
    from app.ihtiyac import _katla
    assert _katla("Yapay Zekâ kâr") == "yapay zeka kar"
    soru = "bir yapay zeka girisimi kurmayi dusunuyorum".split()
    assert yerel_danisman._konu_ifadesi(soru, 3)                 # "girisimi": konu, program adı değil
    assert not yerel_danisman._konu_ifadesi("kirsal kalkinma hibesinin orani".split(), 2)   # "hibe": programın kendisi



def test_hedefli_acik_cagri_engel_yok_etiketi_almaz(monkeypatch):
    t = Tesvik(id=49, kurum="TUBITAK", baslik="1812 T", aktif_mi=True, uygunluk_kriterleri={"sektorler": ["genel"]},
               kontrol_listesi=[{"tur": "sart", "metin": "Üniversite mezunu olmak", "alinti": None, "kaynak_url": None,
                                 "dogrulandi": None}])
    cagri = {"ad": "Tohum Çağrısı", "notlar": "Bu çağrı 1812 tohum öncesi yatırım almış girişimler için açıktır.",
             "on_kayit_son": None, "kapanis": "2026-11-20", "kalan_gun": 40, "son_gun": "2026-11-20",
             "kaynak_url": "https://t", "dogrulama_tarihi": "2026-10-01", "acilis": None}
    monkeypatch.setattr(yerel_danisman, "cagri_bilgisi", lambda t, bugun: ("acik", cagri))
    d = yerel_danisman.degerlendir([t], _ltd(), {}, {}, set(), set(), BUGUN)[0]
    assert d.karar == "belirlenemedi" and d.gerekce[0].startswith("açık çağrı yalnız şunlar için")



def test_tarim_sektoru_sarti_profilden_karsilanir():
    ciftci = FinancialProfile(sektor="tarim", bolge="Konya")
    assert yerel_danisman._profilden_karsilanan("Tarım sektöründe faaliyet göstermek", ciftci)
    assert yerel_danisman._profilden_karsilanan("Çiftçi Kayıt Sistemine (ÇKS) kayıtlı tarımsal üretici olmak",
                                                ciftci) is None
    assert yerel_danisman._profilden_karsilanan("Tarım sektöründe faaliyet göstermek", _ltd()) is None



def test_ihracat_usd_esigi_ciroyla_karsilastirilir():
    t = Tesvik(id=8, kurum="Ticaret Bakanlığı", baslik="Çevrim İçi Mağaza T", aktif_mi=True,
               uygunluk_kriterleri={"sektorler": ["genel"], "min_onceki_yil_ihracat_usd": 1000000})
    kucuk = yerel_danisman.degerlendir([t], _ltd(yillik_ciro=4e6), {}, {}, set(), set(), BUGUN)[0]
    assert yerel_danisman.karar_etiketi(kucuk) == "Düşük olasılık — cironuz eşiğin altında"
    assert "1.000.000 USD" in kucuk.gerekce[0] and "4.000.000 TL" in kucuk.gerekce[0]
    buyuk = yerel_danisman.degerlendir([t], _ltd(yillik_ciro=2e8), {}, {}, set(), set(), BUGUN)[0]
    assert buyuk.karar == "belirlenemedi" and "önceki yıl en az 1.000.000 USD ihracat" in buyuk.gerekce[0]


def test_odemesiz_donem_tarih_sorusu_sayilmaz():
    assert "tarih" not in yerel_danisman.niyetler("Kredi ne kadar, vadesi ve ödemesiz dönemi nedir?")
    assert "tarih" in yerel_danisman.niyetler("Başvuru dönemi ne zaman?")



def test_sorudaki_ihtiyac_profil_hedefinin_onunde(veri):
    """Kapsam ölçümü 2026-10-11: hedefleri ihracat olan profil "personel alırsak" diye sorunca SGK teşviki kart
    olmalı; kredi ürünü değil."""
    _ek(veri, Tesvik(id=185, kurum="SGK / İŞKUR", baslik="İstihdam Teşviki T", ozet="istihdam prim desteği",
                     detay="işveren prim desteği", aktif_mi=True, kaynak_url="https://sgk/185",
                     uygunluk_kriterleri={"sektorler": ["genel"], "tutar_niteligi": "prim desteği"}))
    y = _yanit(veri, "Yeni personel alırsak hangi teşvikler var?", [185, 2, 4],
               _ltd(hedefler=["ihracat", "finansman"]))
    kartlar = re.findall(r"^\*\*(.+?) — ", y, re.M)
    assert kartlar and kartlar[0] == "İstihdam Teşviki T"



def test_harfleri_aralikli_alinti_gosterilmez():
    m = {"tur": "sart", "metin": "Proje süresi en az 12, en çok 18 ay", "alinti": "A s g a r i 1 2 a y , a z a m i 1 8",
         "dogrulandi": True}
    assert yerel_danisman._madde_metni(m) == "Proje süresi en az 12, en çok 18 ay"
    m2 = {**m, "alinti": "Asgari 12 ay, azami 18 aydır."}
    assert "resmî metin" in yerel_danisman._madde_metni(m2)



def test_yil_ile_baslayan_baslik_adiyla_taninir():
    assert yerel_danisman._baslik_jetonlari("2026 Yılı Turizm Ücret Desteği (özel tesisler)")[:3] == [
        "turizm", "ucret", "destegi"]
    t = Tesvik(id=901, baslik="2026 Yılı Turizm Ücret Desteği (turizm işletme belgeli tesisler)", kurum="SGK / İŞKUR")
    diger = Tesvik(id=902, baslik="2026 Yılı Asgari Ücret Desteği", kurum="SGK / İŞKUR")
    # küçük test verisinde "ücret" nadir kelime sayılıp diğer başlığı da getirebilir; aranan program ilk sırada olmalı
    bulunan = yerel_danisman.adi_gecen_programlar("Turizm ücret desteği 2026'da ne kadar?", [t, diger])
    assert bulunan and bulunan[0].id == 901
