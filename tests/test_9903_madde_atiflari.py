"""9903 hesap çıktısındaki madde atıfları Karar metniyle (R.G. 30/05/2025) aynı olmalı.

GERÇEK OLAY (denetim 2026-10-07): vergi indirimi "MADDE 12", sigorta primi işveren
hissesi "MADDE 14" diye gösteriliyordu; Karar'da bunlar MADDE 20 ve MADDE 18. Değerler
doğruydu, kullanıcıya gösterilen atıf yanlıştı. İşçi hissesi desteği (MADDE 19, 6. bölge,
10 yıl) hiç yoktu."""
from app.tesvik_9903_hesap import hesapla

DOGRU_ATIF = {
    "Vergi indirimi (yatırıma katkı tutarı)": "MADDE 20",
    "Sigorta primi işveren hissesi desteği": "MADDE 18",
    "Sigorta primi desteği (işçi hissesi)": "MADDE 19",
    "Faiz veya kâr payı desteği": "MADDE 15",
    "Makine desteği": "MADDE 16",
}


def _kalemler(program, il, **kw):
    return {k.ad: k for k in hesapla(program, il, 50_000_000, **kw).kalemler}


def test_madde_atiflari_karar_metniyle_uyumlu():
    k = _kalemler("teknoloji_hamlesi", "Van", ilave_istihdam=10, aylik_asgari_ucret_isveren_primi_tl=5000,
                  kredi_tl=10_000_000, repo_faiz_orani=40, makine_techizat_tl=20_000_000)
    for ad, madde in DOGRU_ATIF.items():
        assert ad in k, ad
        assert k[ad].madde == madde, (ad, k[ad].madde)
    assert not any(x.madde in ("MADDE 12", "MADDE 14") for x in k.values())


def test_isci_hissesi_destegi_yalnizca_altinci_bolgede():
    assert "Sigorta primi desteği (işçi hissesi)" in _kalemler("hedef_yatirimlar", "Van")
    assert "Sigorta primi desteği (işçi hissesi)" not in _kalemler("hedef_yatirimlar", "Konya")
    kalem = _kalemler("hedef_yatirimlar", "Van")["Sigorta primi desteği (işçi hissesi)"]
    assert kalem.tutar_tl is None and "10 yıl" in kalem.aciklama and kalem.eksik_bilgi
