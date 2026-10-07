"""app/tesvik_9903_hesap.py testleri.

Bu modül kullanıcıya milyonlarca TL'lik bir rakam söylüyor. Tek bir yanlış
oran ya da kaçırılmış bir bölge kısıtı, yatırımcının hak etmediği bir desteği
bütçesine yazmasına yol açar. Testler bu yüzden her oranı Karar metnindeki
değerle ve her hesabı elle çarpımla karşılaştırıyor.

Kaynak: 9903 sayılı Yatırımlarda Devlet Yardımları Hakkında Karar
(Resmî Gazete, 30/05/2025) — MADDE 5, 12, 14, 15, 16.
"""
import pytest

from app.tesvik_9903_hesap import (
    ASGARI_SABIT_YATIRIM,
    FAIZ_DESTEGI,
    FAIZ_DESTEGI_AZAMI_YIL,
    FAIZ_DESTEGI_BOLGE_KISITI,
    FAIZ_DESTEGI_KREDI_ORANI,
    KALKINMA_HAMLESI,
    MAKINE_BIRIM_FIYAT_ESIGI,
    MAKINE_DESTEGI_ORANI,
    MAKINE_DESTEGI_TAVANI,
    PROGRAMLAR,
    SIGORTA_PRIMI_KARSILAMA,
    SIGORTA_PRIMI_SURESI,
    SIGORTA_PRIMI_SURESI_HAMLE,
    YATIRIMA_KATKI_ORANI,
    hesapla,
    programlari_karsilastir,
)


def _kalem(h, ad_baslangici):
    for k in h.kalemler:
        if k.ad.startswith(ad_baslangici):
            return k
    raise AssertionError(f"kalem bulunamadı: {ad_baslangici}")


# ------------------------------------------------- oran tablosu bütünlüğü

def test_tum_programlar_icin_oran_tanimli():
    for p in PROGRAMLAR:
        assert p in YATIRIMA_KATKI_ORANI, f"{p}: yatırıma katkı oranı yok"
        assert p in FAIZ_DESTEGI, f"{p}: faiz desteği oranı yok"


def test_yatirima_katki_oranlari_karar_metniyle_ayni():
    """MADDE 20/1: Teknoloji ve Yerel Kalkınma %50, Stratejik %40,
    Öncelikli %30, Hedef %20."""
    assert YATIRIMA_KATKI_ORANI == {
        "teknoloji_hamlesi": 0.50,
        "yerel_kalkinma_hamlesi": 0.50,
        "stratejik_hamle": 0.40,
        "oncelikli_yatirimlar": 0.30,
        "hedef_yatirimlar": 0.20,
    }


def test_sigorta_primi_sureleri_karar_metniyle_ayni():
    """MADDE 18/2: bölge 1-2 → 1 yıl, 3 → 2, 4 → 4, 5 → 8, 6 → 12."""
    assert SIGORTA_PRIMI_SURESI == {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 12}


def test_kalkinma_hamlesi_sigorta_suresi_daha_uzun():
    """MADDE 18/3: Kalkınma Hamlesi kapsamında 6. bölgede 12, diğerlerinde
    8 yıl. Bu ayrım kaybolursa 1. bölgedeki yatırımcı 8 yıl yerine 1 yıl
    hesaplanır - sekiz kat eksik."""
    for bolge in (1, 2, 3, 4, 5):
        assert SIGORTA_PRIMI_SURESI_HAMLE[bolge] == 8
        assert SIGORTA_PRIMI_SURESI_HAMLE[bolge] >= SIGORTA_PRIMI_SURESI[bolge]
    assert SIGORTA_PRIMI_SURESI_HAMLE[6] == 12


def test_altinci_bolgede_prim_tamami_karsilanir():
    """MADDE 18/1: 6. bölgede primin tamamı, diğerlerinde %50'si."""
    assert SIGORTA_PRIMI_KARSILAMA[6] == 1.00
    for b in (1, 2, 3, 4, 5):
        assert SIGORTA_PRIMI_KARSILAMA[b] == 0.50


def test_faiz_destegi_puan_tavanlari():
    """MADDE 15/1: Teknoloji/Yerel %40 (max 20 puan), Stratejik %30 (15),
    Öncelikli %25 (12,5), Hedef %25 (12,5)."""
    assert FAIZ_DESTEGI["teknoloji_hamlesi"] == (0.40, 20.0)
    assert FAIZ_DESTEGI["stratejik_hamle"] == (0.30, 15.0)
    assert FAIZ_DESTEGI["oncelikli_yatirimlar"] == (0.25, 12.5)
    assert FAIZ_DESTEGI["hedef_yatirimlar"] == (0.25, 12.5)


def test_makine_destegi_yalnizca_kalkinma_hamlesinde():
    """MADDE 16/1: makine desteği yalnızca Türkiye Yüzyılı Kalkınma
    Hamlesi kapsamındaki yatırımlara verilir."""
    assert set(MAKINE_DESTEGI_TAVANI) == KALKINMA_HAMLESI
    assert "hedef_yatirimlar" not in MAKINE_DESTEGI_TAVANI
    assert "oncelikli_yatirimlar" not in MAKINE_DESTEGI_TAVANI


def test_asgari_sabit_yatirim_karar_metniyle_ayni():
    """MADDE 5/2: 1-2. bölgelerde 12 milyon TL, diğerlerinde 6 milyon TL."""
    assert ASGARI_SABIT_YATIRIM[1] == ASGARI_SABIT_YATIRIM[2] == 12_000_000
    for b in (3, 4, 5, 6):
        assert ASGARI_SABIT_YATIRIM[b] == 6_000_000


# ------------------------------------------------------ vergi indirimi

def test_vergi_indirimi_elle_carpimla_ayni():
    h = hesapla("hedef_yatirimlar", "Gaziantep", 40_000_000)
    k = _kalem(h, "Vergi indirimi")
    assert k.tutar_tl == pytest.approx(40_000_000 * 0.20)


@pytest.mark.parametrize("program,oran", list(YATIRIMA_KATKI_ORANI.items()))
def test_her_program_icin_vergi_indirimi(program, oran):
    h = hesapla(program, "Konya", 10_000_000)
    assert _kalem(h, "Vergi indirimi").tutar_tl == pytest.approx(10_000_000 * oran)


# --------------------------------------------------------- sigorta primi

def test_sigorta_primi_elle_carpimla_ayni():
    """Gaziantep 3. bölge, genel süre 2 yıl, karşılama %50."""
    h = hesapla("hedef_yatirimlar", "Gaziantep", 40_000_000,
                ilave_istihdam=30, aylik_asgari_ucret_isveren_primi_tl=4_500)
    beklenen = 30 * 4_500 * 12 * 2 * 0.50
    assert _kalem(h, "Sigorta primi").tutar_tl == pytest.approx(beklenen)


def test_kalkinma_hamlesinde_sigorta_primi_daha_yuksek():
    ortak = dict(ilave_istihdam=10, aylik_asgari_ucret_isveren_primi_tl=4_000)
    hedef = hesapla("hedef_yatirimlar", "Konya", 20_000_000, **ortak)
    hamle = hesapla("teknoloji_hamlesi", "Konya", 20_000_000, **ortak)
    # Konya 2. bölge: genel 1 yıl, Kalkınma Hamlesi 8 yıl.
    assert _kalem(hamle, "Sigorta primi").tutar_tl == pytest.approx(
        _kalem(hedef, "Sigorta primi").tutar_tl * 8)


def test_altinci_bolgede_prim_iki_kat():
    ortak = dict(ilave_istihdam=10, aylik_asgari_ucret_isveren_primi_tl=4_000)
    # Van (6) ve Hatay (5): ikisinde de Kalkınma Hamlesi süresi 8/12 yıl,
    # karşılama 1.00 / 0.50. Süre farkını da hesaba katarak karşılaştır.
    van = _kalem(hesapla("teknoloji_hamlesi", "Van", 20_000_000, **ortak),
                 "Sigorta primi").tutar_tl
    hatay = _kalem(hesapla("teknoloji_hamlesi", "Hatay", 20_000_000, **ortak),
                   "Sigorta primi").tutar_tl
    # Van: 12 yıl x 1.00 = 12 birim; Hatay: 8 yıl x 0.50 = 4 birim -> 3 kat.
    assert van == pytest.approx(hatay * 3)


def test_istihdam_verisi_yoksa_tutar_uydurulmaz():
    """Asgari ücret işveren primi her yıl değişiyor ve SGK belirliyor;
    koda gömülmüş bir varsayılanla hesaplamak sessiz bir uydurma olurdu."""
    h = hesapla("hedef_yatirimlar", "Konya", 20_000_000, ilave_istihdam=10)
    k = _kalem(h, "Sigorta primi")
    assert k.tutar_tl is None
    assert "asgari ücret işveren primi" in k.eksik_bilgi


# ----------------------------------------------------------- faiz desteği

def test_faiz_destegi_elle_hesapla_ayni():
    h = hesapla("teknoloji_hamlesi", "Gaziantep", 40_000_000,
                kredi_tl=20_000_000, repo_faiz_orani=37.0)
    # Destekli kredi = min(20M, 40M*0.70=28M) = 20M
    # Puan = min(37*0.40=14.8, 20) = 14.8
    beklenen = 20_000_000 * 0.148 * FAIZ_DESTEGI_AZAMI_YIL
    assert _kalem(h, "Faiz veya kâr payı").tutar_tl == pytest.approx(beklenen)


def test_kredi_sabit_yatirimin_yuzde_yetmisiyle_sinirli():
    """MADDE 15/1: kredinin yalnızca sabit yatırımın %70'ine kadarki kısmı
    desteklenir. Sınır uygulanmazsa yatırımcıya fazla tutar gösterilir."""
    h = hesapla("teknoloji_hamlesi", "Konya", 10_000_000,
                kredi_tl=50_000_000, repo_faiz_orani=37.0)
    destekli = 10_000_000 * FAIZ_DESTEGI_KREDI_ORANI
    beklenen = destekli * 0.148 * FAIZ_DESTEGI_AZAMI_YIL
    assert _kalem(h, "Faiz veya kâr payı").tutar_tl == pytest.approx(beklenen)


def test_azami_puan_tavani_uygulanir():
    """Repo oranı çok yüksekse puan tavanı devreye girmeli: %60 x %40 = 24
    puan ama tavan 20."""
    h = hesapla("teknoloji_hamlesi", "Konya", 10_000_000,
                kredi_tl=7_000_000, repo_faiz_orani=60.0)
    beklenen = 7_000_000 * 0.20 * FAIZ_DESTEGI_AZAMI_YIL  # 20 puan tavanı
    assert _kalem(h, "Faiz veya kâr payı").tutar_tl == pytest.approx(beklenen)


def test_hedef_yatirimlarda_faiz_destegi_bolge_kisitli():
    """MADDE 15/1-c: Hedef Yatırımlarda faiz desteği YALNIZCA 4, 5 ve 6.
    bölgelerde. Kısıt atlanırsa 1. bölgedeki kullanıcıya hak etmediği bir
    destek gösterilir."""
    assert FAIZ_DESTEGI_BOLGE_KISITI["hedef_yatirimlar"] == {4, 5, 6}

    # Gaziantep 3. bölge -> destek yok
    h3 = hesapla("hedef_yatirimlar", "Gaziantep", 40_000_000,
                 kredi_tl=20_000_000, repo_faiz_orani=37.0)
    assert _kalem(h3, "Faiz veya kâr payı").tutar_tl == 0.0

    # Van 6. bölge -> destek var
    h6 = hesapla("hedef_yatirimlar", "Van", 40_000_000,
                 kredi_tl=20_000_000, repo_faiz_orani=37.0)
    assert _kalem(h6, "Faiz veya kâr payı").tutar_tl > 0


def test_repo_orani_yoksa_faiz_destegi_hesaplanmaz():
    h = hesapla("teknoloji_hamlesi", "Konya", 10_000_000, kredi_tl=5_000_000)
    k = _kalem(h, "Faiz veya kâr payı")
    assert k.tutar_tl is None
    assert "repo" in k.eksik_bilgi.lower()


# --------------------------------------------------------- makine desteği

def test_makine_destegi_elle_hesapla_ayni():
    """Tavan: sabit yatırımın %15'i veya 240M TL, hangisi küçükse."""
    h = hesapla("teknoloji_hamlesi", "Konya", 100_000_000,
                makine_techizat_tl=40_000_000)
    ham = 40_000_000 * MAKINE_DESTEGI_ORANI          # 10M
    tavan = min(100_000_000 * 0.15, 240_000_000)      # 15M
    assert _kalem(h, "Makine desteği").tutar_tl == pytest.approx(min(ham, tavan))


def test_makine_destegi_tavanla_sinirlanir():
    h = hesapla("teknoloji_hamlesi", "Konya", 20_000_000,
                makine_techizat_tl=40_000_000)
    # ham = 10M ama tavan = 20M x %15 = 3M
    assert _kalem(h, "Makine desteği").tutar_tl == pytest.approx(3_000_000)
    assert "tavan" in _kalem(h, "Makine desteği").aciklama.lower()


def test_stratejik_hamlede_mutlak_tavan_daha_dusuk():
    tek = MAKINE_DESTEGI_TAVANI["teknoloji_hamlesi"][1]
    strat = MAKINE_DESTEGI_TAVANI["stratejik_hamle"][1]
    assert tek == 240_000_000
    assert strat == 180_000_000
    assert strat < tek


def test_kalkinma_hamlesi_disinda_makine_destegi_sifir():
    h = hesapla("hedef_yatirimlar", "Konya", 40_000_000,
                makine_techizat_tl=30_000_000)
    k = _kalem(h, "Makine desteği")
    assert k.tutar_tl == 0.0
    assert "Kalkınma Hamlesi" in k.aciklama


def test_makine_birim_fiyat_esigi_belirtilir():
    h = hesapla("teknoloji_hamlesi", "Konya", 20_000_000)
    assert str(MAKINE_BIRIM_FIYAT_ESIGI)[:1] in _kalem(h, "Makine desteği").aciklama \
        or "2.000.000" in _kalem(h, "Makine desteği").aciklama


# ------------------------------------------- asgari tutar ve uyarı davranışı

def test_asgari_tutarin_altinda_uyarilir():
    h = hesapla("teknoloji_hamlesi", "İstanbul", 5_000_000)
    assert h.asgari_sabit_yatirim_tl == 12_000_000
    assert h.asgari_karsilaniyor_mu is False
    assert any("asgari" in u.lower() for u in h.uyarilar)


def test_asgari_tutar_karsilaniyorsa_uyari_yok():
    h = hesapla("teknoloji_hamlesi", "İstanbul", 20_000_000)
    assert h.asgari_karsilaniyor_mu is True
    assert not any("altında" in u for u in h.uyarilar)


def test_il_taninmazsa_bolgeye_bagli_kalemler_hesaplanmaz():
    h = hesapla("teknoloji_hamlesi", "Olmayan Şehir", 20_000_000,
                ilave_istihdam=10, aylik_asgari_ucret_isveren_primi_tl=4_000)
    assert h.bolge is None
    assert _kalem(h, "Sigorta primi").tutar_tl is None
    assert any("bölge belirlenemedi" in u for u in h.uyarilar)
    # Vergi indirimi bölgeden bağımsız, yine hesaplanmalı.
    assert _kalem(h, "Vergi indirimi").tutar_tl is not None


def test_azami_tutar_uyarisi_her_zaman_var():
    """Tavanı kesin gelir gibi sunmak yatırımcıyı yanlış bütçeye sürükler."""
    h = hesapla("teknoloji_hamlesi", "Konya", 20_000_000)
    birlesik = " ".join(h.uyarilar)
    assert "AZAMİ" in birlesik
    assert "garanti değildir" in birlesik


def test_faiz_ve_makine_birlikte_alinamaz_uyarisi():
    """MADDE 16/3. İki senaryo ayrı toplanmalı, toplamları birleştirilmemeli."""
    h = hesapla("teknoloji_hamlesi", "Konya", 40_000_000,
                makine_techizat_tl=20_000_000, kredi_tl=20_000_000,
                repo_faiz_orani=37.0)
    assert any("birlikte" in u and "alınamaz" in u for u in h.uyarilar)
    assert h.toplam_faiz_senaryosu_tl != h.toplam_makine_senaryosu_tl


def test_toplamlar_kalemlerle_tutarli():
    h = hesapla("teknoloji_hamlesi", "Konya", 40_000_000,
                makine_techizat_tl=20_000_000, kredi_tl=20_000_000,
                ilave_istihdam=10, aylik_asgari_ucret_isveren_primi_tl=4_000,
                repo_faiz_orani=37.0)
    ortak = (_kalem(h, "Vergi indirimi").tutar_tl
             + _kalem(h, "Sigorta primi").tutar_tl)
    assert h.toplam_faiz_senaryosu_tl == pytest.approx(
        ortak + _kalem(h, "Faiz veya kâr payı").tutar_tl)
    assert h.toplam_makine_senaryosu_tl == pytest.approx(
        ortak + _kalem(h, "Makine desteği").tutar_tl)


# ------------------------------------------------------------ geçersiz girdi

def test_bilinmeyen_program_hata_verir():
    with pytest.raises(ValueError, match="Bilinmeyen program"):
        hesapla("olmayan_program", "Konya", 1_000_000)


@pytest.mark.parametrize("tutar", [0, -1, None])
def test_gecersiz_yatirim_tutari_hata_verir(tutar):
    with pytest.raises(ValueError):
        hesapla("teknoloji_hamlesi", "Konya", tutar)


# -------------------------------------------------------- karşılaştırma

def test_karsilastirma_bes_programi_doner_ve_siralar():
    sonuclar = programlari_karsilastir(
        "Gaziantep", 40_000_000, makine_techizat_tl=25_000_000,
        kredi_tl=20_000_000, ilave_istihdam=30,
        aylik_asgari_ucret_isveren_primi_tl=4_500, repo_faiz_orani=37.0)
    assert len(sonuclar) == len(PROGRAMLAR)
    enler = [max(h.toplam_faiz_senaryosu_tl, h.toplam_makine_senaryosu_tl)
             for h in sonuclar]
    assert enler == sorted(enler, reverse=True), "en yüksek destek başta olmalı"
    # Yatırıma katkı oranı en yüksek program (%50) en üstte beklenir.
    assert sonuclar[0].program in ("teknoloji_hamlesi", "yerel_kalkinma_hamlesi")
    # Hedef Yatırımlar (%20, faiz/makine desteği yok) en altta.
    assert sonuclar[-1].program == "hedef_yatirimlar"


def test_sozluk_cikisinda_kaynak_var():
    h = hesapla("teknoloji_hamlesi", "Konya", 20_000_000)
    d = h.sozluk()
    assert "9903" in d["kaynak"]
    assert d["kalemler"] and all("madde" in k for k in d["kalemler"])
