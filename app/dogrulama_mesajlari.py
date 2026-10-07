"""422 doğrulama hatalarının Türkçe mesajları (2026-10-08).

FastAPI/pydantic varsayılanı İngilizce ("String should have at most 100 characters") ve kullanıcının gönderdiği
değeri yanıtta geri yansıtır ("input"): parola politikasına takılan parola yanıtta açık metin dönüyordu. Burada
yapı korunur (detail: [{loc, msg, type}]; ön yüzler msg'yi okur), msg Türkçeleşir, input/ctx/url atılır.

    python -m app.dogrulama_mesajlari --self-test
"""
from __future__ import annotations

import sys

# Alan adı -> kullanıcıya görünen etiket. Listede olmayan alan adı olduğu gibi kullanılır.
ETIKETLER = {
    "email": "E-posta", "password": "Parola", "new_password": "Yeni parola", "full_name": "Ad soyad",
    "company_name": "Şirket adı", "token": "Bağlantı", "question": "Soru", "onay": "Onay",
    "ad": "Ad", "ortam_tipi": "Ortam tipi", "alan_dekar": "Alan (dekar)", "cesit": "Çeşit",
    "dikim_tarihi": "Dikim tarihi", "isci_adi": "İşçi adı", "toplanan_kasa": "Toplanan kasa",
    "ilac_adi": "İlaç adı", "phi_gun": "Hasat bekleme süresi (gün)", "hedef": "Hedef", "tutar": "Tutar",
    "aciklama": "Açıklama", "kategori": "Kategori", "depo_adi": "Depo adı", "sicaklik": "Sıcaklık",
    "tarih": "Tarih", "fiyat_kg": "Kilogram fiyatı", "bolge": "Bölge", "sektor": "Sektör",
    "calisan_sayisi": "Çalışan sayısı", "yillik_ciro": "Yıllık ciro", "nace_kodu": "NACE kodu",
    "kurulus_tarihi": "Kuruluş tarihi", "hedefler": "Hedefler", "plan": "Plan",
}


def _etiket(loc) -> str:
    adlar = [p for p in (loc or ()) if isinstance(p, str) and p not in ("body", "query", "path", "header")]
    return ETIKETLER.get(adlar[-1], adlar[-1]) if adlar else "İstek"


def _mesaj(hata: dict) -> str:
    tip = hata.get("type", "")
    ctx = hata.get("ctx") or {}
    ham = str(hata.get("msg", ""))
    alan = _etiket(hata.get("loc"))
    if tip == "missing":
        return f"{alan} zorunlu."
    if tip == "string_too_short":
        n = ctx.get("min_length", 1)
        return f"{alan} boş bırakılamaz." if n == 1 else f"{alan} en az {n} karakter olmalı."
    if tip == "string_too_long":
        return f"{alan} en fazla {ctx.get('max_length')} karakter olabilir."
    if tip in ("too_short", "too_long"):
        sinir = ctx.get("min_length") if tip == "too_short" else ctx.get("max_length")
        return f"{alan} en {'az' if tip == 'too_short' else 'fazla'} {sinir} öğe içermeli."
    if tip == "literal_error" or tip == "enum":
        return f"{alan} için geçerli değerler: {str(ctx.get('expected', '')).replace(' or ', ' veya ')}."
    if tip == "string_pattern_mismatch":
        return f"{alan} biçimi geçersiz."
    if tip in ("int_parsing", "int_type", "float_parsing", "float_type", "int_from_float"):
        return f"{alan} bir sayı olmalı."
    if tip in ("greater_than_equal", "greater_than"):
        return f"{alan} en az {ctx.get('ge', ctx.get('gt'))} olmalı." if tip.endswith("equal") \
            else f"{alan} {ctx.get('gt')} değerinden büyük olmalı."
    if tip in ("less_than_equal", "less_than"):
        return f"{alan} en çok {ctx.get('le', ctx.get('lt'))} olabilir." if tip.endswith("equal") \
            else f"{alan} {ctx.get('lt')} değerinden küçük olmalı."
    if tip.startswith(("date_", "datetime_")):
        return f"{alan} geçerli bir tarih olmalı."
    if tip.startswith("bool_"):
        return f"{alan} doğru/yanlış olmalı."
    if tip in ("json_invalid", "model_attributes_type", "dict_type", "model_type"):
        return "İstek gövdesi geçersiz."
    if tip == "value_error":
        if "email address" in ham:
            return "Geçerli bir e-posta adresi girin."
        metin = ham.removeprefix("Value error, ")  # uygulamanın kendi doğrulayıcıları zaten Türkçe
        return metin if metin.endswith((".", "!", "?")) else metin + "."
    return f"{alan} geçersiz."


def turkce_hatalar(hatalar) -> list[dict]:
    """pydantic hata listesi -> [{loc, msg, type}] (input/ctx/url atılır: kullanıcı verisi yansıtılmaz)."""
    return [{"loc": list(h.get("loc", ())), "msg": _mesaj(h), "type": h.get("type", "")} for h in hatalar]


def _self_test() -> int:
    vakalar = [
        ({"type": "missing", "loc": ("body", "email"), "msg": "Field required"}, "E-posta zorunlu."),
        ({"type": "string_too_long", "loc": ("body", "ad"), "ctx": {"max_length": 100}}, "Ad en fazla 100 karakter olabilir."),
        ({"type": "string_too_short", "loc": ("body", "ad"), "ctx": {"min_length": 1}}, "Ad boş bırakılamaz."),
        ({"type": "string_too_short", "loc": ("body", "token"), "ctx": {"min_length": 10}}, "Bağlantı en az 10 karakter olmalı."),
        ({"type": "literal_error", "loc": ("body", "ortam_tipi"), "ctx": {"expected": "'sera' or 'acik_tarla'"}},
         "Ortam tipi için geçerli değerler: 'sera' veya 'acik_tarla'."),
        ({"type": "value_error", "loc": ("body", "email"), "msg": "value is not a valid email address: x"},
         "Geçerli bir e-posta adresi girin."),
        ({"type": "value_error", "loc": ("body", "password"), "msg": "Value error, Parola en az 8 karakter olmalı"},
         "Parola en az 8 karakter olmalı."),
        ({"type": "float_parsing", "loc": ("body", "tutar")}, "Tutar bir sayı olmalı."),
        ({"type": "greater_than_equal", "loc": ("query", "yil"), "ctx": {"ge": 2020}}, "yil en az 2020 olmalı."),
        ({"type": "date_from_datetime_parsing", "loc": ("body", "tarih")}, "Tarih geçerli bir tarih olmalı."),
        ({"type": "bilinmeyen_tur", "loc": ("body", "x")}, "x geçersiz."),
    ]
    gecen = 0
    for girdi, beklenen in vakalar:
        ok = _mesaj(girdi) == beklenen
        gecen += ok
        print(f"  {'OK ' if ok else 'HATA'} {girdi['type']:28} -> {_mesaj(girdi)}")
    temiz = turkce_hatalar([{"type": "missing", "loc": ("body", "password"), "input": "gizliParola1",
                             "ctx": {}, "url": "u", "msg": "m"}])
    ok = "gizliParola1" not in str(temiz) and set(temiz[0]) == {"loc", "msg", "type"}
    gecen += ok
    print(f"  {'OK ' if ok else 'HATA'} input/ctx/url yanıttan atılır")
    print(f"\nself-test: {gecen}/{len(vakalar) + 1} geçti")
    return 0 if gecen == len(vakalar) + 1 else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
