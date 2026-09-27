"""
2026 üretim yılı bitkisel üretim destekleme birim fiyatları ve hesaplayıcı.

NEDEN BU MODÜL VAR
------------------
Tarım Bakanlığı kayıtlarında tutar yalnızca serbest metin olarak duruyordu
("Dekar başına ... TL" gibi) ve çiftçinin kendi arazi büyüklüğüyle
ölçeklenmiyordu. Ölçüm (2026-09-26): 176 kaydın 162'sinde hiçbir yapısal
tutar yoktu ve "toplam tahmini destek" çoğu profilde 0 TL çıkıyordu.

Bakanlık desteği dekar başına ve KATSAYI sistemiyle veriyor: her ürün bir
kategoriye giriyor, kategorinin katsayısı temel destek birim değeriyle
çarpılıyor. Bu yüzden tutar kayda değil ÜRÜNE + ALANA bağlıdır ve burada
hesaplanır.

ÖNEMLİ: 2026'da mazot ve gübre destekleri "Temel Destek" adı altında
BİRLEŞTİRİLDİ. Eski "mazot desteği + gübre desteği" ayrımıyla hesap yapan
bir metin artık yanlıştır.

KAYNAK
------
T.C. Tarım ve Orman Bakanlığı BUGEM, "2026 Üretim Yılı Bitkisel Üretim
Destekleme Birim Fiyatları":
https://www.tarimorman.gov.tr/BUGEM/Belgeler/Tarım%20Havzaları/2026%20Yılı%20Destekleme%20Birim%20Fiyatları.pdf
Tüm katsayı ve tutarlar bu resmî tablodan birebir alınmıştır
(doğrulama: 2026-09-26).

NOT: Bazı haber kaynakları temel destek birim değerini 367 TL/da olarak
veriyor. Bakanlığın kendi yayınladığı tabloda değer 310,00 TL/da ve tablodaki
tüm toplamlar bu değerle tutarlı (1,3 x 310 = 403,00; 2,25 x 310 = 697,50).
Bu modül resmî tabloyu esas alıyor; haber kaynaklarındaki farklı rakam
doğrulanamadı.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.urun_sektor_anahtarlari import kucult

KAYNAK = ("T.C. Tarım ve Orman Bakanlığı BUGEM, 2026 Üretim Yılı Bitkisel "
          "Üretim Destekleme Birim Fiyatları")
KAYNAK_URL = ("https://www.tarimorman.gov.tr/BUGEM/Belgeler/"
              "Tar%C4%B1m%20Havzalar%C4%B1/2026%20Y%C4%B1l%C4%B1%20"
              "Destekleme%20Birim%20Fiyatlar%C4%B1.pdf")
URETIM_YILI = 2026

# Temel destek birim değeri: katsayı 1 = bu tutar (TL/dekar).
# Tablodaki tüm toplamlar bu değerle doğrulandı.
KATSAYI_BIRIM_TL = 310.00

# ---------------------------------------------------------------------------
# Yem bitkisi grupları
# ---------------------------------------------------------------------------
# Resmî tablo kategorilerde "Birinci/İkinci grup yem bitkileri" diyor ve hangi
# ürünleri kapsadığını DİPNOTTA sayıyor. Dipnotu almazsak "yonca" ya da "fiğ"
# yazan çiftçi hiçbir kategoriye eşleşmiyor ve destek hesaplanamıyor
# (doğrulandı 2026-09-26). Listeler tablonun dipnotundan birebir alındı.
BIRINCI_GRUP_YEM = (
    "fiğ", "burçak", "mürdümük", "hayvan pancarı", "yem şalgamı",
    "yem bezelyesi", "yem baklası", "üçgül", "italyan çimi", "yulaf",
    "çavdar", "tritikale",
)
IKINCI_GRUP_YEM = (
    "yonca", "korunga", "yapay çayır mera", "silajlık mısır", "silajlık soya",
    "sorgum otu", "sudan otu", "sorgum-sudan otu melezi",
)
TUM_YEM_BITKILERI = BIRINCI_GRUP_YEM + IKINCI_GRUP_YEM


# ---------------------------------------------------------------------------
# 1 - TEMEL DESTEK (eski mazot + gübre desteği, 2026'da birleştirildi)
# ---------------------------------------------------------------------------
# kategori no -> (katsayı, ürünler)
TEMEL_DESTEK_KATEGORILERI: dict[int, tuple[float, tuple[str, ...]]] = {
    # DİKKAT: kategori sırası önemli. "silajlık soya" 2. kategoride,
    # düz "soya" 3. kategoride; daha uzun/özel ifade önce denenmeli.
    1: (1.0, ("aspir", "mercimek", "nohut", "patates", "soğan",
              "birinci grup yem bitkileri") + BIRINCI_GRUP_YEM),
    2: (1.3, ("arpa", "buğday", "mısır", "ikinci grup yem bitkileri")
             + IKINCI_GRUP_YEM),
    3: (1.5, ("ayçiçeği", "fındık", "kolza", "kanola", "fasulye", "soya", "çay")),
    4: (2.25, ("çeltik", "pamuk")),
}

# Nadas ayrı bir katsayıya sahip (ürün değil, arazi durumu).
NADAS_KATSAYISI = 0.3

# KOBÜKS kayıtlı genç ve kadın çiftçilere 3 katsayısı ile İLAVE temel destek.
GENC_KADIN_ILAVE_KATSAYI = 3.0

# ---------------------------------------------------------------------------
# 2 - PLANLI ÜRETİM DESTEĞİ
# ---------------------------------------------------------------------------
# Temel destekle aynı kategori katsayıları, ancak ürün listesi biraz farklı:
# fındık ve çay planlı üretim desteği kapsamında DEĞİL.
PLANLI_URETIM_KATEGORILERI: dict[int, tuple[float, tuple[str, ...]]] = {
    1: (1.0, ("aspir", "mercimek", "nohut", "patates", "soğan",
              "birinci grup yem bitkileri") + BIRINCI_GRUP_YEM),
    2: (1.3, ("arpa", "buğday", "mısır", "ikinci grup yem bitkileri")
             + IKINCI_GRUP_YEM),
    3: (1.5, ("ayçiçeği", "kolza", "kanola", "fasulye", "soya")),
    4: (2.25, ("pamuk",)),
}
# Kütlü pamukta yurt içinde üretilip sertifikalandırılan tohum şartı var.
PLANLI_PAMUK_TOHUM_SARTI = ("Kütlü pamuk için yurt içinde üretilip "
                            "sertifikalandırılan tohum kullanma şartı aranır.")

# Süt havzası illerinde yem bitkisi üretenlere, kategori katsayısının %50'si
# kadar ilave planlı üretim desteği.
SUT_HAVZASI_ILLERI = ("Amasya", "Bingöl", "Bitlis", "Çorum", "Elâzığ",
                      "Erzincan", "Erzurum", "Muş", "Tokat", "Tunceli")
SUT_HAVZASI_YEM_ILAVE_ORANI = 0.50

# ---------------------------------------------------------------------------
# SU KISITI DESTEĞİ (yeraltı su kısıtı belirlenen havzalar)
# ---------------------------------------------------------------------------
SU_KISITI_KATEGORILERI: dict[int, tuple[float, tuple[str, ...]]] = {
    1: (0.8, ("aspir", "fiğ", "mercimek", "nohut", "yem bezelyesi")),
    2: (1.4, ("arpa", "buğday")),
    3: (1.2, ("ayçiçeği",)),
}
SU_KISITI_NOTU = (
    "Yeraltı sularının yetersiz olduğu Bakanlıkça tespit edilmiş 11 il 52 "
    "ilçe/havzada, sulu tarım arazilerinde ilave ödenir. Aynı havzalarda "
    "mısır (dane) ve patates ekilişlerine temel, planlı üretim ve üretimi "
    "geliştirme desteği ÖDENMEZ."
)

# ---------------------------------------------------------------------------
# 3 - ÜRETİMİ GELİŞTİRME DESTEĞİ
# ---------------------------------------------------------------------------
# A - Sertifikalı tohum kullanım desteği
SERTIFIKALI_TOHUM: tuple[tuple[float, tuple[str, ...]], ...] = (
    (0.56, ("arpa", "buğday", "çavdar", "çeltik", "fasulye", "tritikale", "yulaf")),
    (0.20, ("aspir", "kolza", "kanola", "susam")),
    (0.60, ("korunga", "soya", "yer fıstığı", "yonca")),
    (0.40, ("fiğ", "mercimek", "nohut", "yem bezelyesi")),
    (2.20, ("patates",)),
)
# Yerli sertifikalı tohum kullanım desteği (yukarıdakine ek)
YERLI_SERTIFIKALI_TOHUM: tuple[tuple[float, tuple[str, ...]], ...] = (
    (0.60, ("ayçiçeği", "mısır", "soya")),
    (1.00, ("patates",)),   # STKD'ye İLAVE ödenir
)

# B - Sertifikalı / standart fidan kullanım desteği
FIDAN_URUNLERI = (
    "altıntop", "armut", "asma", "ayva", "badem", "ceviz", "dut", "elma",
    "erik", "fındık", "incir", "kayısı", "kestane", "kiraz", "kivi", "limon",
    "mandarin", "mandalina", "nektarin", "pikan cevizi", "portakal", "şeftali",
    "trabzon hurması", "vişne", "zeytin",
)
FIDAN_KATSAYILARI = {"standart": 2.0, "sertifikali": 5.0}

# C - Organik tarım desteği: ürün grubu -> (bireysel, grup)
ORGANIK_TARIM = {
    1: (1.2, 0.6),
    2: (0.6, 0.3),
    3: (0.4, 0.2),
}
ORGANIK_ARILI_KOVAN_KATSAYI = 0.3   # kovan başına
# 1. derece tarımsal amaçlı örgüt üyelerine katsayının %25'i kadar ilave.
ORGANIK_ORGUT_ILAVE_ORANI = 0.25

# D - İyi tarım uygulamaları desteği
IYI_TARIM = {
    "1_ortualti": (1.7, 0.85),   # örtüaltı/kapalı ortamda bitkisel üretim
    "1_acikta": (0.7, 0.35),
    "2": (0.6, 0.3),
    "3": (0.4, 0.2),
}

# E - Katı organik / organomineral gübre desteği
ORGANOMINERAL_GUBRE_KATSAYI = 0.32


def _tl(x: float) -> str:
    return f"{x:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _urun_eslesir_mi(urun: str, liste: tuple[str, ...]) -> bool:
    """Ürün adı listedeki bir kalemle eşleşiyor mu?

    kucult() kullanılıyor; Python'un str.lower()'i "MISIR" gibi büyük harfli
    girdiyi bozuyor (bkz. urun_sektor_anahtarlari.kucult).
    """
    u = kucult(urun).strip()
    if not u:
        return False
    for kalem in liste:
        k = kucult(kalem)
        # YALNIZCA "liste kalemi kullanıcı metninin içinde mi" yönü. Ters yön
        # (kullanıcı metni liste kaleminin içinde mi) yanlış kategori veriyordu:
        # düz "soya" 3. kategoridir (katsayı 1,5) ama ters yön onu 2. kategorideki
        # "silajlık soya" kalemine eşleştiriyordu (1,3) - yani soya üreticisine
        # eksik tutar gösteriliyordu (doğrulandı 2026-09-26).
        # Bu yön Türkçe ekleri yine karşılar: "buğdayım" içinde "buğday" var.
        if k in u:
            return True
    return False


def _kategori_bul(urun: str,
                  kategoriler: dict[int, tuple[float, tuple[str, ...]]],
                  ) -> tuple[int, float] | None:
    for no, (katsayi, urunler) in kategoriler.items():
        if _urun_eslesir_mi(urun, urunler):
            return no, katsayi
    return None


@dataclass
class DestekKalemi:
    ad: str
    katsayi: float
    dekar_basi_tl: float
    toplam_tl: float
    not_: str = ""


@dataclass
class TarimDestekHesabi:
    urun: str
    alan_dekar: float
    kalemler: list[DestekKalemi] = field(default_factory=list)
    toplam_tl: float = 0.0
    dekar_basi_toplam_tl: float = 0.0
    uyarilar: list[str] = field(default_factory=list)
    kapsam_disi: bool = False

    def sozluk(self) -> dict:
        return {
            "uretim_yili": URETIM_YILI,
            "urun": self.urun,
            "alan_dekar": self.alan_dekar,
            "katsayi_birim_tl": KATSAYI_BIRIM_TL,
            "kalemler": [
                {"ad": k.ad, "katsayi": k.katsayi,
                 "dekar_basi_tl": k.dekar_basi_tl, "toplam_tl": k.toplam_tl,
                 "not": k.not_ or None}
                for k in self.kalemler
            ],
            "dekar_basi_toplam_tl": self.dekar_basi_toplam_tl,
            "toplam_tl": self.toplam_tl,
            "kapsam_disi": self.kapsam_disi,
            "uyarilar": self.uyarilar,
            "kaynak": KAYNAK,
            "kaynak_url": KAYNAK_URL,
        }


def hesapla(
    urun: str,
    alan_dekar: float,
    *,
    il: str | None = None,
    planli_uretim: bool = True,
    sertifikali_tohum: bool = False,
    yerli_sertifikali_tohum: bool = False,
    fidan: str | None = None,          # "standart" | "sertifikali"
    organik_grup: int | None = None,   # 1 | 2 | 3
    organik_sertifika: str = "bireysel",   # "bireysel" | "grup"
    organik_orgut_uyesi: bool = False,
    iyi_tarim: str | None = None,      # IYI_TARIM anahtarları
    iyi_tarim_sertifika: str = "bireysel",
    organomineral_gubre: bool = False,
    genc_veya_kadin_kobuks: bool = False,
    su_kisiti_havzasi: bool = False,
    yem_bitkisi: bool = False,
) -> TarimDestekHesabi:
    """Bir ürün ve alan için 2026 bitkisel üretim desteklerini hesaplar.

    Varsayılan olarak yalnızca temel destek ve planlı üretim desteği
    hesaplanır; diğer kalemler ancak ilgili şart açıkça belirtilirse eklenir.
    Sertifikalı tohum ya da organik sertifika olmadığı hâlde o desteği
    toplamaya katmak, çiftçiye alamayacağı bir tutar göstermek olurdu.
    """
    if alan_dekar is None or alan_dekar <= 0:
        raise ValueError("alan_dekar pozitif olmalı")
    if not urun or not urun.strip():
        raise ValueError("ürün adı gerekli")

    h = TarimDestekHesabi(urun=urun.strip(), alan_dekar=alan_dekar)

    def ekle(ad: str, katsayi: float, not_: str = "", birim_alan: float | None = None):
        dekar_basi = katsayi * KATSAYI_BIRIM_TL
        alan = alan_dekar if birim_alan is None else birim_alan
        h.kalemler.append(DestekKalemi(
            ad=ad, katsayi=katsayi, dekar_basi_tl=round(dekar_basi, 2),
            toplam_tl=round(dekar_basi * alan, 2), not_=not_))

    # --- Temel destek ------------------------------------------------------
    temel = _kategori_bul(urun, TEMEL_DESTEK_KATEGORILERI)
    if temel is None:
        # "Diğer ürünler" 1. kategoride; yani listede olmayan bir bitkisel
        # ürün de 1,0 katsayıyla temel destek alır. Yine de bunu varsayım
        # olarak açıkça söylüyoruz.
        temel = (1, TEMEL_DESTEK_KATEGORILERI[1][0])
        h.uyarilar.append(
            f"'{urun}' resmî tabloda ayrı bir kategoride listelenmiyor; "
            "1. kategorideki \"Diğer ürünler\" kalemi varsayıldı (katsayı 1,0). "
            "Ürününüz farklı bir kategoriye giriyorsa tutar değişir."
        )
    kategori_no, katsayi = temel
    ekle(f"Temel destek ({kategori_no}. kategori)", katsayi,
         "2026'da mazot ve gübre destekleri bu kalemde BİRLEŞTİRİLDİ; "
         "artık ayrı mazot/gübre ödemesi yok.")

    if genc_veya_kadin_kobuks:
        ekle("İlave temel destek (KOBÜKS kayıtlı genç/kadın çiftçi)",
             GENC_KADIN_ILAVE_KATSAYI,
             "KOBÜKS kaydı şart; 3 katsayısı ile ilave ödenir.")

    # --- Planlı üretim desteği --------------------------------------------
    if planli_uretim:
        planli = _kategori_bul(urun, PLANLI_URETIM_KATEGORILERI)
        if planli is None:
            h.uyarilar.append(
                f"'{urun}' planlı üretim desteği kategorilerinde yok "
                "(fındık ve çay bu destek kapsamında değil); bu kalem "
                "hesaba katılmadı."
            )
        else:
            p_no, p_kat = planli
            notu = ""
            if _urun_eslesir_mi(urun, ("pamuk",)):
                notu = PLANLI_PAMUK_TOHUM_SARTI
            ekle(f"Planlı üretim desteği ({p_no}. kategori)", p_kat, notu)

            if yem_bitkisi and il and any(
                    kucult(il).strip() == kucult(x) for x in SUT_HAVZASI_ILLERI):
                ekle("İlave planlı üretim desteği (süt havzası, yem bitkisi)",
                     p_kat * SUT_HAVZASI_YEM_ILAVE_ORANI,
                     f"{il} süt havzası illeri arasında; yem bitkisi üretiminde "
                     "kategori katsayısının %50'si kadar ilave ödenir.")
    else:
        h.uyarilar.append(
            "Planlı üretim desteği hesaba katılmadı. Bu destek, Bakanlığın "
            "üretim planlaması kapsamında ilan ettiği ürün ve havzalarda "
            "ödenir; kaydınızın uygun olup olmadığını il/ilçe müdürlüğünden "
            "teyit edin."
        )

    # --- Su kısıtı desteği -------------------------------------------------
    if su_kisiti_havzasi:
        su = _kategori_bul(urun, SU_KISITI_KATEGORILERI)
        if su is None:
            h.uyarilar.append(
                f"'{urun}' su kısıtı desteği kategorilerinde yok; bu kalem "
                "hesaba katılmadı."
            )
        else:
            ekle(f"Yeraltı su kısıtı desteği ({su[0]}. kategori)", su[1],
                 SU_KISITI_NOTU)
        if _urun_eslesir_mi(urun, ("mısır", "patates")):
            h.uyarilar.append(
                "DİKKAT: su kısıtı havzalarında mısır (dane) ve patates "
                "ekilişlerine temel, planlı üretim ve üretimi geliştirme "
                "desteği ÖDENMEZ. Yukarıdaki temel/planlı kalemler bu havzada "
                "geçerli olmayabilir."
            )

    # --- Üretimi geliştirme: sertifikalı tohum ----------------------------
    if sertifikali_tohum:
        bulundu = False
        for kat, urunler in SERTIFIKALI_TOHUM:
            if _urun_eslesir_mi(urun, urunler):
                ekle("Sertifikalı tohum kullanım desteği", kat)
                bulundu = True
                break
        if not bulundu:
            h.uyarilar.append(
                f"'{urun}' için sertifikalı tohum kullanım desteği resmî "
                "tabloda tanımlı değil; bu kalem hesaba katılmadı."
            )
    if yerli_sertifikali_tohum:
        bulundu = False
        for kat, urunler in YERLI_SERTIFIKALI_TOHUM:
            if _urun_eslesir_mi(urun, urunler):
                notu = ("Patateste bu destek sertifikalı tohum desteğine "
                        "İLAVE ödenir." if _urun_eslesir_mi(urun, ("patates",))
                        else "")
                ekle("Yerli sertifikalı tohum kullanım desteği", kat, notu)
                bulundu = True
                break
        if not bulundu:
            h.uyarilar.append(
                f"'{urun}' için yerli sertifikalı tohum desteği tanımlı değil."
            )

    # --- Fidan -------------------------------------------------------------
    if fidan:
        if fidan not in FIDAN_KATSAYILARI:
            raise ValueError(
                f"fidan 'standart' veya 'sertifikali' olmalı, verilen: {fidan!r}")
        if not _urun_eslesir_mi(urun, FIDAN_URUNLERI):
            h.uyarilar.append(
                f"'{urun}' fidan kullanım desteği ürün listesinde yok; bu "
                "kalem hesaba katılmadı."
            )
        else:
            ekle(f"Sertifikalı/standart fidan kullanım desteği ({fidan})",
                 FIDAN_KATSAYILARI[fidan])

    # --- Organik tarım -----------------------------------------------------
    if organik_grup is not None:
        if organik_grup not in ORGANIK_TARIM:
            raise ValueError("organik_grup 1, 2 veya 3 olmalı")
        if organik_sertifika not in ("bireysel", "grup"):
            raise ValueError("organik_sertifika 'bireysel' veya 'grup' olmalı")
        bireysel, grup = ORGANIK_TARIM[organik_grup]
        kat = bireysel if organik_sertifika == "bireysel" else grup
        ekle(f"Organik tarım desteği ({organik_grup}. grup, {organik_sertifika})", kat)
        if organik_orgut_uyesi:
            ekle("İlave organik tarım desteği (1. derece örgüt üyesi)",
                 kat * ORGANIK_ORGUT_ILAVE_ORANI,
                 "Tarımsal amaçlı 1. derece örgüt üyeliği şart; katsayının "
                 "%25'i kadar ilave.")

    # --- İyi tarım ---------------------------------------------------------
    if iyi_tarim:
        if iyi_tarim not in IYI_TARIM:
            raise ValueError(
                f"iyi_tarim şunlardan biri olmalı: {', '.join(IYI_TARIM)}")
        if iyi_tarim_sertifika not in ("bireysel", "grup"):
            raise ValueError("iyi_tarim_sertifika 'bireysel' veya 'grup' olmalı")
        bireysel, grup = IYI_TARIM[iyi_tarim]
        kat = bireysel if iyi_tarim_sertifika == "bireysel" else grup
        ekle(f"İyi tarım uygulamaları desteği ({iyi_tarim}, {iyi_tarim_sertifika})",
             kat)

    # --- Organomineral gübre ----------------------------------------------
    if organomineral_gubre:
        ekle("Katı organik/organomineral gübre desteği",
             ORGANOMINERAL_GUBRE_KATSAYI,
             "İlgili üretim yılında bu gübreyi kullanmış olma şartı var.")

    h.dekar_basi_toplam_tl = round(sum(k.dekar_basi_tl for k in h.kalemler), 2)
    h.toplam_tl = round(sum(k.toplam_tl for k in h.kalemler), 2)

    h.uyarilar.append(
        f"Tutarlar {URETIM_YILI} üretim yılı resmî birim fiyatlarına göre "
        "hesaplandı ve ÇKS kaydınızın uygun olması şartına bağlıdır. Ödemeler "
        "hasat takvimine göre yapılır. Nihai tutar için il/ilçe tarım "
        "müdürlüğünden teyit alın."
    )
    return h


def arilik_destegi(kovan_sayisi: int) -> DestekKalemi:
    """Organik arılı kovan desteği - dekar değil KOVAN başına ödenir.

    Ayrı fonksiyon: kovan sayısını dekar gibi işlemek tutarı tamamen
    yanlış hesaplardı.
    """
    if kovan_sayisi is None or kovan_sayisi <= 0:
        raise ValueError("kovan_sayisi pozitif olmalı")
    birim = ORGANIK_ARILI_KOVAN_KATSAYI * KATSAYI_BIRIM_TL
    return DestekKalemi(
        ad="Organik arılı kovan desteği", katsayi=ORGANIK_ARILI_KOVAN_KATSAYI,
        dekar_basi_tl=round(birim, 2),
        toplam_tl=round(birim * kovan_sayisi, 2),
        not_="Kovan başına ödenir (dekar başına değil).",
    )
