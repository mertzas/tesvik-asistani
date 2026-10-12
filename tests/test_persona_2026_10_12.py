"""Persona denemesinin (docs/olcum/2026-10-12-persona: Rekortiv, fındık/çilek üreticisi, matbaa, sürücü kursu, 5 KOBİ,
10 İKAS mağazası) ortaya çıkardığı hataları kilitleyen testler. Her test bir hakem bulgusuna karşılık gelir."""
import pytest

from app import yerel_danisman
from app.ihtiyac import program_ihtiyaclari, soru_ihtiyaclari
from app.matching import esles, ihracat_odakli, uygunluk_engeli
from app.models import FinancialProfile, Tesvik


def _t(**kw):
    v = dict(kurum="KOSGEB", baslik="Program", ozet="o", detay="d", aktif_mi=True,
             kaynak_url=f"https://t/{kw.get('id', kw.get('baslik', 'x'))}", uygunluk_kriterleri={"sektorler": ["genel"]})
    v.update(kw)
    return Tesvik(**v)


# ------------------------------------------------------------------ soru ihtiyaçları
@pytest.mark.parametrize("soru,var,yok", [
    ("Dolu ve don riskine karşı sigorta yaptırırsam devlet ne kadarını öder?", {"sigorta"}, {"istihdam"}),
    ("İki yeni çalışan alacağız; SGK ve İŞKUR teşvikleri neler?", {"istihdam"}, {"sigorta"}),
    ("Sigorta primi desteği var mı?", {"istihdam"}, {"sigorta"}),
    ("Yurt dışına gönderdiğim kargoların masrafı için destek alabilir miyim?", {"lojistik", "ihracat"}, set()),
    ("Instagram ve Google reklam giderlerim için destek alabilir miyim?", {"tanitim"}, set()),
    ("Markamızı yurt dışında tescil ettirmenin desteği var mı?", {"tescil"}, {"tanitim"}),
    ("Matbaamıza 4 milyon TL'lik yeni dijital baskı makinesi almak istiyoruz", {"yatirim"}, {"dijital"}),
    ("Online kahve satışımızı büyütmek için dijital pazarlama desteği var mı?", {"tanitim"}, {"dijital"}),
    ("Evcil hayvan ürünleri satan e-ticaret şirketimiz için işletme sermayesi kredisi", {"finansman"}, {"dijital"}),
    ("Depoya 3 kişi alacağız, istihdam teşviki var mı?", {"istihdam"}, {"lojistik"}),
    ("Amazon Avrupa'da mağaza açmak için destek var mı?", {"ihracat", "dijital"}, set()),
    ("9 dönüm fındık bahçem var, toplam ne kadar eder?", {"tarim_odeme"}, set()),
    ("Bahçeyi yenilemek ve damla sulama kurmak için kredi var mı?", {"finansman"}, {"tarim_odeme"}),
    ("Seramik fırını almak için KOSGEB'den destek alabilir miyim?", {"yatirim"}, set()),
])
def test_soru_ihtiyaclari(soru, var, yok):
    s = set(soru_ihtiyaclari(soru))
    assert var <= s and not (yok & s), s


@pytest.mark.parametrize("kurum,baslik,var,yok", [
    ("TARSİM", "TARSİM — Devlet Destekli Tarım Sigortası, 2026 Prim Desteği", {"sigorta"}, set()),
    ("SGK / İŞKUR", "Malullük, Yaşlılık ve Ölüm Sigortaları İşveren Hissesinden Prim İndirimi (5510 sayılı Kanun 81/ı) — "
                    "2 puan, imalatta 2026 sonuna kadar 5 puan", {"istihdam"}, {"yatirim", "sigorta"}),
    ("SGK / İŞKUR", "İş Sağlığı ve Güvenliği Hizmetlerinin Desteklenmesi", set(), {"istihdam"}),
    ("KGF", "İSTİHDAM KORUMA DESTEK PROGRAMI", {"finansman"}, {"istihdam"}),
    ("Ticaret Bakanlığı", "Şirket ve Marka Alım Desteği (5973 sayılı Karar m.9)", set(), {"tanitim"}),
    ("Ticaret Bakanlığı", "Yurt Dışı Marka Tescil Desteği (5973 sayılı Karar m.4)", {"tescil"}, {"tanitim"}),
    ("KOSGEB", "YÖNDE - Yönderlik ve Değerlendirme Destek Programı", {"dijital"}, set()),
])
def test_program_ihtiyaclari(kurum, baslik, var, yok):
    s = program_ihtiyaclari(_t(kurum=kurum, baslik=baslik))
    assert var <= s and not (yok & s), s


# ------------------------------------------------------------------ uygunluk kuralları
def test_calisan_ve_magaza_esikleri():
    isbasi = _t(kurum="SGK / İŞKUR", baslik="İşbaşı", kontrol_listesi=[
        {"tur": "sart", "metin": "İşverenin en az beş sigortalı çalışanı olmalıdır."}])
    ayb = _t(kurum="Türk Eximbank", baslik="AYB", kontrol_listesi=[
        {"tur": "sart", "metin": "250 ile 3.000 arasında çalışanı olan orta ölçekli işletme"}])
    zincir = _t(kurum="Ticaret Bakanlığı", baslik="Zincir", kontrol_listesi=[
        {"tur": "sart", "metin": "yurt içinde en az 100 fiziksel perakende mağazası bulunmalıdır."}])
    tehlikeli = _t(kurum="SGK / İŞKUR", baslik="Çok tehlikeli", kontrol_listesi=[
        {"tur": "sart", "metin": "her ay toplamda ondan fazla çalışanı bulunmalıdır."}])
    kucuk = FinancialProfile(sektor="imalat", sirket_turu="limited", calisan_sayisi=4)
    assert "en az 5 çalışan" in uygunluk_engeli(isbasi, kucuk)
    assert "250-3000" in uygunluk_engeli(ayb, kucuk)
    assert "100 mağaza" in uygunluk_engeli(zincir, kucuk)
    assert "ondan fazla" in uygunluk_engeli(tehlikeli, kucuk)
    assert uygunluk_engeli(isbasi, FinancialProfile(sektor="imalat", sirket_turu="limited")) is None, \
        "çalışan sayısı bilinmiyorsa elemez"


def test_atilim_programi_sektor_kapsami():
    atilim = _t(kurum="Ticaret Bakanlığı", baslik="Hizmet Sektörleri Atılım Programı — Etkinlik (10962 sayılı Karar m.13)")
    yazilim = _t(kurum="Ticaret Bakanlığı", baslik="Hizmet Sektörleri Atılım Programı — Yazılım Lisans (10962 sayılı "
                 "Karar m.31)", kontrol_listesi=[{"tur": "sart", "metin": "Destek, bilişim sektöründeki yararlanıcının "
                                                  "yazılım pazarlamasına verilir."}])
    otel = FinancialProfile(sektor="hizmet", nace_kodu="55.10", sirket_turu="limited")
    surucu = FinancialProfile(sektor="hizmet", nace_kodu="85.53", sirket_turu="limited")
    saas = FinancialProfile(sektor="arge", nace_kodu="62.01", sirket_turu="limited")
    assert "Atılım Programı yalnız" in uygunluk_engeli(atilim, otel)
    assert uygunluk_engeli(atilim, surucu) is None, "eğitim (85) Atılım sektörlerinde"
    assert "bilişim" in uygunluk_engeli(yazilim, surucu), "bilişime özgü destek unsuru"
    assert uygunluk_engeli(yazilim, saas) is None


def test_kultur_turizm_baska_urun_ve_urun_listesi():
    turizm = _t(kurum="Kültür ve Turizm Bakanlığı", baslik="Turizm Yatırımı/İşletme Belgeli Tesislere Teşvikler")
    findik = _t(kurum="Tarım Bakanlığı", baslik="Fındık Temel Desteği", uygunluk_kriterleri={"sektorler": ["tarim"]})
    fidan = _t(kurum="Tarım Bakanlığı", baslik="Sertifikalı/Standart Fidan Kullanım Desteği",
               uygunluk_kriterleri={"sektorler": ["tarim"], "urun_listesi": ["elma", "fındık"]})
    assert "turizm belgeli" in uygunluk_engeli(turizm, FinancialProfile(sektor="hizmet", nace_kodu="85.53"))
    assert uygunluk_engeli(turizm, FinancialProfile(sektor="hizmet", nace_kodu="55.10")) is None
    cilek = FinancialProfile(sektor="tarim", urun_turu="çilek", sirket_turu="sahis")
    assert uygunluk_engeli(findik, cilek) == "başka bir ürüne özel destek"
    assert "listede yok" in uygunluk_engeli(fidan, cilek)
    assert uygunluk_engeli(fidan, FinancialProfile(sektor="tarim", urun_turu="fındık")) is None


def test_sirketsize_acik_kayit_ve_araci_kurulus():
    egitim = _t(kurum="KOSGEB", baslik="KOSGEB Girişimcilik Eğitimi",
                uygunluk_kriterleri={"sektorler": ["genel"], "sirket_turleri": ["yok"]})
    fon = _t(kurum="KOSGEB", baslik="Girişim Sermayesi Fonları", uygunluk_kriterleri={"sektorler": ["genel"],
                                                                                        "araci_kurulus": True})
    assert uygunluk_engeli(egitim, FinancialProfile(sektor="arge", sirket_turu="yok")) is None
    assert uygunluk_engeli(fon, FinancialProfile(sektor="imalat", sirket_turu="limited")).startswith("aracı")


def test_ihracat_odakli_tanimi():
    assert ihracat_odakli(_t(kurum="Türk Eximbank", baslik="E-İhracat Destek Kredisi"))
    assert ihracat_odakli(_t(kurum="KGF", baslik="ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ"))
    assert ihracat_odakli(_t(kurum="Ticaret Bakanlığı", baslik="Yurt Dışı Fuar Desteği (5973 sayılı Karar m.7)"))
    assert not ihracat_odakli(_t(kurum="KGF", baslik="KGF Genel Destek Programı"))


# ------------------------------------------------------------------ eşleştirme sırası
def test_ihracat_programi_ihracatsiz_profilde_geride_ama_listede(db_session):
    db_session.add_all([
        _t(id=901, kurum="Türk Eximbank", baslik="İhracata Hazırlık Kredisi",
           uygunluk_kriterleri={"sektorler": ["ihracat", "hizmet"]}),
        _t(id=902, kurum="KGF", baslik="Genel Kefalet", uygunluk_kriterleri={"sektorler": ["genel"],
                                                                            "tutar_niteligi": "kredi_kefalet"}),
    ])
    db_session.commit()
    kurs = FinancialProfile(sektor="hizmet", nace_kodu="85.53", sirket_turu="limited", calisan_sayisi=9,
                            hedefler=["finansman"])
    sonuc = [s.tesvik.id for s in esles(kurs, db_session)]
    assert sonuc.index(902) < sonuc.index(901), "ihracat kredisi ihracatı olmayan kursta geride"
    ihracatci = FinancialProfile(sektor="hizmet", nace_kodu="85.53", sirket_turu="limited", calisan_sayisi=9,
                                 hedefler=["finansman", "ihracat"])
    assert [s.tesvik.id for s in esles(ihracatci, db_session)][0] == 901
    # Hazırlık karşı-olgusu ilgi cezası uygulamaz: uygunluk sayılır.
    ham = {s.tesvik.id: s.skor for s in esles(kurs, db_session, ilgi_cezalari=False)}
    assert ham[901] >= ham[902]


def test_makine_hedefi_yatirim_programina_eslesir_durum_programi_geride(db_session):
    db_session.add_all([
        _t(id=911, kurum="KGF", baslik="YATIRIM-İŞLETME DESTEK PAKETİ",
           uygunluk_kriterleri={"sektorler": ["genel"], "tutar_niteligi": "kredi_kefalet"}),
        _t(id=912, kurum="KGF", baslik="REFİNANSMAN KEFALET PROGRAMI",
           uygunluk_kriterleri={"sektorler": ["imalat"], "tutar_niteligi": "kredi_kefalet"}),
    ])
    db_session.commit()
    matbaa = FinancialProfile(sektor="imalat", nace_kodu="18.12", sirket_turu="limited", calisan_sayisi=6,
                              hedefler=["makine", "finansman"])
    sonuc = [s.tesvik.id for s in esles(matbaa, db_session)]
    assert sonuc.index(911) < sonuc.index(912)


# ------------------------------------------------------------------ yanıt motoru yardımcıları
def test_varsayimsal_sirket_profili():
    p = FinancialProfile(sektor="arge", sirket_turu="yok", nace_kodu="62.01", kurucu_yasi=21)
    v = yerel_danisman.varsayimsal_profil("Şirket kurarsam KOSGEB'den ne alabilirim?", p)
    assert v.sirket_turu == "limited" and "varsayımıyla" in v._varsayim and p.sirket_turu == "yok"
    assert yerel_danisman.varsayimsal_profil("Hangi hibeler var?", p) is p
    z = yerel_danisman.varsayimsal_profil("Reklam desteği var mı?", p, zorla=True)
    assert z.sirket_turu == "limited" and "şirketiniz olmadan" in z._varsayim
    ltd = FinancialProfile(sektor="imalat", sirket_turu="limited")
    assert yerel_danisman.varsayimsal_profil("Şirket kurarsam?", ltd) is ltd


def test_tarim_odeme_satiri_findik_ve_cilek():
    findik = FinancialProfile(sektor="tarim", urun_turu="fındık", arazi_buyuklugu_dekar=9, bolge="Ordu")
    s = yerel_danisman.tarim_odeme_satiri("9 dönüm fındık bahçem var, toplam ne kadar eder?", findik)
    assert "550,50 TL/da × 9 da = 4.954,50 TL" in s and "fındık üretimine izin verilen ilçe" in s
    cilek = FinancialProfile(sektor="tarim", urun_turu="çilek", arazi_buyuklugu_dekar=1.5)
    assert "367,00 TL/da × 1,5 da = 550,50 TL" in yerel_danisman.tarim_odeme_satiri("hangi destekler var?", cilek)
    assert yerel_danisman.tarim_odeme_satiri("Dolu sigortası yaptırırsam devlet ne kadarını öder?", cilek) == "", \
        "sigorta sorusunda doğrudan ödeme hesabı yazılmaz"
    assert yerel_danisman.tarim_odeme_satiri("toplam ne kadar?", FinancialProfile(sektor="imalat")) == ""


def test_kredi_etiketi_ve_adi_gecen_genel_kelimeler(db_session):
    assert yerel_danisman._kredi_mi(_t(kurum="KGF", baslik="X"))
    assert not yerel_danisman._kredi_mi(_t(kurum="Ticaret Bakanlığı", baslik="Y", basvuru_bicimi="faiz_destegi"))
    tum = [_t(id=921, kurum="Türk Eximbank", baslik="Türk Eximbank Sevk Öncesi İhracat Kredi Sigortası (alıcının siparişi "
              "iptal etme riskine karşı sigorta)"),
           _t(id=922, kurum="Ticaret Bakanlığı", baslik="Yurt Dışı Pazar Araştırması Desteği (5973 sayılı Karar m.6)"),
           _t(id=923, kurum="Ticaret Bakanlığı", baslik="Yurt Dışı Pazaryeri Komisyon Gideri Desteği")]
    # "riskine karşı" gündelik ifadedir, program adı değil (gerçek veritabanında "sigorta" zaten çok başlıkta geçer)
    assert yerel_danisman.adi_gecen_programlar("Dolu ve don riskine karşı ne yapabilirim?", tum) == []
    adlar = [t.id for t in yerel_danisman.adi_gecen_programlar("yurt dışı pazaryerlerinde reklam desteği var mı?", tum)]
    assert 922 not in adlar, "pazar ≠ pazaryeri"


# ------------------------------------------------------------------ ikinci hakem turu bulguları
def test_ek3_haric_alt_kol_uygun_degil():
    from app.tesvik_9903_uygunluk import _ek3_durumu
    assert _ek3_durumu("85.53")[0] == "uygun_degil", "sürücü kursu: 85 Eğitim kaleminde 85.5 hariç"
    assert _ek3_durumu("85.10")[0] in ("sartli", "uygun")
    assert _ek3_durumu("87.90")[0] == "uygun_degil" and _ek3_durumu("87.10")[0] == "uygun"


def test_turizm_ucret_teknopark_ve_teknik_destek():
    turizm = _t(kurum="SGK / İŞKUR", baslik="2026 Yılı Turizm Ücret Desteği (turizm işletme belgeli konaklama)")
    assert "turizm belgeli" in uygunluk_engeli(turizm, FinancialProfile(sektor="hizmet", nace_kodu="85.53",
                                                                       sirket_turu="limited"))
    assert uygunluk_engeli(turizm, FinancialProfile(sektor="hizmet", nace_kodu="55.10", sirket_turu="limited")) is None
    tgb = _t(kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Teknoloji Geliştirme Bölgesi (Teknopark) Kazanç İstisnası")
    assert program_ihtiyaclari(tgb) == {"arge"}
    ajans = _t(kurum="Ahiler Kalkınma Ajansı", baslik="Sanayide Verimlilik Teknik Destek Programı",
               kategori="yatirim tesvik")
    assert "yatirim" not in program_ihtiyaclari(ajans)


def test_olcek_adi_turkce():
    from app.match_adapter import company_from_profile, program_from_tesvik
    from app.match_scoring import hard_filter
    t = _t(kurum="KOSGEB", baslik="X", uygunluk_kriterleri={"sektorler": ["imalat"], "min_olcek": "kucuk"})
    s = hard_filter(company_from_profile(FinancialProfile(sektor="imalat", calisan_sayisi=3, yillik_ciro=4e6)),
                    program_from_tesvik(t))[0]
    assert any("küçük ölçeğindeki" in x for x in s) and not any("'kucuk'" in x for x in s)


def test_yatirim_buyuklugu_tutar_iddiasi_sayilmaz():
    assert yerel_danisman.dogrulanamayan_tutarlar("4 milyon TL'lik baskı makinesi almak istiyoruz", []) == []
    assert yerel_danisman.dogrulanamayan_tutarlar("Hâlâ 15.102 TL mi veriliyor?", []) == ["15.102 TL"]


def test_sirket_kurma_niyeti_varsayim_degil():
    p = FinancialProfile(sektor="arge", sirket_turu="yok")
    assert yerel_danisman.varsayimsal_profil("Şirket kurmak istiyorum, hangi girişim destekleri var?", p) is p
    assert yerel_danisman.varsayimsal_profil("Şirketimi kurduktan sonra hangi destekler açılır?", p).sirket_turu == "limited"


def test_kucuk_ailedeki_tekrar_eki_bir_kez():
    metin = "a (kayıttan; güncel çağrıyı kurumdan teyit edin) b (kayıttan; güncel çağrıyı kurumdan teyit edin) c"
    assert yerel_danisman.tekrarlari_kisalt(metin).count("(kayıttan; güncel çağrıyı kurumdan teyit edin)") == 1


# ------------------------------------------------------------------ üçüncü hakem turu bulguları
def test_calisan_esigi_ve_isletme_yasi_profilden_karsilanir():
    dokuz = FinancialProfile(sektor="hizmet", sirket_turu="limited", calisan_sayisi=9)
    assert "en az 5; profilinizde 9" in yerel_danisman._profilden_karsilanan(
        "İşverenin en az beş sigortalı çalışanı olmalıdır.", dokuz)
    assert yerel_danisman._profilden_karsilanan(
        "İşverenin en az beş sigortalı çalışanı olmalıdır.",
        FinancialProfile(sektor="hizmet", sirket_turu="limited", calisan_sayisi=3)) is None
    yok = FinancialProfile(sektor="arge", sirket_turu="yok", nace_kodu="62.01")
    kurulacak = yerel_danisman.varsayimsal_profil("Şirket kurarsam KOSGEB'den ne alabilirim?", yok)
    assert kurulacak.kurulus_tarihi is not None and yok.kurulus_tarihi is None
    sart = "İş Kurma Desteği: KOSGEB destekli sektörde faaliyet gösteren 0-1 yaş işletme"
    assert "kurulacak şirket" in yerel_danisman._profilden_karsilanan(sart, kurulacak)
    assert yerel_danisman._profilden_karsilanan(sart, yok) is None


def test_girisimcilik_egitimi_girisim_ihtiyacidir():
    t = _t(kurum="KOSGEB", baslik="KOSGEB Girişimcilik Eğitimi (e-Akademi) — Ücretsiz Online Geleneksel ve İleri "
                                  "Girişimcilik Eğitimi")
    assert program_ihtiyaclari(t) == {"girisim"}


# ------------------------------------------------------------------ dördüncü hakem turu bulguları
def test_ek3_sutun_kaymasi_duzeldi():
    from app.nace_9903 import ek3_kaydi
    assert ek3_kaydi("55.10")["sartlar"].startswith("50 oda ve üzeri"), "otel: oda şartı şart sütununda"
    assert "100 Milyon TL ve üzerindeki tevsi ve modernizasyon" in ek3_kaydi("18.12")["sartlar"]
    assert ek3_kaydi("82.20")["sartlar"].startswith("Sadece 6 ncı bölgede"), "çağrı merkezi şartı tanımda kalmıştı"
    assert "Demir cevherinin" in ek3_kaydi("24.10.08")["tanim"], "komşu kodun (ferro alaşım) metni yazılmıştı"


def test_soru_yatirim_tutari_ve_9903_asgari():
    from app.tesvik_9903_uygunluk import degerlendir, soru_yatirim_tutari, tutar_siniri
    assert soru_yatirim_tutari("yaklaşık 4 milyon TL'lik baskı makinesi") == 4_000_000
    assert soru_yatirim_tutari("750 bin TL") == 750_000 and soru_yatirim_tutari("%50 hibe") is None
    matbaa = tutar_siniri(degerlendir("hedef_yatirimlar", "18.12", "İstanbul", "kucuk"), 4e6, "İstanbul")
    assert matbaa.durum == "uygun_degil" and "EK-3 kalem şartının altında" in matbaa.gerekce
    otel = tutar_siniri(degerlendir("hedef_yatirimlar", "55.10", "Antalya", "kucuk"), 8e6, "Antalya")
    assert otel.durum == "uygun_degil" and otel.madde == "MADDE 5/2"
    buyuk = tutar_siniri(degerlendir("hedef_yatirimlar", "55.10", "Antalya", "kucuk"), 50e6, "Antalya")
    assert buyuk.durum == "sartli"


def test_tesvik_belgesi_satiri_kisa_cevapta():
    p = FinancialProfile(sektor="imalat", nace_kodu="18.12", sirket_turu="limited", calisan_sayisi=6,
                         yillik_ciro=9e6, bolge="İstanbul")
    s = yerel_danisman.tesvik_belgesi_satiri("4 milyon TL'lik makine için hangi kredi, hibe ya da teşvik belgesi?", p, [])
    assert "Hedef Yatırımlar" in s and "uygun değil" in s
    assert yerel_danisman.tesvik_belgesi_satiri("Makine kredisi var mı?", p, []) == ""


def test_usd_esigi_sart_metninden():
    t = _t(kurum="Ticaret Bakanlığı", baslik="Marka", kontrol_listesi=[
        {"tur": "sart", "metin": "Son 3 yıl ortalama ihracatın en az 3.000.000 ABD Doları olması"}])
    assert yerel_danisman.usd_esigi(t) == (3_000_000, "ihracat")
    g = _t(kurum="Ticaret Bakanlığı", baslik="Markalaşma", kontrol_listesi=[
        {"tur": "sart", "metin": "Son üç takvim yılı gelirlerinin ortalaması en az 1.500.000 ABD doları olmalıdır."}])
    assert yerel_danisman.usd_esigi(g) == (1_500_000, "gelir")
    ithalat = _t(kurum="Sanayi", baslik="Hamle", kontrol_listesi=[
        {"tur": "sart", "metin": "konu ürünün son 1 yıldaki toplam ithalatı en az 50 milyon ABD doları"}])
    assert yerel_danisman.usd_esigi(ithalat) is None


def test_tobb_uyeligi_sirkette_saglanir():
    sart = "TOBB üyesi bir işletme olmak (ticaret, sanayi veya deniz ticaret odası ya da ticaret borsası üyesi)"
    assert "oda (TOBB) üyeliği" in yerel_danisman._profilden_karsilanan(sart, FinancialProfile(sirket_turu="limited"))
    assert yerel_danisman._profilden_karsilanan(sart, FinancialProfile(sirket_turu="sahis")) is None
    assert yerel_danisman._profilden_karsilanan("Esnaf ve sanatkârlar odası üyesi olmak",
                                               FinancialProfile(sirket_turu="limited")) is None


def test_ise_alinacak_kisi_sarti_kilit_degil(db_session):
    from datetime import date
    t = _t(id=941, kurum="SGK / İŞKUR", baslik="Kadın, Genç ve MYB İstihdamı Teşviki", kontrol_listesi=[
        {"tur": "sart", "metin": "İşe alınan kişinin son 6 aydır işsiz olması"}])
    p = FinancialProfile(sektor="hizmet", sirket_turu="limited", calisan_sayisi=9, yillik_ciro=7.5e6)
    d = yerel_danisman.degerlendir([t], p, {}, {}, set(), set(), date(2026, 10, 12), soru="Yeni çalışan alırsak?")[0]
    assert d.karar == "belirlenemedi" and d.gerekce[0].startswith(yerel_danisman.KISI_ONEKI)
    assert not any(g.startswith(yerel_danisman.KILIT_ONEKI) for g in d.gerekce)


def test_yenileme_yatirim_ihtiyaci_ve_kosgeb_kaydi():
    assert "yatirim" in soru_ihtiyaclari("Butik otelimizi yenilemek için kredi ya da hibe var mı?")
    assert "yatirim" not in soru_ihtiyaclari("Teşvik belgemi yenilemem gerekiyor mu?")
    assert "yatirim" not in soru_ihtiyaclari("Bahçeyi yenilemek ve damla sulama kurmak için kredi var mı?")
    from app.hazirlik import program_adimlari
    egitim = _t(kurum="KOSGEB", baslik="KOSGEB Girişimcilik Eğitimi (e-Akademi)",
                tesvil_tutari="Ücretsiz eğitim (parasal destek değildir)")
    assert "kosgeb_kaydi" not in program_adimlari(egitim)
    assert "kosgeb_kaydi" in program_adimlari(_t(kurum="KOSGEB", baslik="Girişimci Destek Programı"))



def test_gider_kalemi_eslesmesi():
    dijital = _t(kurum="KOSGEB", baslik="KOBİ Dijital Dönüşüm", tesvil_tutari="Yazılım ve Donanım Giderleri için faiz desteği")
    yonde = _t(kurum="KOSGEB", baslik="YÖNDE", tesvil_tutari="belgeli danışmandan alınan hizmet desteği")
    soru = "Üretimi dijitalleştirmek (ERP, makinelere sensör) için hibe var mı?"
    assert yerel_danisman.gider_kalemi_eslesmesi(soru, dijital) > yerel_danisman.gider_kalemi_eslesmesi(soru, yonde)
    assert yerel_danisman.gider_kalemi_eslesmesi("Hangi destekler var?", dijital) == 0


def test_bilgi_yok_cumlesi_ve_sektor_gerekcesi_tekrarlanmaz():
    cumle = "Dönemsel çağrı yoktur; kaynakta başvuru tarihi veya son başvuru süresi belirtilmemiştir."
    metin = yerel_danisman.tekrarlari_kisalt(f"- A: {cumle} X.\n- B: {cumle} Y..")
    assert metin.count("belirtilmemiştir") == 1 and ".." not in metin
    assert yerel_danisman._birlestir(["mikro; program sektörü işletmenin NACE kodlarıyla örtüşmüyor; programın sektör "
                                      "kapsamı (imalat) faaliyetinizi kapsamıyor"]) == \
        "programın sektör kapsamı (imalat) faaliyetinizi kapsamıyor; mikro"   # kalıcı engel önce


def test_kapali_cagri_eslesme_listesinde_geride(db_session):
    from datetime import date, timedelta
    from app.models import TesvikCagrisi
    acik = _t(id=951, kurum="KOSGEB", baslik="Açık Program", uygunluk_kriterleri={"sektorler": ["imalat"]})
    kapali = _t(id=952, kurum="KOSGEB", baslik="Kapanmış Program", uygunluk_kriterleri={"sektorler": ["imalat"]})
    db_session.add_all([acik, kapali])
    db_session.add(TesvikCagrisi(tesvik_id=952, ad="2026/2", acilis=date.today() - timedelta(days=120),
                                 kapanis=date.today() - timedelta(days=10), kaynak_url="https://t/c952",
                                 dogrulama_tarihi=date.today()))
    db_session.commit()
    p = FinancialProfile(sektor="imalat", sirket_turu="limited", calisan_sayisi=20, yillik_ciro=30e6)
    sonuc = {e.tesvik.id: e for e in esles(p, db_session, limit=10_000)}
    assert sonuc[952].siralama < sonuc[951].siralama
    assert any("Başvuru dönemi şu an kapalı" in x for x in sonuc[952].eksik_kriterler)



# ------------------------------------------------------------------ beşinci hakem turu bulguları
def test_arge_personeli_sarti_toplam_calisanla_karsilanmaz():
    sart = "Ar-Ge merkezi: en az elli tam zaman eşdeğer Ar-Ge personeli istihdam edilmelidir"
    p = FinancialProfile(sektor="imalat", sirket_turu="anonim", calisan_sayisi=65, yillik_ciro=210e6)
    assert yerel_danisman._profilden_karsilanan(sart, p) is None
    assert yerel_danisman._KILIT.search(sart)


def test_orta_olcekli_firmanin_trl_projesi_girisim_degil():
    from app.girisim import girisim_modu_mu
    buyuk = FinancialProfile(sektor="imalat", sirket_turu="anonim", calisan_sayisi=65, yillik_ciro=210e6, trl=5)
    kucuk = FinancialProfile(sektor="arge", sirket_turu="limited", calisan_sayisi=4, yillik_ciro=2e6, trl=5)
    assert not girisim_modu_mu(buyuk, "Ar-Ge merkezi kurmanın şartları neler?")
    assert girisim_modu_mu(kucuk, "Ar-Ge merkezi kurmanın şartları neler?")


def test_tarsim_urun_orani_kayittaki_listeden():
    t = _t(kurum="TARSİM", baslik="TARSİM — Devlet Destekli Tarım Sigortası", kontrol_listesi=[
        {"tur": "bilgi", "metin": "Yüzde 70 prim desteği: açık alanda yetiştirilen meyveler, domates, biber ve patates."},
        {"tur": "bilgi", "metin": "Kayısı, elma ve vişnede kış donu zararı risk priminin yüzde 70'i devletçe karşılanır."}])
    cilek = yerel_danisman.sigorta_orani_satiri(t, FinancialProfile(sektor="tarim", urun_turu="çilek"))
    assert "%50" in cilek and "kayısı, elma, vişne" in cilek and "bu listede yok" in cilek
    assert "%70'i" in yerel_danisman.sigorta_orani_satiri(t, FinancialProfile(sektor="tarim", urun_turu="domates"))
    assert "kış donu riskinde %70" in yerel_danisman.sigorta_orani_satiri(
        t, FinancialProfile(sektor="tarim", urun_turu="kayısı"))


def test_hedef_ulke_satiri_korfez():
    t = _t(kurum="Ticaret Bakanlığı", baslik="Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı Karar m.4)",
           detay="Oran %50; hedef ülkelerde 20 puan artar. Hedef ülkeler (EK-Hedef Ülkeler Listesi, 35 ülke): ABD, "
                 "Almanya, BAE, Katar, Kuveyt, Suudi Arabistan, Şili.")
    s = yerel_danisman.hedef_ulke_satiri("Körfez ülkelerine satmak istiyoruz", [t])
    assert "BAE, Katar, Kuveyt, Suudi Arabistan listede" in s and "Bahreyn, Umman listede değil" in s
    assert "Almanya listede" in yerel_danisman.hedef_ulke_satiri("Almanya'ya satış", [t])
    assert yerel_danisman.hedef_ulke_satiri("Yurt dışına satış", [t]) == ""


def test_pazaryerlerinde_ekli_kelime_pazaryeri_sorusu():
    assert {"tanitim", "ihracat"} <= set(soru_ihtiyaclari("Yurt dışı pazaryerlerinde reklam desteği var mı?"))



def test_bilgi_yok_cumlesi_bicimi_bozmaz():
    t = yerel_danisman.tekrarlari_kisalt(
        "- **Başvuru dönemi:** Sayfada dönem/son tarih belirtilmiyor; başvuru KOSGEB.\n"
        "- **Başvuru dönemi:** Sayfada dönem/son tarih belirtilmiyor; başvuru X.\n"
        "asgari 12 TL (MADDE 5, EK-3'te ayrıca belirtilmemişse); son tarih.")
    assert t.count("**Başvuru dönemi:**") == 2 and t.count("belirtilmiyor") == 1
    assert "(MADDE 5, EK-3'te ayrıca belirtilmemişse)" in t and "  " not in t


def test_panel_siralama_notlari_kartta_gorunmez():
    for not_ in ("Belirttiğiniz hedeflerle doğrudan eşleşme bulunamadı, ayrıntıları kontrol edin.",
                 "Bu destek sektörden bağımsız genel bir programdır.",
                 "Program ölçeği (asgari yatırım ya da kredi tavanı) yıllık cironuza göre çok büyük.",
                 "Başvuru dönemi şu an kapalı (2026/2); yeni çağrıyı izleyin."):
        assert yerel_danisman._PANEL_NOTU.search(not_), not_


def test_tobb_baglı_oda_uyeligi_varyanti():
    sart = "TOBB'a bağlı ticaret/sanayi/deniz ticaret odası veya ticaret borsası üyeliği"
    assert yerel_danisman._profilden_karsilanan(sart, FinancialProfile(sirket_turu="anonim"))


def test_ek3_ilgisiz_kod_dislamasi_sart_sayilmaz():
    from app.tesvik_9903_uygunluk import _ek3_durumu
    assert _ek3_durumu("13.93")[0] == "uygun", "halı: dışlama yalnız 13.10.12 ve 13.92.06 için"



def test_hibe_satiri():
    from types import SimpleNamespace as N
    kredi = N(tesvik=_t(kurum="KGF", baslik="Kefalet Paketi", tesvil_tutari="%80 kefalet"), karar="sartli", gerekce=[], teyit=[])
    hibe = N(tesvik=_t(kurum="KOSGEB", baslik="YÖNDE - Yönderlik", tesvil_tutari="%100 geri ödemesiz; 700.000 TL"),
             karar="sartli", gerekce=[], teyit=[])
    assert yerel_danisman.hibe_mi(hibe.tesvik) and not yerel_danisman.hibe_mi(kredi.tesvik)
    assert "YÖNDE" in yerel_danisman.hibe_satiri("Dijitalleşme için kredi ya da hibe var mı?", kredi, [kredi, hibe])
    assert "bulamadım" in yerel_danisman.hibe_satiri("Makine için kredi ya da hibe var mı?", kredi, [kredi])
    assert yerel_danisman.hibe_satiri("Makine kredisi var mı?", kredi, [kredi, hibe]) == ""


def test_fidan_kalemi_ve_urun_kutusu():
    fidan = _t(kurum="Tarım ve Orman Bakanlığı", baslik="Sertifikalı/Standart Fidan Kullanım Desteği",
               uygunluk_kriterleri={"sektorler": ["tarim"], "urun_listesi": ["fındık", "elma"]})
    cilek = FinancialProfile(sektor="tarim", urun_turu="çilek")
    assert "çilek bu listede yok" in yerel_danisman.fidan_kalemi_notu(cilek, [fidan])
    assert yerel_danisman.fidan_kalemi_notu(FinancialProfile(sektor="tarim", urun_turu="fındık"), [fidan]) == ""



# ------------------------------------------------------------------ altıncı hakem turu bulguları
def test_statusuz_kalemler_kayittan():
    t = _t(kurum="Ticaret Bakanlığı", baslik="E-İhracat Destekleri (5986 Sayılı Karar)",
           detay="Statüsüz şirketin yararlanabildiği kalemler: dijital pazaryeri reklamı, sipariş karşılama, pazaryeri "
                 "komisyonu. Diğer metin.")
    s = yerel_danisman.statusuz_kalem_satiri(t)
    assert "dijital pazaryeri reklamı, sipariş karşılama, pazaryeri komisyonu" in s and "statü şartlıdır" in s
    assert yerel_danisman.statusuz_kalem_satiri(_t(baslik="Başka")) == ""


def test_ihtiyac_etiketleri_sektor_kisiti_degil_ve_ortaklik_kilit():
    kuresel = _t(kurum="KOSGEB", baslik="Küresel Rekabetçilik", uygunluk_kriterleri={"sektorler": ["arge", "ihracat"]})
    matbaa = FinancialProfile(sektor="imalat", nace_kodu="18.12", sirket_turu="limited", calisan_sayisi=6)
    assert yerel_danisman._sektor_disi(kuresel, matbaa) is None
    imalat = _t(kurum="KOSGEB", baslik="KOBİ Dijital", uygunluk_kriterleri={"sektorler": ["imalat"]})
    assert "sektör kapsamı" in yerel_danisman._sektor_disi(imalat, FinancialProfile(sektor="hizmet", nace_kodu="85.53"))
    assert yerel_danisman._KILIT.search("EUREKA altında yurt dışı ortaklı uluslararası proje başvurusu yapılmış olmalı")
