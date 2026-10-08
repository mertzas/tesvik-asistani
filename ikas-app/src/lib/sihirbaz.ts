// Taslak sihirbazı veri yapısı ve saf yardımcıları. Sorular GET /api/basvuru-listesi/{id}/taslak-sorulari'dan gelir
// (app/sablon_taslak.sorular; resmi form şablonu olan programlarda app/form_sablonlari.py bölümleri), cevaplar
// POST /taslak gövdesinde app/basvuru_listesi.TaslakCevaplari yapısıyla gider. Hesap web panelindeki sihirbazHesapla ile aynı.

export type Soru = { anahtar: string; etiket: string; ipucu: string };

export type Sorular = {
  turler: string[];
  gerekce: Soru[];
  cikti: Soru[];
  faaliyet_onerileri: string[];
  gider_kalemleri: string[];
  oran_secenekleri: number[];
  ust_limit: number | null;
  form: { ad: string; kaynak: string; tablolar: string[] } | null;
  cevaplar: Cevaplar | null;
};

export type Faaliyet = { ad: string; baslangic: string | null; bitis: string | null };
export type ButceKalemi = { kalem: string; tutar: number };

export type Cevaplar = {
  proje_adi: string;
  proje_ozeti: string;
  gerekce: Record<string, string>;
  faaliyetler: Faaliyet[];
  butce: ButceKalemi[];
  destek_orani: number | null;
  ciktilar: Record<string, string>;
};

/** Formun ilk hali: kayıtlı cevaplar varsa onlar, yoksa önerilen iş adımları ve üç boş bütçe satırı. */
export function ilkCevaplar(s: Sorular): Cevaplar {
  const k = s.cevaplar;
  return {
    proje_adi: k?.proje_adi ?? '',
    proje_ozeti: k?.proje_ozeti ?? '',
    gerekce: { ...(k?.gerekce ?? {}) },
    faaliyetler: k?.faaliyetler?.length
      ? k.faaliyetler.map((f) => ({ ...f }))
      : s.faaliyet_onerileri.map((ad) => ({ ad, baslangic: null, bitis: null })),
    butce: k?.butce?.length ? k.butce.map((b) => ({ ...b })) : [0, 1, 2].map(() => ({ kalem: '', tutar: 0 })),
    destek_orani: k?.destek_orani != null && s.oran_secenekleri.includes(k.destek_orani) ? k.destek_orani : null,
    ciktilar: { ...(k?.ciktilar ?? {}) },
  };
}

export type DestekHesabi = { toplam: number; destek: number | null; sinirli: boolean };

/** Toplam bütçe ve talep edilebilecek destek (toplam × oran, üst limitle sınırlı). Oran ya da toplam yoksa destek null. */
export function destekHesabi(butce: ButceKalemi[], oran: number | null, ustLimit: number | null): DestekHesabi {
  const toplam = butce.reduce((a, b) => a + (Number.isFinite(b.tutar) && b.tutar > 0 ? b.tutar : 0), 0);
  if (!oran || !toplam) return { toplam, destek: null, sinirli: false };
  const ham = (toplam * oran) / 100;
  const sinirli = ustLimit != null && ustLimit > 0 && ham > ustLimit;
  return { toplam, destek: sinirli ? (ustLimit as number) : ham, sinirli };
}

function temizSozluk(d: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(d).map(([k, v]) => [k, v.trim()]).filter(([, v]) => v));
}

/** Gönderilecek gövde: boşluklar kırpılır, adsız adım ve kalemsiz/tutarsız bütçe satırı atılır. */
export function gonderilecek(c: Cevaplar): Cevaplar {
  return {
    proje_adi: c.proje_adi.trim(),
    proje_ozeti: c.proje_ozeti.trim(),
    gerekce: temizSozluk(c.gerekce),
    faaliyetler: c.faaliyetler
      .map((f) => ({ ad: f.ad.trim(), baslangic: f.baslangic || null, bitis: f.bitis || null }))
      .filter((f) => f.ad),
    butce: c.butce.map((b) => ({ kalem: b.kalem.trim(), tutar: Number(b.tutar) || 0 })).filter((b) => b.kalem && b.tutar > 0),
    destek_orani: c.destek_orani,
    ciktilar: temizSozluk(c.ciktilar),
  };
}
