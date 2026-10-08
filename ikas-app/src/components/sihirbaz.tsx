'use client';

// Taslak sihirbazı (web panelindeki sihirbazın İKAS karşılığı): proje, resmi form bölümleri ya da program türüne göre
// gerekçe soruları, iş adımları ve takvim, bütçe ve destek hesabı, beklenen çıktılar. Gönderilince yapay zekâsız
// şablon taslak bu cevaplarla yazılır ve cevaplar kaydedilir (app/basvuru_listesi.py, app/sablon_taslak.py).

import React, { useEffect, useState } from 'react';
import { api, type Liste } from '@/lib/api';
import { para } from '@/lib/bicim';
import { destekHesabi, gonderilecek, ilkCevaplar, type Cevaplar, type Sorular } from '@/lib/sihirbaz';
import { Bilgi, Dugme, Kart, Yukleniyor } from './ui';

const GIRDI = 'w-full rounded-md border border-cizgi bg-yuzey px-3 py-2 text-sm';
const ETIKET = 'mb-1 block text-sm font-semibold';

export function TaslakSihirbazi({ tesvikId, onBitti, onKapat }: { tesvikId: number; onBitti: (l: Liste) => void; onKapat: () => void }) {
  const [s, setS] = useState<Sorular | null>(null);
  const [c, setC] = useState<Cevaplar | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  useEffect(() => {
    api
      .taslakSorulari(tesvikId)
      .then((v) => {
        setS(v);
        setC(ilkCevaplar(v));
      })
      .catch((e) => setHata(e instanceof Error ? e.message : 'Sihirbaz açılamadı.'));
  }, [tesvikId]);

  if (!s || !c) return <Kart>{hata ? <Bilgi tur="hata">{hata}</Bilgi> : <Yukleniyor />}</Kart>;

  const guncelle = (p: Partial<Cevaplar>) => setC({ ...c, ...p });
  const hesap = destekHesabi(c.butce, c.destek_orani, s.ust_limit);

  async function gonder() {
    if (!c) return;
    setGonderiliyor(true);
    setHata(null);
    try {
      onBitti(await api.taslak(tesvikId, gonderilecek(c)));
    } catch (e) {
      setHata(e instanceof Error ? e.message : 'Taslak oluşturulamadı.');
    } finally {
      setGonderiliyor(false);
    }
  }

  return (
    <Kart className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-bold">Taslak sihirbazı</h3>
        <Dugme tur="ikincil" onClick={onKapat}>
          Kapat
        </Dugme>
      </div>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 text-sm font-bold text-vurgu">1. Proje</legend>
        <div>
          <label htmlFor="sh-proje" className={ETIKET}>Projenin adı</label>
          <input id="sh-proje" maxLength={200} className={GIRDI} value={c.proje_adi} onChange={(e) => guncelle({ proje_adi: e.target.value })} />
        </div>
        <div>
          <label htmlFor="sh-ozet" className={ETIKET}>Bir-iki cümleyle proje</label>
          <textarea id="sh-ozet" rows={2} maxLength={2000} className={GIRDI} value={c.proje_ozeti}
            onChange={(e) => guncelle({ proje_ozeti: e.target.value })} />
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 text-sm font-bold text-vurgu">2. {s.form ? 'Resmi form bölümleri' : 'Gerekçe'}</legend>
        {s.form && (
          <p className="text-sm text-soluk">
            Bu sorular{' '}
            <a href={s.form.kaynak} target="_blank" rel="noopener noreferrer" className="text-vurgu underline">{s.form.ad}</a>{' '}
            bölümleridir; cevaplarınız taslakta aynı başlıklarla yer alır.
          </p>
        )}
        {s.gerekce.map((q) => (
          <div key={q.anahtar}>
            <label htmlFor={`sh-g-${q.anahtar}`} className={ETIKET}>{q.etiket}</label>
            <textarea id={`sh-g-${q.anahtar}`} rows={s.form ? 3 : 2} maxLength={2000} placeholder={q.ipucu} className={GIRDI}
              value={c.gerekce[q.anahtar] ?? ''} onChange={(e) => guncelle({ gerekce: { ...c.gerekce, [q.anahtar]: e.target.value } })} />
          </div>
        ))}
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-bold text-vurgu">3. İş adımları ve takvim</legend>
        {c.faaliyetler.map((f, i) => (
          <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_9.5rem_9.5rem]">
            <input aria-label="İş adımı" placeholder="İş adımı" maxLength={200} className={GIRDI} value={f.ad}
              onChange={(e) => guncelle({ faaliyetler: c.faaliyetler.map((x, j) => (j === i ? { ...x, ad: e.target.value } : x)) })} />
            <input type="month" aria-label="Başlangıç" className={GIRDI} value={f.baslangic ?? ''}
              onChange={(e) => guncelle({ faaliyetler: c.faaliyetler.map((x, j) => (j === i ? { ...x, baslangic: e.target.value || null } : x)) })} />
            <input type="month" aria-label="Bitiş" className={GIRDI} value={f.bitis ?? ''}
              onChange={(e) => guncelle({ faaliyetler: c.faaliyetler.map((x, j) => (j === i ? { ...x, bitis: e.target.value || null } : x)) })} />
          </div>
        ))}
        <div>
          <Dugme tur="ikincil" disabled={c.faaliyetler.length >= 20}
            onClick={() => guncelle({ faaliyetler: [...c.faaliyetler, { ad: '', baslangic: null, bitis: null }] })}>
            + adım ekle
          </Dugme>
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-bold text-vurgu">4. Bütçe</legend>
        <datalist id="sh-gider-liste">
          {s.gider_kalemleri.map((k) => <option key={k} value={k} />)}
        </datalist>
        {c.butce.map((b, i) => (
          <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_11rem]">
            <input aria-label="Gider kalemi" placeholder="Gider kalemi" list="sh-gider-liste" maxLength={200} className={GIRDI} value={b.kalem}
              onChange={(e) => guncelle({ butce: c.butce.map((x, j) => (j === i ? { ...x, kalem: e.target.value } : x)) })} />
            <input type="number" min={0} step={1000} inputMode="numeric" aria-label="Tutar (TL)" placeholder="Tutar (TL)" className={GIRDI}
              value={b.tutar || ''}
              onChange={(e) => guncelle({ butce: c.butce.map((x, j) => (j === i ? { ...x, tutar: Number(e.target.value) || 0 } : x)) })} />
          </div>
        ))}
        <div>
          <Dugme tur="ikincil" disabled={c.butce.length >= 30} onClick={() => guncelle({ butce: [...c.butce, { kalem: '', tutar: 0 }] })}>
            + kalem ekle
          </Dugme>
        </div>
        {s.oran_secenekleri.length > 0 && (
          <div>
            <label htmlFor="sh-oran" className={ETIKET}>Size uygulanacak destek oranı (programın metninden)</label>
            <select id="sh-oran" className={GIRDI} value={c.destek_orani ?? ''}
              onChange={(e) => guncelle({ destek_orani: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Seçiniz</option>
              {s.oran_secenekleri.map((o) => <option key={o} value={o}>%{o}</option>)}
            </select>
          </div>
        )}
        <p className="text-sm tabular-nums" aria-live="polite">
          Toplam: <strong>{para(hesap.toplam)}</strong>
          {hesap.destek != null && (
            <>
              {' '}· Talep edilebilecek destek (tahmini): <strong>{para(hesap.destek)}</strong>
              {hesap.sinirli && ` (üst limit ${para(s.ust_limit)})`}
            </>
          )}
        </p>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 text-sm font-bold text-vurgu">5. Beklenen çıktılar</legend>
        {[...s.cikti, { anahtar: 'olcum', etiket: 'Göstergeleri nasıl izleyeceksiniz?', ipucu: 'Fatura, SGK bildirgesi, gümrük verisi…' }].map((q) => (
          <div key={q.anahtar}>
            <label htmlFor={`sh-c-${q.anahtar}`} className={ETIKET}>{q.etiket}</label>
            <input id={`sh-c-${q.anahtar}`} maxLength={2000} placeholder={q.ipucu} className={GIRDI} value={c.ciktilar[q.anahtar] ?? ''}
              onChange={(e) => guncelle({ ciktilar: { ...c.ciktilar, [q.anahtar]: e.target.value } })} />
          </div>
        ))}
      </fieldset>

      {hata && <Bilgi tur="hata">{hata}</Bilgi>}
      <div className="flex flex-wrap items-center gap-3">
        <Dugme onClick={gonder} disabled={gonderiliyor}>{gonderiliyor ? 'Oluşturuluyor…' : 'Taslağı oluştur'}</Dugme>
        <span className="text-sm text-soluk">Boş bıraktığınız yerler taslakta işaretli kalır.</span>
      </div>
    </Kart>
  );
}
