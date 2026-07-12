#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
58 teşvik programını database'e aktar
"""
import sqlite3
import json

TESVIKLER = [
    {"kurum": "KOSGEB", "baslik": "İş Kurma Desteği", "ozet": "Yeni kurulan işletmelerin kurulması ve ilk dönemlerinde ayakta kalması için verilen destek.", "detay": "Girişim giderlerine yönelik yardım sağlanır.", "hedef_kitle": "Girişimciler", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "KOSGEB", "baslik": "İş Geliştirme Desteği", "ozet": "0-3 yaş arası işletmelerin üretim kapasitesini artırmak için destek.", "detay": "Personel, ekipman ve yazılım yatırımlarını finanse eder.", "hedef_kitle": "İmalat/Bilişim", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "KOSGEB", "baslik": "Kapasite Geliştirme Programı", "ozet": "KOBİ'lerin verimliliğini ve kurumsal kapasitesini artırmayı hedefleyen destek.", "detay": "Personel, makine, yazılım ve hizmet alımlarını kapsar.", "hedef_kitle": "KOBİ", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "KOSGEB", "baslik": "Küresel Rekabetçilik Destek Programı", "ozet": "Yüksek teknoloji sektörlerinde yenilikçi ürün geliştirme ve R&D desteği.", "detay": "Uluslararası işbirlikleri ve ihracat destekleri de kapsar.", "hedef_kitle": "Teknoloji şirketleri", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "KOSGEB", "baslik": "Dijital Dönüşüm Destek Programı", "ozet": "KOBİ'lerin iş süreçlerini dijitalleştirmek için makine ve yazılım desteği.", "detay": "Kredi ve faiz desteği kombinasyonu sağlanır.", "hedef_kitle": "İmalat KOBİ", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "KOSGEB", "baslik": "İstihdamı Koruma Desteği", "ozet": "İmalat sektöründe istihdamın korunması için aylık performans desteği.", "detay": "Kredi finansmanı ve nakit destek seçenekleri vardır.", "hedef_kitle": "İmalat işletmeleri", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "KOSGEB", "baslik": "Teknoloji Merkezi Kuruluş Desteği", "ozet": "Ar-Ge ve inovasyon odaklı teknoloji merkezlerinin kurulmasına yönelik destek.", "detay": "Altyapı ve ekipman yatırımlarını kapsar.", "hedef_kitle": "Girişimciler/Üniversiteler", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "KOSGEB", "baslik": "Teknoloji Merkezi Performans Desteği", "ozet": "Kuruluş desteği almış teknoloji merkezlerinin operasyonel maliyetleri desteklenir.", "detay": "Aylık performans-temelli destek sağlanır.", "hedef_kitle": "Teknoloji merkezleri", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "KOSGEB", "baslik": "SEGEM Sektörel Gelişim Merkezi Desteği", "ozet": "KOBİ'lere modern yönetim uygulamalarının verilmesi sağlayan merkezlerin kurulması.", "detay": "Sektör geliştirme işletmelerine tam destek sağlanır.", "hedef_kitle": "Sektör merkezleri", "link": "https://www.kosgeb.gov.tr"},
    {"kurum": "TÜBİTAK", "baslik": "1001 - Bilimsel Araştırma Projelerine Destek", "ozet": "Üniversite ve araştırma enstitülerine temel bilim araştırmaları için finansman.", "detay": "Personel, ekipman ve sarf malzeme masraflarını karşılar.", "hedef_kitle": "Araştırma kurumları", "link": "https://www.tubitak.gov.tr"},
    {"kurum": "TÜBİTAK", "baslik": "1511 - Sanayi Odaklı Ar-Ge Projeleri", "ozet": "Sanayi kuruluşlarının teknoloji geliştirme projelerine finansman desteği.", "detay": "KOBİ'ler için yüksek oranlı destek sağlanır.", "hedef_kitle": "Sanayi kuruluşları", "link": "https://www.tubitak.gov.tr"},
    {"kurum": "TÜBİTAK", "baslik": "TEYDEB - Teknoloji Geliştirme Bölgeleri Desteği", "ozet": "Teknoloji Geliştirme Bölgeleri'ndeki şirketlere kuruluş ve işletme desteği.", "detay": "Vergi indirimi ve gümrük muafiyeti kapsar.", "hedef_kitle": "Teknoloji şirketleri", "link": "https://www.tubitak.gov.tr"},
    {"kurum": "TÜBİTAK", "baslik": "ULUSLARARASI AR-GE İŞBİRLİKLERİ", "ozet": "Uluslararası araştırma işbirliğini destekleyen çeşitli program alternatifleri.", "detay": "İkili ve çok taraflı işbirilikler kapsar.", "hedef_kitle": "Araştırma kurumları", "link": "https://www.tubitak.gov.tr"},
    {"kurum": "TÜBİTAK", "baslik": "Lisans Öğrencileri Araştırma Bursları", "ozet": "Lisans öğrencilerine verilen bilimsel araştırma bursları.", "detay": "Aylık burs ve araştırma desteği sağlanır.", "hedef_kitle": "Lisans öğrencileri", "link": "https://www.tubitak.gov.tr"},
    {"kurum": "TÜBİTAK", "baslik": "Yüksek Lisans Öğrencileri Araştırma Bursları", "ozet": "Yüksek lisans öğrencilerine verilen araştırma destekleme bursları.", "detay": "Tez araştırması için mali destek.", "hedef_kitle": "Yüksek lisans öğrencileri", "link": "https://www.tubitak.gov.tr"},
    {"kurum": "TÜBİTAK", "baslik": "Doktora Öğrencileri Araştırma Bursları", "ozet": "Doktora öğrencilerine doktora tez araştırması için finansman.", "detay": "Uluslararası konferans katılımı da desteklenir.", "hedef_kitle": "Doktora öğrencileri", "link": "https://www.tubitak.gov.tr"},
    {"kurum": "KGF", "baslik": "Kredi Garantisi Fonu", "ozet": "KOBİ'lerin banka kredilerine garanti sağlanır. Kredilerin %80'ine kadar garanti.", "detay": "Kamu bankaları ve özel bankalar üzerinden verilir.", "hedef_kitle": "KOBİ", "link": "https://www.kgf.org.tr"},
    {"kurum": "KGF", "baslik": "Kadın Girişimci Programı", "ozet": "Kadın girişimcilerin kuruluş ve işletme masrafları için kredi garantisi.", "detay": "Uygun faiz oranları ve esnek geri ödeme şartları vardır.", "hedef_kitle": "Kadın girişimciler", "link": "https://www.kgf.org.tr"},
    {"kurum": "KGF", "baslik": "Yüksek Teknoloji İhracatı Destekleme", "ozet": "Yüksek teknoloji ürünleri ihraç eden şirketlere finansman desteği.", "detay": "İhracat öncesi finansman da sağlanır.", "hedef_kitle": "Teknoloji ihracatçıları", "link": "https://www.kgf.org.tr"},
    {"kurum": "Ticaret Bakanlığı", "baslik": "Yeni Nesil İhracat Destekleri", "ozet": "Modern ihracat stratejileri ve prefinansman modeli kullanarak ihracatı artırma.", "detay": "Dijital platform yardımı da kapsar.", "hedef_kitle": "İhracat yapan işletmeler", "link": "https://www.ticaret.gov.tr"},
    {"kurum": "Ticaret Bakanlığı", "baslik": "TURQUALITY Program", "ozet": "Özel markaların uluslararası pazarda geliştirilmesine hükümet tarafından verilen destek.", "detay": "Marka yönetimi ve pazarlama desteği sağlanır.", "hedef_kitle": "Marka geliştiren ihraçatçılar", "link": "http://www.turquality.com"},
    {"kurum": "Ticaret Bakanlığı", "baslik": "Fuarlar ve Ticari Etkinlikler Destek Programı", "ozet": "Uluslararası fuarlara işletmelerin katılmasını teşvik etmek amacıyla katılım desteği.", "detay": "Stant masrafları ve katılım ücretlerini kapsar.", "hedef_kitle": "İhraç yapan işletmeler", "link": "https://www.ticaret.gov.tr"},
    {"kurum": "Ticaret Bakanlığı", "baslik": "E-İhracat Destekleri", "ozet": "Dijital platform ve e-ticaret yoluyla yapılan ihracatı teşvik eden destek.", "detay": "Platform kurma ve eğitim desteği vardır.", "hedef_kitle": "E-ticaret yapan işletmeler", "link": "https://www.ticaret.gov.tr"},
    {"kurum": "Ticaret Bakanlığı", "baslik": "Turizm Teşvikleri", "ozet": "Turizm işletmelerine finansman ve vergi indirimi desteği.", "detay": "Otel, resepsiyon ve turizm ekipmanlarına yatırım desteklenir.", "hedef_kitle": "Turizm işletmeleri", "link": "https://www.ticaret.gov.tr"},
    {"kurum": "Ticaret Bakanlığı", "baslik": "Hizmet Sektörü Destekleri", "ozet": "Hizmet sektöründe faaliyet gösteren işletmelere teşvik ve finansman destekleri.", "detay": "Konsültasyon ve eğitim hizmetleri kapsar.", "hedef_kitle": "Hizmet sektörü işletmeleri", "link": "https://www.ticaret.gov.tr"},
    {"kurum": "Tarım Bakanlığı", "baslik": "Tarımsal Araştırma Projeleri Destekleme", "ozet": "Tarımsal araştırma ve geliştirme projeleri için finansman desteği.", "detay": "Ürün iyileştirme ve verim artırma projelerini destekler.", "hedef_kitle": "Tarım işletmeleri", "link": "https://www.tarim.gov.tr"},
    {"kurum": "Tarım Bakanlığı", "baslik": "Organik Tarım Destekleri", "ozet": "Organik tarım uygulamalarına geçen işletmelere destek sağlanır.", "detay": "Sertifikasyon ve denetim masrafları kapsar.", "hedef_kitle": "Çiftçiler", "link": "https://www.tarim.gov.tr"},
    {"kurum": "Tarım Bakanlığı", "baslik": "Hayvancılık Destekleri", "ozet": "Hayvancılık işletmelerine hayvan bakım ve iyileştirme destekleri.", "detay": "Veteriner hizmetleri ve hayvan alımı desteği vardır.", "hedef_kitle": "Hayvancılık işletmeleri", "link": "https://www.tarim.gov.tr"},
    {"kurum": "Tarım Bakanlığı", "baslik": "Tarımsal Makineleştirme Destekleri", "ozet": "Çiftçilere tarımsal makine ve ekipman alım desteği sağlanır.", "detay": "Traktör, hasat makinaları gibi temel araçları kapsar.", "hedef_kitle": "Çiftçiler", "link": "https://www.tarim.gov.tr"},
    {"kurum": "TKDK", "baslik": "Tarımsal Kalkınma Kooperatifleri Finansman", "ozet": "Tarımsal kooperatiflerin kuruluş ve işletme giderleri için kredi desteği.", "detay": "Uygun faiz oranları ve uzun geri ödeme süreleri vardır.", "hedef_kitle": "Tarım kooperatifleri", "link": "https://www.tkdk.gov.tr"},
    {"kurum": "TKDK", "baslik": "Kırsal Turizm Projelerine Destek", "ozet": "Kırsal alanında turizm işletmelerinin geliştirilmesi için finansman.", "detay": "Agroturizm ve kültür turizmi desteklenir.", "hedef_kitle": "Kırsal turizm işletmeleri", "link": "https://www.tkdk.gov.tr"},
    {"kurum": "İŞKUR", "baslik": "Mesleki Eğitim Kursları", "ozet": "İşsizlerin ve iş arayanların mesleki becerilerini artırmak için verilen eğitim.", "detay": "Kursum masrafları ve aylık yardım sağlanır.", "hedef_kitle": "İşsizler/İş arayanlar", "link": "https://www.iskur.gov.tr"},
    {"kurum": "İŞKUR", "baslik": "İşbaşı Eğitim Programları", "ozet": "İşletmelere çalışan yeteneklendirmek için verilen pratik iş başında eğitim.", "detay": "İşveren ve çalışan desteği kombinasyonu vardır.", "hedef_kitle": "İş arayanlar/İşletmeler", "link": "https://www.iskur.gov.tr"},
    {"kurum": "İŞKUR", "baslik": "Kamu Çalışma Programı", "ozet": "İşsizlere geçici kamusal işlerde istihdam sağlayan sosyal program.", "detay": "Aylık ücret ve sosyal sigorta kapsar.", "hedef_kitle": "Uzun süreli işsizler", "link": "https://www.iskur.gov.tr"},
    {"kurum": "İŞKUR", "baslik": "İşgücü Uyum Programı", "ozet": "İşgücü arz ve talebini dengelemek amacıyla aktif işgücü piyasası programı.", "detay": "Eğitim ve istihdam desteği birlikte sağlanır.", "hedef_kitle": "İş arayanlar/İşveren", "link": "https://www.iskur.gov.tr"},
    {"kurum": "İŞKUR", "baslik": "Gençlik İstihdam Programları", "ozet": "Gençlere işe yerleşme ve kariyer gelişim desteği sağlayan program.", "detay": "Staj ve iş bulma desteği vardır.", "hedef_kitle": "Gençler (15-24 yaş)", "link": "https://www.iskur.gov.tr"},
    {"kurum": "İŞKUR", "baslik": "Engelsiz İŞKUR", "ozet": "Engelli bireyler için özelleştirilmiş istihdam ve eğitim hizmetleri.", "detay": "Erişim desteği ve danışmanlık hizmetleri kapsar.", "hedef_kitle": "Engelli bireyler", "link": "https://www.iskur.gov.tr"},
    {"kurum": "Hazine", "baslik": "Bölgesel Teşvik Uygulamaları", "ozet": "Ulke, gelismislik duzeyine gore 6 bolgeye ayrilir; her bolgede belirlenen sektorlerdeki yatirimlar.", "detay": "Vergi indirimi ve destek oranlari bölgeye göre degisir.", "hedef_kitle": "Yatırımcı/Sanayi", "link": "https://www.yatirimadestek.gov.tr"},
    {"kurum": "Hazine", "baslik": "Genel Teşvik Uygulamaları", "ozet": "Bölgesel, büyük ölçekli veya stratejik yatırım teşvik kapsamına girmeyen yatırımlar.", "detay": "KDV istisnası, gümrük vergisi muafiyeti, gelir vergisi stopajı desteği vardır.", "hedef_kitle": "Yatırımcı", "link": "https://www.yatirimadestek.gov.tr"},
    {"kurum": "Hazine", "baslik": "Büyük Ölçekli Yatırımların Teşviki", "ozet": "Mevzuatta tanimlanan onemli sanayi sektorlerinde belirli asgari yatirim tutarini asan projeler.", "detay": "Rafineriler, kimya, otomotiv gibi sektörlere yüksek teşvik oranları vardır.", "hedef_kitle": "Büyük sanayi yatırımcıları", "link": "https://www.yatirimadestek.gov.tr"},
    {"kurum": "Hazine", "baslik": "Stratejik Yatırımların Teşviki", "ozet": "Stratejik önemi yüksek yatırım projelerine özel teşvikler sağlanır.", "detay": "Teknoloji ve inovasyonlu projelere öncelik verilir.", "hedef_kitle": "Stratejik yatırımcılar", "link": "https://www.yatirimadestek.gov.tr"},
    {"kurum": "Invest in Turkey", "baslik": "FDI Stratejisi (2024-2028)", "ozet": "Türkiye'nin yüksek kaliteli yatırımı çekmek için belirlediği strateji ve yol haritası.", "detay": "Sektörel odaklanma ve bölgesel gelişim planları kapsar.", "hedef_kitle": "Yabancı doğrudan yatırımcılar", "link": "https://www.invest.gov.tr"},
    {"kurum": "Invest in Turkey", "baslik": "Başlangıç Merkezi (Start in Turkey)", "ozet": "Girişimcilerin ve start-up'ların finansmanını ve mentoring desteğini sağlayan platform.", "detay": "Hibe ve kredi finansmanı kombinasyonu sunulur.", "hedef_kitle": "Girişimciler/Start-uplar", "link": "https://startinturkiye.gov.tr"},
    {"kurum": "Invest in Turkey", "baslik": "Yatırım Süreci Rehberi", "ozet": "Türkiye'de şirket kurulumundan tesisler faaliyete geçişine kadar tüm prosedürler.", "detay": "Lisanslama, izin ve tescil işlemleri detaylı anlatılır.", "hedef_kitle": "Yatırımcılar", "link": "https://www.invest.gov.tr"},
    {"kurum": "Çalışma Bakanlığı", "baslik": "İşsizlik Sigortası Fonu Destekleri", "ozet": "İşçi istihdam ettiren işletmelere sigorta primi teşvikleri.", "detay": "Belli dönemler için primlere katkı sağlanır.", "hedef_kitle": "İşveren", "link": "https://www.calismakurumu.gov.tr"},
    {"kurum": "Çalışma Bakanlığı", "baslik": "Meslek Edindirme Kursları", "ozet": "İşveren tarafından talep edilen işçilerin eğitimi için destek.", "detay": "Kurs masrafları ve katılımcı ücretleri karşılanır.", "hedef_kitle": "İşveren/İşçi", "link": "https://www.calismakurumu.gov.tr"},
    {"kurum": "Çalışma Bakanlığı", "baslik": "Gençlerin İstihdamı Destekleme", "ozet": "18-24 yaş arası gençlerin işe yerleştirilmesine destek sağlanır.", "detay": "Eğitim ve iş bulma desteği kombinasyonu vardır.", "hedef_kitle": "Genç işveren", "link": "https://www.calismakurumu.gov.tr"},
    {"kurum": "Kalkınma Ajansları", "baslik": "Bölgesel Kalkınma Projeleri", "ozet": "Kalkınmakta olan bölgelerdeki işletmelere proje destekleri sağlanır.", "detay": "Sosyal ve ekonomik projelere hibe desteği vardır.", "hedef_kitle": "KOBİ/Sosyal kuruluşlar", "link": "https://www.kalkinma.gov.tr"},
    {"kurum": "Enerji Bakanlığı", "baslik": "Yenilenebilir Enerji Teşvikleri", "ozet": "Güneş, rüzgar, biyokütle gibi yenilenebilir enerji projelerine destek.", "detay": "FIT (Akaryakıt Alım Garantisi) tarifesi uygulanır.", "hedef_kitle": "Enerji işletmeleri", "link": "https://www.enerji.gov.tr"},
    {"kurum": "Enerji Bakanlığı", "baslik": "Enerji Verimliliği Projeleri", "ozet": "Endüstri ve işletmelerin enerji tasarrufu projelerine finansman.", "detay": "Denetim ve sertifikasyon desteği de sağlanır.", "hedef_kitle": "İşletme", "link": "https://www.enerji.gov.tr"},
    {"kurum": "Çevre Bakanlığı", "baslik": "Yeşil Finansman Desteği", "ozet": "Çevreye duyarlı proje ve işletmelere finansman desteği.", "detay": "Atık yönetimi ve çevre koruma projeleri desteklenir.", "hedef_kitle": "KOBİ", "link": "https://www.csb.gov.tr"},
    {"kurum": "Kültür Bakanlığı", "baslik": "Kültür ve Turizm Alanında Proje Destekleri", "ozet": "Kültür ve sanat projeleri için hibe desteği sağlanır.", "detay": "Restorasyon ve sanat etkinlikleri kapsar.", "hedef_kitle": "Kültür kuruluşu", "link": "https://www.ktb.gov.tr"},
    {"kurum": "Spor Bakanlığı", "baslik": "Spor Tesisleri Destekleme", "ozet": "Spor tesisleri ve spor işletmeleri kuruluşuna yatırım desteği.", "detay": "Modern spor kompleksleri ve akademileri desteklenir.", "hedef_kitle": "Spor işletmesi", "link": "https://www.gsb.gov.tr"},
]

DB_PATH = "data/tesvikler.db"

def import_tesvikler():
    """58 teşvik programını database'e ekle"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Mevcut verileri kontrol et
        cursor.execute('SELECT COUNT(*) FROM tesvikler')
        existing = cursor.fetchone()[0]
        print(f"Mevcut kayıt: {existing}")

        # Yeni verileri ekle
        added = 0
        for t in TESVIKLER:
            cursor.execute('''
                INSERT INTO tesvikler (kurum, baslik, ozet, detay, hedef_kitle, kaynak_url)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (t['kurum'], t['baslik'], t['ozet'], t['detay'], t['hedef_kitle'], t['link']))
            added += 1

        conn.commit()
        conn.close()

        print(f"✓ {added} yeni teşvik eklendi")
        print(f"✓ Toplam: {existing + added} teşvik")

    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    import_tesvikler()
