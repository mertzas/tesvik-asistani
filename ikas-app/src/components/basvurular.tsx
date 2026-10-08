'use client';

// Başvuru kontrol listesi + ön taslak (FastAPI app/basvuru_listesi.py; varsayılan yapay zekâsız şablon, app/sablon_taslak.py). Yazdırma yok: İKAS paneli
// iframe'inde yazdırma güvenilir değil; taslak kopyalanır ya da tüm dosya Word olarak indirilir.

import React, { useCallback, useEffect, useState } from 'react';
import { api, wordIndir, type Liste, type ListeOzeti } from '@/lib/api';
import { cagriOzeti, tarih, tarihSaat } from '@/lib/bicim';
import { Bilgi, Dugme, Kart, Yukleniyor } from './ui';

const TUR_ETIKETI = { sart: 'Şart', belge: 'Belge', basvuru: 'Başvuru' } as const;

export function BasvurularSekmesi({ secili, onSec }: { secili: number | null; onSec: (id: number | null) => void }) {
  const [listeler, setListeler] = useState<ListeOzeti[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  const listeleriYukle = useCallback(() => {
    api
      .listeler()
      .then((r) => setListeler(r.listeler))
      .catch((e) => setHata(e instanceof Error ? e.message : 'Listeler yüklenemedi.'));
  }, []);

  useEffect(listeleriYukle, [listeleriYukle]);

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="flex min-w-0 flex-col gap-2">
        <h2 className="text-sm font-bold">Takip ettiğim başvurular</h2>
        {hata && <Bilgi tur="hata">{hata}</Bilgi>}
        {!listeler && !hata && <Yukleniyor />}
        {listeler?.length === 0 && (
          <p className="text-sm text-soluk">Henüz yok. &quot;Uygun destekler&quot; bölümünden bir programın kontrol listesini açın.</p>
        )}
        {listeler?.map((l) => (
          <button
            key={l.tesvik_id}
            onClick={() => onSec(l.tesvik_id)}
            className={`rounded-md border px-3 py-2 text-left text-sm ${
              secili === l.tesvik_id ? 'border-vurgu bg-yuzey' : 'border-cizgi bg-yuzey hover:border-vurgu'
            }`}
          >
            <span className="block font-semibold">{l.baslik}</span>
            <span className="block text-xs text-soluk tabular-nums">
              {l.kurum} · {l.tamamlanan}/{l.toplam} tamamlandı
            </span>
          </button>
        ))}
      </aside>

      <div className="min-w-0">
        {secili === null ? (
          <Kart>
            <p className="text-sm text-soluk">Bir başvuru seçin.</p>
          </Kart>
        ) : (
          <ListeAyrinti
            key={secili}
            tesvikId={secili}
            onDegisti={listeleriYukle}
            onKaldirildi={() => {
              onSec(null);
              listeleriYukle();
            }}
          />
        )}
      </div>
    </div>
  );
}

function ListeAyrinti({ tesvikId, onDegisti, onKaldirildi }: { tesvikId: number; onDegisti: () => void; onKaldirildi: () => void }) {
  const [liste, setListe] = useState<Liste | null>(null);
  const [mesaj, setMesaj] = useState<{ tur: 'iyi' | 'uyari' | 'hata'; metin: string } | null>(null);
  const [taslakYaziliyor, setTaslakYaziliyor] = useState(false);

  useEffect(() => {
    api
      .liste(tesvikId)
      .then(setListe)
      .catch((e) => setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Liste yüklenemedi.' }));
  }, [tesvikId]);

  if (!liste) return mesaj ? <Bilgi tur={mesaj.tur}>{mesaj.metin}</Bilgi> : <Yukleniyor />;
  const t = liste.tesvik;

  async function isaretle(anahtar: string, isaretli: boolean) {
    if (!liste) return;
    const yeni = liste.maddeler.filter((m) => (m.anahtar === anahtar ? isaretli : m.isaretli)).map((m) => m.anahtar);
    try {
      setListe(await api.isaretle(tesvikId, yeni));
      onDegisti();
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Kaydedilemedi.' });
    }
  }

  async function taslakYaz() {
    setTaslakYaziliyor(true);
    setMesaj({ tur: 'uyari', metin: 'Taslak hazırlanıyor…' });
    try {
      setListe(await api.taslak(tesvikId));
      setMesaj({ tur: 'iyi', metin: 'Taslak hazır. [DOLDURUN] ile işaretli yerleri kendi bilgilerinizle tamamlayın.' });
      onDegisti();
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Taslak yazılamadı.' });
    } finally {
      setTaslakYaziliyor(false);
    }
  }

  async function kopyala() {
    if (!liste?.taslak) return;
    try {
      await navigator.clipboard.writeText(liste.taslak);
      setMesaj({ tur: 'iyi', metin: 'Taslak panoya kopyalandı.' });
    } catch {
      const alan = document.getElementById('taslak-metni') as HTMLTextAreaElement | null;
      alan?.select();
      setMesaj({ tur: 'uyari', metin: 'Tarayıcı panoya erişime izin vermedi; metin seçildi, Ctrl+C ile kopyalayın.' });
    }
  }

  async function word() {
    try {
      await wordIndir(tesvikId);
      setMesaj({ tur: 'iyi', metin: 'Word dosyası indirildi. İndirme başlamadıysa uygulamayı yeni sekmede açıp tekrar deneyin.' });
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Word dosyası hazırlanamadı.' });
    }
  }

  async function kaldir() {
    try {
      await api.birak(tesvikId);
      onKaldirildi();
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Kaldırılamadı.' });
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Kart>
        <p className="text-xs font-semibold uppercase tracking-wide text-soluk">{t.kurum}</p>
        <h2 className="mt-0.5 text-lg font-bold">{t.baslik}</h2>
        <p className="mt-1 text-sm text-soluk">
          {[t.basvuru_yeri && `Başvuru yeri: ${t.basvuru_yeri}`, t.basvuru_suresi && `Dönem: ${t.basvuru_suresi}`].filter(Boolean).join(' · ')}
          {t.aktif_mi === false && ' · Bu program şu an başvuruya kapalı görünüyor'}
        </p>
        {t.kaynak_url && (
          <a href={t.kaynak_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-sm text-vurgu underline">
            Kurumun resmi sayfası
          </a>
        )}
      </Kart>

      {mesaj && <Bilgi tur={mesaj.tur}>{mesaj.metin}</Bilgi>}

      <Kart>
        <h3 className="font-bold">Başvuru dönemleri</h3>
        {liste.cagrilar.length === 0 ? (
          <p className="mt-1 text-sm text-soluk">
            Bu program için doğrulanmış başvuru dönemi kaydımız yok; tarihleri kurumun resmi sayfasından kontrol edin.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {liste.cagrilar.map((c) => (
              <li key={c.id} className="text-sm">
                <span className={`font-semibold ${c.durum === 'acik' ? 'text-iyi' : c.durum === 'kapandi' ? 'text-soluk' : ''}`}>
                  {c.ad}: {cagriOzeti(c)}
                </span>
                {c.notlar && <span className="block text-soluk">{c.notlar}</span>}
                <span className="block text-xs text-soluk">
                  Kaynak:{' '}
                  <a href={c.kaynak_url} target="_blank" rel="noopener noreferrer" className="underline">
                    resmi duyuru
                  </a>{' '}
                  · doğrulama {tarih(c.dogrulama_tarihi)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Kart>

      <Kart>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-bold">Kontrol listesi</h3>
          <span className="text-sm tabular-nums text-soluk">
            {liste.tamamlanan}/{liste.toplam} tamamlandı
          </span>
        </div>
        {liste.uyari && <p className="mt-2 text-sm text-soluk">{liste.uyari}</p>}
        <ul className="mt-3 flex flex-col gap-2">
          {liste.maddeler.map((m) => (
            <li key={m.anahtar}>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={m.isaretli}
                  onChange={(e) => isaretle(m.anahtar, e.target.checked)}
                  className="mt-0.5 h-4 w-4 shrink-0 accent-vurgu"
                />
                <span>
                  <span className="mr-1 rounded bg-zemin px-1.5 py-0.5 text-xs font-semibold text-soluk">{TUR_ETIKETI[m.tur]}</span>
                  {m.metin}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </Kart>

      <Kart>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-bold">Başvuru ön taslağı</h3>
          <div className="flex flex-wrap gap-2">
            {liste.taslak && (
              <Dugme tur="ikincil" onClick={kopyala}>
                Kopyala
              </Dugme>
            )}
            <Dugme onClick={taslakYaz} disabled={taslakYaziliyor}>
              {liste.taslak ? 'Yeniden yaz' : 'Taslak oluştur'}
            </Dugme>
          </div>
        </div>
        {liste.taslak ? (
          <>
            <p className="mt-1 text-xs text-soluk">Oluşturma: {tarihSaat(liste.taslak_tarihi)} · Resmi başvuru formu değildir.</p>
            <textarea
              id="taslak-metni"
              readOnly
              value={liste.taslak}
              className="mt-3 h-96 w-full resize-y rounded-md border border-cizgi bg-zemin p-3 font-mono text-xs leading-relaxed"
            />
          </>
        ) : (
          <p className="mt-2 text-sm text-soluk">
            İşletme profiliniz ve mağaza verinizle bu program için düzenlenebilir bir başvuru metni taslağı yazılır.
            Bilinmeyen yerler [DOLDURUN] olarak bırakılır, rakam uydurulmaz.
          </p>
        )}
      </Kart>

      <div className="flex flex-wrap gap-2">
        <Dugme onClick={word}>Word (.docx) indir</Dugme>
        <Dugme tur="tehlike" onClick={kaldir}>
          Bu başvuruyu takipten çıkar
        </Dugme>
      </div>
    </div>
  );
}
