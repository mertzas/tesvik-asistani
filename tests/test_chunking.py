import pytest
from app.models import SessionLocal, Tesvik, TesvikChunk, init_db
from app.chunking import split_text_to_parents, split_parent_to_children, create_parent_child_chunks

def test_split_text_to_parents_structural():
    text = """
    MADDE 1 - Tanımlar ve Kapsam
    Bu destek KOBİ'lerin dijital dönüşüm projelerini kapsar.

    MADDE 2 - Başvuru Şartları
    Başvuru sahibi imalat veya yazılım sektöründe en az 2 yıl faal olmalıdır.

    BAŞVURU ŞARTLARI
    Destek üst limiti 750.000 TL'dir. Destek oranı %60 olarak uygulanır.
    """
    parents = split_text_to_parents(text)
    assert len(parents) >= 3
    assert "MADDE 1" in parents[0]["title"]
    assert "MADDE 2" in parents[1]["title"]
    assert "BAŞVURU ŞARTLARI" in parents[2]["title"].upper()

def test_split_parent_to_children():
    parent_text = "Birinci cümle burada yer alıyor. İkinci cümle ise destek şartlarını açıklıyor. Üçüncü cümle son detayları veriyor."
    children = split_parent_to_children(parent_text, target_size=50)
    assert len(children) >= 2
    assert all(len(c) <= 80 for c in children)

def test_create_parent_child_chunks_db():
    init_db()
    db = SessionLocal()
    
    # Test teşvik oluştur
    tesvik = db.query(Tesvik).first()
    if not tesvik:
        tesvik = Tesvik(
            kurum="KOSGEB",
            baslik="Test Chunking Destek",
            ozet="Test özeti",
            detay="MADDE 1\nKapsam metni detaylı.\n\nMADDE 2\nBaşvuru şartları detaylı.",
            kaynak_url="https://test.chunking.gov.tr"
        )
        db.add(tesvik)
        db.commit()

    p_cnt, c_cnt = create_parent_child_chunks(tesvik.id, f"{tesvik.baslik}\n{tesvik.detay}", db)
    assert p_cnt > 0
    assert c_cnt >= p_cnt

    # DB kontrolü
    parents_db = db.query(TesvikChunk).filter(TesvikChunk.tesvik_id == tesvik.id, TesvikChunk.chunk_type == "parent").all()
    children_db = db.query(TesvikChunk).filter(TesvikChunk.tesvik_id == tesvik.id, TesvikChunk.chunk_type == "child").all()
    
    assert len(parents_db) == p_cnt
    assert len(children_db) == c_cnt
    assert all(c.parent_id is not None for c in children_db)

    db.close()
