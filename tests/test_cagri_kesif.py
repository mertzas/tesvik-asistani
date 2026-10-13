"""Yeni çağrı keşif hattı (app/cagri_kesif.py, 2026-10-13)."""
import json
from datetime import date

from app import cagri_kesif
from app.models import Tesvik, TesvikCagrisi


def test_self_test():
    assert cagri_kesif._self_test() == 0


def test_katalog_gercek_kayitlarla(db_session):
    db_session.add_all([
        Tesvik(id=801, kurum="TUBITAK", baslik="1501 - TÜBİTAK Sanayi Ar-Ge Projeleri Destekleme Programı", ozet="o",
               detay="d", aktif_mi=True, kaynak_url="https://www.tubitak.gov.tr/tr/destekler/sanayi/1501#x"),
        Tesvik(id=802, kurum="Mevlana Kalkınma Ajansı", baslik="2026 Yılı Turizm Altyapısı Mali Destek Programı",
               ozet="o", detay="d", aktif_mi=True, kaynak_url="https://www.mevka.org.tr/a"),
    ])
    db_session.flush()
    db_session.add(TesvikCagrisi(tesvik_id=802, ad="2026", kaynak_url="https://www.mevka.org.tr/cagri-2026/",
                                 dogrulama_tarihi=date(2026, 10, 1)))
    db_session.commit()
    k = cagri_kesif.Katalog.yukle(db_session)

    def sinif(kurum, metin, url):
        ilan = cagri_kesif.Ilan("t", kurum, metin, url)
        k.siniflandir(ilan)
        return ilan.sinif, ilan.tesvik_id

    assert sinif("TÜBİTAK", "x", "http://tubitak.gov.tr/tr/destekler/sanayi/1501/") == ("bilinen", None)
    assert sinif("Mevlana", "x", "https://mevka.org.tr/cagri-2026") == ("bilinen", None)
    assert sinif("TÜBİTAK", "1501 Sanayi Ar-Ge 2026-3 Dönemi Çağrısı Açıldı", "https://tubitak.gov.tr/d/9") == \
        ("cagri_adayi", 801)
    assert sinif("Mevlana Kalkınma Ajansı", "2027 Yılı Turizm Altyapısı Mali Destek Programı İlan Edildi",
                 "https://www.mevka.org.tr/b") == ("cagri_adayi", 802)
    assert sinif("Mevlana Kalkınma Ajansı", "Sosyal Kalkınma Programı 2026 Başvuruları",
                 "https://www.mevka.org.tr/c")[0] == "yeni_program"


def test_kaynak_dosyasi_gecerli():
    veri = json.loads(cagri_kesif.KAYNAK_DOSYASI.read_text(encoding="utf-8"))
    adlar = [k["ad"] for k in veri["kaynaklar"]]
    assert len(adlar) == len(set(adlar)) and any(k.get("tur") == "resmi_gazete" for k in veri["kaynaklar"])
    for k in veri["kaynaklar"]:
        if k.get("tur") != "resmi_gazete":
            assert k["url"].startswith("https://") and k["kurum"] and k["alan_adi"] in k["url"]


def test_kayitli_cagri_tarihi_bilinen_sayilir(db_session):
    """Duyuru adresi kayıtlı olmasa da ilandaki son gün programın kayıtlı çağrısıyla aynıysa çağrı zaten girilmiştir."""
    db_session.add(Tesvik(id=803, kurum="TUBITAK", baslik="2224-A Yurt Dışı Bilimsel Etkinliklere Katılımı Destekleme",
                          ozet="o", detay="d", aktif_mi=True))
    db_session.flush()
    db_session.add(TesvikCagrisi(tesvik_id=803, ad="2026-3", kapanis=date(2026, 11, 3),
                                 kaynak_url="https://tubitak.gov.tr/x", dogrulama_tarihi=date(2026, 10, 1)))
    db_session.commit()
    k = cagri_kesif.Katalog.yukle(db_session)
    ayni = cagri_kesif.Ilan("t", "TÜBİTAK", "m", "u", tesvik_id=803,
                            tarihler=[{"tarih": "2026-11-03", "alinti": "Son başvuru 3 Kasım 2026"}])
    yeni = cagri_kesif.Ilan("t", "TÜBİTAK", "m", "u2", tesvik_id=803,
                            tarihler=[{"tarih": "2027-03-02", "alinti": "Son başvuru 2 Mart 2027"}])
    assert k.cagri_kayitli_mi(ayni) and not k.cagri_kayitli_mi(yeni)


def test_kuyruk_isaretle(tmp_path):
    kuyruk = [{"url": "https://a.gov.tr/duyuru/1", "durum": "beklemede"},
              {"url": "https://a.gov.tr/duyuru/2", "durum": "eklendi"},
              {"url": "https://b.gov.tr/x", "durum": "beklemede"}]
    (tmp_path / "kuyruk.json").write_text(json.dumps(kuyruk), encoding="utf-8")
    assert cagri_kesif.kuyruk_isaretle("https://a.gov.tr/duyuru/", "bilinen", "kayıt 5", dizin=tmp_path) == 1
    sonuc = json.loads((tmp_path / "kuyruk.json").read_text(encoding="utf-8"))
    assert [x["durum"] for x in sonuc] == ["bilinen", "eklendi", "beklemede"]
    assert sonuc[0]["aciklama"] == "kayıt 5" and sonuc[0]["isaretlenme"] == date.today().isoformat()
