// Türkçe sayı/tarih biçimleri ve API hata metni (saf işlevler; `npm test`).

export function sayi(x: number | null | undefined, basamak = 0): string {
  return Number(x || 0).toLocaleString('tr-TR', { minimumFractionDigits: basamak, maximumFractionDigits: basamak });
}

export function para(x: number | null | undefined, birim = 'TL'): string {
  return `${sayi(x, 2)} ${birim}`;
}

/** FastAPI saat dilimsiz UTC döndürür ("2026-10-08T06:00:48"); sonuna Z eklenip yerel saate çevrilir. */
export function tarihSaat(iso: string | null | undefined): string {
  if (!iso) return 'henüz yok';
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z');
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('tr-TR', { dateStyle: 'medium', timeStyle: 'short' });
}

/** FastAPI hata gövdesi: {detail: "metin"} ya da 422'de {detail: [{msg}]}. */
export function hataMetni(govde: unknown, durum: number): string {
  const detay = (govde as { detail?: unknown } | null)?.detail;
  if (typeof detay === 'string') return detay;
  if (Array.isArray(detay) && detay.length && typeof detay[0]?.msg === 'string') return detay[0].msg;
  return `İşlem tamamlanamadı (${durum}).`;
}
