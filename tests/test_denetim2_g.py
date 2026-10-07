"""Denetim 2 / Aşama G: tarayıcıda sentetik profillerle yapılan denemede bulunan eşleştirme ve arama hataları
(2026-10-07). Konya'da 220 dekar buğday eken şahıs çiftçi ve Bursa'da 18 çalışanlı metal işleme KOBİ'si."""
from datetime import date

import pytest

from app.ihtiyac import soru_ihtiyaclari
from app.matching import (_hedef_eslesmeleri, _isletme_yas_siniri, esles, tutari_tahmini_hesapla,
                          uygunluk_engeli)
from app.models import FinancialProfile, Tesvik


def _t(id, kurum, baslik, sektorler, alt_kategori=None, ozet="o", sartlar=None, genislik=None,
       kaynak_url=None, **kw):
    uk = {"sektorler": list(sektorler)}
    if alt_kategori:
        uk["alt_kategori"] = alt_kategori
    if genislik:
        uk["genislik"] = genislik
    return Tesvik(id=id, kurum=kurum, baslik=baslik, ozet=ozet, detay="d", aktif_mi=True,
                  kaynak_url=kaynak_url or f"https://t/{id}", uygunluk_kriterleri=uk, basvuru_sartlari=sartlar or [], **kw)


# ---------------------------------------------------------------- 1. hedef eşleşmesi
def test_yatirim_hedefi_turkce_baslikla_eslesir():
    """ESKİ HATA: 'yatirim' kayıt başlığında harfiyen aranıyordu; 'Yatırım' hiç eşleşmiyordu."""
    kapasite = _t(8, "KOSGEB", "Kapasite Geliştirme Destek Programı", ["imalat"])
    hedef = _t(180, "Sanayi ve Teknoloji Bakanlığı", "Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)", ["genel"])
    assert _hedef_eslesmeleri(kapasite, {"yatirim"}, None) == ["yatirim"]
    assert _hedef_eslesmeleri(hedef, {"yatirim", "ihracat"}, None) == ["yatirim"]


def test_yatirim_tabanli_girisimcilik_yatirim_sayilmaz():
    bigg = _t(177, "TUBITAK", "1812 - Yatırım Tabanlı Girişimcilik Destek Programı (BiGG Yatırım)", ["arge"])
    assert "yatirim" not in _hedef_eslesmeleri(bigg, {"yatirim"}, None)


def test_tarim_hedefi_alt_kategoriyle_eslesir():
    hayvan = _t(76, "Tarım Bakanlığı", "Hayvancılık Destekleri", ["tarim"], "hayvancilik")
    assert _hedef_eslesmeleri(hayvan, {"hayvan", "makine"}, "hayvancilik") == ["hayvan"]


# ---------------------------------------------------------------- 2. sermaye şirketi ve işletme yaşı
@pytest.mark.parametrize("tur,engelli", [("sahis", True), ("kooperatif", True), ("limited", False), ("anonim", False)])
def test_tubitak_sanayi_sermaye_sirketi_ister(tur, engelli):
    t1501 = _t(40, "TUBITAK", "1501 - TÜBİTAK Sanayi Ar-Ge Projeleri Destekleme Programı", ["arge"],
               kaynak_url="https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/1501")
    sonuc = uygunluk_engeli(t1501, FinancialProfile(sektor="tarim", sirket_turu=tur))
    assert (sonuc is not None) is engelli
    if engelli:
        assert "sermaye şirketi" in sonuc


KOSGEB_GIRISIMCI_SARTLARI = ["İş Kurma Desteği: KOSGEB destekli sektörde faaliyet gösteren 0-1 yaş işletme",
                             "İş Geliştirme Desteği: İmalat/yazılım/Ar-Ge sektöründe 0-3 yaş işletme"]


def test_girisimci_programi_3_yasindan_buyuk_isletmeye_kapali():
    t1 = _t(1, "KOSGEB", "Girişimci Destek Programı", ["genel"], sartlar=KOSGEB_GIRISIMCI_SARTLARI)
    eski = FinancialProfile(sektor="imalat", sirket_turu="limited", kurulus_tarihi=date(2011, 6, 15))
    yeni = FinancialProfile(sektor="imalat", sirket_turu="limited", kurulus_tarihi=date(date.today().year - 1, 1, 1))
    bilinmiyor = FinancialProfile(sektor="imalat", sirket_turu="limited")
    assert "3 yaşına kadar" in uygunluk_engeli(t1, eski)
    assert uygunluk_engeli(t1, yeni) is None
    assert uygunluk_engeli(t1, bilinmiyor) is None, "kuruluş tarihi bilinmiyorsa elenmez"


def test_kisi_yasi_isletme_yasi_sayilmaz():
    """4447 SGK teşvikindeki '18-29 yaş erkekler' işletme yaşı değildir."""
    assert _isletme_yas_siniri("18-29 yaş erkekler 24–54 ay; 29 yaş ve üzeri erkekler") is None
    assert _isletme_yas_siniri(" ".join(KOSGEB_GIRISIMCI_SARTLARI)) == 3.0


# ---------------------------------------------------------------- 3. tarım alt kategorisi
@pytest.fixture
def tarim_db(db_session):
    db_session.add_all([
        _t(160, "Tarım Bakanlığı", "Hububat ve Baklagil Üretim Destekleri (Temel Destek + Planlı Üretim)", ["tarim"], "tahil_baklagil",
           genislik="dar"),
        _t(161, "Tarım Bakanlığı", "Meyve-Sebze Üretim Destekleri (Temel Destek)", ["tarim"], "sebze_meyve", genislik="dar"),
        _t(79, "Tarım Bakanlığı", "Sera/Örtüaltı Tarım Destekleri", ["tarim"], "sera", genislik="dar"),
        _t(76, "Tarım Bakanlığı", "Hayvancılık Destekleri", ["tarim"], "hayvancilik", genislik="dar"),
        _t(77, "Tarım Bakanlığı", "Organik Tarım Destekleri", ["tarim"], "organik", genislik="genis",
           tutari_min=500.0, tutari_max=2000.0, tutari_hesaplama_kriteri="dekar"),
    ])
    db_session.commit()
    return db_session


def _bugday(**kw):
    alan = dict(sektor="tarim", bolge="Konya", calisan_sayisi=3, yillik_ciro=2.4e6, arazi_buyuklugu_dekar=220,
                urun_turu="buğday, arpa", tarim_kategori="tahil_baklagil", sirket_turu="sahis", hedefler=["makine", "hayvan"])
    alan.update(kw)
    return FinancialProfile(**alan)


def test_acik_kategori_secilince_ilgisiz_dar_programlar_gelmez(tarim_db):
    ids = [s.tesvik.id for s in esles(_bugday(), tarim_db)]
    assert 160 in ids and 161 not in ids and 79 not in ids
    assert 76 in ids, "hedefinde hayvancılık olan tahıl üreticisi hayvancılık desteğini görür"


def test_hedefte_yoksa_hayvancilik_da_gelmez(tarim_db):
    ids = [s.tesvik.id for s in esles(_bugday(hedefler=["makine"]), tarim_db)]
    assert 76 not in ids


def test_organik_tahmini_tutar_yalniz_organik_ureticiye(tarim_db):
    organik = tarim_db.get(Tesvik, 77)
    assert tutari_tahmini_hesapla(organik, _bugday()) is None, "organik üretim yapmayana tahmini tutar yazılmaz"
    assert tutari_tahmini_hesapla(organik, _bugday(hedefler=["organik"])) == 220 * 1250
    assert tutari_tahmini_hesapla(organik, _bugday(tarim_kategori="organik")) == 220 * 1250
    assert tutari_tahmini_hesapla(organik, _bugday(tarim_kategori=None, urun_turu=None)) == 220 * 1250, \
        "faaliyet bilinmiyorsa tahmin engellenmez"


# ---------------------------------------------------------------- 4. arama: soru sınıflandırma
@pytest.mark.parametrize("soru,beklenen,beklenmeyen", [
    ("5 eksenli CNC tezgahı almak istiyoruz, yaklaşık 18 milyon TL, hangi destek ve krediler var?", "yatirim", None),
    ("Robot kaynak hücresi kurmak istiyoruz", "yatirim", None),
    ("Enjeksiyon kalıbı yaptıracağız", "yatirim", None),
    ("Çatıya güneş enerjisi santrali (GES) kuracağız", "yatirim", None),
    ("3 kişi daha işe alacağım, SGK desteği var mı?", "istihdam", None),
    ("Traktör ve mibzer almak istiyorum, hibe var mı?", None, "yatirim"),
    ("Depo kiraladım, stok için kredi lazım", "finansman", "yatirim"),
])
def test_soru_ihtiyaclari(soru, beklenen, beklenmeyen):
    ihtiyac = soru_ihtiyaclari(soru)
    if beklenen:
        assert beklenen in ihtiyac, ihtiyac
    if beklenmeyen:
        assert beklenmeyen not in ihtiyac, ihtiyac


# ---------------------------------------------------------------- 7. KOSGEB onayına bağlı KGF paketleri
@pytest.fixture
def kapasite_db(db_session):
    from app.models import TesvikNace
    db_session.add_all([
        _t(8, "KOSGEB", "Kapasite Geliştirme Destek Programı", ["imalat", "arge"]),
        _t(81, "KGF", "KAPASİTE GELİŞTİRME DESTEK PAKETİ", ["imalat", "arge"],
           ozet="KOSGEB tarafından desteklenmesi uygun bulunan KOBİ’lerin ölçek büyütme yatırımlarına finansman desteği"),
        _t(90, "KGF", "YATIRIM-İŞLETME DESTEK PAKETİ", ["imalat"], ozet="İmalatçı KOBİ’lerin yatırım harcamalarına finansman"),
    ])
    db_session.flush()
    for tid in (8, 81):
        for p in ("C", "62"):
            db_session.add(TesvikNace(tesvik_id=tid, nace_prefix=p, kaynak="test"))
    db_session.commit()
    return db_session


def test_kosgeb_onayina_bagli_paket_asil_programin_arkasinda(kapasite_db):
    p = FinancialProfile(sektor="imalat", bolge="Bursa", calisan_sayisi=18, yillik_ciro=32e6, nace_kodu="25.62",
                         sirket_turu="limited", hedefler=["yatirim", "ihracat"])
    es = esles(p, kapasite_db)
    sira = {e.tesvik.id: i for i, e in enumerate(es)}
    assert sira[8] < sira[81], [(e.tesvik.id, e.skor) for e in es]
    paket = next(e for e in es if e.tesvik.id == 81)
    assert any("KOSGEB programına kabul" in x for x in paket.eksik_kriterler)
    bagimsiz = next(e for e in es if e.tesvik.id == 90)
    assert not any("KOSGEB programına kabul" in x for x in bagimsiz.eksik_kriterler), "bağımsız KGF paketi cezalanmaz"


def test_ceza_tavandan_sonra_uygulanir(kapasite_db):
    """Ham skor 1,0'ı aşsa bile bağımlı paket asıl programla eşitlenmez."""
    p = FinancialProfile(sektor="imalat", calisan_sayisi=18, yillik_ciro=32e6, nace_kodu="25.62",
                         sirket_turu="limited", hedefler=["yatirim"])
    skor = {e.tesvik.id: e.skor for e in esles(p, kapasite_db)}
    assert skor[81] == pytest.approx(skor[8] - 0.05)


# ---------------------------------------------------------------- 8. serbest metinden toplam tahmin
@pytest.mark.parametrize("metin,beklenen", [
    ("₺100.000 - ₺500.000", (100000.0, 500000.0)),
    ("100.000–500.000 TL", (100000.0, 500000.0)),
    ("₺1.350.000", (1350000.0, 1350000.0)),
    ("5973 sayılı İhracat Destekleri Hakkında Karar kapsamında; limit Genelge'den teyit edilmeli "
     "(15.102 TL ifadesi 2022 yılına aitti)", (None, None)),
    ("%100 geri ödemesiz; program üst limiti toplam 700.000 TL (hizmet başına 20.000–150.000 TL)", (None, None)),
    (None, (None, None)),
])
def test_tutar_metni_yalniz_sade_aralikta_okunur(metin, beklenen):
    """GERÇEK OLAY: açıklayıcı tutar metnindeki yıl/karar no/yüzde toplam tahmine giriyordu."""
    from app.matching import _tutari_parse
    assert _tutari_parse(metin) == beklenen


# ---------------------------------------------------------------- 9. alt ölçek sınırı ve başlıkla sınırlı hedef araması
def test_min_olcek_mikro_isletmeyi_eler():
    from app.match_adapter import company_from_profile, program_from_tesvik
    from app.match_scoring import hard_filter
    t = _t(3, "KOSGEB", "KOBİ Dijital Dönüşüm Destek Programı", ["imalat"])
    t.uygunluk_kriterleri = {**t.uygunluk_kriterleri, "min_olcek": "kucuk", "max_olcek": "orta"}
    program = program_from_tesvik(t)
    mikro = company_from_profile(FinancialProfile(sektor="imalat", calisan_sayisi=3, yillik_ciro=4e6))
    kucuk = company_from_profile(FinancialProfile(sektor="imalat", calisan_sayisi=18, yillik_ciro=32e6))
    buyuk = company_from_profile(FinancialProfile(sektor="imalat", calisan_sayisi=400, yillik_ciro=2e9))
    bilinmiyor = company_from_profile(FinancialProfile(sektor="imalat"))
    assert any("en az 'kucuk'" in s for s in hard_filter(mikro, program)[0])
    assert hard_filter(kucuk, program)[0] == []
    assert any("en çok 'orta'" in s for s in hard_filter(buyuk, program)[0])
    assert hard_filter(bilinmiyor, program)[0] == [], "ölçek bilinmiyorsa elemez"


def test_hedef_yedek_aramasi_ozetteki_menu_metnine_bakmaz():
    """GERÇEK OLAY: kazınmış özetteki site menüsü ('İhracat Destek Paketi') KGF Dijital Dönüşüm paketini
    ihracat hedefiyle eşleştiriyor ve asıl KOSGEB programının önüne geçiriyordu."""
    paket = _t(125, "KGF", "2024 Dijital Dönüşüm Destek Paketi", ["imalat"],
               ozet="2024 Dijital Dönüşüm Destek Paketi\nİhracat Destek Paketi\nİstihdamı Koruma")
    assert _hedef_eslesmeleri(paket, {"ihracat", "istihdam"}, None) == []
    ihracat = _t(159, "KGF", "İhracat Destek Paketi", ["ihracat"])
    assert _hedef_eslesmeleri(ihracat, {"ihracat"}, None) == ["ihracat"]
