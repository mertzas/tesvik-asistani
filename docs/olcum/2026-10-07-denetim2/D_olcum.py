"""Denetim 2 / Aşama D — performans ve dayanıklılık (çalışan sunucuya karşı, 127.0.0.1:8000).

  python D_olcum.py eszamanli          -> test hesabıyla (rıza KAPALI, ücretsiz) 5 eşzamanlı /api/sor/akis
  python D_olcum.py akis N             -> rıza AÇIK, N gerçek çağrı: ilk parça süresi / toplam süre (ÜCRETLİ)
                                          (rızayı açar, ölçer, sonunda KAPATIR)
  python D_olcum.py yuk                -> 30 sn boyunca kimliksiz uç noktalara (health, kobi-sinifi, nace/ara)
                                          5 iş parçacığıyla istek; gecikme/hata oranı; IP hız sınırı (429) gözlemi

Çıktı: D_ozet.json (her koşu eklenir).
"""
import json, os, re, sys, threading, time, urllib.request, urllib.error

OUT = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:8000"
PROJE = os.path.abspath(os.path.join(OUT, "..", "..", ".."))


def _token():
    sifre = re.search(r'TEST_SIFRE = "([^"]+)"', open(os.path.join(PROJE, "scripts", "seed_test_hesabi.py"), encoding="utf-8").read()).group(1)
    req = urllib.request.Request(BASE + "/api/auth/login", data=json.dumps({"email": "test@example.com", "password": sifre}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["access_token"]


def _riza(tok, ac: bool):
    req = urllib.request.Request(BASE + "/api/organizations/ai-riza", data=json.dumps({"riza": ac}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
    return json.load(urllib.request.urlopen(req, timeout=30))["ai_yurtdisi_riza"]


def _akis(tok, soru, timeout=300):
    """SSE akışını okur; (durum, ilk_parca_sn, son_sn, parca_sayisi, metin_uzunlugu)."""
    req = urllib.request.Request(BASE + "/api/sor/akis", data=json.dumps({"question": soru}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
    t0 = time.time(); ilk = None; n = 0; uz = 0; son = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            durum = r.status; buf = b""
            while True:
                chunk = r.read(1)
                if not chunk:
                    break
                buf += chunk
                while b"\n\n" in buf:
                    blok, buf = buf.split(b"\n\n", 1)
                    tip = ""; veri = ""
                    for sat in blok.decode("utf-8", "replace").split("\n"):
                        if sat.startswith("event:"): tip = sat[6:].strip()
                        elif sat.startswith("data:"): veri += sat[5:].strip()
                    if tip == "parca":
                        n += 1; uz += len(veri)
                        if ilk is None: ilk = round(time.time() - t0, 2)
                    elif tip in ("son", "hata"):
                        son = tip
        return dict(durum=durum, ilk_parca_sn=ilk, toplam_sn=round(time.time() - t0, 2), parca=n, metin_kar=uz, son=son)
    except urllib.error.HTTPError as e:
        return dict(durum=e.code, hata=e.read()[:200].decode("utf-8", "replace"), toplam_sn=round(time.time() - t0, 2))
    except Exception as e:
        return dict(durum="EXC", hata=f"{type(e).__name__}: {e}", toplam_sn=round(time.time() - t0, 2))


def eszamanli(tok, adet=5):
    sonuc = [None] * adet
    def gorev(i):
        sonuc[i] = _akis(tok, f"KOSGEB makine yatırımı desteği {i}")
    th = [threading.Thread(target=gorev, args=(i,)) for i in range(adet)]
    t0 = time.time(); [t.start() for t in th]; [t.join() for t in th]
    return dict(tur="eszamanli", adet=adet, duvar_sn=round(time.time() - t0, 2), sonuclar=sonuc)


def yuk(sure_sn=30, is_parcacigi=5):
    yollar = ["/health", "/api/kobi-sinifi?calisan=12&ciro=20000000", "/api/nace/ara?q=ekmek"]
    kayit = []; kilit = threading.Lock(); dur = time.time() + sure_sn
    def gorev(i):
        k = 0
        while time.time() < dur:
            yol = yollar[(i + k) % len(yollar)]; k += 1; t0 = time.time()
            try:
                with urllib.request.urlopen(BASE + yol, timeout=30) as r: d = r.status
            except urllib.error.HTTPError as e: d = e.code
            except Exception as e: d = f"EXC {type(e).__name__}"
            with kilit: kayit.append((yol.split("?")[0], d, round(time.time() - t0, 3)))
    th = [threading.Thread(target=gorev, args=(i,)) for i in range(is_parcacigi)]
    [t.start() for t in th]; [t.join() for t in th]
    ozet = {}
    for yol, d, s in kayit:
        o = ozet.setdefault(yol, {"n": 0, "durumlar": {}, "sureler": []})
        o["n"] += 1; o["durumlar"][str(d)] = o["durumlar"].get(str(d), 0) + 1; o["sureler"].append(s)
    for o in ozet.values():
        ss = sorted(o.pop("sureler")); o["p50_ms"] = round(ss[len(ss) // 2] * 1000); o["p95_ms"] = round(ss[int(len(ss) * .95) - 1] * 1000); o["max_ms"] = round(ss[-1] * 1000)
    return dict(tur="yuk", sure_sn=sure_sn, is_parcacigi=is_parcacigi, toplam_istek=len(kayit), uc_noktalar=ozet)


def akis_olcum(tok, n):
    sorular = ["Yeni ekmek üretim hattı için makine alacağım, yatırım teşvik belgesi alabilir miyim?",
               "İhracata başlayacağız, hangi destekler var?", "3 kişi daha işe alacağım, SGK desteği var mı?",
               "Ar-Ge projemiz için TÜBİTAK 1507 uygun mu?", "İşletme kredisi için kefalet desteği var mı?"]
    _riza(tok, True)
    try:
        sonuclar = [dict(soru=sorular[i % len(sorular)][:40], **_akis(tok, sorular[i % len(sorular)])) for i in range(n)]
    finally:
        _riza(tok, False)
    ilk = [s["ilk_parca_sn"] for s in sonuclar if s.get("ilk_parca_sn")]
    top = [s["toplam_sn"] for s in sonuclar if s.get("son") == "son"]
    return dict(tur="akis", n=n, ilk_parca_sn=dict(min=min(ilk), ort=round(sum(ilk) / len(ilk), 1), max=max(ilk)) if ilk else None,
                toplam_sn=dict(min=min(top), ort=round(sum(top) / len(top), 1), max=max(top)) if top else None, sonuclar=sonuclar)


if __name__ == "__main__":
    mod = sys.argv[1] if len(sys.argv) > 1 else "eszamanli"
    if mod == "eszamanli":
        tok = _token(); assert _riza(tok, False) is False
        r = eszamanli(tok)
    elif mod == "akis":
        tok = _token(); r = akis_olcum(tok, int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    elif mod == "yuk":
        r = yuk()
    else:
        raise SystemExit("mod: eszamanli | akis N | yuk")
    r["zaman"] = time.strftime("%Y-%m-%d %H:%M:%S")
    yol = os.path.join(OUT, "D_ozet.json")
    eski = json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else []
    eski.append(r); json.dump(eski, open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:3000])
