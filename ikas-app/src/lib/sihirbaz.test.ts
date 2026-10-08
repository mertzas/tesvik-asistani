import { test } from 'node:test';
import assert from 'node:assert/strict';
import { destekHesabi, gonderilecek, ilkCevaplar, type Sorular } from './sihirbaz.ts';

const SORULAR: Sorular = {
  turler: ['ar_ge'],
  gerekce: [{ anahtar: 'B2', etiket: 'B.2 Projenin Teknoloji Düzeyi', ipucu: 'Tekniğin güncel durumu' }],
  cikti: [{ anahtar: 'istihdam', etiket: 'Yeni istihdam', ipucu: 'Kişi' }],
  faaliyet_onerileri: ['Literatür taraması', 'Prototip'],
  gider_kalemleri: ['Personel'],
  oran_secenekleri: [60, 75],
  ust_limit: 1_000_000,
  form: { ad: 'TÜBİTAK Proje Öneri Bilgileri Formu', kaynak: 'https://www.tubitak.gov.tr/x.pdf', tablolar: ['M011 Personel'] },
  cevaplar: null,
};

test('ilk hal: önerilen adımlar ve üç boş bütçe satırı; kayıtlı cevap varsa o', () => {
  const c = ilkCevaplar(SORULAR);
  assert.deepEqual(c.faaliyetler.map((f) => f.ad), ['Literatür taraması', 'Prototip']);
  assert.equal(c.butce.length, 3);
  assert.equal(c.destek_orani, null);
  const k = ilkCevaplar({
    ...SORULAR,
    cevaplar: { ...c, proje_adi: 'Sensör', gerekce: { B2: 'metin' }, faaliyetler: [{ ad: 'Tek', baslangic: '2027-01', bitis: null }],
      destek_orani: 75 },
  });
  assert.equal(k.proje_adi, 'Sensör');
  assert.equal(k.gerekce.B2, 'metin');
  assert.deepEqual(k.faaliyetler, [{ ad: 'Tek', baslangic: '2027-01', bitis: null }]);
  assert.equal(k.destek_orani, 75);
});

test('kayıttaki oran programın seçeneklerinde yoksa düşer', () => {
  const c = ilkCevaplar({ ...SORULAR, cevaplar: { ...ilkCevaplar(SORULAR), destek_orani: 50 } });
  assert.equal(c.destek_orani, null);
});

test('destek hesabı: oran × toplam, üst limitle sınırlı; oran yoksa destek yok', () => {
  const butce = [{ kalem: 'Personel', tutar: 800_000 }, { kalem: 'Malzeme', tutar: 400_000 }, { kalem: '', tutar: -5 }];
  assert.deepEqual(destekHesabi(butce, 60, 1_000_000), { toplam: 1_200_000, destek: 720_000, sinirli: false });
  assert.deepEqual(destekHesabi(butce, 75, 500_000), { toplam: 1_200_000, destek: 500_000, sinirli: true });
  assert.deepEqual(destekHesabi(butce, null, 500_000), { toplam: 1_200_000, destek: null, sinirli: false });
  assert.deepEqual(destekHesabi(butce, 60, null), { toplam: 1_200_000, destek: 720_000, sinirli: false });
});

test('gönderim: kırpılır, boş satır ve boş cevap atılır', () => {
  const g = gonderilecek({
    proje_adi: '  Sensör ', proje_ozeti: '', gerekce: { B2: ' var ', B3: '   ' },
    faaliyetler: [{ ad: ' Prototip ', baslangic: '2027-01', bitis: '' as unknown as null }, { ad: ' ', baslangic: null, bitis: null }],
    butce: [{ kalem: 'Personel', tutar: 1000 }, { kalem: 'Malzeme', tutar: 0 }, { kalem: '', tutar: 50 }],
    destek_orani: 60, ciktilar: { istihdam: '3 kişi', satis: '' },
  });
  assert.equal(g.proje_adi, 'Sensör');
  assert.deepEqual(g.gerekce, { B2: 'var' });
  assert.deepEqual(g.faaliyetler, [{ ad: 'Prototip', baslangic: '2027-01', bitis: null }]);
  assert.deepEqual(g.butce, [{ kalem: 'Personel', tutar: 1000 }]);
  assert.deepEqual(g.ciktilar, { istihdam: '3 kişi' });
});
