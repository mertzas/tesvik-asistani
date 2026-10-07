"""rag.profil_sozlugu: /api/sor'un danışmana gönderdiği profil sözlüğü (tek tanım)."""
from datetime import date

from app.rag import profil_sozlugu
from app.models import FinancialProfile


def test_turetilmis_alanlar_ve_bos_degerler():
    p = FinancialProfile(sektor="arge", bolge="Van", calisan_sayisi=12, yillik_ciro=20e6, nace_kodu="62.01",
                         sirket_turu="limited", kurulus_tarihi=date(2024, 3, 1), trl=8, hedefler=["ihracat"])
    s = profil_sozlugu(p)
    assert s["NACE kodu"] == "62.01" and s["kuruluş tarihi"] == "2024-03-01" and s["TRL (teknoloji hazırlık seviyesi)"] == 8
    assert s["KOBİ ölçeği"].startswith("küçük işletme") and "7 Ağustos 2025" in s["KOBİ ölçeği"]
    assert s["yatırım teşvik bölgesi (9903 sayılı Karar EK-2)"] == "6. bölge"
    assert s["tarım kategorisi"] is None and s["ürün türü"] is None


def test_bilinmeyen_il_ve_eksik_olcek_turetilmis_alan_uretmez():
    s = profil_sozlugu(FinancialProfile(sektor="hizmet", bolge="Bilinmeyen İl"))
    assert "yatırım teşvik bölgesi (9903 sayılı Karar EK-2)" not in s
    assert "KOBİ ölçeği" not in s
    assert s["kuruluş tarihi"] is None
