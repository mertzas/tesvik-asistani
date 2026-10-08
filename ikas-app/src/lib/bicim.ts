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

/** "2026-11-30" -> "30 Kas 2026" (saat dilimi kayması olmasın diye yerel tarih olarak kurulur). */
export function tarih(iso: string | null | undefined): string {
  if (!iso) return '';
  const [y, a, g] = iso.split('-').map(Number);
  return new Date(y, a - 1, g).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Çağrı özeti: "Son başvuru 30 Kas 2026 (23 gün)", "15 Kas 2026'da açılıyor (7 gün)", "Kapandı (…)". */
export function cagriOzeti(c: { durum: string; acilis: string | null; kapanis: string | null; kalan_gun: number | null }): string {
  if (c.durum === 'acik') {
    if (!c.kapanis) return 'Başvuruya açık (son tarih duyurulmadı)';
    return c.kalan_gun === 0 ? `Son başvuru bugün (${tarih(c.kapanis)})` : `Son başvuru ${tarih(c.kapanis)} (${c.kalan_gun} gün)`;
  }
  if (c.durum === 'yaklasan') return `${tarih(c.acilis)} tarihinde açılıyor (${c.kalan_gun} gün)`;
  if (c.durum === 'kapandi') return `Son çağrı ${tarih(c.kapanis)} tarihinde kapandı`;
  return 'Başvuru tarihi duyurulmadı';
}
