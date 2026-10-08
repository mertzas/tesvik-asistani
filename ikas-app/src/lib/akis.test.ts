import { test } from 'node:test';
import assert from 'node:assert/strict';
import { girisAdimi, kurulumAdresi, magazaAdiDuzelt, magazaAdiGecerliMi } from './akis.ts';

const imzali = 'storeName=demo&merchantId=m&authorizedAppId=a&timestamp=1&signature=s';

test('imzalı parametreler her şeyden önce gelir (iframe ve saklı oturum olsa da)', () => {
  const a = girisAdimi({ iframe: true, sakliOturum: true, sorgu: new URLSearchParams(imzali) });
  assert.equal(a.tur, 'imzali');
  if (a.tur === 'imzali') assert.equal(a.girdi.authorizedAppId, 'a');
});

test('eksik imzalı parametre imzalı yola girmez', () => {
  const a = girisAdimi({ iframe: false, sakliOturum: false, sorgu: new URLSearchParams('storeName=demo&signature=s') });
  assert.deepEqual(a, { tur: 'kurulum', storeName: 'demo' });
});

test('iframe içinde saklı oturum kullanılmaz, AppBridge istenir', () => {
  assert.deepEqual(girisAdimi({ iframe: true, sakliOturum: true, sorgu: new URLSearchParams() }), { tur: 'appbridge' });
});

test('iframe dışında saklı oturum panele götürür', () => {
  assert.deepEqual(girisAdimi({ iframe: false, sakliOturum: true, sorgu: new URLSearchParams() }), { tur: 'panel' });
});

test('geçersiz mağaza adı kuruluma gitmez, forma döner', () => {
  for (const ad of ['evil.com/x', '-a', 'a b']) {
    const a = girisAdimi({ iframe: false, sakliOturum: false, sorgu: new URLSearchParams({ storeName: ad }) });
    assert.equal(a.tur, 'form', ad);
  }
});

test('mağaza adı düzeltme ve doğrulama FastAPI kuralıyla aynı', () => {
  assert.equal(magazaAdiDuzelt(' Benim-Magazam.myikas.com/admin '), 'benim-magazam');
  assert.ok(magazaAdiGecerliMi('benim-magazam'));
  assert.ok(!magazaAdiGecerliMi('benim_magazam'));
  assert.equal(kurulumAdresi('a-b'), '/api/oauth/authorize/ikas?storeName=a-b');
});
