'use client';

import React, { useEffect, useState } from 'react';
import { api, type PanelYaniti } from '@/lib/api';
import { cagriOzeti } from '@/lib/bicim';
import { Bilgi, Dugme, Kart, Yukleniyor } from './ui';

export function TesviklerSekmesi({ onListeAc }: { onListeAc: (tesvikId: number) => void }) {
  const [veri, setVeri] = useState<PanelYaniti | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    api
      .panel()
      .then(setVeri)
      .catch((e) => setHata(e instanceof Error ? e.message : 'Destekler yüklenemedi.'));
  }, []);

  if (hata) return <Bilgi tur="hata">{hata}</Bilgi>;
  if (!veri) return <Yukleniyor metin="Mağazanıza uygun destekler hesaplanıyor…" />;
  const liste = veri.eslesen_teşvikler;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-soluk">
        Profilinize ve son 12 ayın satış verisine göre başvurabileceğiniz programlar. Uygunluk kesin değildir; şartları
        kontrol listesinde tek tek işaretleyin.
      </p>
      {liste.length === 0 && (
        <Kart>
          <p className="text-sm">Şu an profilinize uyan açık bir program bulunamadı.</p>
        </Kart>
      )}
      {liste.map((e) => (
        <Kart key={e.id} className="flex flex-col gap-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-soluk">{e.kurum}</p>
              <h3 className="mt-0.5 font-bold">{e.baslik}</h3>
            </div>
            {/* skor 0-1 (app/matching.py); ana paneldeki gibi yüzde gösterilir */}
            <span className="rounded-full bg-zemin px-2.5 py-0.5 text-xs font-semibold tabular-nums text-vurgu" title="Profil eşleşme oranı">
              Uygunluk %{Math.round(e.skor * 100)}
            </span>
          </div>
          <p className={`text-sm font-semibold ${e.cagri?.durum === 'acik' ? 'text-iyi' : 'text-soluk'}`}>
            {e.cagri ? cagriOzeti(e.cagri) : 'Başvuru tarihi duyurulmadı'}
          </p>
          {e.gerekce.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-5 text-sm text-soluk">
              {e.gerekce.slice(0, 3).map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
          )}
          <div>
            <Dugme tur="ikincil" onClick={() => onListeAc(e.id)}>
              Kontrol listesi ve taslak
            </Dugme>
          </div>
        </Kart>
      ))}
    </div>
  );
}
