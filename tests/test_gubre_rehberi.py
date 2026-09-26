"""app/gubre_rehberi.py testleri.

Bu modül çiftçiye gübre DOZAJI söylüyor. Yanlış evre veya yanlış çarpım
doğrudan ürün zararı ya da gereksiz masraf demek, bu yüzden testler hem
evre haritasının bütünlüğünü hem de "veri yoksa uydurmama" davranışını
sabitliyor.
"""
from datetime import date, timedelta

import pytest

from app.gubre_rehberi import (
    EVRELER,
    gubre_dozaj_oneri_getir,
    tum_evreleri_listele,
)


# ---------------------------------------------------------------- evre haritası

def test_evreler_bosluksuz_ve_cakismasiz():
    """Aralıklarda boşluk olsa o günlere denk gelen çiftçi "evre bulunamadı"
    görürdü; çakışma olsa hangi dozun geldiği sıraya bağlı olurdu."""
    araliklar = [e.gun_araligi for e in EVRELER]
    assert araliklar == sorted(araliklar), "evreler gün sırasına göre olmalı"
    assert araliklar[0][0] == 0, "ilk evre 0. günden başlamalı"
    for (_, onceki_bitis), (sonraki_bas, _) in zip(araliklar, araliklar[1:]):
        assert onceki_bitis == sonraki_bas, (
            f"evre aralıklarında boşluk/çakışma var: {onceki_bitis} -> {sonraki_bas}")
    for bas, bitis in araliklar:
        assert bas < bitis, f"geçersiz aralık: {bas}-{bitis}"


def test_dozlar_negatif_degil_ve_tanimli():
    for e in EVRELER:
        for alan in ("n_kg_da", "p2o5_kg_da", "k2o_kg_da", "cao_kg_da"):
            deger = getattr(e, alan)
            assert deger is not None, f"{e.ad}: {alan} tanımsız"
            assert deger >= 0, f"{e.ad}: {alan} negatif ({deger})"


def test_tum_evreleri_listele_ayni_veriyi_doner():
    assert tum_evreleri_listele() == list(EVRELER)


# ------------------------------------------------------------- dozaj hesaplama

def test_dikim_tarihi_yoksa_tarih_uydurulmaz():
    """En önemli davranış: tarih bilinmiyorsa varsayılan bir tarihle doz
    önerilmemeli - yanlış evrenin dozu gerçek zarar verir."""
    s = gubre_dozaj_oneri_getir(dikim_tarihi=None, alan_dekar=10)
    assert s.evre is None
    assert s.n_kg_da is None
    assert s.gun_sayisi is None
    assert s.toplam_n_kg is None
    assert any("dikim tarihi girilmemiş" in n for n in s.notlar)


def test_gun_sayisina_gore_dogru_evre_secilir():
    bugun = date(2026, 6, 1)
    for evre in EVRELER:
        bas, bitis = evre.gun_araligi
        # Aralığın içinden bir gün seç (üst sınır dışlayıcı).
        orta = bas + min(1, max(0, bitis - bas - 1))
        s = gubre_dozaj_oneri_getir(
            dikim_tarihi=bugun - timedelta(days=orta), bugun=bugun)
        assert s.evre == evre.ad, (
            f"{orta}. gün için {evre.ad} beklenirken {s.evre} döndü")
        assert s.gun_sayisi == orta


def test_evre_sinirlari_ust_sinir_dislayici():
    """Sınır günü bir sonraki evreye ait olmalı; iki evrenin aynı günü
    sahiplenmesi hangi dozun geldiğini belirsizleştirirdi."""
    bugun = date(2026, 6, 1)
    ilk, ikinci = EVRELER[0], EVRELER[1]
    sinir = ilk.gun_araligi[1]

    s_once = gubre_dozaj_oneri_getir(
        dikim_tarihi=bugun - timedelta(days=sinir - 1), bugun=bugun)
    s_sinir = gubre_dozaj_oneri_getir(
        dikim_tarihi=bugun - timedelta(days=sinir), bugun=bugun)

    assert s_once.evre == ilk.ad
    assert s_sinir.evre == ikinci.ad


def test_alan_verilirse_toplam_ihtiyac_carpilir():
    bugun = date(2026, 6, 1)
    s = gubre_dozaj_oneri_getir(
        dikim_tarihi=bugun - timedelta(days=100), alan_dekar=12.5, bugun=bugun)
    assert s.evre is not None
    assert s.alan_dekar == 12.5
    assert s.toplam_n_kg == round(s.n_kg_da * 12.5, 2)
    assert s.toplam_p2o5_kg == round(s.p2o5_kg_da * 12.5, 2)
    assert s.toplam_k2o_kg == round(s.k2o_kg_da * 12.5, 2)
    assert s.toplam_cao_kg == round(s.cao_kg_da * 12.5, 2)


@pytest.mark.parametrize("alan", [None, 0, -5])
def test_gecersiz_alanda_toplam_hesaplanmaz(alan):
    """Negatif alanla çarpım negatif gübre ihtiyacı üretirdi."""
    bugun = date(2026, 6, 1)
    s = gubre_dozaj_oneri_getir(
        dikim_tarihi=bugun - timedelta(days=100), alan_dekar=alan, bugun=bugun)
    assert s.toplam_n_kg is None
    # Dekar başı doz yine verilmeli - alan bilinmese de öneri anlamlı.
    assert s.n_kg_da is not None


def test_gelecek_tarihli_dikim_uyarir():
    bugun = date(2026, 6, 1)
    s = gubre_dozaj_oneri_getir(
        dikim_tarihi=bugun + timedelta(days=10), bugun=bugun)
    assert s.evre is None
    assert any("gelecekte" in n for n in s.notlar)


def test_toprak_analizi_uyarisi_her_dozda_var():
    """Dozlar "orta bünyeli toprak" varsayımına dayanıyor; bu uyarı düşerse
    çiftçi değerleri kendi toprağı için kesinmiş gibi uygular."""
    bugun = date(2026, 6, 1)
    for gun in (5, 45, 100, 130, 180, 250):
        s = gubre_dozaj_oneri_getir(
            dikim_tarihi=bugun - timedelta(days=gun), bugun=bugun)
        if s.evre is None:
            continue
        assert any("analiz" in n.lower() for n in s.notlar), (
            f"{gun}. gün için toprak analizi uyarısı yok")
