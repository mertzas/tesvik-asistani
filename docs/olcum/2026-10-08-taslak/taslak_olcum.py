"""Başvuru ön taslağı — gerçek modelle ölçüm (2026-10-08). Kullanıcı verisine dokunmaz: uç nokta yerine
app.basvuru_taslagi.uret() doğrudan çağrılır; sentetik profiller G_persona_esles.py'den, programlar canlı DB'den.

  python taslak_olcum.py --kuru    istemleri ve tahmini token sayısını yazar (ücretsiz, ağ yok)
  python taslak_olcum.py --canli   3 ücretli çağrı (onaylı, ≤ ~0,15 USD); ilk hata çağrıda durur
  python taslak_olcum.py --dok     birebir istemleri istem_<n>.md olarak yazar (Aşama C yöntemi: API bakiyesi yokken
                                   oturum modeli aynı istemle yanıtlar ve yanit_<n>.md'ye yazar)
  python taslak_olcum.py --elle    yanit_<n>.md'leri uygulamanın aynı birleştirme + denetiminden geçirir
                                   (olcum_elle.json; üretici "oturum modeli" olarak etiketlenir)

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


SAYI = re.compile(r"(\d[\d.,]*)(\s*(?:milyon|Milyon|bin|Bin))?")


def _degerler(metin: str) -> set[float]:
    """Metindeki sayıları DEĞER olarak çıkarır: '32000000.0', '32.000.000', '32 milyon' aynı sayıdır."""
    sonuc = set()
    for ham, carpan in SAYI.findall(metin):
        s = ham.rstrip(".,")
        if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):      # 1.000.000 / 1.000.000,50
            s = s.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d+,\d+", s):                       # 1,5
            s = s.replace(",", ".")
        try:
            v = float(s)
        except ValueError:
            continue
        carpan = carpan.strip().lower()
        sonuc.add(round(v * (1e6 if carpan == "milyon" else 1e3 if carpan == "bin" else 1), 4))
    return sonuc


def denetle(model_metni: str, baglam_metni: str) -> dict:
    basliklar = re.findall(r"^##\s+(.+)$", model_metni, re.M)
    sira_tamam = [b.strip() for b in basliklar[:5]] == list(BT.BOLUMLER)
    govde = re.sub(r"^##\s+\d\..*$", "", model_metni, flags=re.M)   # başlık numaralarını say
    govde = re.sub(r"\[DOLDURUN[^\]]*\]", "", govde)
    supheli = sorted(_degerler(govde) - _degerler(baglam_metni))
    return {"baslik_sirasi_dogru": sira_tamam, "basliklar": basliklar,
            "doldurun_sayisi": len(re.findall(r"\[DOLDURUN", model_metni)),
            "kelime": len(model_metni.split()), "baglamda_olmayan_sayilar": supheli}


def _vaka(db, persona, tid):
    t = db.get(Tesvik, tid)
    profil = profil_sozlugu(FinancialProfile(**G.PERSONA[persona]))
    baglam = BT.baglam(t, profil)
    return t, maddeler(t), baglam, f"BAĞLAM:\n{baglam}\n\nBu program için başvuru ön taslağını yaz."


def dok():
    db = SessionLocal()
    for n, (persona, tid) in enumerate(VAKALAR, 1):
        t, _, _, istem = _vaka(db, persona, tid)
        with open(os.path.join(HERE, f"istem_{n}.md"), "w", encoding="utf-8") as f:
            f.write(f"# SİSTEM\n\n{BT.SISTEM}\n\n# KULLANICI\n\n{istem}\n")
        print(f"istem_{n}.md yazıldı ({persona} → {t.baslik})")
    db.close()


def elle():
    db = SessionLocal()
    sonuc = []
    for n, (persona, tid) in enumerate(VAKALAR, 1):
        yol = os.path.join(HERE, f"yanit_{n}.md")
        if not os.path.exists(yol):
            print(f"[{n}] yanit_{n}.md yok, atlandı")
            continue
        t, liste, baglam, _ = _vaka(db, persona, tid)
        metin = open(yol, encoding="utf-8").read().strip()
        with open(os.path.join(HERE, f"taslak_elle_{n}.md"), "w", encoding="utf-8") as f:
            f.write(f"<!-- {persona} | {t.kurum} — {t.baslik} | üretici: oturum modeli, birebir istem (üretim modeli DEĞİL) -->"
                    f"\n\n{BT.birlestir(metin, liste)}")
        d = denetle(metin, baglam)
        sonuc.append({"vaka": n, "persona": persona, "tesvik_id": tid, "program": t.baslik, "denetim": d})
        print(f"[{n}] {t.baslik[:45]}: başlık sırası {d['baslik_sirasi_dogru']}, [DOLDURUN] {d['doldurun_sayisi']}, "
              f"kelime {d['kelime']}, bağlamda olmayan sayılar {d['baglamda_olmayan_sayilar']}")
    db.close()
    with open(os.path.join(HERE, "olcum_elle.json"), "w", encoding="utf-8") as f:
        json.dump({"uretici": "oturum modeli (Aşama C yöntemi: birebir sistem + kullanıcı istemi, API bakiyesi yok)",
                   "sonuclar": sonuc}, f, ensure_ascii=False, indent=1)


def main(canli: bool):
    db = SessionLocal()
    sonuc = []
    for n, (persona, tid) in enumerate(VAKALAR, 1):
        t, liste, baglam, istem = _vaka(db, persona, tid)
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
    elif "--dok" in sys.argv:
        dok()
    elif "--elle" in sys.argv:
        elle()
    else:
        print(__doc__)
