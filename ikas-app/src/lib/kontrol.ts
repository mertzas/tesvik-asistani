// Kontrol listesi: dört bölüm, dört etkileşim (web panelindeki klBolumlerHtml ile aynı; app/basvuru_listesi.py).
// Şart -> Evet/Hayır/Emin değilim; belge -> hazır; adım -> yapıldı; kural/bilgi -> işaretlenmez.

import type { Cevap, Madde } from './api';

export type Bolum = 'sart' | 'belge' | 'adim' | 'bilinmesi';

export const BOLUM: Record<Bolum, { baslik: string; aciklama: string }> = {
  sart: {
    baslik: 'Başvurabilir miyim?',
    aciklama: 'Her şart için durumunuzu seçin. “Hayır” dediğiniz bir şart varsa bu programa başvuramazsınız.',
  },
  belge: { baslik: 'Hazırlanacak belgeler', aciklama: 'Hazır olanları işaretleyin.' },
  adim: { baslik: 'Başvuru adımları', aciklama: 'Sırayla izleyin; yaptıklarınızı işaretleyin.' },
  bilinmesi: { baslik: 'Bilmeniz gerekenler', aciklama: 'Kurallar ve sınırlar; işaretlenmez.' },
};

export const CEVAP_ETIKETI: Record<Cevap, string> = { evet: 'Evet', hayir: 'Hayır', bilmiyorum: 'Emin değilim' };

export function bolumu(m: Pick<Madde, 'tur'>): Bolum {
  return m.tur === 'kural' || m.tur === 'bilgi' ? 'bilinmesi' : m.tur;
}

export function gruplar(maddeler: Madde[]): [Bolum, Madde[]][] {
  return (Object.keys(BOLUM) as Bolum[]).map((b) => [b, maddeler.filter((m) => bolumu(m) === b)] as [Bolum, Madde[]])
    .filter(([, m]) => m.length > 0);
}

/** PUT gövdesi: belge/adım işaretleri tam liste, şart cevapları tam sözlük (bir maddenin değişmesiyle). */
export function kaydedilecek(maddeler: Madde[], degisen?: { anahtar: string; isaretli?: boolean; cevap?: Cevap }) {
  const isaretli = maddeler
    .filter((m) => m.tur === 'belge' || m.tur === 'adim')
    .filter((m) => (degisen && m.anahtar === degisen.anahtar && degisen.isaretli !== undefined ? degisen.isaretli : m.isaretli))
    .map((m) => m.anahtar);
  const uygunluk: Record<string, Cevap> = {};
  for (const m of maddeler) {
    if (m.tur !== 'sart') continue;
    const c = degisen && m.anahtar === degisen.anahtar && degisen.cevap ? degisen.cevap : m.cevap;
    if (c) uygunluk[m.anahtar] = c;
  }
  return { isaretli, uygunluk };
}

export function uygunlukOzeti(u: { toplam: number; evet: number; hayir: number; bilmiyorum: number }) {
  const cevapsiz = u.toplam - u.evet - u.hayir - u.bilmiyorum;
  const parca = [`${u.evet} evet`, u.hayir ? `${u.hayir} hayır` : '', u.bilmiyorum ? `${u.bilmiyorum} emin değil` : '',
    cevapsiz ? `${cevapsiz} cevaplanmadı` : ''].filter(Boolean).join(' · ');
  const uyari = u.hayir > 0;
  const baslik = uyari
    ? 'Sağlamadığınızı belirttiğiniz şart var: bu programa bu haliyle başvuramazsınız.'
    : cevapsiz || u.bilmiyorum ? 'Şartlar:' : 'Şartların hepsini sağladığınızı belirttiniz.';
  return { metin: `${baslik} ${parca}`, uyari };
}
