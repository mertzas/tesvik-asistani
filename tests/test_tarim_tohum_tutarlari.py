"""Tarım kazıyıcısının tohum tutarları, 2026 birim fiyat modülüyle (app/tarim_destek_2026.py) tutarlı olmalı.

Denetim 2 tur 7 (2026-10-08): kazıyıcıdaki metinler eski/kaynaksızdı ("Dekar başına ₺500 - ₺2.000", "m² başına
₺50 - ₺200", "mazot+gübre desteği"); canlı DB düzeltildi, tohum da aynı değerlere çekildi. Bu test, birim fiyat
güncellenip tohum unutulursa (ya da tersi) kırmızı yanar.
"""
import pytest

from app import tarim_destek_2026 as T
from app.scrapers.tarim_bakanligi import TARIM_BAKANLIGI_DESTEKLERI

BIRIM = T.KATSAYI_BIRIM_TL


def _kayit(baslik):
    return next(d for d in TARIM_BAKANLIGI_DESTEKLERI if d["baslik"] == baslik)


# (başlık, beklenen min, beklenen max) — sabitlerden türetilir, elle yazılmaz.
BEKLENEN = [
    ("Organik Tarım Destekleri",
     T.ORGANIK_TARIM[3][1] * BIRIM,                                       # 3. grup, grup sertifikası
     T.ORGANIK_TARIM[1][0] * (1 + T.ORGANIK_ORGUT_ILAVE_ORANI) * BIRIM),  # 1. grup bireysel + örgüt ilavesi
    ("Sera/Örtüaltı Tarım Destekleri",
     BIRIM,
     BIRIM + T.IYI_TARIM["1_ortualti"][0] * BIRIM),
    ("Hububat ve Baklagil Üretim Destekleri (Temel Destek + Planlı Üretim)",
     2 * T.TEMEL_DESTEK_KATEGORILERI[1][0] * BIRIM,                       # temel + planlı, mercimek/nohut
     2 * T.TEMEL_DESTEK_KATEGORILERI[2][0] * BIRIM),                      # temel + planlı, buğday/arpa/mısır
    ("Meyve-Sebze Üretim Destekleri (Temel Destek)", BIRIM, BIRIM),
]


@pytest.mark.parametrize("baslik,alt,ust", BEKLENEN)
def test_tohum_min_max_birim_fiyatlarla_ayni(baslik, alt, ust):
    d = _kayit(baslik)
    assert d["tutari_hesaplama_kriteri"] == "dekar"
    assert d["tutari_min"] == pytest.approx(alt)
    assert d["tutari_max"] == pytest.approx(ust)


@pytest.mark.parametrize("baslik,alt,ust", BEKLENEN)
def test_tohum_metni_sinirlari_soyluyor(baslik, alt, ust):
    metin = _kayit(baslik)["tesvil_tutari"]
    assert f"{ust:,.0f}".replace(",", ".") in metin
    if alt != ust:
        assert f"{alt:,.0f}".replace(",", ".") in metin


@pytest.mark.parametrize("eski", ["₺500 - ₺2.000", "m² başına ₺50", "mazot+gübre desteği, ürün grubuna göre",
                                  "(Mazot-Gübre)", "hububata göre daha yüksek"])
def test_eski_kaynaksiz_metinler_yok(eski):
    for d in TARIM_BAKANLIGI_DESTEKLERI:
        for alan in ("baslik", "ozet", "detay", "tesvil_tutari", "tutari_hesaplama_formulu"):
            assert eski not in (d.get(alan) or ""), (d["baslik"], alan)
