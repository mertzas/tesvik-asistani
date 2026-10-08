"""Tur15 başvuru süresi verisi ve uzak son günlü çağrıların "yaklaşan" listesine girmemesi (2026-10-08)."""
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from app.models import Tesvik, TesvikCagrisi

KOK = Path(__file__).resolve().parent.parent
BUGUN = date.today()


def test_uzak_kapanisli_acik_cagri_yaklasanlarda_yok(client, test_user_token, db_session):
    db_session.add_all([Tesvik(id=180, kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Hedef Yatırımlar", ozet="o",
                               detay="d", aktif_mi=True, kaynak_url="https://t/180"),
                        Tesvik(id=142, kurum="KGF", baslik="İstihdam Koruma", ozet="o", detay="d", aktif_mi=True,
                               kaynak_url="https://t/142")])
    db_session.flush()
    db_session.add_all([
        TesvikCagrisi(tesvik_id=180, ad="9903 müracaat süresi", kapanis=date(2030, 12, 31), kaynak_url="https://k/a",
                      dogrulama_tarihi=BUGUN),
        TesvikCagrisi(tesvik_id=142, ad="2026-2", acilis=BUGUN - timedelta(days=30), kapanis=BUGUN + timedelta(days=20),
                      kaynak_url="https://k/b", dogrulama_tarihi=BUGUN),
        TesvikCagrisi(tesvik_id=142, ad="açık, kapanış yok", acilis=BUGUN - timedelta(days=5), kaynak_url="https://k/c",
                      dogrulama_tarihi=BUGUN),
    ])
    db_session.commit()
    h = {"Authorization": f"Bearer {test_user_token}"}
    adlar = [c["ad"] for c in client.get("/api/cagrilar?gun=90", headers=h).json()["cagrilar"]]
    assert "9903 müracaat süresi" not in adlar and {"2026-2", "açık, kapanış yok"} <= set(adlar)
    # Programın kendi kontrol listesinde ise görünür (son başvuru 31.12.2030).
    c = client.get("/api/basvuru-listesi/180", headers=h).json()["cagrilar"][0]
    assert c["kapanis"] == "2030-12-31" and c["durum"] == "acik"


def test_tur15_self_test():
    r = subprocess.run([sys.executable, "scripts/fix_veri_2026_10_08_basvuru_suresi_tur15.py", "--self-test"], cwd=KOK,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= 6, r.stdout


def test_tur16_ve_kgf_izleme_self_test():
    for komut, asgari in ((["scripts/fix_veri_2026_10_08_sart_yer_sure_tur16.py"], 6), (["-m", "app.kgf_izleme"], 6)):
        r = subprocess.run([sys.executable, *komut, "--self-test"], cwd=KOK, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, encoding="utf-8")
        m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
        assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= asgari, r.stdout


def test_kgf_izleme_zamanlayicida_ve_tabani_var():
    import json
    from app.kgf_izleme import TABAN
    from app.scheduler import setup_scheduler
    assert "kgf_izleme" in {j.id for j in setup_scheduler().get_jobs()}
    taban = json.loads(TABAN.read_text(encoding="utf-8"))
    assert len(taban) >= 28 and all(len(v["ozet"]) == 16 for v in taban.values())
