'use client';

// Oturum: FastAPI'nin verdiği kendi belirtecimiz (JWT, 7 gün) sessionStorage'da tutulur. İKAS paneli içinde
// (iframe) depolama üçüncü taraf bağlamına bölünür; tarayıcı depolamayı engellerse bellek içi yedek kullanılır
// (sayfa yenilenince AppBridge ile yeniden alınır).

import { AppBridgeHelper } from '@ikas/app-helpers';
import { hataMetni } from './bicim';
import type { ImzaliGirdi } from './akis';

const ANAHTAR = 'tesvik-asistani-oturum';
let bellek: string | null = null;

export function iframeIcindeMi(): boolean {
  try {
    return window.self !== window.top;
  } catch {
    return true; // çapraz köken erişimi engellendiyse kesinlikle iframe içindeyiz
  }
}

export function oturumOku(): string | null {
  try {
    return sessionStorage.getItem(ANAHTAR) ?? bellek;
  } catch {
    return bellek;
  }
}

function oturumYaz(belirtec: string) {
  bellek = belirtec;
  try {
    sessionStorage.setItem(ANAHTAR, belirtec);
  } catch {
    /* bellek içi yedek yeterli */
  }
}

export function oturumSil() {
  bellek = null;
  try {
    sessionStorage.removeItem(ANAHTAR);
  } catch {
    /* yok */
  }
}

export type GirisYaniti = { access_token: string; store_name: string; senkron_bekliyor: boolean };

async function girisIstegi(url: string, init: RequestInit): Promise<GirisYaniti> {
  const r = await fetch(url, init);
  const v = await r.json().catch(() => null);
  if (!r.ok) throw new Error(hataMetni(v, r.status));
  oturumYaz((v as GirisYaniti).access_token);
  return v as GirisYaniti;
}

/** İKAS paneli içinde: AppBridge REQUEST_TOKEN -> FastAPI /api/ikas/appbridge-oturum. */
export async function appBridgeIleGiris(): Promise<GirisYaniti> {
  AppBridgeHelper.closeLoader();
  let ikasBelirteci: string | undefined;
  try {
    ikasBelirteci = await AppBridgeHelper.getNewToken();
  } catch {
    throw new Error('İKAS paneli oturum bilgisini göndermedi. Uygulamayı İKAS panelinden yeniden açın.');
  }
  if (!ikasBelirteci) throw new Error('İKAS paneli oturum bilgisini göndermedi. Uygulamayı İKAS panelinden yeniden açın.');
  return girisIstegi('/api/ikas/appbridge-oturum', { method: 'POST', headers: { Authorization: `JWT ${ikasBelirteci}` } });
}

/** İmzalı açılış adresi (İKAS ya da FastAPI mock callback'i): /api/ikas/oturum. */
export async function imzaliGiris(girdi: ImzaliGirdi): Promise<GirisYaniti> {
  return girisIstegi('/api/ikas/oturum', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(girdi),
  });
}
