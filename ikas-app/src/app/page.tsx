'use client';

// Giriş: İKAS paneli içinde AppBridge, imzalı açılış adresi, İKAS "Kurulum Adresi" ya da mağaza adı formu.
// Karar mantığı src/lib/akis.ts'te (birim testli).

import { useRouter } from 'next/navigation';
import React, { useEffect, useState } from 'react';
import { Bilgi, Dugme, Kart, Yukleniyor } from '@/components/ui';
import { girisAdimi, kurulumAdresi, magazaAdiDuzelt, magazaAdiGecerliMi } from '@/lib/akis';
import { appBridgeIleGiris, iframeIcindeMi, imzaliGiris, oturumOku } from '@/lib/oturum';

export default function GirisSayfasi() {
  const router = useRouter();
  const [durum, setDurum] = useState<'calisiyor' | 'form' | 'hata'>('calisiyor');
  const [mesaj, setMesaj] = useState('İKAS oturumunuz doğrulanıyor…');
  const [magaza, setMagaza] = useState('');

  useEffect(() => {
    const sorgu = new URLSearchParams(window.location.search);
    const adim = girisAdimi({ iframe: iframeIcindeMi(), sorgu, sakliOturum: !!oturumOku() });
    // İmzalı parametreler geçmişte/yer imlerinde kalmasın.
    if (window.location.search) window.history.replaceState(null, '', window.location.pathname);

    (async () => {
      try {
        if (adim.tur === 'imzali' || adim.tur === 'appbridge') {
          const g = adim.tur === 'imzali' ? await imzaliGiris(adim.girdi) : await appBridgeIleGiris();
          router.replace(g.senkron_bekliyor ? '/panel?ilk=1' : '/panel');
        } else if (adim.tur === 'panel') {
          router.replace('/panel');
        } else if (adim.tur === 'kurulum') {
          setMesaj('İKAS onay ekranına yönlendiriliyorsunuz…');
          window.location.replace(kurulumAdresi(adim.storeName));
        } else {
          setMagaza(adim.storeName);
          setDurum('form');
        }
      } catch (e) {
        setMesaj(e instanceof Error ? e.message : 'Giriş yapılamadı.');
        setDurum('hata');
      }
    })();
  }, [router]);

  const duzgun = magazaAdiDuzelt(magaza);
  const gecerli = magazaAdiGecerliMi(duzgun);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4 py-10">
      <header>
        <p className="text-xs font-semibold uppercase tracking-wide text-soluk">İKAS uygulaması</p>
        <h1 className="mt-1 text-2xl font-bold">Teşvik Asistanı</h1>
        <p className="mt-2 text-sm text-soluk">
          Mağazanızın satış verisinden size uygun devlet desteklerini bulur, başvuru belgelerinizi hazırlamanıza yardım eder.
        </p>
      </header>

      {durum === 'calisiyor' && <Yukleniyor metin={mesaj} />}
      {durum === 'hata' && <Bilgi tur="hata">{mesaj}</Bilgi>}

      {durum === 'form' && (
        <Kart>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (gecerli) window.location.assign(kurulumAdresi(duzgun));
            }}
          >
            <label htmlFor="magaza" className="text-sm font-semibold">
              İKAS mağaza adınız
            </label>
            <div className="flex items-center rounded-md border border-cizgi focus-within:border-vurgu">
              <input
                id="magaza"
                name="storeName"
                value={magaza}
                onChange={(e) => setMagaza(e.target.value)}
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
                required
                className="min-w-0 flex-1 rounded-l-md bg-transparent px-3 py-2 text-sm outline-none"
                placeholder="benim-magazam"
              />
              <span className="px-3 text-sm text-soluk">.myikas.com</span>
            </div>
            {magaza && !gecerli && (
              <p className="text-xs text-hata">Yalnızca küçük harf, rakam ve tire kullanın (ör. benim-magazam).</p>
            )}
            <Dugme type="submit" disabled={!gecerli}>
              Mağazama ekle
            </Dugme>
            <p className="text-xs text-soluk">
              İKAS onay ekranında uygulamanın yalnızca sipariş verilerinizi okumasına izin verirsiniz.
            </p>
          </form>
        </Kart>
      )}
    </main>
  );
}
