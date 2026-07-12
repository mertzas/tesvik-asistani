"""
Hazine Tesvik Belgesi (Yatirim Tesvik Sistemi) icin veri kaynagi.

KOSGEB/TUBITAK/KGF'nin aksine, yatirim tesvik sistemi tek tek "program"
sayfalari halinde crawl edilebilecek bir liste sunmuyor: bu, Ticaret
Bakanligi'nin yonettigi tek bir sertifika rejimi olup 4 destek kategorisine
ayriliyor (Genel, Bolgesel, Buyuk Olcekli, Stratejik Yatirimlar). Bu yuzden
scrape yerine, Ticaret Bakanligi / yatirimadestek.gov.tr kaynaklarina dayanan
kucuk, elle derlenmis (curated) bir veri seti kullaniyoruz.

Kaynaklar (guncelligi periyodik kontrol edilmeli):
- https://www.yatirimadestek.gov.tr/pdf/assets/upload/dosyalar/sunum-yatirim_tesvik_uygulamalari.pdf
- https://ticaret.gov.tr/data/5b87fac913b8761160fa1cf0/Devlet%20Yard%C4%B1mlar%C4%B1%20Rehberi%202022.pdf
"""
from app.models import SessionLocal, Tesvik, init_db

KAYNAK_URL = "https://www.yatirimadestek.gov.tr/pdf/assets/upload/dosyalar/sunum-yatirim_tesvik_uygulamalari.pdf"

TESVIK_KATEGORILERI = [
    {
        "baslik": "Genel Teşvik Uygulamaları",
        "ozet": (
            "Bölgesel, büyük ölçekli veya stratejik yatırım teşvik "
            "kapsamına girmeyen, tüm illerde asgari sabit yatırım tutarını "
            "(1-2. bölgelerde 1.000.000 TL, diğer bölgelerde 500.000 TL) "
            "sağlayan yatırımlar için geçerlidir."
        ),
        "detay": (
            "Destek unsurlari: KDV istisnasi, gumruk vergisi muafiyeti, "
            "6. bolgede gelir vergisi stopaji destegi. Tesvikten "
            "yararlanamayacak yatirim konulari mevzuatta ayrica listelenir."
        ),
    },
    {
        "baslik": "Bölgesel Teşvik Uygulamaları",
        "ozet": (
            "Ulke, gelismislik duzeyine gore 6 bolgeye ayrilir; her bolgede "
            "belirlenen sektorlerdeki yatirimlar bolgeye ozgu vergi "
            "indirimi ve digre destek oranlarindan yararlanir."
        ),
        "detay": (
            "Destek unsurlari: vergi indirimi (bolgeye gore degisen oran ve "
            "sure), sigorta primi isveren hissesi destegi, faiz/kar payi "
            "destegi, yatirim yeri tahsisi. Bolge ve sektor eslesmesi "
            "yatirim tesvik sistemi teblig ve kararlarinda yer alir."
        ),
    },
    {
        "baslik": "Büyük Ölçekli Yatırımların Teşviki",
        "ozet": (
            "Mevzuatta tanimlanan onemli sanayi sektorlerinde (rafineri, "
            "kimyasal madde, otomotiv ana sanayi, elektronik vb.) belirli "
            "asgari yatirim tutarini asan buyuk olcekli yatirimlara "
            "yoneliktir."
        ),
        "detay": (
            "Destek unsurlari bolgesel tesvige benzer ancak daha yuksek "
            "vergi indirimi orani ve daha uzun destek suresi icerir; "
            "sektor bazinda asgari yatirim tutarlari mevzuatta ayri ayri "
            "belirtilir."
        ),
    },
    {
        "baslik": "Stratejik Yatırımların Teşviki",
        "ozet": (
            "Ithalat bagimliligi yuksek urunlerin yurt icinde uretimini "
            "hedefleyen, belirlenen asgari yatirim ve katma deger "
            "kriterlerini saglayan yatirimlar icin en yuksek destek "
            "seviyesini sunar."
        ),
        "detay": (
            "Destek unsurlari: yuksek oranli vergi indirimi, gumruk vergisi "
            "muafiyeti, KDV istisnasi/iadesi, sigorta primi ve faiz/kar "
            "payi destegi, yatirim yeri tahsisi. Kriterler (asgari tutar, "
            "yerlilik/ithal ikamesi orani vb.) Cumhurbaskani karari ile "
            "yatirim tesvik mevzuatinda belirlenir."
        ),
    },
]


def run():
    init_db()
    db = SessionLocal()
    seen_titles = {t for (t,) in db.query(Tesvik.baslik).filter(Tesvik.kurum == "Hazine/Ticaret Bakanligi").all()}

    new_count = 0
    for kategori in TESVIK_KATEGORILERI:
        if kategori["baslik"] in seen_titles:
            continue
        db.add(
            Tesvik(
                kurum="Hazine/Ticaret Bakanligi",
                baslik=kategori["baslik"],
                ozet=kategori["ozet"],
                detay=kategori["detay"],
                hedef_kitle="yatirimci/sanayi",
                kaynak_url=None,  # Tüm kayıtlar aynı URL kullanıyor - UNIQUE constraint kaçınmak için
            )
        )
        new_count += 1

    db.commit()
    db.close()
    print(f"{new_count} yeni tesvik kategorisi eklendi.")


if __name__ == "__main__":
    run()
