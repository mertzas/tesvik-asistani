# GPU'lu sunucuda model ölçümü — adım adım

Amaç: kendi sunucumuzda çalışacak açık ağırlıklı modelin hızını ve kayıtlara sadakatini 30 senaryoda ölçmek; sonucu
yerel danışmanla (hakem puanı 3,54) karşılaştırıp `ozel_sunucu`'nun açılıp açılmayacağına karar vermek.

Veri güvenliği: sunucuya yalnız teşvik kayıtları gider. `scripts/gpu_olcum_paketi.py` kullanıcı, kuruluş, profil,
soru geçmişi, başvuru takibi, İKAS bağlantısı ve oturum tablolarını boşaltılmış bir kopya üretir. Model sunucusu
yalnız 127.0.0.1'de dinler; üçüncü taraf yapay zekâ servisi kullanılmaz. Ölçüm senaryoları sentetik personalardır.

## 1. Sunucuyu kiralayın (siz)

- Herhangi bir GPU kiralama sağlayıcısı; **Ubuntu 22.04 ya da 24.04, NVIDIA sürücülü** imaj seçin.
- GPU belleği (VRAM), 32 bin token bağlamla birlikte yaklaşık:
  - 14B model: 24 GB'lık kart yeterli olmalı.
  - 32B model: 48 GB'lık kart önerilir (24 GB'ta bağlam penceresi sığmayabilir).
  Bu değerler yaklaşık; betik `nvidia-smi` çıktısını kaydeder, ölçüm gerçek sonucu gösterir.
- Disk: en az 60 GB (iki model + Python paketleri). SSH anahtarıyla erişim.
- Ücret sağlayıcıya ve karta göre saatliktir; güncel fiyatı sağlayıcının sayfasından kontrol edin. Test bitince
  sunucuyu **silin** (durdurulmuş sunucu da disk ücreti işletebilir).
- Bölge: veri yalnız kamuya açık teşvik kayıtlarıdır; yine de mümkünse AB/Türkiye bölgesi seçin.

## 2. Bilgisayarınızda veri kopyasını üretin

```bash
python scripts/gpu_olcum_paketi.py
```

Çıktı `data/tesvikler_kamu.db`; betik kişisel tabloların boş olduğunu denetler, değilse dosyayı siler.

## 3. Kopyayı sunucuya gönderin

```bash
scp data/tesvikler_kamu.db root@SUNUCU:/root/tesvikler_kamu.db
```

## 4. Sunucuda kurulum ve ölçüm

```bash
curl -fsSL https://raw.githubusercontent.com/mertzas/tesvik-asistani/master/docs/olcum/2026-10-11-ozel-model/gpu_kurulum.sh -o gpu_kurulum.sh
```

```bash
MODELLER="qwen2.5:14b qwen2.5:32b" bash gpu_kurulum.sh
```

Betik sırayla: GPU'yu doğrular (yoksa durur) → Ollama'yı kurar, 127.0.0.1 ve 32 bin token bağlamla başlatır →
modelleri indirir → depoyu klonlar, Python ortamını kurar, veri kopyasını yerleştirir, self-test'leri çalıştırır →
her modeli 30 senaryoda ayrı ölçer → sonuçları `/root/gpu_olcum_sonuc.tgz` olarak paketler. Önce kısa deneme
isterseniz: `SENARYOLAR="1 6 11 15 23" MODELLER="qwen2.5:14b" bash gpu_kurulum.sh`.

Model adları Ollama kütüphanesindeki etiketlerdir; başka bir açık model denemek için `MODELLER` değişkenini değiştirin.

## 5. Sonuçları alın ve sunucuyu silin

```bash
scp root@SUNUCU:/root/gpu_olcum_sonuc.tgz root@SUNUCU:/root/gpu_bilgi.txt .
```

Sonra sağlayıcı panelinden sunucuyu silin. Paketi bu klasöre koyun; değerlendirme buradan yapılır.

## 6. Karar ölçütü (paketten sonra burada)

- Dayanak denetiminden geçen senaryo oranı ve yanıt süresi (ortanca, en kötü).
- Geçen yanıtlar 5 bağımsız hakemle puanlanır (yerel danışmanla aynı ölçüt). Dayanak denetimi sayı içermeyen
  olgusal hatayı yakalamadığı için bu adım şarttır.
- `ozel_sunucu` yalnız hakem puanı yerel danışmanınkinden belirgin yüksek, kritik bulgu sıfır ve süre kabul
  edilebilirse açılır; açılsa da kuruluş bazında varsayılan kapalıdır.

## Denendi / denenmedi

- Bu bilgisayarda denendi: veri kopyası (284 teşvik, kişisel tablolar 0), temiz klonda self-test'ler, ölçüm döngüsü ve
  özet satırı yerel Ollama ile tek senaryoda (küçük bağlam penceresinde kesik istem koruması devreye girdi, beklenen).
- Denenmedi: betiğin Linux kurulum adımları (GPU kontrolü, Ollama kurulumu, systemd ayarı, apt/pip) — burada Linux
  ve GPU yok. Bash sözdizimi denetimi (`bash -n`) temiz. İlk koşuda bir adım hata verirse çıktıyı buraya getirin.
