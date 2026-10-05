"""NACE hiyerarşisi: normalizasyon ve sektör uyum skoru (saf fonksiyonlar).

Kod biçimleri: Kısım (tek harf, A-U), Bölüm (2 hane, "10"), Grup/Sınıf/Alt
sınıf (3-6 hane: "10.7", "10.71", "10.71.01"). Kullanıcı girdisinde kısım
harfi olabilir ("C.10.71", "C10.71"); sistemde standart biçim harfsiz noktalı
rakamdır, yalnızca kısım düzeyindeki kodlar tek harf olarak kalır. Bu biçim
hem NACE Rev.2 hem de 9903 EK-3'ün kullandığı Rev.2.1 kodlarıyla uyumludur.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Rev.2 kısım -> bölüm aralığı (dahil)
_KISIMLAR: dict[str, tuple[int, int]] = {
    "A": (1, 3), "B": (5, 9), "C": (10, 33), "D": (35, 35), "E": (36, 39),
    "F": (41, 43), "G": (45, 47), "H": (49, 53), "I": (55, 56), "J": (58, 63),
    "K": (64, 66), "L": (68, 68), "M": (69, 75), "N": (77, 82), "O": (84, 84),
    "P": (85, 85), "Q": (86, 88), "R": (90, 93), "S": (94, 96), "T": (97, 98),
    "U": (99, 99),
}
_BOLUM_KISIM: dict[int, str] = {
    b: k for k, (lo, hi) in _KISIMLAR.items() for b in range(lo, hi + 1)
}

KISIM_ADLARI: dict[str, str] = {
    "A": "Tarım, ormancılık ve balıkçılık", "B": "Madencilik ve taş ocakçılığı",
    "C": "İmalat", "D": "Elektrik, gaz, buhar", "E": "Su temini, atık yönetimi",
    "F": "İnşaat", "G": "Toptan ve perakende ticaret", "H": "Ulaştırma ve depolama",
    "I": "Konaklama ve yiyecek hizmeti", "J": "Bilgi ve iletişim",
    "K": "Finans ve sigorta", "L": "Gayrimenkul", "M": "Mesleki, bilimsel, teknik",
    "N": "İdari ve destek hizmetleri", "O": "Kamu yönetimi", "P": "Eğitim",
    "Q": "Sağlık ve sosyal hizmet", "R": "Kültür, sanat, eğlence",
    "S": "Diğer hizmetler", "T": "Hane halkı faaliyetleri", "U": "Uluslararası kuruluşlar",
}

# Skor sabitleri (0-1)
TAM = 1.0              # program kodu işletmenin kodunu kapsıyor (veya eşit)
ISLETME_GENIS = 0.6    # işletme kodu programınkinden daha geniş ("10" vs "10.71")
AYNI_BOLUM = 0.3       # aynı bölüm, farklı dal
YATAY = 0.4            # NACE kısıtı olmayan, sektör bağımsız program

_GIRDI = re.compile(r"^([A-U])?[\s.\-]*([0-9][0-9.\s]*)?$")


def kisim_of(kod: str) -> str | None:
    """Standart biçimdeki kodun kısım harfi."""
    if kod in _KISIMLAR:
        return kod
    if kod and kod[:2].isdigit():
        return _BOLUM_KISIM.get(int(kod[:2]))
    return None


def normalize_nace(ham: str | None) -> str | None:
    """Kullanıcı girdisini standart biçime çevirir; geçersizse None.

    "C" -> "C" | "C.10.71", "c10.71", "1071", "10.71" -> "10.71" |
    "10.7" -> "10.7" | "A.10" -> None (harf bölümle uyuşmuyor)."""
    if ham is None:
        return None
    metin = str(ham).strip().upper()
    if not metin:
        return None
    m = _GIRDI.match(metin)
    if not m:
        return None
    harf, kalan = m.group(1), m.group(2)
    rakam = re.sub(r"\D", "", kalan or "")
    if not rakam:
        return harf if harf in _KISIMLAR else None
    if not 2 <= len(rakam) <= 6:
        return None
    kisim = _BOLUM_KISIM.get(int(rakam[:2]))
    if kisim is None or (harf is not None and harf != kisim):
        return None
    parca = [rakam[:2]]
    if len(rakam) > 2:
        parca.append(rakam[2:4])
    if len(rakam) > 4:
        parca.append(rakam[4:6])
    return ".".join(parca)


def _rakam(kod: str) -> str:
    return kod.replace(".", "")


def _cift_uyumu(c: str, p: str) -> float:
    """Standart biçimli iki kod için uyum (0-1)."""
    c_kisim, p_kisim = c in _KISIMLAR, p in _KISIMLAR
    if c_kisim or p_kisim:
        if c_kisim and p_kisim:
            return TAM if c == p else 0.0
        if p_kisim:                       # program tüm kısmı kapsıyor
            return TAM if kisim_of(c) == p else 0.0
        return ISLETME_GENIS if kisim_of(p) == c else 0.0   # işletme kısım düzeyinde
    cr, pr = _rakam(c), _rakam(p)
    if cr.startswith(pr):
        return TAM
    if pr.startswith(cr):
        return ISLETME_GENIS
    if cr[:2] == pr[:2]:
        return AYNI_BOLUM
    return 0.0


@dataclass(frozen=True)
class SektorUyumu:
    skor: float                 # 0.0-1.0
    durum: str                  # "yatay" | "nace_yok" | "tam" | "kismi" | "uyumsuz"
    aciklama: str


def sector_match(isletme_kodu: str | None, program_kodlari: list[str]) -> SektorUyumu:
    """İşletmenin NACE kodu ile programın NACE kodları arasındaki uyum.

    Program kodu işletmeyi kapsıyorsa tam; işletme programdan geniş ya da aynı
    bölümde ise kısmi; aksi hâlde 0. Programın kodu yoksa yatay (sektör
    bağımsız) sayılır. İşletmenin kodu yoksa ve program sektörlüyse 0."""
    kodlar = [k for k in (normalize_nace(x) for x in program_kodlari) if k]
    if not kodlar:
        return SektorUyumu(YATAY, "yatay", "sektör bağımsız (yatay) destek")
    c = normalize_nace(isletme_kodu)
    if c is None:
        return SektorUyumu(0.0, "nace_yok",
                           "işletmenin NACE kodu girilmemiş, sektör uyumu ölçülemedi")
    en_iyi, en_iyi_kod = 0.0, None
    for p in kodlar:
        u = _cift_uyumu(c, p)
        if u > en_iyi:
            en_iyi, en_iyi_kod = u, p
    if en_iyi_kod is None:
        return SektorUyumu(0.0, "uyumsuz", f"{c} sektörü programın sektörleriyle örtüşmüyor")
    durum = "tam" if en_iyi == TAM else "kismi"
    ad = "tam sektör eşleşmesi" if durum == "tam" else "kısmi sektör eşleşmesi"
    return SektorUyumu(en_iyi, durum, f"{c} sektörü ile {en_iyi_kod} için {ad}")


def sector_fit(isletme_kodu: str | None, program_kodlari: list[str]) -> float:
    """0.0-1.0 sektör uyum skoru (bkz. sector_match)."""
    return sector_match(isletme_kodu, program_kodlari).skor
