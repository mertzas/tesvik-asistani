'use client';

// FastAPI uçları (app/ikas_panel.py, app/basvuru_listesi.py, app/main.py). Tipler yanıt şemalarının bu arayüzde
// kullanılan kısmıdır. 401 gelirse oturum silinir ve giriş sayfasına dönülür (İKAS içinde AppBridge yeniden doğrular).

import { hataMetni } from './bicim';
import { oturumOku, oturumSil } from './oturum';

export class ApiHatasi extends Error {
  constructor(public durum: number, mesaj: string) {
    super(mesaj);
  }
}

async function istek<T>(yol: string, init: RequestInit = {}): Promise<T> {
  const belirtec = oturumOku();
  const r = await fetch(yol, {
    ...init,
    headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), Authorization: `Bearer ${belirtec ?? ''}`, ...init.headers },
  });
  const v = await r.json().catch(() => null);
  if (r.status === 401) {
    oturumSil();
    window.location.replace('/');
    throw new ApiHatasi(401, 'Oturum sona erdi.');
  }
  if (!r.ok) throw new ApiHatasi(r.status, hataMetni(v, r.status));
  return v as T;
}

export type Ozet = {
  siparis_sayisi: number;
  yillik_ciro: number;
  doviz_toplamlari: Record<string, number>;
  yurt_disi_siparis: number;
  yurt_disi_oran: number;
  yurt_disi_ulkeler: string[];
  en_cok_satan_urun_kategorileri: [string, number][];
  kaynak_donem_baslangic: string | null;
  kaynak_donem_bitis: string | null;
  notlar: string[];
};

export type Durum = {
  baglanti_durumu: 'bagli' | 'beklemede' | 'hata' | 'kaldirildi' | 'bagli_degil';
  store_name?: string;
  son_senkron_zamani?: string | null;
  son_senkron_hata?: string | null;
  senkron_bekliyor?: boolean;
  webhook_kaydi?: string | null;
  ozet?: Ozet | null;
  mock_mode: boolean;
};

/** Dönemsel başvuru çağrısı (app/cagrilar.py). */
export type Cagri = {
  id: number;
  ad: string;
  acilis: string | null;
  kapanis: string | null;
  kaynak_url: string;
  dogrulama_tarihi: string;
  notlar: string | null;
  durum: 'acik' | 'yaklasan' | 'kapandi' | 'tarihsiz';
  durum_metni: string;
  kalan_gun: number | null;
};

/** skor: 0-1 arası eşleşme oranı (app/matching.py). */
export type Eslesme = { id: number; kurum: string; baslik: string; skor: number; gerekce: string[]; cagri: Cagri | null };

export type PanelYaniti = {
  magaza: string | null;
  yillik_ciro: number | null;
  sektor: string | null;
  eslesen_teşvikler: Eslesme[];
};

export type ListeOzeti = {
  tesvik_id: number;
  baslik: string;
  kurum: string;
  aktif_mi: boolean | null;
  tamamlanan: number;
  toplam: number;
  guncelleme: string | null;
};

export type Madde = { anahtar: string; tur: 'sart' | 'belge' | 'basvuru'; metin: string; isaretli: boolean };

export type Liste = {
  tesvik: { id: number; baslik: string; kurum: string; kaynak_url: string | null; basvuru_yeri: string | null;
    basvuru_suresi: string | null; aktif_mi: boolean | null };
  maddeler: Madde[];
  tamamlanan: number;
  toplam: number;
  takipte: boolean;
  taslak: string | null;
  taslak_tarihi: string | null;
  cagrilar: Cagri[];
  uyari: string | null;
};

export type Kurulus = { name: string; email: string; plan: string; ai_yurtdisi_riza: boolean };

export const api = {
  durum: () => istek<Durum>('/api/ikas/durum'),
  senkronize: () => istek<{ siparis_sayisi: number; notlar: string[] }>('/api/ikas/senkronize', { method: 'POST' }),
  baglantiKes: () => istek<{ mesaj: string }>('/api/ikas/baglanti', { method: 'DELETE' }),
  panel: () => istek<PanelYaniti>('/api/ikas/panel'),
  kurulus: () => istek<Kurulus>('/api/organizations/me'),
  riza: (riza: boolean) => istek<{ mesaj: string }>('/api/organizations/ai-riza', { method: 'POST', body: JSON.stringify({ riza }) }),
  listeler: () => istek<{ listeler: ListeOzeti[] }>('/api/basvuru-listesi'),
  liste: (id: number) => istek<Liste>(`/api/basvuru-listesi/${id}`),
  isaretle: (id: number, isaretli: string[]) =>
    istek<Liste>(`/api/basvuru-listesi/${id}`, { method: 'PUT', body: JSON.stringify({ isaretli }) }),
  taslak: (id: number) => istek<Liste>(`/api/basvuru-listesi/${id}/taslak`, { method: 'POST' }),
  birak: (id: number) => istek<{ mesaj: string }>(`/api/basvuru-listesi/${id}`, { method: 'DELETE' }),
};
