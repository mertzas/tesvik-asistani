"""Denetim 2 / Aşama D — dayanıklılık deneyleri (gerçek süreç, GERÇEK Claude ÇAĞRISI YOK, ücretsiz).

Üretim DB'sine dokunmaz: data/tesvikler.db geçici bir kopyaya alınır, uvicorn :8001'de o kopyayla ve
SAHTE bir Anthropic sunucusuna (127.0.0.1:8765) bağlı başlatılır. Hiçbir veri dış ağa gitmez.

  python D_dayaniklilik.py claude      -> sahte Claude: 500, 529, akış ortasında kopma (+ "hang" için --hang)
  python D_dayaniklilik.py dblock      -> SQLite kilidi altında /health, okuma, yazma
  python D_dayaniklilik.py redis       -> ölü REDIS_URL ile açılış, /health, giriş sınırı hâlâ çalışıyor mu
  python D_dayaniklilik.py kilit       -> iki gerçek süreçte scheduler_kilidi_al() (Windows'ta fcntl yok)

Çıktı: D_dayaniklilik.json (her koşu eklenir).
"""
import json, os, shutil, sqlite3, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PROJE = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import D_olcum as D  # noqa: E402

PORT = 8001
FAKE_PORT = 8765
MOD = {"m": "500"}
ISTEK_SAYISI = {"n": 0}


class Sahte(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        ISTEK_SAYISI["n"] += 1
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        m = MOD["m"]
        if m in ("500", "529"):
            body = json.dumps({"type": "error", "error": {"type": "api_error" if m == "500" else "overloaded_error", "message": "sahte " + m}}).encode()
            self.send_response(int(m)); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif m == "hang":
            time.sleep(400)
        elif m == "kopma":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Connection", "close"); self.end_headers()
            olaylar = [
                ("message_start", {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "model": "x", "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}}),
                ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "### 1. Şirket & Proje Uygunluk Özeti\nKısmi yanıt..."}}),
            ]
            for ad, veri in olaylar:
                self.wfile.write(f"event: {ad}\ndata: {json.dumps(veri, ensure_ascii=False)}\n\n".encode()); self.wfile.flush()
            time.sleep(0.3)
            self.connection.close()  # message_stop gelmeden kop


def sahte_baslat():
    s = ThreadingHTTPServer(("127.0.0.1", FAKE_PORT), Sahte)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def uvicorn_baslat(db_yolu, extra_env=None, port=PORT):
    env = dict(os.environ)
    env.update(DATABASE_URL=f"sqlite:///{db_yolu}", ANTHROPIC_API_KEY="sahte-anahtar", ANTHROPIC_BASE_URL=f"http://127.0.0.1:{FAKE_PORT}",
               SCHEDULER_ENABLED="false", PYTHONIOENCODING="utf-8", ALLOW_INSECURE_SECRET="1")
    env.update(extra_env or {})
    log = open(os.path.join(tempfile.gettempdir(), f"uvicorn_{port}.log"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=PROJE, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2); return p, log.name
        except Exception:
            time.sleep(0.5)
    p.kill(); raise SystemExit("uvicorn açılmadı: " + log.name)


def kopya_db():
    kaynak = os.path.join(PROJE, "data", "tesvikler.db")
    hedef = os.path.join(tempfile.gettempdir(), "tesvikler_dayaniklilik.db")
    s = sqlite3.connect(kaynak); d = sqlite3.connect(hedef); s.backup(d); d.close(); s.close()
    return hedef


def _get(yol, tok=None, timeout=60):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{yol}", headers={"Authorization": f"Bearer {tok}"} if tok else {})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, round(time.time() - t0, 2), r.read()[:160].decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, round(time.time() - t0, 2), e.read()[:160].decode("utf-8", "replace")
    except Exception as e:
        return f"EXC {type(e).__name__}", round(time.time() - t0, 2), str(e)[:100]


def akis_ayrintili(tok, soru="KOSGEB makine yatırımı desteği", timeout=420):
    """SSE olaylarını (ad, ilk 90 karakter, saniye) olarak döndürür."""
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/sor/akis", data=json.dumps({"question": soru}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
    t0 = time.time(); olaylar = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            buf = b""
            while True:
                c = r.read(1)
                if not c:
                    break
                buf += c
                while b"\n\n" in buf:
                    blok, buf = buf.split(b"\n\n", 1)
                    ad = ""; veri = ""
                    for sat in blok.decode("utf-8", "replace").split("\n"):
                        if sat.startswith("event:"): ad = sat[6:].strip()
                        elif sat.startswith("data:"): veri += sat[5:].strip()
                    olaylar.append((ad, veri[:90], round(time.time() - t0, 2)))
        return dict(durum=200, toplam_sn=round(time.time() - t0, 2), olaylar=olaylar)
    except Exception as e:
        return dict(durum=f"EXC {type(e).__name__}", toplam_sn=round(time.time() - t0, 2), olaylar=olaylar, hata=str(e)[:100])


def giris():
    D.BASE = f"http://127.0.0.1:{PORT}"
    tok = D._token()
    return tok


def claude(hang=False):
    sahte_baslat(); db = kopya_db(); p, log = uvicorn_baslat(db)
    sonuc = dict(tur="claude", senaryolar={})
    try:
        tok = giris(); assert D._riza(tok, True) is True
        modlar = ["500", "529", "kopma"] + (["hang"] if hang else [])
        for m in modlar:
            MOD["m"] = m; ISTEK_SAYISI["n"] = 0
            r = akis_ayrintili(tok)
            r["sahteye_giden_istek"] = ISTEK_SAYISI["n"]
            sonuc["senaryolar"][m] = r
            print(m, json.dumps({k: v for k, v in r.items() if k != "olaylar"}, ensure_ascii=False), [(a, v[:40], s) for a, v, s in r["olaylar"]][:6])
        sonuc["sunucu_gunlugu"] = open(log, encoding="utf-8").read()[-1500:]
    finally:
        p.kill()
    return sonuc


def dblock():
    db = kopya_db(); p, log = uvicorn_baslat(db)
    sonuc = dict(tur="dblock", adimlar={})
    try:
        tok = giris()
        sonuc["adimlar"]["once_health"] = _get("/health")[:2]
        sonuc["adimlar"]["once_profil"] = _get("/api/eslesme", tok)[:2]
        kilit = sqlite3.connect(db, timeout=0, isolation_level=None)
        kilit.execute("BEGIN EXCLUSIVE")
        t0 = time.time()
        try:
            sonuc["adimlar"]["kilitli_health"] = _get("/health")
            sonuc["adimlar"]["kilitli_eslesme_okuma"] = _get("/api/eslesme", tok)
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/sor/akis", data=json.dumps({"question": "test"}).encode(),
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
            t1 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    govde = r.read()[:200].decode("utf-8", "replace"); d = r.status
            except urllib.error.HTTPError as e:
                govde = e.read()[:200].decode("utf-8", "replace"); d = e.code
            except Exception as e:
                govde = str(e)[:100]; d = f"EXC {type(e).__name__}"
            sonuc["adimlar"]["kilitli_yazan_akis"] = (d, round(time.time() - t1, 2), govde)
        finally:
            kilit.execute("ROLLBACK"); kilit.close()
        sonuc["kilit_suresi_sn"] = round(time.time() - t0, 1)
        sonuc["adimlar"]["sonra_health"] = _get("/health")[:2]
        sonuc["adimlar"]["sonra_eslesme"] = _get("/api/eslesme", tok)[:2]
        sonuc["sunucu_gunlugu"] = open(log, encoding="utf-8").read()[-1200:]
        for k, v in sonuc["adimlar"].items():
            print(k, v)
    finally:
        p.kill()
    return sonuc


def redis_olu():
    db = kopya_db(); p, log = uvicorn_baslat(db, {"REDIS_URL": "redis://127.0.0.1:6399/0"})
    sonuc = dict(tur="redis_olu")
    try:
        sonuc["health"] = json.loads(_get("/health")[2] or "{}") if _get("/health")[0] == 200 else _get("/health")
        # giriş sınırı hâlâ çalışıyor mu? (süreç içi sayaca düşmüş olmalı: 10/dk)
        kodlar = []
        for i in range(13):
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/auth/login", data=json.dumps({"email": "yok@example.com", "password": "yanlis123"}).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=10); kodlar.append(200)
            except urllib.error.HTTPError as e:
                kodlar.append(e.code)
        sonuc["login_kodlari"] = kodlar
        sonuc["sunucu_gunlugu"] = [l for l in open(log, encoding="utf-8").read().splitlines() if "Redis" in l or "REDIS" in l][:3]
        print(sonuc)
    finally:
        p.kill()
    return sonuc


def yuk():
    """30 sn, 5 iş parçacığı, kimliksiz uç noktalar + eşzamanlı 5 yetkili /api/eslesme (üretim DB'sinin kopyası)."""
    db = kopya_db(); p, log = uvicorn_baslat(db)
    sonuc = dict(tur="yuk")
    try:
        tok = giris()
        for yol in ("/health", "/api/kobi-sinifi?calisan=12&ciro=20000000", "/api/nace/ara?q=ekmek"):
            sonuc.setdefault("on_kontrol", {})[yol.split("?")[0]] = _get(yol)[:2]
        sonuc["yuk"] = D.yuk(30, 5)
        sonlar = [None] * 5
        def g(i):
            sonlar[i] = _get("/api/eslesme", tok, timeout=120)[:2]
        th = [threading.Thread(target=g, args=(i,)) for i in range(5)]
        t0 = time.time(); [t.start() for t in th]; [t.join() for t in th]
        sonuc["eszamanli_eslesme"] = dict(duvar_sn=round(time.time() - t0, 2), sonuclar=sonlar)
        print(json.dumps(sonuc, ensure_ascii=False)[:2500])
    finally:
        p.kill()
    return sonuc


def kilit():
    kod = "import sys,time; sys.path.insert(0,r'%s'); from app.scheduler import scheduler_kilidi_al; print(scheduler_kilidi_al(), flush=True); time.sleep(3)" % PROJE
    ps = [subprocess.Popen([sys.executable, "-c", kod], cwd=PROJE, stdout=subprocess.PIPE, text=True, env=dict(os.environ, PYTHONIOENCODING="utf-8")) for _ in range(2)]
    cikti = [p.communicate()[0].strip().splitlines()[-1] for p in ps]
    try:
        import fcntl  # noqa: F401
        fcntl_var = True
    except ImportError:
        fcntl_var = False
    r = dict(tur="kilit", fcntl_var=fcntl_var, iki_surec_sonucu=cikti)
    print(r)
    return r


if __name__ == "__main__":
    mod = sys.argv[1]
    r = {"claude": lambda: claude("--hang" in sys.argv), "dblock": dblock, "redis": redis_olu, "kilit": kilit, "yuk": yuk}[mod]()
    r["zaman"] = time.strftime("%Y-%m-%d %H:%M:%S")
    yol = os.path.join(HERE, "D_dayaniklilik.json")
    eski = json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else []
    eski.append(r); json.dump(eski, open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
