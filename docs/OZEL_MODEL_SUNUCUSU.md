# Kendi sunucumuzda dil modeli (isteğe bağlı)

Teşvik Asistanı hiçbir üçüncü taraf yapay zekâ servisine veri göndermez (Anthropic, Google Gemini/AI Studio,
OpenAI; karar 2026-10-11). Varsayılan yanıt servisi kural tabanlı yerel danışmandır (`app/yerel_danisman.py`) ve
dil modeli gerektirmez. Bu belge, daha akıcı metin isteniyorsa **kendi altyapımızda** açık ağırlıklı bir modelin
nasıl çalıştırılacağını anlatır.

## Güvenlik modeli

`app/llm_saglayici.py` yalnız iki değeri kabul eder:

| `LLM_SAGLAYICI` | Davranış |
| --- | --- |
| `yerel` (varsayılan) | Dil modeli yok. Yanıt veritabanı kayıtlarından kuralla üretilir. |
| `ozel_sunucu` | Kendi model sunucumuz (Ollama, vLLM ya da llama.cpp sunucusu; Chat Completions protokolü). |

`gemini`, `openai_uyumlu`, `openai`, `anthropic` gibi eski değerler reddedilir ve yerel danışman kullanılır
(günlüğe hata yazılır).

`ozel_sunucu` için kod düzeyinde zorunlu kurallar:

1. `LLM_BASE_URL` iç ağ adresi olmalıdır: loopback (127.0.0.0/8, ::1), özel IP (10/8, 172.16/12, 192.168/16,
   fc00::/7; açık izin listesi) ya da harfle başlayan ASCII tek etiketli servis adı (Docker ağında `ollama`). Alan
   adı (`api.openai.com`), genel IP, 6to4/Teredo/NAT64, belgeleme ve CGNAT aralıkları, bulut meta veri adresi
   (169.254.169.254), 0.0.0.0, sayısal (`http://134744072/`) ve Unicode adlar reddedilir.
2. Her çağrıdan hemen önce sunucu adı çözülür; çözülen adreslerin **hepsi** iç ağda değilse istek gönderilmez. http'de
   istek denetlenen IP'ye gider (Host başlığı özgün ad), böylece denetim ile bağlantı arasında DNS yanıtı değişse de
   trafik dışarı çıkamaz. https'te sertifika adı gerektiği için sabitleme yapılmaz; iç ağda http önerilir.
3. HTTP(S)_PROXY ortam değişkenleri yok sayılır (`trust_env=False`), yönlendirme izlenmez.
4. Üçüncü taraf SDK yoktur (`openai`, `anthropic` paketleri bağımlılıklarda yok); istek `httpx` ile gider.
5. Modelin yanıtı `app/dayanak.py` denetiminden geçmezse (bağlamda olmayan tutar, oran, tarih, URL, telefon)
   kullanıcı yerel danışmanın yanıtını görür. Zaman aşımı ya da hata durumunda da aynı.
6. Model her kuruluş için **varsayılan olarak kapalıdır**; kullanıcı Ayarlar'dan açar ve istediği an kapatır
   (`POST /api/organizations/ai-riza {"riza": true|false}`). Tercih sağlayıcıdan ve sunucu adresinden bağımsız saklanır;
   yönetici modeli kapatıp açsa ya da adresi değiştirse de korunur. Eski üçüncü taraf rıza kayıtları modeli açmaz.
7. Model sunucusunun hata gövdesi günlüğe ve hataya yazılmaz (istem içeriği yansıtılmış olabilir).
8. "Kendi sunucumuz" bir işletim taahhüdüdür: iç ağ denetimi, adresin özel ağda olduğunu doğrular, sunucunun kime ait
   olduğunu ya da nerede durduğunu doğrulamaz. Modeli uygulamayla aynı barındırma ortamında çalıştırın; başka bir
   ülkedeki GPU'ya VPN ile bağlanmak bu taahhüdü bozar. Ülke beyanı `LLM_ULKE` ile yapılandırılır (varsayılan Türkiye).

## Kurulum (aynı sunucuda, Docker ağı içinde)

Model sunucusunu dışarıya port açmadan, uygulamayla aynı Docker ağında çalıştırın. Örnek (Ollama):

```bash
docker run -d --name ollama --network <uygulama-agi> -v ollama:/root/.ollama --restart unless-stopped ollama/ollama
docker exec ollama ollama pull <model-adi>
```

`-p 11434:11434` **vermeyin**; port yalnız Docker ağı içinden erişilebilir kalmalı.

`.env`:

```
LLM_SAGLAYICI=ozel_sunucu
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=<model-adi>
LLM_ZAMAN_ASIMI_SN=90
```

Doğrulama:

```bash
python -m app.llm_saglayici            # {'saglayici': 'ozel_sunucu', ..., 'etkin': True}
python -m app.llm_saglayici --self-test
```

## Model seçimi ve ölçüm

Model seçmeden önce aday modeli 30 senaryoluk ölçümle deneyin. Ölçüm, üretimdeki yolu birebir kullanır: aynı bağlam,
aynı sistem istemi ve aynı dayanak denetimi.

```bash
LLM_SAGLAYICI=ozel_sunucu LLM_BASE_URL=http://ollama:11434/v1 LLM_MODEL=<model> LLM_ZAMAN_ASIMI_SN=900 \
    python docs/olcum/2026-10-11-ozel-model/ozel_model_olc.py
```

`ozet.json` her senaryo için süreyi ve yanıtın dayanak denetiminden geçip geçmediğini yazar. Geçme oranı düşük
olan model kullanıcıya fark yaratmaz; kullanıcı zaten yerel danışmanın yanıtını görür. Sonuçlar ve donanım notu:
`docs/olcum/2026-10-11-ozel-model/SONUC.md`.

Donanım: 8B parametreli bir model GPU'suz dizüstünde yanıt başına 3,5-4,5 dk sürdü (2026-10-11 ölçümü). Üretimde
modeli GPU'lu bir sunucuda çalıştırın ya da yerel danışmanla devam edin.

**Bağlam penceresi zorunlu ayardır.** Ollama'nın varsayılan penceresi danışman istemini sessizce kesiyor (ölçümde
~9 bin token'lık istemin 2.051'i görüldü) ve model kayıtları görmeden yanlış hüküm verebiliyor. Sunucuyu
`OLLAMA_CONTEXT_LENGTH=32768` (ya da vLLM'de `--max-model-len 32768`) ile başlatın. Kod, sunucunun bildirdiği giriş
token'ı istemden beklenenin %60'ının altındaysa yanıtı reddeder.

**Dayanak denetimi yalnız sayıları ve iletişim bilgisini denetler.** Sayı içermeyen olgusal bir yanlışı ("bireysel
traktör desteklenir") yakalamaz. Bu yüzden modeli açmadan önce hakem değerlendirmesi yapın.
