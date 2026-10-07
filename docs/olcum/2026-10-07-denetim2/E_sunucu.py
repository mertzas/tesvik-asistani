"""Aşama E tarayıcı doğrulaması için: üretim DB'sinin KOPYASIYLA :8001'de uvicorn (Claude anahtarı sahte, zamanlayıcı kapalı).
Bloklar; Ctrl+C / süreç sonlandırma ile kapanır. Ayrıca XSS yükü içeren bir parsel ve bir JWT üretir (E_token.txt, git dışı)."""
import json, os, subprocess, sys, tempfile, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import D_dayaniklilik as DD  # noqa: E402
import D_olcum as D  # noqa: E402

db = DD.kopya_db()
p, log = DD.uvicorn_baslat(db)
D.BASE = f"http://127.0.0.1:{DD.PORT}"
tok = D._token()
istek = urllib.request.Request(D.BASE + "/api/cilek/parseller", data=json.dumps({"ad": "<img src=x onerror=\"window.__xss=1\">Parsel-A", "alan_dekar": 5}).encode(),
                               headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
try:
    urllib.request.urlopen(istek, timeout=20).read()
except Exception as e:
    print("parsel olusturulamadi", e)
open(os.path.join(tempfile.gettempdir(), "E_token.txt"), "w").write(tok)
print("hazir", flush=True)
p.wait()
