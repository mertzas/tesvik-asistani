import { test } from 'node:test';
import assert from 'node:assert/strict';
import { gruplar, kaydedilecek, uygunlukOzeti } from './kontrol.ts';
import type { Madde } from './api.ts';

const m = (anahtar: string, tur: Madde['tur'], ek: Partial<Madde> = {}): Madde => ({
  anahtar, tur, metin: anahtar, isaretli: false, cevap: null, alinti: null, kaynak_url: null, dogrulandi: true, ...ek,
});

const LISTE = [m('s1', 'sart', { cevap: 'evet' }), m('s2', 'sart'), m('b1', 'belge', { isaretli: true }), m('a1', 'adim'),
  m('k1', 'kural'), m('i1', 'bilgi')];

test('dört bölüm; kural ve bilgi aynı "bilmeniz gerekenler" bölümünde', () => {
  assert.deepEqual(gruplar(LISTE).map(([b, x]) => [b, x.map((y) => y.anahtar)]), [
    ['sart', ['s1', 's2']], ['belge', ['b1']], ['adim', ['a1']], ['bilinmesi', ['k1', 'i1']]]);
});

test('kaydedilecek: şart işaret listesine, belge cevap sözlüğüne girmez', () => {
  assert.deepEqual(kaydedilecek(LISTE), { isaretli: ['b1'], uygunluk: { s1: 'evet' } });
  assert.deepEqual(kaydedilecek(LISTE, { anahtar: 'a1', isaretli: true }), { isaretli: ['b1', 'a1'], uygunluk: { s1: 'evet' } });
  assert.deepEqual(kaydedilecek(LISTE, { anahtar: 's2', cevap: 'hayir' }), { isaretli: ['b1'], uygunluk: { s1: 'evet', s2: 'hayir' } });
  assert.deepEqual(kaydedilecek(LISTE, { anahtar: 'b1', isaretli: false }).isaretli, []);
});

test('uygunluk özeti: hayır varsa uyarı', () => {
  assert.equal(uygunlukOzeti({ toplam: 3, evet: 1, hayir: 1, bilmiyorum: 0 }).uyari, true);
  assert.match(uygunlukOzeti({ toplam: 3, evet: 1, hayir: 1, bilmiyorum: 0 }).metin, /başvuramazsınız. 1 evet · 1 hayır · 1 cevaplanmadı/);
  assert.match(uygunlukOzeti({ toplam: 2, evet: 2, hayir: 0, bilmiyorum: 0 }).metin, /hepsini sağladığınızı/);
});
