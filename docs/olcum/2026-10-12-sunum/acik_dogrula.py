"""Arayüz simülasyonunda açık kalan dört maddenin tarayıcıda doğrulanması (2026-10-12).

  1 Profil formunda finansman / dijitalleşme / makine hedefleri (e-ticaret profilinde de) seçilebiliyor.
  2 Rekortiv: hazırlık kartında BiGG sıra uyarısı var, e-ihracat konsorsiyum notu yok.
  3 Evcil hayvan (istihdam hedefi): hazırlık adımlarında DYS / ihracatçı birliği / Madrid yok.
  4 Bebek tekstili: yanıtta öne çıkan program kayıt listesinin başında işaretli; düğmesi o programın kontrol
    listesini açıyor.
Mevcut sunum test hesaplarıyla (ekran_akisi.py) çalışır; ekran görüntüleri data/sunum_ekran/_dogrula/.

    python docs/olcum/2026-10-12-sunum/acik_dogrula.py --self-test
    python docs/olcum/2026-10-12-sunum/acik_dogrula.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ekran_akisi as ea  # noqa: E402

CIKTI = ea.CIKTI / "_dogrula"


def giris(c, anahtar: str) -> None:
    eposta = f"sunum.{anahtar.replace('_', '.')}@example.com"
    parola = ea.hesaplar()[eposta]
    kod, d = ea._istek("/api/auth/login", {"email": eposta, "password": parola})
    assert kod == 200, (anahtar, kod)
    c.git(f"{ea.URL}/")
    c.js(f"localStorage.setItem('auth_token', {json.dumps(d['access_token'])}); "
         f"localStorage.setItem('token', {json.dumps(d['access_token'])})")
    c.git(f"{ea.URL}/dashboard")
    c.bekle("document.querySelector('#ozet-icerik .loading') === null", aciklama="panel")


def kontroller(c) -> list[tuple[str, bool]]:
    sonuc = []
    # 1 hedef kutuları (e-ticaret profili)
    giris(c, "ikas_pet")
    ea.bolum(c, "profil")
    gorunen = c.js("""[...document.querySelectorAll('.p-hedef')].filter(k => k.offsetParent !== null)
        .map(k => k.value)""")
    sonuc.append(("e-ticaret profilinde finansman, dijital, makine seçilebiliyor",
                   {"finansman", "dijital", "makine"} <= set(gorunen)))
    c.cek("#profil-form", CIKTI / "hedefler.png", 500)
    # 3 evcil hayvan hazırlık adımları
    ea.bolum(c, "destekler")
    c.bekle("getComputedStyle(document.getElementById('hazirlik-section')).display !== 'none'", 20, "hazırlık")
    metin = c.js("document.getElementById('hazirlik-adimlar').innerText")
    sonuc.append(("istihdam hedefli mağazada e-ihracat adımı yok",
                  not any(x in metin for x in ("DYS", "İhracatçı birliği", "Madrid"))))
    # 2 Rekortiv uyarısı
    giris(c, "rekortiv")
    ea.bolum(c, "destekler")
    c.bekle("getComputedStyle(document.getElementById('hazirlik-section')).display !== 'none'", 20, "hazırlık")
    metin = c.js("document.getElementById('hazirlik-adimlar').innerText")
    sonuc.append(("Rekortiv hazırlık kartında BiGG sıra uyarısı", "kabulden sonra kurun" in metin and "1812" in metin))
    sonuc.append(("Rekortiv hazırlık kartında konsorsiyum notu yok", "Konsorsiyum" not in metin))
    c.cek("#hazirlik-section", CIKTI / "rekortiv_hazirlik.png", 600)
    # 4 bebek: yanıtta öne çıkan → kontrol listesi
    giris(c, "ikas_bebek")
    ea.bolum(c, "search")
    c.js(f"""(() => {{ const e = document.getElementById('search-input'); e.value = {json.dumps(ea.PERSONA['ikas_bebek']['soru'])};
        document.querySelector('[data-tikla="performSearch"]').click(); }})()""")
    c.bekle("document.getElementById('ai-durum') && document.getElementById('ai-durum').textContent === ''", 90, "yanıt")
    time.sleep(0.5)
    ilk = c.js("""(() => { const k = document.querySelector('#kayit-listesi .result-card');
        return k ? [k.innerText.slice(0, 200), k.dataset.kayitBaslik] : null; })()""")
    sonuc.append(("öne çıkan program kayıt listesinin başında işaretli",
                  bool(ilk) and "YANITTA ÖNE ÇIKAN PROGRAM" in ilk[0].upper()))   # etiket CSS ile büyük harf
    c.cek("#kayit-listesi", CIKTI / "bebek_kayit_listesi.png", 700)
    c.js("document.querySelector('#kayit-listesi .result-card [data-tikla=\"kontrolListesiAc\"]').click()")
    c.bekle("!document.getElementById('basvurular').classList.contains('hidden') && "
            "document.querySelector('[data-tikla=\"sihirbazAc\"]')", 40, "kontrol listesi")
    time.sleep(0.8)
    acilan = c.js("document.querySelector('#basvurular').innerText")
    sonuc.append(("düğme yanıttaki programın listesini açıyor", bool(ilk) and ilk[1] in acilan))
    c.cek("#basvurular", CIKTI / "bebek_kontrol_listesi.png", 900)
    return sonuc


def _self_test() -> int:
    k = [("doğrulama klasörü sunum ekranları altında", CIKTI.parent == ea.CIKTI),
         ("persona sorusu tanımlı", bool(ea.PERSONA["ikas_bebek"]["soru"]))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    CIKTI.mkdir(parents=True, exist_ok=True)
    proc, c = ea.chrome_ac()
    try:
        c("Page.enable")
        c("Emulation.setDeviceMetricsOverride", width=ea.GENISLIK, height=ea.YUKSEKLIK, deviceScaleFactor=ea.OLCEK,
          mobile=False)
        sonuc = kontroller(c)
    finally:
        proc.kill()
    for ad, ok in sonuc:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in sonuc)
    print(f"\ndoğrulama: {g}/{len(sonuc)} geçti")
    sys.exit(0 if g == len(sonuc) else 1)
