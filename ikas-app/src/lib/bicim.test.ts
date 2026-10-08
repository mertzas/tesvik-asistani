import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hataMetni, para, sayi, tarihSaat } from './bicim.ts';

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
