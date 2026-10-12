"""13 persona simülasyonunun Teşvik Asistanı arayüzünde adım adım kaydı (ekran görüntüleri, 2026-10-12).

Yerel geliştirme sunucusu (http://127.0.0.1:8000) makinedeki Chrome ile başsız (headless) sürülür; Chrome DevTools
Protocol'e websocket-client ile bağlanılır (ek kurulum yok). Her persona için arayüzde:
  1 kayıt (ilk personada kayıt formu görüntüsü)      5 danışmana soru ve yanıt
  2 işletme profili formu (dolu)                       6 kontrol listesi (öne çıkan program)
  3 uygun destekler (eşleşme)                          7 taslak sihirbazı ve şablon taslak
  4 hazırlık adımları / e-ihracat hesaplayıcı          8 ana sayfa özeti (süreç sonu)
Test hesapları <persona>@example.com; parolalar rastgele, data/sunum_test_hesaplari.json (git dışı). Yerelde Stripe
test modu yapılandırılmadığı için PRO plan yerel veritabanında atanır (ödeme adımı simüle edilmez).

    python docs/olcum/2026-10-12-sunum/ekran_akisi.py --self-test
    python docs/olcum/2026-10-12-sunum/ekran_akisi.py [persona ...]     (varsayılan: 13 personanın hepsi)
"""
import base64
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KOK))
URL = "http://127.0.0.1:8000"
CIKTI = KOK / "data/sunum_ekran"
HESAPLAR = KOK / "data/sunum_test_hesaplari.json"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9333
GENISLIK, YUKSEKLIK, OLCEK = 1440, 1000, 1.5

E = dict(sektor="e-ticaret", nace="47.91")
# Arayüzde seçilebilen alanlar (hedef kutularında "finansman" ve "dijital" yok; persona profilinden düşer).
PERSONA = {
    "rekortiv": dict(ad="Rekortiv", sektor="arge", il="Ankara", tur="yok", calisan=0, ciro=60000, hedef=["arge"],
                     nace="62.01", trl="7", yas=21, ortaklik="hayir",
                     soru="Rekortiv adında sınav hazırlık mobil uygulamam var; App Store ve Google Play'de abonelikle "
                          "gelir alıyorum ama şirketim yok, 20/B istisnasıyla çalışıyorum. Şirket kurmadan "
                          "alabileceğim hibe ya da destek var mı?"),
    "findik": dict(ad="Fındık üreticisi", sektor="tarim", il="Ordu", tur="sahis", calisan=0, ciro=250000, hedef=[],
                   kategori="sebze_meyve", urun="fındık", arazi=9,
                   soru="9 dönüm fındık bahçem var. Bu yıl devletten hangi destekleri alabilirim, toplam ne kadar eder?"),
    "cilek": dict(ad="Çilek üreticisi", sektor="tarim", il="Aydın", tur="sahis", calisan=0, ciro=150000,
                  hedef=["sulama"], kategori="sebze_meyve", urun="çilek", arazi=1.5,
                  soru="1,5 dönüm açık tarlada çilek yetiştiriyorum. Hangi desteklerden yararlanabilirim?"),
    "ikas_giyim": dict(ad="ikas · kadın giyim", **E, il="İstanbul", tur="limited", calisan=5, ciro=6000000,
                       hedef=["ihracat"], ozellik=["kadin_girisimci"], eihracat=True,
                       soru="Kadın giyim e-ticaret mağazam var. Yurt dışına satış için hangi destekler var?"),
    "ikas_kozmetik": dict(ad="ikas · doğal kozmetik", **E, il="Ankara", tur="sahis", calisan=3, ciro=2500000,
                          hedef=[], ozellik=["kadin_girisimci"],
                          soru="Doğal kozmetik markamla online satış yapıyorum; kadın girişimciye kredi ya da hibe "
                               "var mı?"),
    "ikas_evtekstil": dict(ad="ikas · ev tekstili", **E, il="Denizli", tur="limited", calisan=15, ciro=20000000,
                           hedef=["ihracat"],
                           soru="Havlu ve bornoz üretip kendi sitemizden satıyoruz; Amazon Avrupa'da mağaza açmak için "
                                "destek var mı?"),
    "ikas_taki": dict(ad="ikas · gümüş takı", **E, il="İstanbul", tur="sahis", calisan=4, ciro=8000000,
                      hedef=["ihracat"], eihracat=True,
                      soru="Gümüş takı satan online mağazam var; Etsy ve kendi sitemden yurt dışı satış için destek "
                           "var mı?"),
    "ikas_kahve": dict(ad="ikas · kahve", **E, il="İzmir", tur="limited", calisan=6, ciro=5000000, hedef=[],
                       soru="Kahve kavurma makinesi almak istiyorum, hangi kredi ya da hibeler var?"),
    "ikas_pet": dict(ad="ikas · evcil hayvan ürünleri", **E, il="İstanbul", tur="limited", calisan=8,
                     ciro=12000000, hedef=["istihdam"],
                     soru="Evcil hayvan ürünleri satan e-ticaret şirketimiz için işletme sermayesi kredisi bulabilir "
                          "miyiz?"),
    "ikas_bebek": dict(ad="ikas · organik bebek tekstili", **E, il="Bursa", tur="limited", calisan=10,
                       ciro=15000000, hedef=["ihracat"],
                       soru="Organik bebek tekstili markamızı Körfez ülkelerine satmak istiyoruz; hangi destekler "
                            "var?"),
    "ikas_spor": dict(ad="ikas · spor giyim", **E, il="Konya", tur="limited", calisan=7, ciro=9000000,
                      hedef=["ihracat"],
                      soru="Spor giyim markamız için yurt dışı pazaryerlerinde reklam desteği var mı?"),
    "ikas_seramik": dict(ad="ikas · el yapımı seramik", **E, il="Eskişehir", tur="sahis", calisan=1, ciro=600000,
                         hedef=[], yas=27,
                         soru="El yapımı seramik satıyorum, tek kişilik şahıs işletmesiyim; genç girişimciye uygun "
                              "kredi ya da hibe var mı?"),
    "ikas_elektronik": dict(ad="ikas · telefon aksesuarı", **E, il="İstanbul", tur="anonim", calisan=12,
                            ciro=35000000, hedef=["ihracat"],
                            soru="Telefon aksesuarı satıyoruz, e-ihracata başlayacağız; Ticaret Bakanlığı e-ihracat "
                                 "desteklerinin şartları neler?"),
}
# E-ihracat hesaplayıcısına girilen simülasyon giderleri (yıllık TL; persona tanımının parçası, gerçek veri değil).
EIHRACAT = {"eh-pazaryeri_reklam": 240000, "eh-siparis_karsilama": 120000, "eh-pazaryeri_komisyon": 90000,
            "eh-satis": 2000000, "eh-hedef": 60, "eh-turk": 100, "eh-birlik": "true", "eh-madrid": "false",
            "eh-statu": "false"}


class Cdp:
    def __init__(self, ws_url):
        import websocket
        self.ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True)
        self.n = 0

    def __call__(self, metod, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": metod, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(f"{metod}: {m['error']}")
                return m.get("result", {})

    def js(self, ifade, bekle=True):
        r = self("Runtime.evaluate", expression=ifade, awaitPromise=bekle, returnByValue=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(f"JS hatası: {r['exceptionDetails'].get('exception', {}).get('description', r)}")
        return r.get("result", {}).get("value")

    def bekle(self, kosul, sure=40, aciklama=""):
        bitis = time.time() + sure
        while time.time() < bitis:
            if self.js(f"!!({kosul})"):
                return
            time.sleep(0.3)
        raise TimeoutError(f"beklenen olmadı: {aciklama or kosul}")

    def git(self, adres):
        self("Page.navigate", url=adres)
        time.sleep(0.8)
        self.bekle("document.readyState === 'complete'", aciklama=adres)

    def cek(self, secici, dosya, en_cok=1500, ust=0):
        """Öğenin (secici) ekran görüntüsü; boyu en_cok CSS pikselle sınırlı, `ust` px aşağıdan başlar."""
        k = self.js(f"""(() => {{ const e = document.querySelector({json.dumps(secici)}); if (!e) return null;
            const r = e.getBoundingClientRect(); return {{x: r.left + scrollX, y: r.top + scrollY, w: r.width,
            h: r.height}}; }})()""")
        if not k:
            raise RuntimeError(f"öğe yok: {secici}")
        kirp = kirpma(k, en_cok, ust)
        veri = self("Page.captureScreenshot", format="png", captureBeyondViewport=True, clip=kirp)["data"]
        dosya.write_bytes(base64.b64decode(veri))
        return dosya


def kirpma(k: dict, en_cok: int, ust: int, pay: int = 10) -> dict:
    """Öğe kutusundan kırpma alanı: kenarlarda `pay` px, boy en çok `en_cok`."""
    y = max(0, k["y"] + ust - pay)
    return {"x": max(0, k["x"] - pay), "y": y, "width": k["w"] + 2 * pay,
            "height": min(k["h"] - ust + 2 * pay, en_cok), "scale": 1}


def hesaplar() -> dict:
    return json.loads(HESAPLAR.read_text(encoding="utf-8")) if HESAPLAR.exists() else {}


def _istek(yol: str, govde: dict, yontem: str = "POST", belirtec: str = "") -> tuple[int, dict]:
    basliklar = {"Content-Type": "application/json"}
    if belirtec:
        basliklar["Authorization"] = f"Bearer {belirtec}"
    r = urllib.request.Request(f"{URL}{yol}", data=json.dumps(govde).encode(), headers=basliklar, method=yontem)
    for _ in range(10):
        try:
            with urllib.request.urlopen(r) as y:
                return y.status, json.loads(y.read() or b"{}")
        except urllib.error.HTTPError as h:
            if h.code != 429:
                return h.code, {}
            time.sleep(int(h.headers.get("Retry-After") or 15) + 1)   # IP hız sınırı
    return 429, {}


def onceki_hesabi_sil(eposta: str, parola: str) -> None:
    """Tekrar koşuda aynı test hesabı uygulamanın kendi silme uç noktasıyla (DELETE /api/organizations/me) silinir;
    yalnız bu betiğin oluşturduğu sunum.*@example.com hesapları."""
    assert eposta.startswith("sunum.") and eposta.endswith("@example.com")
    kod, d = _istek("/api/auth/login", {"email": eposta, "password": parola})
    if kod == 200:
        kod, _ = _istek("/api/organizations/me", {"password": parola, "onay": True}, "DELETE", d["access_token"])
        if kod != 200:
            raise RuntimeError(f"test hesabı silinemedi: {eposta} ({kod})")


def pro_yap(eposta: str) -> None:
    from app.models import Organization, PlanType, SessionLocal, User
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == eposta).one()
        org = db.get(Organization, u.org_id)
        org.plan = PlanType.PRO
        db.commit()
    finally:
        db.close()


def chrome_ac():
    profil = CIKTI / "_chrome_profil"
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={profil}",
                             f"--window-size={GENISLIK},{YUKSEKLIK}", "--hide-scrollbars", "--lang=tr-TR",
                             "--no-first-run", "--no-default-browser-check", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            hedefler = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
            sayfa = next(h for h in hedefler if h["type"] == "page")
            return proc, Cdp(sayfa["webSocketDebuggerUrl"])
        except Exception:
            time.sleep(0.3)
    proc.kill()
    raise RuntimeError("Chrome açılamadı")


def bolum(c: Cdp, ad: str):
    c.js(f"document.querySelector('.menu-link[data-section=\"{ad}\"]').click()")
    time.sleep(0.6)


def persona_akisi(c: Cdp, anahtar: str, ilk: bool) -> list[str]:
    p = PERSONA[anahtar]
    d = CIKTI / anahtar
    d.mkdir(parents=True, exist_ok=True)
    kayit = hesaplar()
    eposta = f"sunum.{anahtar.replace('_', '.')}@example.com"
    alinan = []
    # 1 kayıt
    c.git(f"{URL}/")
    c.js("localStorage.clear()")       # önceki personanın oturumu kapanır
    c.git(f"{URL}/")
    c.js("document.querySelector('[data-tikla=\"switchForm\"][data-arg=\"signup\"], a[data-arg=\"signup\"]')?.click()")
    c.bekle("document.getElementById('signup-form') && getComputedStyle(document.getElementById('signup-form')).display"
            " !== 'none'", aciklama="kayıt formu")
    if eposta in kayit:
        onceki_hesabi_sil(eposta, kayit[eposta])
    parola = secrets.token_urlsafe(16)
    kayit[eposta] = parola
    HESAPLAR.write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")
    c.js(f"""(() => {{ const d = (i, v) => {{ const e = document.getElementById(i); e.value = v;
        e.dispatchEvent(new Event('input', {{bubbles: true}})); }};
        d('signup-name', {json.dumps(p['ad'])}); d('signup-email', {json.dumps(eposta)});
        d('signup-company', {json.dumps(p['ad'])}); d('signup-password', {json.dumps(parola)});
        d('signup-password-confirm', {json.dumps(parola)}); }})()""")
    if ilk:
        # Parola alanı görüntüde maskeli kalır (type=password).
        alinan.append(c.cek(".container", d / "01_kayit.png", 1400).name)
    c.js("document.getElementById('signup-btn').click()")
    c.bekle("location.pathname === '/dashboard'", aciklama="panel")
    pro_yap(eposta)
    c.git(f"{URL}/dashboard")
    c.bekle("document.querySelector('#ozet-icerik .loading') === null", aciklama="ana sayfa")
    time.sleep(0.5)
    if ilk:
        alinan.append(c.cek("#ozet", d / "02_ana_sayfa_bos.png", 1100).name)
    # 2 profil
    bolum(c, "profil")
    c.js(f"""(() => {{ const p = {json.dumps(p, ensure_ascii=False)};
        const sec = (i, v) => {{ const e = document.getElementById(i); if (!e || v === undefined || v === null) return;
            e.value = String(v); e.dispatchEvent(new Event('input', {{bubbles: true}}));
            e.dispatchEvent(new Event('change', {{bubbles: true}})); }};
        sec('p-sektor', p.sektor); sec('p-bolge', p.il); sec('p-sirket-turu', p.tur); sec('p-calisan', p.calisan);
        sec('p-ciro', p.ciro);
        document.querySelectorAll('.p-hedef').forEach(k => {{ if (k.checked !== (p.hedef || []).includes(k.value)) k.click(); }});
        if (p.kategori) {{ sec('p-tarim-kategori', p.kategori); sec('p-urun', p.urun); sec('p-arazi', p.arazi); }}
        const ayr = p.nace || p.trl || p.yas || p.ortaklik || p.ozellik;
        if (ayr) document.querySelector('.profil-ayrinti').open = true;
        sec('p-nace', p.nace); sec('p-trl', p.trl); sec('p-kurucu-yasi', p.yas); sec('p-ortaklik', p.ortaklik);
        document.querySelectorAll('.p-ozellik').forEach(k => {{ if (k.checked !== (p.ozellik || []).includes(k.value)) k.click(); }});
    }})()""")
    time.sleep(0.4)
    alinan.append(c.cek("#profil .search-section:last-child", d / "03_profil.png", 1700).name)
    # 3 uygun destekler
    c.js("document.querySelector('#profil-form button[type=submit]').click()")
    c.bekle("!document.getElementById('destekler').classList.contains('hidden') && "
            "document.querySelectorAll('#eslesme-results .result-item, #eslesme-results > div').length > 0 && "
            "!document.querySelector('#eslesme-results .loading')", 60, "eşleşme")
    time.sleep(1.2)
    alinan.append(c.cek("#eslesme-section", d / "04_uygun_destekler.png", 1500).name)
    # 4 hazırlık / e-ihracat
    try:
        c.bekle("getComputedStyle(document.getElementById('hazirlik-section')).display !== 'none'", 15, "hazırlık")
        alinan.append(c.cek("#hazirlik-section", d / "05_hazirlik.png", 1300).name)
    except TimeoutError:
        pass
    if p.get("eihracat"):
        c.js(f"""(() => {{ document.getElementById('eihracat-detay').open = true;
            const v = {json.dumps(EIHRACAT)}; for (const [i, x] of Object.entries(v)) {{
              const e = document.getElementById(i); e.value = String(x);
              e.dispatchEvent(new Event('change', {{bubbles: true}})); }}
            document.querySelector('[data-tikla="eihracatHesapla"]').click(); }})()""")
        c.bekle("document.getElementById('eihracat-sonuc').innerText.trim().length > 20", 30, "e-ihracat sonucu")
        time.sleep(0.6)
        alinan.append(c.cek("#eihracat-detay", d / "06_eihracat.png", 1700).name)
    # 5 danışmana soru
    bolum(c, "search")
    c.js(f"""(() => {{ const e = document.getElementById('search-input'); e.value = {json.dumps(p['soru'])};
        e.dispatchEvent(new Event('input', {{bubbles: true}})); document.querySelector('[data-tikla="performSearch"]').click();
    }})()""")
    c.bekle("document.getElementById('search-results').innerText.includes('Kısa cevap')", 90, "yanıt")
    onceki = -1
    for _ in range(60):          # akış bitene kadar (metin uzunluğu sabitlenince)
        n = c.js("document.getElementById('search-results').innerText.length")
        if n == onceki:
            break
        onceki = n
        time.sleep(0.7)
    alinan.append(c.cek("#search .search-section", d / "07_soru_yanit.png", 1700).name)
    # 6 kontrol listesi (uygun desteklerdeki ilk kart)
    bolum(c, "destekler")
    c.bekle("document.querySelector('#eslesme-results [data-tikla=\"kontrolListesiAc\"]')", 30, "kontrol listesi düğmesi")
    c.js("document.querySelector('#eslesme-results [data-tikla=\"kontrolListesiAc\"]').click()")
    c.bekle("!document.getElementById('basvurular').classList.contains('hidden') && "
            "document.querySelector('[data-tikla=\"sihirbazAc\"]')", 40, "kontrol listesi")
    time.sleep(0.8)
    # Örnek işaretleme: ilk belge "hazır" (her tıklama kaydedip listeyi yeniden çizer; tek madde işaretlenir)
    c.js("""(() => { const k = [...document.querySelectorAll('#basvurular input[type=checkbox]')]
        .find(x => !x.disabled && !x.checked); if (k) k.click(); })()""")
    time.sleep(1.5)
    alinan.append(c.cek("#basvurular", d / "08_kontrol_listesi.png", 1700).name)
    # 7 taslak sihirbazı → şablon taslak
    c.js("document.querySelector('[data-tikla=\"sihirbazAc\"]').click()")
    c.bekle("document.querySelector('[data-tikla=\"sihirbazGonder\"]')", 30, "sihirbaz")
    time.sleep(0.6)
    alinan.append(c.cek("#kl-sihirbaz", d / "09_sihirbaz.png", 1700).name)
    c.js("document.querySelector('[data-tikla=\"sihirbazGonder\"]').click()")
    c.bekle("document.querySelector('[data-tikla=\"taslakKopyala\"]')", 40, "taslak")
    time.sleep(0.8)
    alinan.append(c.cek(".kl-taslak", d / "10_taslak.png", 1700).name)
    # 8 ana sayfa özeti
    bolum(c, "ozet")
    c.bekle("document.querySelector('#ozet-icerik .loading') === null", 30, "özet")
    time.sleep(1.0)
    alinan.append(c.cek("#ozet", d / "11_ana_sayfa_ozet.png", 1500).name)
    return alinan


def _self_test() -> int:
    k = [
        ("13 persona tanımlı", len(PERSONA) == 13),
        ("her personada soru, il, sektör", all(p.get("soru") and p.get("il") and p.get("sektor")
                                               for p in PERSONA.values())),
        ("hedefler arayüzde seçilebilir değerler", all(set(p["hedef"]) <= {"yatirim", "ihracat", "arge", "istihdam",
                                                                          "makine", "sulama", "hayvan", "organik"}
                                                       for p in PERSONA.values())),
        ("kırpma: pay ve boy sınırı", kirpma({"x": 100, "y": 200, "w": 800, "h": 3000}, 1500, 0)
         == {"x": 90, "y": 190, "width": 820, "height": 1500, "scale": 1}),
        ("kırpma: kısa öğe tam boy", kirpma({"x": 0, "y": 0, "w": 500, "h": 300}, 1500, 0)["height"] == 320),
        ("test e-postaları example.com", all(f"sunum.{a.replace('_', '.')}@example.com".endswith("@example.com")
                                            for a in PERSONA)),
        ("hesap dosyası git dışı data/ altında", HESAPLAR.parent.name == "data"),
    ]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    secilen = [a for a in sys.argv[1:] if a in PERSONA] or list(PERSONA)
    CIKTI.mkdir(parents=True, exist_ok=True)
    proc, c = chrome_ac()
    try:
        c("Page.enable")
        c("Emulation.setDeviceMetricsOverride", width=GENISLIK, height=YUKSEKLIK, deviceScaleFactor=OLCEK,
          mobile=False)
        ozet = {}
        for i, a in enumerate(secilen):
            t = time.time()
            try:
                ozet[a] = persona_akisi(c, a, ilk=(i == 0))
                print(f"[{a}] {len(ozet[a])} görüntü, {time.time() - t:.1f} sn")
            except Exception as hata:
                c.cek("body", CIKTI / f"_hata_{a}.png", 2500)
                print(f"[{a}] HATA: {hata}")
                ozet[a] = {"hata": str(hata)}
        (CIKTI / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        try:
            c("Browser.close")
        except Exception:
            pass
        proc.kill()
