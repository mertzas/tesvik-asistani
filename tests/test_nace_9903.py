"""app/nace_9903.py testleri.

Bu modül kullanıcıya resmî bir hüküm veriyor: "yatırım teşvik belgesi için
asgari şartı karşılıyorsunuz / karşılamıyorsunuz". Yanlış bir eşik ya da
yanlış bir il-bölge eşleşmesi, üreticiyi karşılamadığı bir teşvike başvurmaya
ya da hak kazandığı bir teşvikten vazgeçmeye yönlendirir. Testler bu yüzden
hem veri bütünlüğünü hem de eşik karşılaştırmasını sabitliyor.

Veri kaynağı: 9903 sayılı "Yatırımlarda Devlet Yardımları Hakkında Karar"
(Resmî Gazete, 30/05/2025), EK-2 ve EK-3.
"""
import pytest

from app.nace_9903 import (
    BOLGE_ILLERI,
    EK3_A_ESIKLERI,
    TARIM_KATEGORI_NACE,
    bolge_illeri,
    bolum_sarti,
    ek3_kaydi,
    ek3_kayitlari,
    il_bolgesi,
    kategoriden_uygunluk,
    kaynak_bilgisi,
    nace_destekleniyor_mu,
    olcek_uygunlugu,
)

# ---------------------------------------------------------------- EK-2 bölgeler

def test_tum_81_il_kapsanir():
    """Eksik il, o ildeki kullanıcı için sessizce "bölge bilinmiyor" demek ve
    hiçbir eşik karşılaştırması yapılamaması anlamına gelir."""
    iller = [il for iller in BOLGE_ILLERI.values() for il in iller]
    assert len(iller) == 81, f"81 il beklenir, {len(iller)} var"
    assert len(set(iller)) == 81, "bir il iki bölgede listelenmiş"


def test_bolgeler_1_6():
    assert sorted(BOLGE_ILLERI) == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("il,bolge", [
    ("İstanbul", 1), ("Ankara", 1), ("Bursa", 1),
    ("Konya", 2), ("Kayseri", 2), ("Mersin", 2),
    ("Gaziantep", 3), ("Samsun", 3),
    ("Malatya", 4), ("Sivas", 4),
    ("Hatay", 5), ("Erzurum", 5),
    ("Van", 6), ("Şanlıurfa", 6), ("Diyarbakır", 6),
])
def test_il_bolge_eslesmesi(il, bolge):
    assert il_bolgesi(il) == bolge


@pytest.mark.parametrize("yazim", [
    "istanbul", "İSTANBUL", "İstanbul", " istanbul ",
])
def test_il_yazim_varyantlari(yazim):
    """Python'un str.lower()'i "İ"yi bozduğu için büyük harfle yazılan il adı
    hiç tanınmıyordu (bkz. urun_sektor_anahtarlari.kucult)."""
    assert il_bolgesi(yazim) == 1


@pytest.mark.parametrize("yazim,bolge", [
    ("elazig", 4), ("ELAZIĞ", 4), ("Elâzığ", 4),   # aksanlı resmî yazım
    ("hakkari", 6), ("Hakkâri", 6),
    ("urfa", 6), ("sanliurfa", 6),
    ("afyon", 4),
])
def test_aksansiz_ve_kisaltilmis_yazimlar(yazim, bolge):
    """Kullanıcının klavyesinde Türkçe karakter olmayabilir ya da kısaltma
    kullanabilir; il tanınmazsa eşik karşılaştırması hiç yapılamaz."""
    assert il_bolgesi(yazim) == bolge


def test_bilinmeyen_il_none_doner():
    assert il_bolgesi("Olmayan Şehir") is None
    assert il_bolgesi(None) is None
    assert il_bolgesi("") is None


def test_bolge_illeri_okunabilir():
    assert "Konya" in bolge_illeri(2)
    assert bolge_illeri(99) == ()


# ------------------------------------------------------------- EK-3 veri bütünlüğü

def test_ek3_listesi_yuklendi():
    kayitlar = ek3_kayitlari()
    assert len(kayitlar) >= 80, f"EK-3 listesi eksik görünüyor: {len(kayitlar)}"
    kodlar = [k["kod"] for k in kayitlar]
    assert len(kodlar) == len(set(kodlar)), "aynı NACE kodu iki kez var"
    for k in kayitlar:
        assert k["kod"], "kodu boş kayıt"
        assert k["tanim"], f"{k['kod']}: tanım boş"
        assert k["bolum"], f"{k['kod']}: bölüm atanmamış"


def test_kaynak_bilgisi_var():
    """Resmî bir hüküm veriyoruz; kaynağı göstermeden sunmak kabul edilemez."""
    k = kaynak_bilgisi()
    assert "9903" in (k.get("kaynak") or "")
    assert (k.get("kaynak_url") or "").startswith("http")
    assert k.get("cikarma_tarihi")


@pytest.mark.parametrize("kod", ["01.19.99", "01.41.31", "13", "26", "62.1",
                                 "63.1", "82.2", "86.1", "55.1"])
def test_bilinen_kodlar_listede(kod):
    assert nace_destekleniyor_mu(kod), f"{kod} EK-3'te bulunamadı"


def test_yazilim_ve_veri_merkezi_kapsamda():
    """Bu iki kod, kaba "hizmet" etiketinin ayırt edemediği durumun cevabı:
    yazılım geliştirme yatırım teşvik belgesi kapsamındadır."""
    assert ek3_kaydi("62.1")["bolum"] == "K"
    assert "programlama" in ek3_kaydi("62.1")["tanim"].lower()
    assert ek3_kaydi("63.1") is not None


def test_kapsam_disi_kod_none_doner():
    # 47.11 = perakende gıda satışı; EK-3 listesinde yok.
    assert ek3_kaydi("47.11") is None
    assert nace_destekleniyor_mu("47.11") is False


def test_bolum_duzeyi_sart_kaybolmadi():
    """B (MADENCİLİK) bölümünde NACE satırı yok, şart bölüm düzeyinde metin
    olarak veriliyor; ayrı tutulmasa tamamen kaybolurdu."""
    s = bolum_sarti("B")
    assert s and "Maden Kanunu" in s


# ----------------------------------------------------- yapılandırılmış eşikler

def test_esik_tablosu_tutarli():
    for e in EK3_A_ESIKLERI:
        assert e.nace_kodu, "kodu olmayan eşik"
        assert nace_destekleniyor_mu(e.nace_kodu), \
            f"{e.nace_kodu} eşik tablosunda var ama EK-3'te yok"
        for bolge, deger in e.bolge_esikleri.items():
            assert bolge in (1, 2, 3, 4, 5, 6), f"geçersiz bölge: {bolge}"
            assert deger > 0, f"{e.nace_kodu} bölge {bolge}: eşik pozitif olmalı"
        if e.bolge_esikleri:
            assert e.birim, f"{e.nace_kodu}: eşik var ama birim yok"


def test_esikler_bolgeye_gore_azalir():
    """Karar'ın mantığı: gelişmişlik azaldıkça (bölge numarası büyüdükçe)
    asgari şart düşer. Artan bir eşik veri girişi hatasıdır."""
    for e in EK3_A_ESIKLERI:
        degerler = [e.bolge_esikleri[b] for b in sorted(e.bolge_esikleri)]
        assert degerler == sorted(degerler, reverse=True), \
            f"{e.nace_kodu}: eşikler bölgeye göre artıyor: {degerler}"


@pytest.mark.parametrize("il,olcek,beklenen", [
    ("Konya", 50, "uygun"),       # 2. bölge, asgari 20 dekar
    ("Konya", 20, "uygun"),       # sınır değeri dahil
    ("Konya", 19, "yetersiz"),
    ("Konya", 8, "yetersiz"),
    ("Van", 8, "uygun"),          # 6. bölge, asgari 5 dekar
    ("Van", 4, "yetersiz"),
    ("Malatya", 10, "uygun"),     # 4. bölge, asgari 10 dekar
])
def test_sera_esigi_bolgeye_gore(il, olcek, beklenen):
    """Aynı ölçek, bölgeye göre farklı sonuç vermeli: 8 dekar sera Konya'da
    yetersiz, Van'da yeterlidir."""
    s = olcek_uygunlugu("01.19.99", il, olcek)
    assert s.durum == beklenen, s.aciklama


def test_yetersiz_durumda_eksik_miktar_soylenir():
    s = olcek_uygunlugu("01.19.99", "Konya", 8)
    assert s.durum == "yetersiz"
    assert "12" in s.aciklama, f"eksik miktar belirtilmemiş: {s.aciklama}"
    assert s.uygun_mu is False


def test_olcek_girilmemisse_hukum_verilmez():
    """Ölçek bilinmiyorken "uygun değilsiniz" demek yanlış olur; şart
    söylenip bilgi istenmeli."""
    s = olcek_uygunlugu("01.19.99", "Konya", None)
    assert s.durum == "olcek_bilinmiyor"
    assert s.uygun_mu is False
    assert "20" in s.aciklama


def test_il_taninmazsa_hukum_verilmez():
    s = olcek_uygunlugu("01.19.99", "Olmayan Şehir", 50)
    assert s.durum == "bolge_bilinmiyor"
    assert s.asgari is None


def test_esigi_olmayan_konu_esik_yok_doner():
    """03.2 su ürünleri: Karar'da bölge bazlı asgari ölçek şartı yok.
    0 varsaymak "şart yok" demek olurdu ki bu yanlış bir güvence verir."""
    s = olcek_uygunlugu("03.2", "Konya", 5)
    assert s.durum == "esik_yok"
    assert s.asgari is None


def test_yapilandirilmamis_kod_none_doner():
    """İmalat şartları asgari sabit yatırım tutarına dayanıyor; profilde o
    veri yok, bu yüzden hüküm vermek yerine None dönmeli."""
    assert olcek_uygunlugu("13", "Konya", 100) is None
    assert olcek_uygunlugu("62.1", "İstanbul", 100) is None


@pytest.mark.parametrize("olcek", [0, -5])
def test_sifir_ve_negatif_olcek_bilinmiyor_sayilir(olcek):
    s = olcek_uygunlugu("01.19.99", "Konya", olcek)
    assert s.durum == "olcek_bilinmiyor"


# --------------------------------------------------------- kategori köprüsü

def test_kategori_nace_eslesmesi_gecerli_kodlar_gosterir():
    for kategori, kodlar in TARIM_KATEGORI_NACE.items():
        assert kodlar, f"{kategori} için kod yok"
        for kod in kodlar:
            assert nace_destekleniyor_mu(kod), \
                f"{kategori} -> {kod} EK-3'te yok"


def test_hayvancilik_kategorisi_tum_hayvan_kodlarini_degerlendirir():
    sonuclar = kategoriden_uygunluk("hayvancilik", "Bursa", 40)
    assert len(sonuclar) >= 4
    # 40 hayvan hiçbir büyükbaş/küçükbaş eşiğini karşılamaz.
    assert all(s.durum == "yetersiz" for s in sonuclar), \
        [(s.nace_kodu, s.durum) for s in sonuclar]


def test_buyuk_sut_ciftligi_uygun_cikar():
    sonuclar = kategoriden_uygunluk("hayvancilik", "Van", 200)
    # Van 6. bölge: sütü sağılan büyükbaşta asgari 150 -> karşılıyor.
    sut = [s for s in sonuclar if s.nace_kodu == "01.41.31"]
    assert sut and sut[0].durum == "uygun", sut[0].aciklama if sut else "kayıt yok"


def test_bilinmeyen_kategori_bos_liste_doner():
    assert kategoriden_uygunluk("yazilim", "İstanbul", 10) == []
    assert kategoriden_uygunluk(None, "İstanbul", 10) == []


def test_kapsam_uyarisi_esik_notlarinda_gecmiyor_ama_modulde_var():
    """Eşikler yatırım teşvik belgesi içindir; KOSGEB/Tarım Bakanlığı
    ödemeleri ayrıdır. Bu ayrımın modül dokümantasyonunda yazılı olması
    şart - aksi halde 5 dekar serası olan üretici hak kazandığı mazot-gübre
    desteğini de alamayacağını sanır."""
    import app.nace_9903 as m
    assert "YATIRIM TESVIK BELGESI" in m.__doc__
    assert "KOSGEB" in m.__doc__
