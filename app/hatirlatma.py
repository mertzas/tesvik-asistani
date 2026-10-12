"""Çağrı son tarihi hatırlatması (2026-10-13; DURUM.md "Sıradaki: tarih hatırlatması").

Kullanıcının kontrol listesini açarak takibe aldığı (BasvuruTakibi) programın doğrulanmış bir çağrısı açıksa ve yeni
başvuranın son gününe (cagrilar.son_gun: ön kayıt son günü varsa o) tam ESIKLER gün kaldıysa, kuruluşun e-postası
doğrulanmış etkin kullanıcılarına bir e-posta gider. Bir kullanıcının o günkü bütün hatırlatmaları tek e-postada.

Gönderim kaydı tablosu yok: hatırlatma kalan gün tam eşiğe eşit olduğu gün gider, günlük iş zamanlayıcı kilidiyle tek
süreçte bir kez çalışır (app/scheduler). Tarih yalnız resmî duyurudan doğrulanmış çağrı satırından gelir (app/cagrilar);
tarihsiz çağrı için hatırlatma yok. Doğrulanmamış adrese gönderilmez (başkasının adresiyle açılmış hesap o adrese
hatırlatma yağdırmasın). SMTP yapılandırılmamışsa EmailService False döner; sonuç günlüğe yazılır.

    python -m app.hatirlatma --self-test
    python -m app.hatirlatma --onizle [YYYY-AA-GG]     (gönderilecekleri yazar, göndermez)
"""
from __future__ import annotations

import logging
import sys
from collections import defaultdict
from datetime import date
from html import escape
from typing import Callable

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ESIKLER = (14, 7, 3, 1)


def hatirlatmalar(db: Session, bugun: date | None = None) -> dict[str, dict]:
    """E-posta adresi → {"ad": ad, "kalemler": [{program, cagri, son_gun, kalan_gun, kaynak_url, tesvik_id}]}."""
    from app.cagrilar import durum, son_gun
    from app.models import BasvuruTakibi, Tesvik, User
    bugun = bugun or date.today()
    kalemler: dict[object, list[dict]] = defaultdict(list)
    for takip in db.query(BasvuruTakibi).all():
        t = db.get(Tesvik, takip.tesvik_id)
        if t is None or t.aktif_mi is False:
            continue
        for c in t.cagrilar or []:
            d = durum(c, bugun)
            if d["durum"] == "acik" and d["kalan_gun"] in ESIKLER:
                kalemler[takip.org_id].append({"program": t.baslik, "cagri": c.ad, "son_gun": son_gun(c),
                                               "kalan_gun": d["kalan_gun"], "kaynak_url": c.kaynak_url,
                                               "tesvik_id": t.id})
    sonuc: dict[str, dict] = {}
    for org_id, liste in kalemler.items():
        liste.sort(key=lambda k: (k["kalan_gun"], k["program"]))
        for u in db.query(User).filter(User.org_id == org_id, User.is_active.is_(True),
                                       User.email_dogrulama_zamani.isnot(None)).all():
            sonuc[u.email] = {"ad": u.full_name or "", "kalemler": liste}
    return sonuc


def eposta_metni(ad: str, kalemler: list[dict], uygulama_url: str) -> tuple[str, str, str]:
    """(konu, düz metin, HTML). Tarih biçimi GG.AA.YYYY; kaynak bağlantısı resmî çağrı duyurusu."""
    en_yakin = kalemler[0]["kalan_gun"]
    konu = (f"Teşvik Asistanı - Son başvuruya {en_yakin} gün kaldı" if len(kalemler) == 1 else
            f"Teşvik Asistanı - {len(kalemler)} başvurunun son günü yaklaşıyor")
    satirlar = [f"- {k['program']} ({k['cagri']}): son gün {k['son_gun']:%d.%m.%Y}, {k['kalan_gun']} gün kaldı. "
                f"Resmî duyuru: {k['kaynak_url']}" for k in kalemler]
    metin = (f"Merhaba {ad},\n\nTakip ettiğiniz programlarda yeni başvuru için son gün yaklaşıyor:\n"
             + "\n".join(satirlar)
             + f"\n\nKontrol listeniz: {uygulama_url}/dashboard\nTarihler kurumun duyurusundan alınmıştır; başvurmadan "
               "önce resmî duyurudan teyit edin. Bu hatırlatmayı durdurmak için programı Başvurularım'dan kaldırın."
               "\n\nTeşvik Asistanı")
    html = (f"<p>Merhaba <strong>{escape(ad)}</strong>,</p><p>Takip ettiğiniz programlarda yeni başvuru için son gün "
            "yaklaşıyor:</p><ul>"
            + "".join(f"<li><strong>{escape(k['program'])}</strong> ({escape(k['cagri'])}): son gün "
                      f"{k['son_gun']:%d.%m.%Y}, <strong>{k['kalan_gun']} gün kaldı</strong>. "
                      f"<a href=\"{escape(k['kaynak_url'])}\">Resmî duyuru</a></li>" for k in kalemler)
            + f"</ul><p><a href=\"{escape(uygulama_url)}/dashboard\">Kontrol listenize gidin</a>. Tarihler kurumun "
              "duyurusundan alınmıştır; başvurmadan önce resmî duyurudan teyit edin. Bu hatırlatmayı durdurmak için "
              "programı Başvurularım'dan kaldırın.</p>")
    return konu, metin, html


def gonder(db: Session, bugun: date | None = None,
           gonderici: Callable[[str, str, str, str], bool] | None = None) -> str:
    """Bugünün hatırlatmalarını gönderir; özet döner (zamanlayıcı günlüğü)."""
    from app.models import settings
    if gonderici is None:
        from app.email import EmailService
        gonderici = EmailService().send_email
    giden = basarisiz = 0
    for adres, x in hatirlatmalar(db, bugun).items():
        konu, metin, html = eposta_metni(x["ad"], x["kalemler"], settings.APP_URL)
        if gonderici(adres, konu, metin, html):
            giden += 1
        else:
            basarisiz += 1
    if basarisiz:
        logger.warning("Çağrı hatırlatması: %d e-posta gönderilemedi (SMTP yapılandırmasını denetleyin)", basarisiz)
    return f"{giden} hatırlatma gönderildi, {basarisiz} gönderilemedi"


def _self_test() -> int:
    from datetime import timedelta
    from types import SimpleNamespace as N
    from unittest.mock import patch

    bugun = date(2026, 10, 13)
    cagri = lambda kapanis, on_kayit=None, acilis=None: N(  # noqa: E731
        ad="2026-2", acilis=acilis, kapanis=kapanis, on_kayit_son=on_kayit, kaynak_url="https://kurum.gov.tr/c")
    t_ac = N(id=1, baslik="1501 Sanayi Ar-Ge", aktif_mi=True,
             cagrilar=[cagri(bugun + timedelta(days=11), on_kayit=bugun + timedelta(days=7))])
    t_esik_disi = N(id=2, baslik="Ajans", aktif_mi=True, cagrilar=[cagri(bugun + timedelta(days=5))])
    t_pasif = N(id=3, baslik="Kapalı", aktif_mi=False, cagrilar=[cagri(bugun + timedelta(days=7))])
    t_tarihsiz = N(id=4, baslik="Sürekli", aktif_mi=True, cagrilar=[cagri(None)])
    kayitlar = {1: t_ac, 2: t_esik_disi, 3: t_pasif, 4: t_tarihsiz}
    takipler = [N(org_id="o1", tesvik_id=i) for i in kayitlar] + [N(org_id="o2", tesvik_id=2)]
    kullanicilar = {"o1": [N(email="a@x.com", full_name="Ayşe"), N(email="b@x.com", full_name="Bora")], "o2": []}

    class Sorgu:
        def __init__(self, model):
            self.model = model

        def all(self):
            return takipler if self.model.__name__ == "BasvuruTakibi" else self.sonuc

        def filter(self, kosul, *rest):
            self.sonuc = kullanicilar[kosul.right.value]
            return self

    db = N(query=lambda model: Sorgu(model), get=lambda model, i: kayitlar.get(i))
    h = hatirlatmalar(db, bugun)
    giden = []
    with patch("app.models.settings", N(APP_URL="https://tesvik.example")):
        ozet = gonder(db, bugun, lambda adres, konu, metin, html: giden.append((adres, konu, metin, html)) or True)
    konu, metin, html = eposta_metni("A<b>", h["a@x.com"]["kalemler"], "https://u")
    sonuc = [
        ("ön kayıt son gününe göre 7 gün eşiği", list(h) == ["a@x.com", "b@x.com"]
         and [k["tesvik_id"] for k in h["a@x.com"]["kalemler"]] == [1]
         and h["a@x.com"]["kalemler"][0]["son_gun"] == bugun + timedelta(days=7)),
        ("eşik dışı, pasif, tarihsiz program yok", all(k["tesvik_id"] == 1 for v in h.values() for k in v["kalemler"])),
        ("kullanıcı başına tek e-posta", [g[0] for g in giden] == ["a@x.com", "b@x.com"] and ozet.startswith("2 ")),
        ("metinde tarih, kalan gün, resmî kaynak", "20.10.2026" in metin and "7 gün kaldı" in metin
         and "https://kurum.gov.tr/c" in metin and "Son başvuruya 7 gün kaldı" in konu),
        ("HTML kaçışlı", "A&lt;b&gt;" in html and "<b>" not in html.replace("<strong>", "")),
        ("uygulama bağlantısı", "https://tesvik.example/dashboard" in giden[0][2]),
        ("başarısız gönderim sayılır", gonder(db, bugun, lambda *a: False).startswith("0 hatırlatma gönderildi, 2")),
    ]
    g = sum(1 for _, ok in sonuc if ok)
    for ad, ok in sonuc:
        print(f"  [{'OK' if ok else 'HATA'}] {ad}")
    print(f"hatirlatma self-test: {g}/{len(sonuc)}")
    return 0 if g == len(sonuc) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--onizle" in sys.argv:
        from app.models import SessionLocal
        i = sys.argv.index("--onizle")
        gun = date.fromisoformat(sys.argv[i + 1]) if len(sys.argv) > i + 1 else None
        db = SessionLocal()
        try:
            for adres, x in hatirlatmalar(db, gun).items():
                print(adres, [(k["program"][:50], k["kalan_gun"]) for k in x["kalemler"]])
        finally:
            db.close()
        sys.exit(0)
    print(__doc__)
