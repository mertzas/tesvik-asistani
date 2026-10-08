import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cagriOzeti, hataMetni, para, sayi, tarih, tarihSaat } from './bicim.ts';

test('Türkçe sayı ve para biçimi', () => {
  assert.equal(sayi(1234567), '1.234.567');
  assert.equal(para(3051.18, 'EUR'), '3.051,18 EUR');
  assert.equal(para(null), '0,00 TL');
});

test('saat dilimsiz tarih UTC kabul edilir, boşsa açıklama', () => {
  assert.equal(tarihSaat(null), 'henüz yok');
  assert.equal(tarihSaat('2026-10-08T06:00:48'), tarihSaat('2026-10-08T06:00:48Z'));
});

test('FastAPI hata gövdeleri', () => {
  assert.equal(hataMetni({ detail: 'Taslak PRO planda' }, 403), 'Taslak PRO planda');
  assert.equal(hataMetni({ detail: [{ msg: 'Alan zorunlu' }] }, 422), 'Alan zorunlu');
  assert.equal(hataMetni(null, 502), 'İşlem tamamlanamadı (502).');
});

test('çağrı özeti', () => {
  assert.equal(tarih('2026-11-30'), new Date(2026, 10, 30).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' }));
  assert.match(cagriOzeti({ durum: 'acik', acilis: null, kapanis: '2026-11-30', kalan_gun: 23 }), /^Son başvuru .* \(23 gün\)$/);
  assert.match(cagriOzeti({ durum: 'acik', acilis: null, kapanis: '2026-10-08', kalan_gun: 0 }), /^Son başvuru bugün/);
  assert.equal(cagriOzeti({ durum: 'acik', acilis: '2026-09-01', kapanis: null, kalan_gun: null }), 'Başvuruya açık (son tarih duyurulmadı)');
  assert.match(cagriOzeti({ durum: 'yaklasan', acilis: '2026-10-15', kapanis: null, kalan_gun: 7 }), /açılıyor \(7 gün\)$/);
  assert.equal(cagriOzeti({ durum: 'tarihsiz', acilis: null, kapanis: null, kalan_gun: null }), 'Başvuru tarihi duyurulmadı');
});
