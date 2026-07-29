"""
Türkçe mevzuat ve teşvik kılavuzu metinlerini yapısal olarak bölen
Domain-Aware Parent-Child Chunking Modülü.

Parent Chunk: Programa ait tam bir madde/bölüm (800-1500 karakter). LLM çıkarımı
             ve cevap üretimi için bütünsel bağlam sağlar.
Child Chunk:  Madde altındaki bent/cümle (150-300 karakter). Hassas arama ve
             birebir alıntı eşleme için kullanılır.
"""
import re
import math
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models import Tesvik, TesvikChunk, SessionLocal


# Türkçe mevzuat ve kılavuzlarda yapısal bölüm ayıraçları
STRUCTURAL_PATTERNS = [
    r"(?:MADDE\s+\d+|BAŞLIK\s+\d+|BÖLÜM\s+\d+)",
    r"(?:BAŞVURU ŞARTLARI|DESTEK KAPSAMI|DESTEK ORANI VE LİMİTİ|GEREKLİ BELGELER|BAŞVURU DÖNEMİ)",
]

COMBINED_STRUCTURAL_REGEX = re.compile("|".join(STRUCTURAL_PATTERNS), re.IGNORECASE)


def _simple_embedding(text: str, dim: int = 64) -> List[float]:
    """Yerel hafif embedding fonksiyonu (Vektör indeksi için - dış kütüphane gerektirmez).
    Metindeki kelimelerin hash'leri üzerinden 64 boyutlu normalize edilmiş vektör üretir."""
    words = re.findall(r"\w+", text.lower())
    vec = [0.0] * dim
    if not words:
        return vec
    for w in words:
        h = int(math.sin(sum(ord(c) for c in w)) * 10000) % dim
        vec[h] += 1.0
    
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 4) for v in vec]
    return vec


def split_text_to_parents(full_text: str, target_size: int = 1000) -> List[Dict[str, Any]]:
    """Metni önce yapısal maddelerden (Madde X, Başvuru Şartları vb.),
    bulamazsa paragraf sınırlarından bölerek Parent Chunk'ları üretir."""
    if not full_text:
        return []

    # Yapısal bölünme dene
    matches = list(COMBINED_STRUCTURAL_REGEX.finditer(full_text))
    parents = []

    if len(matches) > 1:
        for i in range(len(matches)):
            start_idx = matches[i].start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            chunk_text = full_text[start_idx:end_idx].strip()
            if chunk_text:
                title = matches[i].group(0)
                parents.append({"title": title, "text": chunk_text})
    else:
        # Paragraf bazlı böl
        paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
        curr_text = ""
        for p in paragraphs:
            if len(curr_text) + len(p) <= target_size:
                curr_text += ("\n\n" + p if curr_text else p)
            else:
                if curr_text:
                    parents.append({"title": "Genel Bölüm", "text": curr_text})
                curr_text = p
        if curr_text:
            parents.append({"title": "Genel Bölüm", "text": curr_text})

    if not parents:
        parents.append({"title": "Ana Metin", "text": full_text.strip()})

    return parents


def split_parent_to_children(parent_text: str, target_size: int = 250) -> List[str]:
    """Parent metnini cümle ve bent sınırlarına göre küçük Child Chunk'lara böler."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", parent_text)
    children = []
    curr_child = ""

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(curr_child) + len(s) <= target_size:
            curr_child += (" " + s if curr_child else s)
        else:
            if curr_child:
                children.append(curr_child)
            curr_child = s

    if curr_child:
        children.append(curr_child)

    return children


def create_parent_child_chunks(tesvik_id: int, full_text: str, db: Session) -> Tuple[int, int]:
    """Bir teşvik kaydı için Parent-Child Chunk'ları oluşturur ve veritabanına kaydeder."""
    # Eski chunk'ları temizle
    db.query(TesvikChunk).filter(TesvikChunk.tesvik_id == tesvik_id).delete()
    db.flush()

    parents = split_text_to_parents(full_text)
    parent_count = 0
    child_count = 0

    for p_idx, p_data in enumerate(parents):
        p_chunk = TesvikChunk(
            tesvik_id=tesvik_id,
            parent_id=None,
            chunk_type="parent",
            metin=p_data["text"],
            embedding=_simple_embedding(p_data["text"]),
            metadata_json={"title": p_data["title"], "parent_index": p_idx}
        )
        db.add(p_chunk)
        db.flush()
        parent_count += 1

        children = split_parent_to_children(p_data["text"])
        for c_idx, c_text in enumerate(children):
            c_chunk = TesvikChunk(
                tesvik_id=tesvik_id,
                parent_id=p_chunk.id,
                chunk_type="child",
                metin=c_text,
                embedding=_simple_embedding(c_text),
                metadata_json={"parent_title": p_data["title"], "child_index": c_idx}
            )
            db.add(c_chunk)
            child_count += 1

    db.commit()
    return parent_count, child_count


def process_all_tesvik_chunking(db: Session) -> Dict[str, int]:
    """Veritabanındaki tüm teşvikler için Parent-Child Chunking işlemini yürütür."""
    tesvikler = db.query(Tesvik).all()
    total_parents = 0
    total_children = 0

    for t in tesvikler:
        metin = f"{t.baslik}\n\n{t.ozet or ''}\n\n{t.detay or ''}"
        p_cnt, c_cnt = create_parent_child_chunks(t.id, metin, db)
        total_parents += p_cnt
        total_children += c_cnt

    return {
        "tesvik_sayisi": len(tesvikler),
        "toplam_parent_chunk": total_parents,
        "toplam_child_chunk": total_children,
    }
