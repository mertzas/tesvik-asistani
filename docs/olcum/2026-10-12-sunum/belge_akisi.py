"""Belge hazırlama adımının arayüzde kaydı: 13 sunum hesabında kontrol listesindeki belgeleri hazır işaretleme,
Yazdır/PDF görünümü ve Word (.docx) çıktısı (2026-10-12).

Her hesapta açık olan ilk kontrol listesi kullanılır (ekran_akisi.py'nin açtığı liste). "Hazırlanacak belgeler"
maddeleri tek tek işaretlenir (her tıklama kaydedip listeyi yeniden çizer); belge bölümü yoksa liste olduğu gibi
alınır. Word dosyası API'den (GET /api/basvuru-listesi/{id}/docx) indirilir; WORD_HESAPLARI için makinedeki
Microsoft Word ile HTML'e çevrilip görüntülenir (dosyanın kendi görünümü). Çıktılar data/sunum_ekran/<persona>/.

    python docs/olcum/2026-10-12-sunum/belge_akisi.py --self-test
    python docs/olcum/2026-10-12-sunum/belge_akisi.py
"""
import base64
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ekran_akisi as ea  # noqa: E402

WORD_HESAPLARI = ("rekortiv", "findik", "ikas_giyim")
YAZDIR_HESAPLARI = ("rekortiv", "cilek", "ikas_evtekstil")


def belirtec(anahtar: str) -> str:
    eposta = f"sunum.{anahtar.replace('_', '.')}@example.com"
    kod, d = ea._istek("/api/auth/login", {"email": eposta, "password": ea.hesaplar()[eposta]})
    assert kod == 200, (anahtar, kod)
    return d["access_token"]


def api(yol: str, t: str) -> bytes:
    r = urllib.request.Request(f"{ea.URL}{yol}", headers={"Authorization": f"Bearer {t}"})
    with urllib.request.urlopen(r) as y:
        return y.read()


def birlesik_kutu(c, seciciler: list[str]) -> dict | None:
    """Verilen öğelerin (var olanların) birleşik sayfa kutusu."""
    return c.js(f"""(() => {{ const r = {json.dumps(seciciler)}.map(s => document.querySelector(s)).filter(Boolean)
        .map(e => e.getBoundingClientRect()); if (!r.length) return null;
        const x = Math.min(...r.map(k => k.left)), y = Math.min(...r.map(k => k.top));
        return {{x: x + scrollX, y: y + scrollY, w: Math.max(...r.map(k => k.right)) - x,
                h: Math.max(...r.map(k => k.bottom)) - y}}; }})()""")


def cek_kutu(c, kutu: dict, dosya: Path, en_cok: int = 1500) -> Path:
    veri = c("Page.captureScreenshot", format="png", captureBeyondViewport=True,
             clip=ea.kirpma(kutu, en_cok, 0))["data"]
    dosya.write_bytes(base64.b64decode(veri))
    return dosya


def word_html(docx: Path) -> Path:
    """Microsoft Word (COM) ile süzülmüş HTML'e çevirir (wdFormatFilteredHTML = 10)."""
    html = docx.with_suffix(".html")
    betik = (f"$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0; "
             f"try {{ $d = $w.Documents.Open('{docx}', $false, $true); $d.SaveAs2('{html}', 10); $d.Close($false) }} "
             f"finally {{ $w.Quit() }}")
    subprocess.run(["powershell", "-NoProfile", "-Command", betik], check=True, capture_output=True, timeout=180)
    return html


def persona(c, anahtar: str) -> dict:
    d = ea.CIKTI / anahtar
    t = belirtec(anahtar)
    tid = json.loads(api("/api/basvuru-listesi", t))["listeler"][0]["tesvik_id"]
    c.git(f"{ea.URL}/")
    c.js(f"localStorage.setItem('auth_token', {json.dumps(t)}); localStorage.setItem('token', {json.dumps(t)})")
    c.git(f"{ea.URL}/dashboard")
    c.bekle("document.querySelector('#ozet-icerik .loading') === null", aciklama="panel")
    ea.bolum(c, "basvurular")
    c.bekle(f"document.querySelector('[data-tikla=\"kontrolListesiAc\"][data-arg=\"{tid}\"]')", 30, "liste düğmesi")
    c.js(f"document.querySelector('[data-tikla=\"kontrolListesiAc\"][data-arg=\"{tid}\"]').click()")
    c.bekle("document.getElementById('kl-sayac')", 30, "kontrol listesi")
    time.sleep(0.8)
    once = c.js("document.getElementById('kl-sayac').textContent")
    isaretlenen = 0
    for _ in range(12):   # belgeleri tek tek "hazır" işaretle
        tik = c.js("""(() => { const k = [...document.querySelectorAll('.kl-bolum-belge input[type=checkbox]')]
            .find(x => !x.disabled && !x.checked); if (!k) return false; k.click(); return true; })()""")
        if not tik:
            break
        isaretlenen += 1
        time.sleep(1.2)
    sonra = c.js("document.getElementById('kl-sayac').textContent")
    belge_var = c.js("!!document.querySelector('.kl-bolum-belge')")
    # Kutu: genişlik içerik kartından (kenar menüsü dışarıda), boy liste başlığından belge/adım bölümünün sonuna.
    kutu = c.js("""(() => { const kart = document.querySelector('#basvurular .search-section') ||
            document.getElementById('basvurular');
        const ust = document.querySelector('#basvurular .kl-ust');
        const alt = [...document.querySelectorAll('.kl-bolum-belge, .kl-bolum-adim')].pop() || ust;
        const k = kart.getBoundingClientRect(), u = ust.getBoundingClientRect(), a = alt.getBoundingClientRect();
        return {x: k.left + scrollX, y: u.top + scrollY, w: k.width, h: a.bottom - u.top}; })()""")
    cek_kutu(c, kutu, d / "12_belgeler.png", 1600)
    sonuc = {"tesvik_id": tid, "sayac_once": once, "sayac_sonra": sonra, "isaretlenen_belge": isaretlenen,
             "belge_bolumu": belge_var}
    if anahtar in YAZDIR_HESAPLARI:
        c.js("window.print = () => {}; document.querySelector('[data-tikla=\"kontrolListesiYazdir\"]').click()")
        time.sleep(0.5)
        c("Emulation.setEmulatedMedia", media="print")
        time.sleep(0.5)
        kutu = birlesik_kutu(c, ["#yazdir-alani"])
        cek_kutu(c, kutu, d / "13_yazdir.png", 2200)
        c("Emulation.setEmulatedMedia", media="")
        sonuc["yazdir"] = True
    docx = d / "basvuru.docx"
    docx.write_bytes(api(f"/api/basvuru-listesi/{tid}/docx", t))
    sonuc["docx_bayt"] = docx.stat().st_size
    if anahtar in WORD_HESAPLARI:
        html = word_html(docx)
        c.git(html.as_uri())
        time.sleep(0.6)
        cek_kutu(c, birlesik_kutu(c, ["body"]), d / "14_word.png", 2200)
        sonuc["word"] = True
    return sonuc


def _self_test() -> int:
    k = [("Word ve yazdır hesapları persona listesinde", set(WORD_HESAPLARI + YAZDIR_HESAPLARI) <= set(ea.PERSONA)),
         ("çıktı klasörü sunum ekranları", ea.CIKTI.name == "sunum_ekran")]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    secilen = [a for a in sys.argv[1:] if a in ea.PERSONA] or list(ea.PERSONA)
    proc, c = ea.chrome_ac()
    ozet = {}
    try:
        c("Page.enable")
        c("Emulation.setDeviceMetricsOverride", width=ea.GENISLIK, height=ea.YUKSEKLIK, deviceScaleFactor=ea.OLCEK,
          mobile=False)
        for a in secilen:
            try:
                ozet[a] = persona(c, a)
                print(f"[{a}] {ozet[a]}")
            except Exception as hata:
                ozet[a] = {"hata": str(hata)}
                print(f"[{a}] HATA: {hata}")
    finally:
        proc.kill()
    (ea.CIKTI / "belge_ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
