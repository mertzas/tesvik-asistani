'use client';

import { useRouter } from 'next/navigation';
import React, { Suspense, useEffect, useState } from 'react';
import { BasvurularSekmesi } from '@/components/basvurular';
import { OzetSekmesi } from '@/components/ozet';
import { TesviklerSekmesi } from '@/components/tesvikler';
import { oturumOku } from '@/lib/oturum';

type Sekme = 'ozet' | 'tesvikler' | 'basvurular';
const SEKMELER: { id: Sekme; ad: string }[] = [
  { id: 'ozet', ad: 'Mağaza özeti' },
  { id: 'tesvikler', ad: 'Uygun destekler' },
  { id: 'basvurular', ad: 'Başvurularım' },
];

function Panel() {
  const router = useRouter();
  const [hazir, setHazir] = useState(false);
  const [ilk, setIlk] = useState(false);
  const [sekme, setSekme] = useState<Sekme>('ozet');
  const [secili, setSecili] = useState<number | null>(null);

  useEffect(() => {
    if (!oturumOku()) {
      router.replace('/');
      return;
    }
    setIlk(new URLSearchParams(window.location.search).get('ilk') === '1');
    setHazir(true);
  }, [router]);

  if (!hazir) return null;

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-5 px-4 py-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Teşvik Asistanı</h1>
          <p className="text-sm text-soluk">Satış verinize göre devlet destekleri ve başvuru hazırlığı</p>
        </div>
      </header>

      <nav className="flex gap-1 overflow-x-auto border-b border-cizgi" role="tablist" aria-label="Bölümler">
        {SEKMELER.map((s) => (
          <button
            key={s.id}
            role="tab"
            aria-selected={sekme === s.id}
            onClick={() => setSekme(s.id)}
            className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-semibold ${
              sekme === s.id ? 'border-vurgu text-vurgu' : 'border-transparent text-soluk hover:text-murekkep'
            }`}
          >
            {s.ad}
          </button>
        ))}
      </nav>

      {sekme === 'ozet' && <OzetSekmesi ilkAcilis={ilk} onDesteklereGit={() => setSekme('tesvikler')} />}
      {sekme === 'tesvikler' && (
        <TesviklerSekmesi
          onListeAc={(id) => {
            setSecili(id);
            setSekme('basvurular');
          }}
        />
      )}
      {sekme === 'basvurular' && <BasvurularSekmesi secili={secili} onSec={setSecili} />}
    </main>
  );
}

export default function PanelSayfasi() {
  return (
    <Suspense>
      <Panel />
    </Suspense>
  );
}
