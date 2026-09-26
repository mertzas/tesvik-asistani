"""app/urun_sektor_anahtarlari.py testleri.

Bu modül serbest metin aramanın hangi sektöre genişletileceğine karar veriyor;
yanlış etiket doğrudan yanlış teşvik önerisi demek. Aşağıdaki testler üç
gerçek hatayı sabitliyor (üçü de 2026-09-26'da ölçüldü ve düzeltildi):

  1. Düz substring araması kelime ORTASINDAN eşleşiyordu: "global pazar"
     ve "bale kursu" tarım olarak etiketleniyordu ("bal"), "mesut" de
     ("süt"). Yani "global pazara açılmak istiyorum" yazan bir yazılımcıya
     tarım teşvikleri gösteriliyordu.
  2. Türkçe ünsüz yumuşaması hiç ele alınmamıştı: "hayvancılığa başladım"
     hiçbir sektöre eşleşmiyordu (hayvancılıK -> hayvancılıĞa).
  3. Python'un str.lower()'i "İ"yi tek harfe değil "i̇" (i + birleşik nokta)
     iki kod noktasına çeviriyor; caps lock ile yazan kullanıcı ("ÇİLEK
     SERASI") hiçbir eşleşme alamıyordu.
"""
import pytest

from app.urun_sektor_anahtarlari import (
    SEKTOR_URUN_ANAHTAR_KELIMELERI,
    anahtar_kelimeden_sektor_bul,
)


@pytest.mark.parametrize("metin", [
    "çilek yetiştiriyorum",
    "cilek yetistiriyorum",          # ASCII yazım da tanınmalı
    "ÇİLEK SERASI",                  # büyük harf
    "buğday ekiyorum",
    "süt sağıyorum",
    "bal üretiyorum",
    "sera kurmak istiyorum",
])
def test_tarim_urunleri_taninir(metin):
    assert anahtar_kelimeden_sektor_bul(metin) == "tarim"


@pytest.mark.parametrize("metin", [
    "çilekten reçel yapıyorum",
    "buğdayı ektim",
    "hayvancılığa başladım",
    "arıcılığa destek var mı",
    "balıkçılığı geliştirmek istiyorum",
    "seracılığa yatırım yapacağım",
    "bağcılığım var",
])
def test_turkce_ekler_ve_yumusama_taninir(metin):
    """Türkçe eklemeli bir dil; çekimli haller de eşleşmeli.

    "hayvancılığa" özellikle önemli: son sessiz yumuşadığı için anahtar
    kelime listesinde tam hâl ("hayvancılık") yazıldığında HİÇ eşleşmiyordu.
    """
    assert anahtar_kelimeden_sektor_bul(metin) == "tarim"


@pytest.mark.parametrize("metin", [
    "global pazara açılmak istiyorum",   # "bal" global'in İÇİNDE
    "bale kursu açıyorum",               # ("bal") - bkz. aşağıdaki sınır testi
    "mesut bir gün",                     # "süt" mesut'un içinde
    "yazılım geliştiriyorum",
    "mobilya imalatı yapıyorum",
    "",
])
def test_kelime_ortasindaki_eslesmeler_sayilmaz(metin):
    assert anahtar_kelimeden_sektor_bul(metin) is None


def test_unlu_uyumu_eki_gercek_kelimeden_ayirir():
    """"bal" kelime başında olduğu için "bale" de eşleşiyordu.

    Kelime sonu serbest bırakılmak zorunda (Türkçe ekler), bu yüzden ayrım
    ünlü uyumuyla yapılıyor: "bal" art ünlülü, dolayısıyla eki de art ünlülü
    olmalı ("bala", "balı", "baldan"). "bale"nin "e"si ön ünlü, yani ek
    değil, farklı bir kelime.
    """
    assert anahtar_kelimeden_sektor_bul("bale kursu açıyorum") is None
    # Gerçek çekimli haller çalışmaya devam ediyor:
    assert anahtar_kelimeden_sektor_bul("bal satıyorum") == "tarim"
    assert anahtar_kelimeden_sektor_bul("balı sattım") == "tarim"
    assert anahtar_kelimeden_sektor_bul("baldan gelir elde ediyorum") == "tarim"


def test_buyuk_harf_turkce_i_sorunu():
    """Python'un str.lower()'i "İ"yi "i̇" (i + birleşik nokta) yapar.

    Bu yüzden caps lock ile yazan kullanıcı HİÇ eşleşme alamıyordu. Modül
    artık kendi kucult()'unu kullanıyor.
    """
    from app.urun_sektor_anahtarlari import kucult

    # Sorunun kaynağını sabitle: standart lower() gerçekten bozuyor.
    assert "çilek" not in "ÇİLEK".lower()
    # kucult() düzeltiyor:
    assert kucult("ÇİLEK") == "çilek"
    assert kucult("ISPANAK") == "ıspanak"

    assert anahtar_kelimeden_sektor_bul("ÇİLEK SERASI KURDUM") == "tarim"
    assert anahtar_kelimeden_sektor_bul("ISPANAK EKİYORUM") == "tarim"


def test_misir_belirsizligi_bilinen_sinir():
    """"Mısır" hem tahıl hem ülke adı; kelime sınırları bunu çözemez.

    Bu test davranışı YANLIŞ diye işaretlemiyor, mevcut ve bilinen sınırı
    sabitliyor - ileride bağlam analizi eklenirse burası bilinçli olarak
    güncellenmeli.
    """
    assert anahtar_kelimeden_sektor_bul("Mısır'a ihracat yapıyorum") == "tarim"


def test_anahtar_kelime_listesi_bozulmamis():
    """Liste elle bakımı yapılıyor; boş/boşluklu girdi sessizce her metne
    eşleşerek her sorguyu tarım sayardı."""
    for sektor, kelimeler in SEKTOR_URUN_ANAHTAR_KELIMELERI.items():
        assert sektor == sektor.lower(), f"sektör etiketi küçük harf olmalı: {sektor}"
        assert kelimeler, f"{sektor} için anahtar kelime listesi boş"
        for k in kelimeler:
            assert k, f"{sektor} içinde boş anahtar kelime var"
            assert k == k.lower(), f"anahtar kelime küçük harf olmalı: {k!r}"
            assert k == k.strip(), f"anahtar kelimede baş/son boşluk var: {k!r}"
            # Tek harfli anahtar her metne eşleşirdi.
            assert len(k) >= 3, f"anahtar kelime çok kısa, yanlış pozitif üretir: {k!r}"
