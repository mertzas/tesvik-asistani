"""CSP sıkılaştırması (2026-10-08): script-src yalnızca 'self'. Satır içi betik/olay özniteliği ve dış betik kalmamalı;
data-* eylemleri sayfanın betiğindeki EYLEMLER listesinde tanımlı olmalı; çilek panelinin derlenmiş Tailwind CSS'i
sayfadaki her sınıfı içermeli (derleme unutulursa kırmızı)."""
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
SAYFALAR = sorted(STATIC.glob("*.html"))
BETIKLER = sorted((STATIC / "js").glob("*.js"))
# sayfa -> olay dinleyicisi taşıyan betik
EYLEM_BETIGI = {"index.html": "giris.js", "dashboard.html": "panel.js", "cilek_dashboard.html": "cilek.js"}
OLAY_OZNITELIGI = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
EYLEM = re.compile(r'data-(tikla|degisim|gonder)="([^"$]+)"')


def test_csp_script_src_yalniz_self():
    from app.main import CSP
    yonergeler = dict(y.split(" ", 1) for y in CSP.split("; "))
    assert yonergeler["script-src"] == "'self'"
    assert "https://" not in CSP and "unsafe-eval" not in CSP


def test_sunulan_sayfalar_sikilastirilmis_csp_tasir(client):
    for yol in ("/", "/dashboard", "/cilek-paneli", "/sifre-sifirla", "/eposta-dogrula", "/kvkk"):
        r = client.get(yol)
        assert r.status_code == 200, yol
        assert "script-src 'self';" in r.headers["Content-Security-Policy"], yol


def test_statik_betik_ve_sayfa_her_acilista_dogrulanir(client):
    """Betikler sürüm numarasız: no-cache olmadan güncellemeden sonra tarayıcı eski betiği çalıştırıyordu."""
    for yol in ("/static/js/panel.js", "/static/css/cilek.css", "/dashboard"):
        assert client.get(yol).headers.get("cache-control") == "no-cache", yol
    r = client.get("/static/js/panel.js")
    assert client.get("/static/js/panel.js", headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    assert "cache-control" not in client.get("/health").headers


@pytest.mark.parametrize("sayfa", SAYFALAR, ids=lambda p: p.name)
def test_sayfada_satir_ici_betik_ve_olay_ozniteligi_yok(sayfa):
    html = sayfa.read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "satır içi <script> (CSP engeller)"
    assert not OLAY_OZNITELIGI.search(html), "onclick/onsubmit gibi öznitelik (CSP engeller)"
    for src in re.findall(r'<script[^>]*\bsrc="([^"]+)"', html):
        assert src.startswith("/static/js/"), f"dış betik: {src}"
        assert (STATIC / src.removeprefix("/static/")).exists(), f"betik dosyası yok: {src}"
    assert "javascript:" not in html


@pytest.mark.parametrize("betik", BETIKLER, ids=lambda p: p.name)
def test_betikte_html_olay_ozniteligi_uretilmez(betik):
    """innerHTML ile basılan şablonlarda onclick="..." de CSP'ye takılır."""
    js = betik.read_text(encoding="utf-8")
    assert not re.search(r"<[a-z][^<>]*\son[a-z]+\s*=", js, re.IGNORECASE)


@pytest.mark.parametrize("sayfa,betik", EYLEM_BETIGI.items())
def test_her_eylem_betikte_tanimli(sayfa, betik):
    js = (STATIC / "js" / betik).read_text(encoding="utf-8")
    blok = re.search(r"const EYLEMLER = \{(.*?)\n\s*\};", js, re.S)
    assert blok, "EYLEMLER listesi yok"
    tanimli = set(re.findall(r"^\s*(\w+):", blok.group(1), re.M))
    kullanilan = {ad for _, ad in EYLEM.findall((STATIC / sayfa).read_text(encoding="utf-8") + js)}
    assert kullanilan, "sayfada hiç data-* eylemi yok (beklenmiyor)"
    assert kullanilan <= tanimli, f"tanımsız eylem: {kullanilan - tanimli}"
    turler = {tur for tur, _ in EYLEM.findall((STATIC / sayfa).read_text(encoding="utf-8") + js)}
    for tur in turler:
        assert f'"data-{tur}"' in js or f"'data-{tur}'" in js, f"data-{tur} için dinleyici bağlanmamış"


def _css_kacis(sinif: str) -> str:
    return re.sub(r"([^A-Za-z0-9_-])", r"\\\1", sinif)


def test_cilek_tailwind_derlemesi_guncel():
    html = (STATIC / "cilek_dashboard.html").read_text(encoding="utf-8")
    js = (STATIC / "js" / "cilek.js").read_text(encoding="utf-8")
    css = (STATIC / "css" / "cilek.css").read_text(encoding="utf-8")
    assert "cdn.tailwindcss.com" not in html and '/static/css/cilek.css' in html
    stil_blogu = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    ozel = set(re.findall(r"\.([A-Za-z_][\w-]*)", stil_blogu))
    siniflar = set()
    for deger in re.findall(r'class="([^"]*)"', html + js):
        siniflar |= {s for s in deger.split() if not re.search(r"[${}]", s)}
    siniflar |= set(re.findall(r"classList\.(?:add|remove|toggle)\('([\w-]+)'\)", js))
    eksik = sorted(s for s in siniflar if s not in ozel and "." + _css_kacis(s) not in css)
    assert len(siniflar) > 50
    assert not eksik, (f"derlenmiş CSS'te olmayan sınıflar: {eksik[:15]} — tools/tailwind/tailwind.config.js "
                       f"içindeki komutla yeniden derleyin")
