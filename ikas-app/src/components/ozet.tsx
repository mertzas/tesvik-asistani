'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiHatasi, type Durum, type Kurulus } from '@/lib/api';
import { para, sayi, tarihSaat } from '@/lib/bicim';
import { Bilgi, Dugme, Gosterge, Kart, Yukleniyor } from './ui';

const DURUM_METNI: Record<Durum['baglanti_durumu'], string> = {
  bagli: 'Bağlı',
  beklemede: 'Onay bekleniyor',
  hata: 'Hata: yeniden bağlanmanız gerekebilir',
  kaldirildi: "Uygulama İKAS'tan kaldırıldı",
  bagli_degil: 'Bağlı mağaza yok',
};

export function OzetSekmesi({ ilkAcilis, onDesteklereGit }: { ilkAcilis: boolean; onDesteklereGit: () => void }) {
  const [durum, setDurum] = useState<Durum | null>(null);
  const [kurulus, setKurulus] = useState<Kurulus | null>(null);
  const [mesaj, setMesaj] = useState<{ tur: 'iyi' | 'uyari' | 'hata'; metin: string } | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const kesOnayi = useRef(0);
  const ilkSenkron = useRef(false);

  const yukle = useCallback(async () => {
    try {
      const [d, k] = await Promise.all([api.durum(), api.kurulus()]);
      setDurum(d);
      setKurulus(k);
    } catch (e) {
      if (e instanceof ApiHatasi && e.durum !== 401) setMesaj({ tur: 'hata', metin: e.message });
    }
  }, []);

  const yenile = useCallback(async () => {
    setMesgul(true);
    setMesaj({ tur: 'uyari', metin: 'Mağaza verileriniz okunuyor (son 12 ay)…' });
    try {
      await api.senkronize();
      setMesaj({ tur: 'iyi', metin: 'Güncellendi. Yıllık ciro ve ihracat göstergeleri mağaza verisinden yenilendi.' });
      await yukle();
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Yenilenemedi.' });
    } finally {
      setMesgul(false);
    }
  }, [yukle]);

  useEffect(() => {
    yukle();
  }, [yukle]);

  useEffect(() => {
    // Kurulumdan hemen sonra ilk senkron arka planda bitmemiş olabilir: bir kez tetikle.
    if (ilkAcilis && durum?.baglanti_durumu === 'bagli' && !durum.ozet && !ilkSenkron.current) {
      ilkSenkron.current = true;
      yenile();
    }
  }, [ilkAcilis, durum, yenile]);

  if (!durum) return <Yukleniyor />;
  const o = durum.ozet;
  const doviz = Object.entries(o?.doviz_toplamlari ?? {});

  async function baglantiKes() {
    if (Date.now() - kesOnayi.current > 8000) {
      kesOnayi.current = Date.now();
      setMesaj({
        tur: 'uyari',
        metin: 'Saklı erişim anahtarları ve sipariş özeti silinecek; profilinizdeki ciro kalır. Onaylamak için 8 saniye içinde tekrar tıklayın.',
      });
      return;
    }
    kesOnayi.current = 0;
    try {
      const r = await api.baglantiKes();
      setMesaj({ tur: 'iyi', metin: r.mesaj });
      await yukle();
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Bağlantı kesilemedi.' });
    }
  }

  async function rizaDegistir(riza: boolean) {
    try {
      const r = await api.riza(riza);
      setMesaj({ tur: 'iyi', metin: r.mesaj });
      setKurulus(await api.kurulus());
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Kaydedilemedi.' });
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {mesaj && <Bilgi tur={mesaj.tur}>{mesaj.metin}</Bilgi>}

      <Kart>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-bold">{durum.store_name ? `${durum.store_name}.myikas.com` : 'Mağaza'}</h2>
            <p className="mt-1 text-sm text-soluk">
              {DURUM_METNI[durum.baglanti_durumu]} · Son okuma: {tarihSaat(durum.son_senkron_zamani)}
              {durum.mock_mode && ' · Deneme modu (örnek veri)'}
            </p>
            {durum.son_senkron_hata && <p className="mt-1 text-sm text-hata">Son hata: {durum.son_senkron_hata}</p>}
          </div>
          <Dugme onClick={yenile} disabled={mesgul || durum.baglanti_durumu !== 'bagli'}>
            Verileri yenile
          </Dugme>
        </div>

        {o ? (
          <>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Gosterge etiket="Satış siparişi (12 ay)" deger={sayi(o.siparis_sayisi)} />
              <Gosterge etiket="Ciro (TL siparişler)" deger={para(o.yillik_ciro)} />
              <Gosterge
                etiket="Yurt dışı teslimat"
                deger={`${sayi(o.yurt_disi_siparis)} sipariş${o.yurt_disi_ulkeler.length ? ` (${o.yurt_disi_ulkeler.join(', ')})` : ''}`}
              />
              <Gosterge etiket="Döviz cinsinden satış" deger={doviz.length ? doviz.map(([k, t]) => para(t, k)).join(', ') : 'yok'} />
            </div>
            {o.notlar.length > 0 && (
              <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-soluk">
                {o.notlar.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
            <div className="mt-4">
              <Dugme tur="ikincil" onClick={onDesteklereGit}>
                Uygun destekleri gör
              </Dugme>
            </div>
          </>
        ) : (
          <p className="mt-4 text-sm text-soluk">
            {durum.baglanti_durumu === 'bagli'
              ? 'Henüz sipariş özeti yok. "Verileri yenile" ile son 12 ayın siparişleri okunur.'
              : 'Mağaza bağlı olmadığı için sipariş verisi okunamıyor.'}
          </p>
        )}
      </Kart>

      <Kart>
        <h2 className="text-base font-bold">Yapay zekâ ile başvuru taslağı</h2>
        <p className="mt-1 max-w-prose text-sm text-soluk">
          Taslak oluşturduğunuzda işletme profiliniz ve sipariş toplamlarınız (müşteri bilgisi değil) taslağı yazması
          için Anthropic&apos;in (ABD) yapay zekâ servisine gönderilir. Bunun için açık rızanız gerekir; istediğiniz zaman
          geri alabilirsiniz.{' '}
          <a href="/kvkk" target="_blank" rel="noopener" className="text-vurgu underline">
            Aydınlatma metni
          </a>
        </p>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            id="ai-riza"
            type="checkbox"
            checked={!!kurulus?.ai_yurtdisi_riza}
            onChange={(e) => rizaDegistir(e.target.checked)}
            className="h-4 w-4 accent-vurgu"
          />
          Yurt dışına aktarıma açık rıza veriyorum
        </label>
        {kurulus && kurulus.plan === 'free' && (
          <p className="mt-2 text-xs text-soluk">Taslak üretimi PRO ve üzeri planlarda kullanılabilir.</p>
        )}
      </Kart>

      <Kart>
        <h2 className="text-base font-bold">Bağlantı</h2>
        <p className="mt-1 max-w-prose text-sm text-soluk">
          Bağlantıyı kestiğinizde İKAS erişim anahtarları ve sipariş özeti silinir. Uygulamayı İKAS panelinizdeki
          Uygulamalar bölümünden de kaldırabilirsiniz; kaldırma bize bildirilir ve aynı silme yapılır.
        </p>
        <div className="mt-3">
          <Dugme tur="tehlike" onClick={baglantiKes} disabled={durum.baglanti_durumu === 'bagli_degil'}>
            Bağlantıyı kes
          </Dugme>
        </div>
      </Kart>
    </div>
  );
}
