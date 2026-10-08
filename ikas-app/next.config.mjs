// Teşvik Asistanı İKAS kabuğu. Sunucu tarafında kendi veritabanı/oturumu YOK: İKAS belirteçleri ve tüm iş mantığı
// FastAPI'de (app/ikas_panel.py). Bu uygulama yalnızca İKAS panelindeki arayüzü ve AppBridge oturumunu sağlar.
//
// BACKEND_URL tanımlıysa /api/* ve /kvkk FastAPI'ye iletilir (yerel geliştirme ve nginx'siz kurulum). Canlıda nginx
// /api/'yi doğrudan FastAPI'ye yönlendirir (istemci IP'si hız sınırı için korunur); bkz. README.md.

const BACKEND_URL = (process.env.BACKEND_URL || '').replace(/\/$/, '');
// İKAS yönetim paneli uygulamayı https://{mağaza}.myikas.com/admin içinde iframe ile açar.
const CERCEVE = (process.env.IKAS_CERCEVE_KAYNAKLARI ?? 'https://*.myikas.com').trim();

const CSP = [
  "default-src 'self'",
  // Next.js App Router hidrasyon için satır içi betik üretir; dış kaynaktan betik yok.
  "script-src 'self' 'unsafe-inline'" + (process.env.NODE_ENV === 'development' ? " 'unsafe-eval'" : ''),
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  `frame-ancestors 'self'${CERCEVE ? ' ' + CERCEVE : ''}`,
].join('; ');

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker imajı yalnız .next/standalone + static ile çalışır (ikas-app/Dockerfile).
  output: 'standalone',
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Content-Security-Policy', value: CSP },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ],
      },
    ];
  },
  async redirects() {
    // FastAPI mock callback'i ve eski bağlantılar /ikas?...imzalı parametreler... adresine döner; sorgu korunur.
    return [{ source: '/ikas', destination: '/', permanent: false }];
  },
  async rewrites() {
    if (!BACKEND_URL) return [];
    return [
      { source: '/api/:path*', destination: `${BACKEND_URL}/api/:path*` },
      { source: '/kvkk', destination: `${BACKEND_URL}/kvkk` },
    ];
  },
};

export default nextConfig;
