"""9903 destek unsurları özeti (tesvik_9903_hesap.destek_unsurlari_ozeti) ve danışman
bağlamına eklenmesi. Ölçüm 2026-10-07 (Van otel sorusu): model "SGK işveren hissesi veya
faiz desteğinin oranı/süresi bağlamda yok" diyordu."""
from sqlalchemy.orm import sessionmaker

from app import rag
from app.models import FinancialProfile, Tesvik
from app.tesvik_9903_hesap import destek_unsurlari_ozeti


def test_hedef_yatirimlar_1_bolge_faiz_destegi_yok():
    m = destek_unsurlari_ozeti("hedef_yatirimlar", 1)
    assert "yatırıma katkı oranı %20" in m and "MADDE 20" in m
    assert "işveren hissesi: %50, 1 yıl" in m
    assert "1. bölgede YOK (MADDE 15/1-c)" in m
    assert "makine desteği: bu programda yok" in m
    assert "asgari sabit yatırım: 12.000.000 TL" in m and "31/12/2030" in m
    assert "MADDE 19" not in m


def test_6_bolge_isci_hissesi_ve_tam_isveren_hissesi():
    m = destek_unsurlari_ozeti("hedef_yatirimlar", 6)
    assert "işveren hissesi: %100, 12 yıl" in m
    assert "işçi hissesi" in m and "10 yıl (MADDE 19" in m
    assert "repo oranının %25'i, azami 12,5 puan" in m.replace("12.5", "12,5")
    assert "asgari sabit yatırım: 6.000.000 TL" in m


def test_hamle_programi_makine_ve_uzun_sigorta_suresi():
    m = destek_unsurlari_ozeti("teknoloji_hamlesi", 2)
    assert "işveren hissesi: %50, 8 yıl (MADDE 18/3" in m
    assert "makine desteği: birim fiyatı 2.000.000 TL üstü" in m and "240.000.000 TL tavan" in m
    assert "yatırıma katkı oranı %50" in m


def test_bolge_bilinmiyorsa_bolgeye_bagli_kalemler_acik_birakilir():
    m = destek_unsurlari_ozeti("stratejik_hamle", None)
    assert "profilde il yok" in m and "asgari sabit yatırım" not in m


def test_9903_disi_program_bos():
    assert destek_unsurlari_ozeti("kosgeb", 3) == ""


def test_hazirla_9903_kaydina_destek_unsurlari_ekler(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    db_session.add(Tesvik(id=180, kurum="Sanayi ve Teknoloji Bakanlığı",
                          baslik="Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)",
                          ozet="Yatırım teşvik belgesi otel", detay="d", aktif_mi=True, kaynak_url="https://t/180",
                          uygunluk_kriterleri={"sektorler": ["genel", "hizmet"]}))
    db_session.commit()
    otel = FinancialProfile(sektor="hizmet", bolge="Van", nace_kodu="55.10", calisan_sayisi=25, yillik_ciro=30e6)
    h = rag._hazirla("otel yatırımı için teşvik belgesi", True, otel)
    assert 180 in h.notlar
    assert "DESTEK UNSURLARI" in h.notlar[180] and "6. bölge" in h.notlar[180] and "MADDE 19" in h.notlar[180]
    assert "DESTEK UNSURLARI" in rag._baglam_metni(h.matches, None, h.notlar, h.elenen)
