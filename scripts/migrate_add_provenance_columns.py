"""
SQLite tablosuna yeni eklenen provenance ve tazelik kolonlarını (son_tarama_tarihi,
html_icerik_hash, cikarim_guven_skoru, cikarim_kanitlari) ekleyen migration betiği.
"""
from sqlalchemy import text
from app.models import engine

def migrate():
    with engine.connect() as conn:
        columns = [
            ("son_tarama_tarihi", "DATETIME"),
            ("html_icerik_hash", "VARCHAR"),
            ("cikarim_guven_skoru", "FLOAT"),
            ("cikarim_kanitlari", "JSON"),
        ]
        for col_name, col_type in columns:
            try:
                conn.execute(text(f"ALTER TABLE tesvikler ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"✅ Colon eklendi: {col_name}")
            except Exception:
                # Kolon zaten varsa pas geç
                pass

if __name__ == "__main__":
    migrate()
