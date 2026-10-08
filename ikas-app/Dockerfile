# İKAS Next.js kabuğu, üretim imajı (Next "standalone" çıktısı; yalnız çalışma zamanı dosyaları).
# BACKEND_URL ve IKAS_CERCEVE_KAYNAKLARI next.config.mjs'te DERLEME anında okunur (yeniden yazım ve CSP başlığı
# routes-manifest'e gömülür): imajı derlerken --build-arg ile verin. nginx /api/'yi doğrudan FastAPI'ye veriyorsa
# BACKEND_URL boş bırakılır.

FROM node:24-alpine AS bagimlilik
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS derleme
WORKDIR /app
ARG BACKEND_URL=""
ARG IKAS_CERCEVE_KAYNAKLARI="https://*.myikas.com"
ENV BACKEND_URL=$BACKEND_URL IKAS_CERCEVE_KAYNAKLARI=$IKAS_CERCEVE_KAYNAKLARI NEXT_TELEMETRY_DISABLED=1
COPY --from=bagimlilik /app/node_modules ./node_modules
COPY . .
RUN npm test && npm run build

FROM node:24-alpine AS calisma
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S uyg && adduser -S uyg -G uyg
COPY --from=derleme --chown=uyg:uyg /app/.next/standalone ./
COPY --from=derleme --chown=uyg:uyg /app/.next/static ./.next/static
COPY --from=derleme --chown=uyg:uyg /app/public ./public
USER uyg
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1
CMD ["node", "server.js"]
