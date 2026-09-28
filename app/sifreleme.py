"""
Veritabanında saklanan gizli değerler için saydam şifreleme.

NEDEN
-----
İKAS OAuth erişim ve yenileme anahtarları (`ikas_baglanti.access_token`,
`.refresh_token`) veritabanında AÇIK METİN olarak duruyordu. Bu anahtarlar
kullanıcının mağaza verisine erişim sağlar; veritabanı yedeğine erişen biri
onları doğrudan kullanabilir. KVKK aydınlatma metni yazılırken tespit edildi
(2026-09-27) ve DEPLOYMENT.md'de üretim engeli olarak listelendi.

TASARIM: SÜTUN DÜZEYİNDE, SAYDAM
--------------------------------
Şifreleme çağrı yerlerinde değil, SQLAlchemy sütun tipinde yapılıyor. Sebebi:
`app/ikas_panel.py` token'ı iki yerde yazıp iki yerde okuyor; her birinde elle
şifrele/çöz çağırmak, ileride eklenecek beşinci bir çağrı yerinde unutulmaya
açıktır. Sütun tipi kullanıldığında unutmak mümkün değil.

ANAHTAR
-------
Anahtar `IKAS_TOKEN_KEY` ortam değişkeninden okunur. Yoksa `SECRET_KEY`'den
türetilir (HKDF-benzeri sabit bir bilgi dizesiyle) - böylece yeni bir ortam
değişkeni zorunlu olmadan şifreleme devreye girer, ama isteyen ayrı anahtar
kullanabilir.

DİKKAT: `SECRET_KEY` değişirse şifrelenmiş değerler ÇÖZÜLEMEZ. Bu durumda
İKAS bağlantısının yeniden kurulması gerekir (token'lar zaten süreli).
Ayrı bir `IKAS_TOKEN_KEY` kullanmak bu bağı koparır ve önerilen yoldur.

MEVCUT AÇIK METİN VERİ
----------------------
Veritabanında hâlihazırda şifresiz token'lar var. Çözme başarısız olursa
değer OLDUĞU GİBİ döner ve uyarı loglanır - böylece sürüm geçişi mevcut
bağlantıları koparmaz. `scripts/sifrele_mevcut_tokenlar.py` bunları
yerinde şifreler.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

logger = logging.getLogger(__name__)

# Turetme icin sabit bilgi dizesi. Degistirilirse mevcut sifreli degerler
# cozulemez hale gelir.
_TURETME_BILGISI = b"tesvik-asistani/ikas-token/v1"

_ONBELLEK: Fernet | None = None


def _anahtar() -> bytes:
    """Fernet anahtari (32 bayt, url-safe base64)."""
    acik = os.getenv("IKAS_TOKEN_KEY")
    if acik:
        # Kullanici dogrudan bir Fernet anahtari verdiyse oldugu gibi kullan;
        # degilse ondan turet (yanlis uzunlukta anahtar Fernet'i patlatir).
        try:
            Fernet(acik.encode())
            return acik.encode()
        except (ValueError, TypeError):
            tohum = acik.encode()
    else:
        from app.models import settings
        tohum = (settings.SECRET_KEY or "").encode()
        if not tohum:
            raise RuntimeError(
                "Şifreleme anahtarı üretilemiyor: SECRET_KEY boş ve "
                "IKAS_TOKEN_KEY tanımlı değil.")
    ham = hashlib.sha256(tohum + _TURETME_BILGISI).digest()
    return base64.urlsafe_b64encode(ham)


def _fernet() -> Fernet:
    global _ONBELLEK
    if _ONBELLEK is None:
        _ONBELLEK = Fernet(_anahtar())
    return _ONBELLEK


def onbellegi_temizle() -> None:
    """Test icin: anahtar degistiginde onbellegi sifirlar."""
    global _ONBELLEK
    _ONBELLEK = None


# Sifreli degerlerin basina konan on ek. Bir degerin sifreli mi acik metin mi
# oldugunu ANLAMAK icin sart: on ek yoksa deger eski (sifresiz) kayittir ve
# cozmeye calismak gereksiz hata uretir.
ONEK = "enc:v1:"


def sifrele(deger: str | None) -> str | None:
    if deger is None:
        return None
    if deger.startswith(ONEK):
        return deger  # zaten sifreli, iki kez sifreleme
    return ONEK + _fernet().encrypt(deger.encode()).decode()


def coz(deger: str | None) -> str | None:
    if deger is None:
        return None
    if not deger.startswith(ONEK):
        # Eski, sifresiz kayit. Bozup uygulamayi kirmak yerine oldugu gibi
        # donuyoruz; scripts/sifrele_mevcut_tokenlar.py bunlari yerinde
        # sifreler.
        return deger
    try:
        return _fernet().decrypt(deger[len(ONEK):].encode()).decode()
    except InvalidToken:
        # Anahtar degismis olabilir (orn. SECRET_KEY donduruldu). Degeri
        # uydurmak yerine acikca bildiriyoruz: cagiran taraf baglantinin
        # yeniden kurulmasi gerektigini anlamali.
        logger.error(
            "Şifreli değer çözülemedi - şifreleme anahtarı değişmiş olabilir. "
            "İlgili İKAS bağlantısının yeniden kurulması gerekiyor.")
        return None


class SifreliMetin(TypeDecorator):
    """Veritabanına şifreli yazan, okurken çözen metin sütunu.

    Kullanım:
        access_token = Column(SifreliMetin, nullable=True)

    Uygulama kodu düz metin görür; diskte şifreli durur.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return sifrele(value)

    def process_result_value(self, value, dialect):
        return coz(value)
