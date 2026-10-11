# Kendi sunucumuzdaki model: ilk canlı ölçüm (2026-10-11)

Amaç: `LLM_SAGLAYICI=ozel_sunucu` yolunu gerçek bir açık ağırlıklı modelle uçtan uca denemek. Üçüncü taraf servis
kullanılmadı; model aynı makinede (Ollama 0.34.4, `127.0.0.1:11434`) çalıştı.

- Model: `gemma4:latest` (8B parametre, 9,6 GB; bu bilgisayarda kurulu olan tek model)
- Donanım: GPU'suz dizüstü (Windows 11)
- Araç: `ozel_model_olc.py` (üretimdeki yolun aynısı: bağlam, sistem istemi, dayanak denetimi)
- Senaryolar: 1, 6, 11, 15, 23 (`docs/olcum/2026-10-11-yerel-danisman` senaryo seti)
- Ham sonuç: `ozet.json`, yanıtlar `model_NN.md`

| Senaryo | Süre (sn) | Dayanak denetimi | Not |
| --- | --- | --- | --- |
| 1 | 235,6 | geçti | giriş 2.051 token: istem sunucuda kesildi |
| 6 | 262,0 | — | yanıt uzunluk sınırında kesildi |
| 11 | 268,2 | — | yanıt uzunluk sınırında kesildi |
| 15 | 209,7 | geçti | giriş 2.051 token: istem sunucuda kesildi |
| 23 | 263,8 | — | yanıt uzunluk sınırında kesildi |

## Bulgular

1. **İstem sessizce kesildi.** Sunucu her istemde 2.051 giriş token'ı bildirdi. Bağlam, karakter sayısına göre
   bunun birkaç katı. Ollama'nın varsayılan bağlam penceresi istemi kesti; model kayıtların çoğunu görmedi.
2. **Kesik bağlamla yanlış hüküm, dayanak denetiminden geçti.** Senaryo 1'de model "bireysel traktör … destek
   kapsamına alınabilir" dedi. Kayıt ise bireysel traktör alımının desteklenmediğini açıkça yazıyor. Yanıtta sayı,
   URL ya da tarih olmadığı için `app/dayanak.py` (yalnız sayısal ve iletişim bilgisi denetler) bunu yakalayamadı.
3. **Süre:** GPU'suz dizüstünde yanıt başına 3,5-4,5 dk. 90 sn zaman aşımıyla kullanıcı her durumda yerel
   danışmana düşer.

## Alınan önlemler (kodda)

- `app/llm_saglayici.py`: sunucunun bildirdiği giriş token'ı istemden beklenenin %60'ının altındaysa yanıt
  reddedilir ("istem model sunucusunda kesildi"), kullanıcı yerel danışmanı görür. Self-test: "sunucuda kesilen
  istem reddedilir".
- Zaman aşımı `LLM_ZAMAN_ASIMI_SN` ile ayarlanabilir.

## Karar

Varsayılan yanıt servisi kural tabanlı yerel danışman olarak kalır. `ozel_sunucu` yalnız şu koşullarla açılmalı:
GPU'lu sunucu, bağlam penceresi en az 32 bin token (Ollama: `OLLAMA_CONTEXT_LENGTH=32768`), ölçüm aracıyla
30 senaryoda dayanak geçme oranı ve hakem değerlendirmesi. Hakem değerlendirmesi şart, çünkü dayanak denetimi
olgusal yanlışları (sayı içermeyen hükümler) yakalamaz.

Bu bilgisayardaki Ollama sunucusunun bağlam penceresi ayarı kullanıcıya ait olduğu için değiştirilmedi; ölçüm bu
ayarla tekrarlanmadı.
