"""Kullanıcıya giden metinlerde Türkçe karakter (2026-10-08): eşleştirme kartı gerekçeleri, 9903 ön değerlendirmesi,
veri tazeliği uyarıları ve hata mesajları ASCII yazılmıştı ("Sektorunuz ... destegin kapsamina uygun")."""
import ast
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent / "app"
MODULLER = ["matching.py", "nace_9903.py", "veri_tazeligi.py", "billing.py", "kobi.py"]
# Türkçede ASCII hâliyle geçmeyen kelimeler (tam kelime). Anahtar/kod dizeleri alt çizgili olduğu için eşleşmez.
# re.IGNORECASE KULLANILMAZ: Python'da "i" büyük/küçük harf duyarsızken "ı" ve "İ" ile de eşleşir ("yatırım"ı yakalar);
# bunun yerine metin küçük harfe çevrilip aranır.
ASCII_KELIMELER = re.compile(
    r"\b(destegin|destegi|isletmesi|isletme|eslesiyor|eslesme|gunluk|ozeldir|girdiginiz|urun|sektorunuz|"
    r"calisan|degil|icin|gore|sart|sarti|olcek|olceginiz|yatirim|yatirimlar|bolgede|bolgeye|karsilayip|"
    r"yetistiriciligi|odeme|kayitlari|fiyatlari|hic|okunamadi|henuz|gecersiz|tamamlanmadi)\b")
KOD_ANAHTARI = re.compile(r"^[a-z0-9_]+$")


def _ascii_turkce(s: str) -> bool:
    return bool(ASCII_KELIMELER.search(s.replace("I", "i").lower()))


def _metin_sabitleri(yol: Path):
    """Metin sabitleri ve f-string'lerin SABİT parçaları (ast ile; Python sürümünden bağımsız).

    2026-10-08: tokenize tabanlı önceki hâl Python 3.12+'da f-string'leri hiç görmüyordu (PEP 701: f-string parça parça
    belirteçlenir), 3.11'de (CI) ise "{olcek:,.0f}" gibi değişken adlarını metin sanıyordu: yerelde yeşil, CI'da
    kırmızıydı ve gerçek bir hatayı ("Odeme henuz tamamlanmadi") gizliyordu. Docstring'ler ve üç tırnaklı metinler
    (açıklama/şablon) önceki gibi dışarıda."""
    kaynak = yol.read_text(encoding="utf-8")
    agac = ast.parse(kaynak)
    docstringler = {id(n.value) for n in ast.walk(agac) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}

    def uc_tirnak(dugum) -> bool:
        parca = ast.get_source_segment(kaynak, dugum) or ""
        return parca.lstrip("rbfuRBFU").startswith(('"""', "'''"))

    fstring_parcalari = {id(v) for n in ast.walk(agac) if isinstance(n, ast.JoinedStr) for v in n.values}
    for n in ast.walk(agac):
        if isinstance(n, ast.JoinedStr) and not uc_tirnak(n):
            sabit = "".join(v.value for v in n.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            yield n.lineno, sabit
        elif (isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstringler
              and id(n) not in fstring_parcalari and not uc_tirnak(n)):
            yield n.lineno, n.value


@pytest.mark.parametrize("modul", MODULLER)
def test_kullaniciya_giden_metinlerde_ascii_turkce_yok(modul):
    hatalar = [f"{modul}:{satir}: {s[:80]}" for satir, s in _metin_sabitleri(KOK / modul)
               if _ascii_turkce(s) and not KOD_ANAHTARI.match(s)]
    assert not hatalar, "ASCII Türkçe metin:\n" + "\n".join(hatalar)


def test_eslesme_karti_gerekceleri_turkce(db_session):
    from app.matching import HEDEF_GEREKCE_ONEKI, esles
    from app.models import FinancialProfile, Tesvik
    db_session.add(Tesvik(id=1, kurum="KOSGEB", baslik="Makine Yatırım Desteği", ozet="makine", detay="d",
                          aktif_mi=True, kaynak_url="https://t/1", uygunluk_kriterleri={"sektorler": ["imalat"]}))
    db_session.commit()
    sonuc = esles(FinancialProfile(sektor="imalat", calisan_sayisi=0, hedefler=["makine"]), db_session)
    metin = " ".join(sonuc[0].gerekce + sonuc[0].eksik_kriterler)
    assert "Sektörünüz (imalat) bu desteğin kapsamına uygun." in metin
    assert "Şahıs işletmesi" in metin
    assert not _ascii_turkce(metin), metin
    assert f"{HEDEF_GEREKCE_ONEKI} makine alımı." in sonuc[0].gerekce, "iç anahtar ('makine') değil etiket"
