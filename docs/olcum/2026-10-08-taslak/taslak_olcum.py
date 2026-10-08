"""Başvuru ön taslağı — gerçek modelle ölçüm (2026-10-08). Kullanıcı verisine dokunmaz: uç nokta yerine
app.basvuru_taslagi.uret() doğrudan çağrılır; sentetik profiller G_persona_esles.py'den, programlar canlı DB'den.

  python taslak_olcum.py --kuru    istemleri ve tahmini token sayısını yazar (ücretsiz, ağ yok)
  python taslak_olcum.py --canli   3 ücretli çağrı (onaylı, ≤ ~0,15 USD); ilk hata çağrıda durur

Çıktılar bu klasöre: taslak_<n>.md (taslak) ve olcum.json (token, süre, otomatik denetimler).
Otomatik denetimler: 5 başlık sırayla var mı; modelin yazdığı her sayı bağlamda geçiyor mu (uydurma rakam adayı);
[DOLDURUN] sayısı; kelime sayısı (hedef 500-900).
"""
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "docs", "olcum", "2026-10-07-denetim2"))

import G_persona_esles as G  # noqa: E402
from app import basvuru_taslagi as BT  # noqa: E402
from app.basvuru_listesi import maddeler  # noqa: E402
from app.models import FinancialProfile, SessionLocal, Tesvik  # noqa: E402
from app.rag import profil_sozlugu  # noqa: E402

VAKALAR = [  # (persona, tesvik_id): her biri farklı kurum/program türü
    ("12 Bursa metal sentetik", 8),      # KOSGEB Kapasite Geliştirme
    ("2 Izmir tekstil", 9),              # KOSGEB Küresel Rekabetçilik
    ("3 Ankara girisim", 49),            # TÜBİTAK 1812 BiGG Yatırım
]
# Varsayılan fiyat (USD / milyon token) — DOĞRULANMADI; raporda tahmin olarak geçer.
FIYAT_GIRIS, FIYAT_CIKIS = 3.0, 15.0


def denetle(model_metni: str, baglam_metni: str) -> dict:
    basliklar = re.findall(r"^##\s+(.+)$", model_metni, re.M)
    sira_tamam = [b.strip() for b in basliklar[:5]] == list(BT.BOLUMLER)
    baglam_sayilari = set(re.findall(r"\d[\d.,]*", baglam_metni))
    govde = re.sub(r"^##\s+\d\..*$", "", model_metni, flags=re.M)   # başlık numaralarını say
    govde = re.sub(r"\[DOLDURUN[^\]]*\]", "", govde)
    supheli = sorted({s.rstrip(".,") for s in re.findall(r"\d[\d.,]*", govde)} - {s.rstrip(".,") for s in baglam_sayilari})
    return {"baslik_sirasi_dogru": sira_tamam, "basliklar": basliklar,
            "doldurun_sayisi": len(re.findall(r"\[DOLDURUN", model_metni)),
            "kelime": len(model_metni.split()), "baglamda_olmayan_sayilar": supheli}


def main(canli: bool):
    db = SessionLocal()
    sonuc = []
    for n, (persona, tid) in enumerate(VAKALAR, 1):
        t = db.get(Tesvik, tid)
        profil = profil_sozlugu(FinancialProfile(**G.PERSONA[persona]))
        liste = maddeler(t)
        baglam = BT.baglam(t, profil)
        istem = f"BAĞLAM:\n{baglam}\n\nBu program için başvuru ön taslağını yaz."
        tahmini = (len(BT.SISTEM) + len(istem)) // 3  # Türkçe metinde kabaca 3 karakter/token
        print(f"[{n}] {persona} → {t.baslik} | istem ~{tahmini} token")
        if not canli:
            continue
        t0 = time.time()
        try:
            metin, kullanim = BT._claude_istek(BT.SISTEM, istem)
        except Exception as e:
            print(f"    ÇAĞRI BAŞARISIZ: {type(e).__name__}: {str(e)[:300]}")
            sonuc.append({"vaka": n, "persona": persona, "tesvik_id": tid, "hata": f"{type(e).__name__}: {str(e)[:300]}"})
            break  # ilk hatada dur: aynı nedenle (bakiye/anahtar) diğerleri de düşer
        sure = round(time.time() - t0, 1)
        tam = BT.birlestir(metin, liste)
        with open(os.path.join(HERE, f"taslak_{n}.md"), "w", encoding="utf-8") as f:
            f.write(f"<!-- {persona} | {t.kurum} — {t.baslik} | model {BT.settings.CLAUDE_MODEL} -->\n\n{tam}")
        maliyet = None
        if kullanim.get("giris") is not None and kullanim.get("cikis") is not None:
            maliyet = round(kullanim["giris"] * FIYAT_GIRIS / 1e6 + kullanim["cikis"] * FIYAT_CIKIS / 1e6, 4)
        kayit = {"vaka": n, "persona": persona, "tesvik_id": tid, "program": t.baslik, "sure_sn": sure,
                 "kullanim": kullanim, "tahmini_maliyet_usd": maliyet, "denetim": denetle(metin, baglam)}
        sonuc.append(kayit)
        print(f"    {sure} sn, token giriş/çıkış {kullanim.get('giris')}/{kullanim.get('cikis')}, "
              f"~{maliyet} USD, denetim {kayit['denetim']['baslik_sirasi_dogru']}, "
              f"[DOLDURUN] {kayit['denetim']['doldurun_sayisi']}, şüpheli sayı {kayit['denetim']['baglamda_olmayan_sayilar']}")
    db.close()
    if canli:
        with open(os.path.join(HERE, "olcum.json"), "w", encoding="utf-8") as f:
            json.dump({"model": BT.settings.CLAUDE_MODEL, "fiyat_varsayimi_usd_mtok": [FIYAT_GIRIS, FIYAT_CIKIS],
                       "sonuclar": sonuc}, f, ensure_ascii=False, indent=1)
        toplam = sum(s.get("tahmini_maliyet_usd") or 0 for s in sonuc)
        print(f"\nToplam tahmini maliyet: ~{toplam:.4f} USD ({len([s for s in sonuc if 'hata' not in s])} başarılı çağrı)")


if __name__ == "__main__":
    if "--canli" in sys.argv:
        main(canli=True)
    elif "--kuru" in sys.argv:
        main(canli=False)
    else:
        print(__doc__)
