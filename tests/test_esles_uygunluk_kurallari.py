"""esles(): kayıt metnine dayalı uygunluk engelleri ve hedef-tabanlı sektör eşleşmesi.

Ölçüm (2026-10-07, 8 persona): akademik TÜBİTAK çağrıları 6 işletme profilinde ilk 10'da;
TEKMER/TTO aracı kuruluş programları şirketsiz girişime 1.00 ile; KGF/KOSGEB kredileri
şirketsiz girişime; ortaklık yasaklı BiGG şirketi olan işletmeye; e-ihracat programları
hedefi ihracat olan imalatçıya hiç gelmiyordu."""
import pytest

from app.matching import esles, uygunluk_engeli
from app.models import FinancialProfile, Tesvik

TUBITAK = "https://tubitak.gov.tr/tr/destekler"


def _t(db, id, baslik, url, kurum="TUBITAK", sartlar=None, hedef_kitle="KOBI", sektorler=("genel",), aktif=True):
    t = Tesvik(id=id, kurum=kurum, baslik=baslik, ozet="o", detay="d", kaynak_url=url, aktif_mi=aktif,
               hedef_kitle=hedef_kitle, basvuru_sartlari=list(sartlar or []),
               uygunluk_kriterleri={"sektorler": list(sektorler)})
    db.add(t)
    return t


@pytest.fixture
def veri(db_session):
    _t(db_session, 65, "1002 - A Hızlı Destek Modülü", f"{TUBITAK}/akademik/1002", sektorler=("arge", "genel"))
    _t(db_session, 4, "Teknoloji Merkezi Destek Programı", "https://t/4", kurum="KOSGEB",
       sartlar=["Programdan TEKMER işletici kuruluşu ve TGB yönetici şirketi yararlanabilir."], sektorler=("arge",))
    _t(db_session, 174, "1512 - Girişimcilik Destek Programı (BiGG)", f"{TUBITAK}/sanayi/1512",
       sartlar=["Başvuru tarihi itibarıyla HERHANGİ BİR İŞLETMENİN ortaklık yapısında yer almamak (şirket kurulduysa başvurulamaz)"],
       hedef_kitle="Şirketi olmayan bireysel girişimciler", sektorler=("genel", "arge"))
    _t(db_session, 44, "1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç", f"{TUBITAK}/sanayi/1507",
       sartlar=["Türkiye'de yerleşik, sermaye şirketi statüsünde bir KOBİ olmak"], sektorler=("arge", "genel"))
    _t(db_session, 152, "TÜBİTAK Transfer Ödemeleri", "https://t/152", kurum="KGF",
       sartlar=["Firmanın; KOBİ niteliklerine sahip olması"])
    _t(db_session, 162, "E-İhracat Destekleri (5986 Sayılı Karar)", "https://t/162", kurum="Ticaret Bakanlığı",
       sektorler=("e-ticaret", "ihracat"))
    _t(db_session, 154, "KGF Genel Destek Programı", "https://t/154", kurum="KGF")
    db_session.commit()


def _basliklar(db, **kw):
    return [s.tesvik.baslik for s in esles(FinancialProfile(**kw), db)]


def test_akademik_cagri_hicbir_isletme_profiline_gelmez(veri, db_session):
    for kw in (dict(sektor="arge", sirket_turu="limited"), dict(sektor="arge"), dict(sektor="hizmet")):
        assert "1002 - A Hızlı Destek Modülü" not in _basliklar(db_session, **kw)


def test_araci_kurulus_programi_elenir(veri, db_session):
    assert "Teknoloji Merkezi Destek Programı" not in _basliklar(db_session, sektor="arge", sirket_turu="yok")
    assert "Teknoloji Merkezi Destek Programı" not in _basliklar(db_session, sektor="arge", sirket_turu="limited")


def test_sirketsiz_girisime_kgf_ve_sermaye_sirketi_sartli_programlar_gelmez(veri, db_session):
    b = _basliklar(db_session, sektor="arge", sirket_turu="yok")
    assert "1512 - Girişimcilik Destek Programı (BiGG)" in b
    assert "1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç" not in b
    assert "TÜBİTAK Transfer Ödemeleri" not in b and "KGF Genel Destek Programı" not in b


def test_sirketi_olana_ortaklik_yasakli_bigg_gelmez_1507_gelir(veri, db_session):
    b = _basliklar(db_session, sektor="arge", sirket_turu="limited")
    assert "1512 - Girişimcilik Destek Programı (BiGG)" not in b
    assert "1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç" in b and "KGF Genel Destek Programı" in b


def test_sirket_turu_bilinmiyorsa_sirketlesme_kurallari_elemez(veri, db_session):
    b = _basliklar(db_session, sektor="arge")
    assert "1512 - Girişimcilik Destek Programı (BiGG)" in b and "1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç" in b


def test_hedefi_ihracat_olan_imalatci_eihracat_programini_gorur(veri, db_session):
    sonuc = {s.tesvik.baslik: s for s in esles(FinancialProfile(sektor="imalat", hedefler=["ihracat"]), db_session)}
    assert "E-İhracat Destekleri (5986 Sayılı Karar)" in sonuc
    assert any("Hedefiniz" in g for g in sonuc["E-İhracat Destekleri (5986 Sayılı Karar)"].gerekce)
    assert "E-İhracat Destekleri (5986 Sayılı Karar)" not in _basliklar(db_session, sektor="imalat", hedefler=["yatirim"])


def test_1812_yer_alan_ifadesi_de_sirketi_olana_kapali():
    t = Tesvik(kurum="TUBITAK", baslik="1812 - Yatırım Tabanlı Girişimcilik Destek Programı (BiGG Yatırım)",
               kaynak_url=f"{TUBITAK}/sanayi/1812", basvuru_sartlari=[
                   "sermaye şirketi veya gerçek kişi işletmesi herhangi bir işletmenin ortaklık yapısında yer alan "
                   "kişiler başvuru yapamaz."])
    assert uygunluk_engeli(t, FinancialProfile(sektor="hizmet", sirket_turu="sahis")) is not None
    assert uygunluk_engeli(t, FinancialProfile(sektor="arge", sirket_turu="yok")) is None


def test_sirketsiz_girisime_teydeb_sanayi_programi_gelmez_bigg_gelir():
    teydeb = Tesvik(kurum="TUBITAK", baslik="1509 - TÜBİTAK Uluslararası Sanayi Ar-Ge Projeleri",
                    kaynak_url=f"{TUBITAK}/sanayi/1509", basvuru_sartlari=[])
    bigg = Tesvik(kurum="TUBITAK", baslik="1812 - Yatırım Tabanlı Girişimcilik Destek Programı (BiGG Yatırım)",
                  kaynak_url=f"{TUBITAK}/sanayi/1812", basvuru_sartlari=[])
    yok = FinancialProfile(sektor="arge", sirket_turu="yok")
    assert "sermaye şirketi" in uygunluk_engeli(teydeb, yok)
    assert uygunluk_engeli(bigg, yok) is None
    assert uygunluk_engeli(teydeb, FinancialProfile(sektor="arge", sirket_turu="limited")) is None


@pytest.mark.parametrize("kod", ["1503", "1513", "1514", "1601", "1612", "1613", "1701"])
def test_tubitak_ekosistem_cagrilari_isletmeye_onerilmez(kod):
    t = Tesvik(kurum="TUBITAK", baslik=f"{kod} - Program", kaynak_url=f"{TUBITAK}/sanayi/{kod}", basvuru_sartlari=[])
    assert uygunluk_engeli(t, FinancialProfile(sektor="arge", sirket_turu="limited")) == "akademik/araştırmacı çağrısı" \
        or uygunluk_engeli(t, FinancialProfile(sektor="arge", sirket_turu="limited")) is not None
    firma = Tesvik(kurum="TUBITAK", baslik="1507 - KOBİ Ar-Ge Başlangıç", kaynak_url=f"{TUBITAK}/sanayi/1507",
                   basvuru_sartlari=[])
    assert uygunluk_engeli(firma, FinancialProfile(sektor="arge", sirket_turu="limited")) is None


def test_esit_ana_skorda_nace_uyumu_siralamayi_belirler(db_session):
    """İki 'genel' program aynı ana skoru alır; NACE kaydı profille eşleşen öne geçer."""
    from app.models import TesvikNace
    a = _t(db_session, 301, "Alfa Genel Destek", "https://t/301", kurum="Ticaret Bakanlığı")
    z = _t(db_session, 302, "Zeta Bilişim Destek", "https://t/302", kurum="Ticaret Bakanlığı")
    z.nace_kayitlari = [TesvikNace(nace_prefix="62", kaynak="elle")]
    db_session.commit()
    sonuc = esles(FinancialProfile(sektor="hizmet", nace_kodu="62.10"), db_session)
    s = {x.tesvik.baslik: x for x in sonuc}
    assert s["Alfa Genel Destek"].skor == s["Zeta Bilişim Destek"].skor
    assert s["Zeta Bilişim Destek"].ince_skor > s["Alfa Genel Destek"].ince_skor
    assert [x.tesvik.baslik for x in sonuc].index("Zeta Bilişim Destek") < \
        [x.tesvik.baslik for x in sonuc].index("Alfa Genel Destek")


def test_kurum_cesitlendirme_ince_skoru_ezmez(db_session):
    """Eşit ana skorlu blokta kurum round-robin'i alfabetik değil, ince_skor sırasıyla döner:
    NACE uyumlu Ticaret Bakanlığı kaydı, 'A'/'K' ile başlayan kurumların arkasına atılmaz."""
    from app.models import TesvikNace
    _t(db_session, 311, "KGF Kredi A", "https://t/311", kurum="KGF")
    _t(db_session, 312, "1507 TÜBİTAK", "https://t/312", kurum="TUBITAK")
    z = _t(db_session, 313, "Hizmet İhracatı Bilişim", "https://t/313", kurum="Ticaret Bakanlığı")
    z.nace_kayitlari = [TesvikNace(nace_prefix="62", kaynak="elle")]
    db_session.commit()
    sonuc = esles(FinancialProfile(sektor="hizmet", nace_kodu="62.10", sirket_turu="limited"), db_session)
    assert len({x.skor for x in sonuc}) == 1, "üçü aynı ana skorda olmalı"
    assert sonuc[0].tesvik.id == 313
    assert {sonuc[1].tesvik.kurum, sonuc[2].tesvik.kurum} == {"KGF", "TUBITAK"}, "çeşitlilik korunur"


def test_nace_kisitli_program_nace_bilinmeyen_profile_tam_sektor_puani_almaz(db_session):
    """'hizmet' etiketli ama NACE 62/63'e kısıtlı program: profilde NACE yoksa genel hizmet
    programının altına iner; NACE 62 girilince tam puan geri gelir."""
    from app.models import TesvikNace
    genel = _t(db_session, 321, "Genel Hizmet Kredisi", "https://t/321", kurum="KGF", sektorler=("hizmet",))
    dar = _t(db_session, 322, "Bilişim Hizmet İhracatı", "https://t/322", kurum="Ticaret Bakanlığı",
             sektorler=("hizmet", "ihracat"))
    dar.nace_kayitlari = [TesvikNace(nace_prefix="62", kaynak="elle"), TesvikNace(nace_prefix="63", kaynak="elle")]
    db_session.commit()

    nacesiz = {x.tesvik.id: x for x in esles(FinancialProfile(sektor="hizmet", calisan_sayisi=4), db_session)}
    assert nacesiz[322].skor == pytest.approx(nacesiz[321].skor - 0.3)
    assert any("NACE" in e for e in nacesiz[322].eksik_kriterler)

    bilisim = {x.tesvik.id: x for x in esles(FinancialProfile(sektor="hizmet", calisan_sayisi=4, nace_kodu="62.01"),
                                             db_session)}
    assert bilisim[322].skor == bilisim[321].skor
    assert 322 not in {x.tesvik.id for x in esles(FinancialProfile(sektor="hizmet", calisan_sayisi=4,
                                                                    nace_kodu="56.10"), db_session)}, \
        "NACE biliniyor ve uyuşmuyorsa katı eleme çalışır"

    # Kısım düzeyi kapsam ("A"): 'tarim' etiketiyle eş anlamlı, NACE'siz çiftçi cezalandırılmaz.
    tarim_a = _t(db_session, 323, "Tarımsal Destek A", "https://t/323", kurum="Tarım Bakanlığı", sektorler=("tarim",))
    tarim_a.nace_kayitlari = [TesvikNace(nace_prefix="A", kaynak="elle")]
    tarim_genel = _t(db_session, 324, "Tarımsal Destek Genel", "https://t/324", kurum="Tarım Bakanlığı",
                     sektorler=("tarim",))
    db_session.commit()
    ciftci = {x.tesvik.id: x for x in esles(FinancialProfile(sektor="tarim", calisan_sayisi=3), db_session)}
    assert ciftci[323].skor == ciftci[324].skor


def test_uygunluk_engeli_gerekceleri():
    akademik = Tesvik(kurum="TUBITAK", baslik="x", kaynak_url=f"{TUBITAK}/akademik/1001")
    assert uygunluk_engeli(akademik, FinancialProfile(sektor="arge")) == "akademik/araştırmacı çağrısı"
    kgf = Tesvik(kurum="KGF", baslik="x", kaynak_url="https://t/k", basvuru_sartlari=[])
    assert "işletme" in uygunluk_engeli(kgf, FinancialProfile(sektor="arge", sirket_turu="yok"))
    assert uygunluk_engeli(kgf, FinancialProfile(sektor="arge", sirket_turu="sahis")) is None
