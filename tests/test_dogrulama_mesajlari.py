"""422 yanıtları Türkçe ve gönderilen değeri yansıtmıyor (2026-10-08)."""
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def test_kayitta_zayif_parola_turkce_ve_parola_yansitilmaz(client):
    gizli = "sadeceharfler"
    r = client.post("/api/auth/signup", json={"email": "a@example.com", "password": gizli,
                                              "full_name": "A", "company_name": "B"})
    assert r.status_code == 422
    assert gizli not in r.text, "parola yanıtta geri dönmemeli"
    hata = r.json()["detail"][0]
    assert set(hata) == {"loc", "msg", "type"} and hata["loc"] == ["body", "password"]
    assert "rakam" in hata["msg"] or "harf" in hata["msg"]


def test_eksik_ve_gecersiz_alanlar_turkce(client):
    r = client.post("/api/auth/signup", json={"email": "gecersiz", "full_name": "", "company_name": "B"})
    mesajlar = {tuple(h["loc"]): h["msg"] for h in r.json()["detail"]}
    assert mesajlar[("body", "email")] == "Geçerli bir e-posta adresi girin."
    assert mesajlar[("body", "password")] == "Parola zorunlu."
    assert mesajlar[("body", "full_name")] == "Ad soyad boş bırakılamaz."


def test_cilek_sinir_ve_secenek_mesajlari(client, test_user_token):
    h = {"Authorization": f"Bearer {test_user_token}"}
    r = client.post("/api/cilek/parseller", headers=h, json={"ad": "x" * 101, "ortam_tipi": "uzay"})
    msg = sorted(e["msg"] for e in r.json()["detail"])
    assert msg == ["Ad en fazla 100 karakter olabilir.", "Ortam tipi için geçerli değerler: 'sera' veya 'acik_tarla'."]


def test_bozuk_json_govdesi(client):
    r = client.post("/api/auth/login", content=b"{bozuk", headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["detail"][0]["msg"] == "İstek gövdesi geçersiz."


def test_self_test_bayragi():
    # stdin=DEVNULL: tam takımda (pytest yakalaması altında) Windows "WinError 6 İşleyici geçersiz" veriyordu
    r = subprocess.run([sys.executable, "-m", "app.dogrulama_mesajlari", "--self-test"], cwd=KOK,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "12/12 geçti" in r.stdout
