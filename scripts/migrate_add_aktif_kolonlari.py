"""
Eski tesvikler.db'ye aktif_mi / durum_notu kolonlarini ekler (ALTER TABLE).
"""
import sqlite3

DB_PATH = "data/tesvikler.db"

NEW_COLUMNS = [
    ("aktif_mi", "BOOLEAN"),
    ("durum_notu", "TEXT"),
]

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("PRAGMA table_info(tesvikler)")
existing_cols = {row[1] for row in cur.fetchall()}

for col_name, col_type in NEW_COLUMNS:
    if col_name not in existing_cols:
        cur.execute(f"ALTER TABLE tesvikler ADD COLUMN {col_name} {col_type}")
        print(f"+ {col_name} ({col_type}) eklendi")
    else:
        print(f"- {col_name} zaten var")

con.commit()
con.close()
