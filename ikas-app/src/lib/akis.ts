// Giriş akışı kararı (saf işlev; tarayıcıya ve React'e bağlı değil, `npm test` ile sınanır).
//
// Öncelik:
//  1. Adreste İKAS'ın imzalı açılış parametreleri varsa (storeName, merchantId, authorizedAppId, timestamp,
//     signature) -> POST /api/ikas/oturum. FastAPI mock callback'i de bu yolla döner.
//  2. İKAS paneli içindeysek (iframe) -> AppBridge REQUEST_TOKEN -> POST /api/ikas/appbridge-oturum.
//     İframe'de saklı oturum KULLANILMAZ: aynı tarayıcıda farklı mağazaların panelleri aynı depolama bölümünü
//     paylaşabilir; her açılışta İKAS'ın verdiği kimlikle yeniden doğrulanır.
//  3. Saklı oturum varsa -> panel.
//  4. Adreste geçerli storeName varsa (İKAS "Kurulum Adresi") -> /api/oauth/authorize/ikas.
//  5. Hiçbiri yoksa -> mağaza adı formu.

export type ImzaliGirdi = {
  storeName: string;
  merchantId: string;
  authorizedAppId: string;
  timestamp: string;
  signature: string;
};

export type Adim =
  | { tur: 'imzali'; girdi: ImzaliGirdi }
  | { tur: 'appbridge' }
  | { tur: 'panel' }
  | { tur: 'kurulum'; storeName: string }
  | { tur: 'form'; storeName: string };

export type Baglam = {
  iframe: boolean;
  sorgu: URLSearchParams;
  sakliOturum: boolean;
};

const MAGAZA_ADI = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

/** FastAPI app/ikas_integration.magaza_adi_gecerli_mi ile aynı kural. */
export function magazaAdiGecerliMi(ad: string): boolean {
  return MAGAZA_ADI.test(ad);
}

export function magazaAdiDuzelt(ad: string): string {
  return ad.trim().toLowerCase().replace(/\.myikas\.com.*$/, '').replace(/^https?:\/\//, '');
}

export function girisAdimi(b: Baglam): Adim {
  const al = (k: string) => (b.sorgu.get(k) || '').trim();
  const girdi: ImzaliGirdi = {
    storeName: al('storeName'),
    merchantId: al('merchantId'),
    authorizedAppId: al('authorizedAppId'),
    timestamp: al('timestamp'),
    signature: al('signature'),
  };
  if (Object.values(girdi).every(Boolean)) return { tur: 'imzali', girdi };
  if (b.iframe) return { tur: 'appbridge' };
  if (b.sakliOturum) return { tur: 'panel' };
  const magaza = magazaAdiDuzelt(girdi.storeName);
  if (magaza && magazaAdiGecerliMi(magaza)) return { tur: 'kurulum', storeName: magaza };
  return { tur: 'form', storeName: magaza };
}

export function kurulumAdresi(storeName: string): string {
  return `/api/oauth/authorize/ikas?storeName=${encodeURIComponent(storeName)}`;
}
