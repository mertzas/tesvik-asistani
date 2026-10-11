#!/usr/bin/env bash
# GPU'lu kiralık sunucuda kendi model sunucumuzun ölçümü (2026-10-12). Ubuntu 22.04/24.04, NVIDIA sürücülü imaj.
# Talimat: docs/olcum/2026-10-11-ozel-model/GPU_TALIMATI.md
#
# Önce bilgisayarınızdan veri kopyasını gönderin (kişisel tablolar boş; scripts/gpu_olcum_paketi.py üretir):
#   scp data/tesvikler_kamu.db root@SUNUCU:/root/tesvikler_kamu.db
# Sonra sunucuda:
#   curl -fsSL https://raw.githubusercontent.com/mertzas/tesvik-asistani/master/docs/olcum/2026-10-11-ozel-model/gpu_kurulum.sh -o gpu_kurulum.sh
#   MODELLER="qwen2.5:14b qwen2.5:32b" bash gpu_kurulum.sh
#
# Model sunucusu yalnız 127.0.0.1'de dinler (dışarıya port açılmaz). Üçüncü taraf yapay zekâ servisi kullanılmaz;
# ağdan yalnız Ollama kurulumu, model ağırlıkları ve Python paketleri indirilir.
set -euo pipefail

MODELLER="${MODELLER:-qwen2.5:14b}"
BAGLAM="${BAGLAM:-32768}"
ZAMAN_ASIMI="${ZAMAN_ASIMI:-600}"
SENARYOLAR="${SENARYOLAR:-}"          # boşsa 30 senaryonun hepsi; örn. "1 6 11 15 23"
REPO="${REPO:-https://github.com/mertzas/tesvik-asistani.git}"
CALISMA="${CALISMA:-/root/tesvik-asistani}"
VERI="${VERI:-/root/tesvikler_kamu.db}"

adim() { printf '\n== %s\n' "$*"; }

adim "1/6 GPU kontrolü"
if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi >/dev/null 2>&1; then
  echo "GPU bulunamadı (nvidia-smi yok ya da çalışmıyor). NVIDIA sürücülü bir GPU imajı seçin." >&2
  exit 1
fi
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
if [ ! -f "$VERI" ]; then
  echo "Veri kopyası yok: $VERI — önce bilgisayarınızdan scp ile gönderin (talimat 3. adım)." >&2
  exit 1
fi

adim "2/6 Ollama kurulumu (yalnız 127.0.0.1, bağlam $BAGLAM token)"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/tesvik.conf <<EOF
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_CONTEXT_LENGTH=$BAGLAM"
EOF
systemctl daemon-reload
systemctl restart ollama
for i in $(seq 1 30); do curl -fs http://127.0.0.1:11434/api/version >/dev/null && break; sleep 1; done
curl -fs http://127.0.0.1:11434/api/version

adim "3/6 Modeller: $MODELLER"
for m in $MODELLER; do ollama pull "$m"; done

adim "4/6 Uygulama ve Python ortamı"
apt-get update -qq && apt-get install -y -qq git python3-venv >/dev/null
if [ ! -d "$CALISMA/.git" ]; then git clone --depth 1 "$REPO" "$CALISMA"; else git -C "$CALISMA" pull --ff-only; fi
cd "$CALISMA"
python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
mkdir -p data
cp "$VERI" data/tesvikler.db
python -m app.llm_saglayici --self-test | tail -1
python docs/olcum/2026-10-11-ozel-model/ozel_model_olc.py --self-test | tail -1

adim "5/6 Ölçüm (her model ayrı; dayanak denetimi ve süre)"
OLC=docs/olcum/2026-10-11-ozel-model
for m in $MODELLER; do
  ad=$(echo "$m" | tr ':/' '__')
  rm -f "$OLC/ozet.json" "$OLC"/model_*.md
  echo "--- $m"
  LLM_SAGLAYICI=ozel_sunucu LLM_BASE_URL=http://127.0.0.1:11434/v1 LLM_MODEL="$m" LLM_ZAMAN_ASIMI_SN="$ZAMAN_ASIMI" \
    python "$OLC/ozel_model_olc.py" $SENARYOLAR
  mkdir -p "sonuc_$ad"
  mv "$OLC/ozet.json" "$OLC"/model_*.md "sonuc_$ad/"
  python - "sonuc_$ad/ozet.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))
gecti = sum(x["gecti"] for x in s)
sureler = sorted(x["sure_sn"] for x in s)
print(f"senaryo {len(s)} | dayanaktan geçti {gecti} | hata {sum(bool(x['hata']) for x in s)} | "
      f"süre ortanca {sureler[len(sureler) // 2]} sn, en çok {sureler[-1]} sn")
PY
done

adim "6/6 Sonuçları paketle"
tar czf /root/gpu_olcum_sonuc.tgz sonuc_*
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader > /root/gpu_bilgi.txt
echo "Bitti. Bilgisayarınıza alın:  scp root@SUNUCU:/root/gpu_olcum_sonuc.tgz root@SUNUCU:/root/gpu_bilgi.txt ."
echo "Sonra sunucuyu kapatın/silin (ücret işlemeye devam eder); veri kopyası da onunla silinir."
