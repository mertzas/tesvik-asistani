"""
Eski tesvikler.db'ye yeni kolonları ekle (ALTER TABLE).
"""
import sqlite3

DB_PATH = "data/tesvikler.db"

# Yeni kolonlar ve tipleri
NEW_COLUMNS = [
    ("tutari_min", "REAL"),
    ("tutari_max", "REAL"),
    ("tutari_hesaplama_kriteri", "TEXT"),
    ("tutari_hesaplama_formulu", "TEXT"),
    ("basvuru_sartlari", "JSON"),
    ("gerekli_belgeler", "JSON"),
    ("basvuru_yeri", "TEXT"),
    ("basvuru_suresi", "TEXT"),
    ("destek_verilme_suresi", "TEXT"),
]

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# Mevcut kolonları kontrol et
cur.execute("PRAGMA table_info(tesvikler)")
existing_cols = {row[1] for row in cur.fetchall()}
print(f"Mevcut kolonlar: {len(existing_cols)}")

for col_name, col_type in NEW_COLUMNS:
    if col_name not in existing_cols:
        try:
            cur.execute(f"ALTER TABLE tesvikler ADD COLUMN {col_name} {col_type}")
            print(f"+ {col_name} ({col_type}) eklendi")
        except sqlite3.OperationalError as e:
            print(f"! {col_name}: {e}")
    else:
        print(f"- {col_name} zaten var")

con.commit()
con.close()
print("Migration tamamlandı!")
