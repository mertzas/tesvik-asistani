import React from 'react';

type DugmeTuru = 'birincil' | 'ikincil' | 'tehlike';

const DUGME: Record<DugmeTuru, string> = {
  birincil: 'bg-vurgu text-white hover:bg-vurgu-koyu border border-vurgu',
  ikincil: 'bg-yuzey text-vurgu border border-vurgu hover:bg-zemin',
  tehlike: 'bg-yuzey text-hata border border-hata hover:bg-hata-zemin',
};

export function Dugme({
  tur = 'birincil',
  className = '',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tur?: DugmeTuru }) {
  return (
    <button
      type="button"
      className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${DUGME[tur]} ${className}`}
      {...props}
    />
  );
}

export function Kart({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-cizgi bg-yuzey p-5 ${className}`}>{children}</section>;
}

export function Bilgi({ tur, children }: { tur: 'iyi' | 'uyari' | 'hata'; children: React.ReactNode }) {
  const renk = { iyi: 'bg-iyi-zemin text-iyi', uyari: 'bg-uyari-zemin text-uyari', hata: 'bg-hata-zemin text-hata' }[tur];
  return (
    <p role={tur === 'hata' ? 'alert' : 'status'} className={`rounded-md px-3 py-2 text-sm ${renk}`}>
      {children}
    </p>
  );
}

export function Yukleniyor({ metin = 'Yükleniyor…' }: { metin?: string }) {
  return (
    <div className="flex items-center gap-3 py-6 text-sm text-soluk" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-cizgi border-t-vurgu" aria-hidden />
      {metin}
    </div>
  );
}

export function Gosterge({ etiket, deger }: { etiket: string; deger: string }) {
  return (
    <div className="min-w-0 rounded-md border border-cizgi bg-yuzey p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-soluk">{etiket}</div>
      <div className="mt-1 text-lg font-bold tabular-nums break-words">{deger}</div>
    </div>
  );
}
