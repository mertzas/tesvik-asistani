"""
Tarim sektorundeki tesvikler arasinda sadece belirli bir alt kategoriye
(orn. hayvancilik) ozel olanlari isaretler. Boylece sektor genel "tarim"
secildiginde bu tur dar kapsamli programlar, kategori acikca belirtilmedigi
surece one cikmaz; "genel" tarim programlari (arastirma, makine, kooperatif,
kirsal turizm, organik) her tarim profiline esit derecede uygun kabul edilir.

Calistirma: python scripts/backfill_alt_kategori.py
"""
import json
import sqlite3

DB_PATH = "data/tesvikler.db"

ALT_KATEGORILER = {
    355: "hayvancilik",  # Hayvancilik Destekleri
}


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    for tesvik_id, alt_kategori in ALT_KATEGORILER.items():
        cur.execute("SELECT uygunluk_kriterleri FROM tesvikler WHERE id=?", (tesvik_id,))
        row = cur.fetchone()
        if row is None:
            print(f"UYARI: id={tesvik_id} bulunamadi, atlandi.")
            continue
        kriterler = json.loads(row[0]) if row[0] else {}
        kriterler["alt_kategori"] = alt_kategori
        cur.execute(
            "UPDATE tesvikler SET uygunluk_kriterleri=? WHERE id=?",
            (json.dumps(kriterler, ensure_ascii=False), tesvik_id),
        )
        print(f"id={tesvik_id} -> alt_kategori={alt_kategori}")
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
