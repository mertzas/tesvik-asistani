"""Dry-run'da bulunan yanlış-pozitif kilit riskine karşı korumalar:
örnekleme dayanağı reddi, çok bileşenli program kuralı (prompt) ve iki çağrı
tutarlılık doğrulaması."""
import asyncio
from types import SimpleNamespace

from app import nace_extraction as ne
from app.nace_extraction import KapsamTuru, SYSTEM_PROMPT, extract_nace_scope

GIRISIMCI = {
    "id": 1, "baslik": "Girişimci Destek Programı",
    "aciklama": "Program çok bileşenlidir. İş Geliştirme Desteği: İmalat/yazılım/Ar-Ge sektöründe 0-3 yaş "
                "işletme başvurabilir. Desteklenen sektörler arasında imalat, telekomünikasyon, bilgisayar "
                "programlama yer alır.",
}


def run(c):
    return asyncio.run(c)


class SahteIstemci:
    def __init__(self, *cevaplar):
        self.cevaplar = list(cevaplar)
        self.cagrilar = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.cagrilar.append(kw)
        blok = SimpleNamespace(type="tool_use", name=ne.TOOL_ADI, input=self.cevaplar.pop(0))
        return SimpleNamespace(content=[blok])


def _kod(prefix, dayanak, guven=0.9):
    return {"nace_prefix": prefix, "guven_skoru": guven, "dayanak_metin": dayanak}


def _cevap(tur, kodlar=(), guven=0.9):
    return {"analiz_notu": "g", "kapsam_turu": tur, "kapsam_guven": guven,
            "yararlanici_tipi": "BELIRSIZ", "hedef_nace_kodlari": list(kodlar),
            "haric_tutulan_nace_kodlari": []}


def test_ornekleme_dayanagi_kod_yazdirmaz():
    """GERÇEK OLAY (dry-run): "Desteklenen sektörler arasında imalat, telekomünikasyon ... yer alır"
    alıntısıyla 61/62/72 kilitlenmişti; bu bir örneklemedir."""
    cevap = _cevap("SEKTOR_KISITLI", [_kod("62", "Desteklenen sektörler arasında imalat, telekomünikasyon, "
                                                   "bilgisayar programlama yer alır")])
    sonuc = run(extract_nace_scope(GIRISIMCI, client=SahteIstemci(cevap)))
    assert sonuc.rows == [] and sonuc.kapsam_turu is KapsamTuru.BELIRSIZ
    assert any("örnekleme" in s for _, s in sonuc.reddedilenler)


def test_baglayici_ifadeli_alinti_ornekleme_kelimesi_icerse_de_gecer():
    metin = {"id": 2, "baslik": "X", "aciklama": "Destek yalnızca gıda dahil olmak üzere imalat yapanlara verilir."}
    cevap = _cevap("SEKTOR_KISITLI", [_kod("C", "yalnızca gıda dahil olmak üzere imalat yapanlara")])
    sonuc = run(extract_nace_scope(metin, client=SahteIstemci(cevap)))
    assert [r["nace_prefix"] for r in sonuc.rows] == ["C"]


def test_prompt_ornekleme_ve_cok_bilesenli_kurallarini_iceriyor():
    for ifade in ["arasında", "Çok bileşenli programlar", "yalnızca BİR unsura", "yer alır"]:
        assert ifade in SYSTEM_PROMPT, ifade


METIN = {"id": 3, "baslik": "Çay Destek", "aciklama": "Prim yalnızca yaş çay üreticilerine ödenir."}
KISITLI_A = _cevap("SEKTOR_KISITLI", [_kod("01.27", "yalnızca yaş çay üreticilerine")])
KISITLI_A2 = _cevap("SEKTOR_KISITLI", [_kod("01", "yalnızca yaş çay üreticilerine")])        # aynı kısım (A)
KISITLI_C = _cevap("SEKTOR_KISITLI", [_kod("10.83", "yalnızca yaş çay üreticilerine")])      # farklı kısım


def test_tutarlilik_varsayilan_kapali_tek_cagri():
    istemci = SahteIstemci(KISITLI_A)
    run(extract_nace_scope(METIN, client=istemci))
    assert len(istemci.cagrilar) == 1


def test_iki_cagri_ayni_kismi_verirse_kilit_yazilir():
    istemci = SahteIstemci(KISITLI_A, KISITLI_A2)
    sonuc = run(extract_nace_scope(METIN, client=istemci, tutarlilik_kontrolu=True))
    assert len(istemci.cagrilar) == 2
    assert [r["nace_prefix"] for r in sonuc.rows] == ["01.27"] and not sonuc.manuel_inceleme_gerekli


def test_iki_cagri_farkli_kisim_verirse_kilit_yazilmaz_incelemeye_duser():
    sonuc = run(extract_nace_scope(METIN, client=SahteIstemci(KISITLI_A, KISITLI_C), tutarlilik_kontrolu=True))
    assert sonuc.rows == [] and sonuc.kapsam_turu is KapsamTuru.BELIRSIZ
    assert sonuc.manuel_inceleme_gerekli and "uyuşmadı" in sonuc.inceleme_nedenleri[0]


def test_ikinci_cagri_yatay_derse_kilit_yazilmaz():
    sonuc = run(extract_nace_scope(METIN, client=SahteIstemci(KISITLI_A, _cevap("YATAY")),
                                   tutarlilik_kontrolu=True))
    assert sonuc.rows == [] and sonuc.manuel_inceleme_gerekli


def test_yatay_ilk_sonuc_icin_ikinci_cagri_yapilmaz():
    istemci = SahteIstemci(_cevap("YATAY"))
    run(extract_nace_scope(METIN, client=istemci, tutarlilik_kontrolu=True))
    assert len(istemci.cagrilar) == 1


def test_tutarlilik_dislama_satirlarini_korur():
    metin = {"id": 4, "baslik": "S", "aciklama": "Yalnızca imalat; tütün ürünleri (12) kapsam dışıdır."}
    c1 = _cevap("SEKTOR_KISITLI", [_kod("C", "Yalnızca imalat")])
    c1["haric_tutulan_nace_kodlari"] = [_kod("12", "tütün ürünleri (12) kapsam dışıdır")]
    c2 = _cevap("YATAY")
    sonuc = run(extract_nace_scope(metin, client=SahteIstemci(c1, c2), tutarlilik_kontrolu=True))
    assert [(r["nace_prefix"], r["haric_mi"]) for r in sonuc.rows] == [("12", True)]
