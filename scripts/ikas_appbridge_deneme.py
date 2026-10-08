"""Yerel AppBridge denemesi: İKAS yönetim panelini taklit eden bir sayfa üretir. Sayfa Next.js kabuğunu (ikas-app/)
iframe içinde açar ve kabuğun AppBridge REQUEST_TOKEN iletisine, İKAS'ın vereceği biçimde (HS256, sub=merchantId,
aud=authorizedAppId) mock sırla imzalı bir JWT ile yanıt verir. Yalnız MOCK modda çalışır (gerçek sırla belirteç
üretmez).

Kullanım (ayrıntı: ikas-app/README.md "Yerel deneme"):
    python scripts/ikas_appbridge_deneme.py --magaza kabuk-magaza --kabuk http://localhost:3001 --cikti DIZIN
    python -m http.server 3002 --directory DIZIN
    python scripts/ikas_appbridge_deneme.py --self-test
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ikas_integration import _mock_mu, appbridge_belirteci_dogrula, appbridge_belirteci_uret, uygulama_siri  # noqa: E402

SABLON = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><title>AppBridge deneme (İKAS paneli taklidi)</title>
<style>
body{font-family:system-ui;margin:0;display:grid;grid-template-rows:auto 1fr auto;height:100vh}
header{padding:8px 12px;background:#222;color:#fff;font-size:13px}
iframe{border:0;width:100%;height:100%}
#log{font:12px monospace;max-height:120px;overflow:auto;background:#f3f3f3;padding:6px 12px}
</style></head>
<body>
<header>YEREL DENEME: İKAS yönetim panelini taklit eder (mağaza: __MAGAZA__). Gerçek İKAS değildir.</header>
<iframe id="uyg" src="__KABUK__/"></iframe>
<div id="log"></div>
<script>
const KABUK = __KABUK_JSON__;
const JWT = __JWT_JSON__;
const APP_ID = __APP_ID_JSON__;
const log = (m) => { document.getElementById('log').textContent += m + ' | '; };
window.addEventListener('message', (e) => {
  if (e.origin !== KABUK) return;
  const t = e.data && e.data.type;
  log('uygulamadan: ' + t);
  if (t === 'REQUEST_TOKEN') e.source.postMessage({type: 'REQUEST_TOKEN_RESPONSE', data: {token: JWT}}, e.origin);
  if (t === 'AUTHORIZED_APP_ID') e.source.postMessage({type: 'AUTHORIZED_APP_ID_RESPONSE', data: {authorizedAppId: APP_ID}}, e.origin);
});
</script>
</body></html>
"""


def sayfa_uret(magaza: str, kabuk: str) -> str:
    if not _mock_mu():
        raise SystemExit("Yalnız mock modda çalışır (IKAS_MOCK_MODE=true ya da IKAS_CLIENT_ID boş).")
    kabuk = kabuk.rstrip("/")
    app_id, merchant_id = f"mock-app-{magaza}", f"mock-merchant-{magaza}"
    jwt = appbridge_belirteci_uret(merchant_id, app_id, uygulama_siri())
    return (SABLON.replace("__MAGAZA__", html.escape(magaza)).replace("__KABUK__", html.escape(kabuk))
            .replace("__KABUK_JSON__", json.dumps(kabuk)).replace("__JWT_JSON__", json.dumps(jwt))
            .replace("__APP_ID_JSON__", json.dumps(app_id)))


def _self_test() -> int:
    sayfa = sayfa_uret("deneme", "http://localhost:3001/")
    kontroller = [
        ("iframe kabuğu açar", '<iframe id="uyg" src="http://localhost:3001/">' in sayfa),
        ("köken denetimi var", 'const KABUK = "http://localhost:3001";' in sayfa),
        ("JWT FastAPI doğrulamasından geçer", appbridge_belirteci_dogrula(
            json.loads(sayfa.split("const JWT = ")[1].split(";")[0]), uygulama_siri())
         == {"merchant_id": "mock-merchant-deneme", "authorized_app_id": "mock-app-deneme"}),
        ("betik satırları kırılmamış", "' | '" in sayfa and "+ '\n'" not in sayfa),
    ]
    for ad, ok in kontroller:
        print(("  ✓ " if ok else "  ✗ ") + ad)
    gecen = sum(ok for _, ok in kontroller)
    print(f"self-test: {gecen}/{len(kontroller)} geçti")
    return 0 if gecen == len(kontroller) else 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--magaza", default="kabuk-magaza", help="kurulumu yapılmış mağaza adı (mock)")
    p.add_argument("--kabuk", default="http://localhost:3001", help="Next.js kabuğunun adresi")
    p.add_argument("--cikti", type=Path, help="index.html'in yazılacağı dizin")
    a = p.parse_args()
    if a.self_test:
        return _self_test()
    if not a.cikti:
        p.error("--cikti gerekli")
    a.cikti.mkdir(parents=True, exist_ok=True)
    (a.cikti / "index.html").write_text(sayfa_uret(a.magaza, a.kabuk), encoding="utf-8")
    print(f"Yazıldı: {a.cikti / 'index.html'} (JWT 4 saat geçerli)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
