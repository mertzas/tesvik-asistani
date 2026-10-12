# Soru anlama (Groq) ölçümü — 2026-10-12

Özgün soru 75, söyleniş 148; Groq çağrısı 568, harcama 0.0994 USD.

Yöntemler üretim kuralıyla: program ya da kurum adı geçen soru Groq'a gönderilmez (o soruda Groq etiketi yok sayılır, `yalniz_groq` boştur); Groq'un niyet etiketleri kullanılmaz (`kalip+groq` niyeti = kalıp). Altın etiket: kalıp etiketi + 10 elle düzeltme (soru_anlama_olc.ALTIN_DUZELTME); kalıba yakın olduğu için özgün sorularda kalıp lehine yanlıdır. Karar ve uçtan uca sonuç: KARAR.md.

## openai/gpt-oss-120b

Sınıflandırılan 223 (biçim hatası 0; program/kurum adı geçtiği için üretimde gönderilmeyecek 81, bunlarda kalıp + Groq = kalıp); gecikme p50 0.643 sn, p95 1.437 sn, en çok 3.326 sn, 2,5 sn üstü 1.

### Özgün sorular

| yöntem | ihtiyaç K / D / F1 | ihtiyaç tam | fazla / eksik | niyet F1 | niyet tam |
|---|---|---|---|---|---|
| kalip | 0.941 / 0.969 / 0.955 | 0.893 | 6 / 3 | 0.972 | 0.96 |
| kalip+groq | 0.922 / 0.969 / 0.945 | 0.88 | 8 / 3 | 0.972 | 0.96 |
| yalniz_groq | 0.931 / 0.551 / 0.692 | 0.48 | 4 / 44 | 0.298 | 0.36 |

### Farklı söylenişler

| yöntem | ihtiyaç K / D / F1 | ihtiyaç tam | fazla / eksik | niyet F1 | niyet tam |
|---|---|---|---|---|---|
| kalip | 0.934 / 0.51 / 0.66 | 0.459 | 7 / 95 | 0.595 | 0.541 |
| kalip+groq | 0.907 / 0.706 / 0.794 | 0.608 | 14 / 57 | 0.595 | 0.541 |
| yalniz_groq | 0.891 / 0.505 / 0.645 | 0.426 | 12 / 96 | 0.304 | 0.345 |

Kayıt örtüşmesi (söyleniş ilk 5 kayıt ∩ özgün soru ilk 5 kayıt, Jaccard): kalıp 0.456, kalıp + Groq 0.52; iyileşen 24, kötüleşen 3 / 148.

## openai/gpt-oss-20b

Sınıflandırılan 223 (biçim hatası 0; program/kurum adı geçtiği için üretimde gönderilmeyecek 81, bunlarda kalıp + Groq = kalıp); gecikme p50 0.508 sn, p95 1.023 sn, en çok 2.166 sn, 2,5 sn üstü 0.

### Özgün sorular

| yöntem | ihtiyaç K / D / F1 | ihtiyaç tam | fazla / eksik | niyet F1 | niyet tam |
|---|---|---|---|---|---|
| kalip | 0.941 / 0.969 / 0.955 | 0.893 | 6 / 3 | 0.972 | 0.96 |
| kalip+groq | 0.932 / 0.98 / 0.955 | 0.893 | 7 / 2 | 0.972 | 0.96 |
| yalniz_groq | 0.885 / 0.469 / 0.613 | 0.4 | 6 / 52 | 0.293 | 0.52 |

### Farklı söylenişler

| yöntem | ihtiyaç K / D / F1 | ihtiyaç tam | fazla / eksik | niyet F1 | niyet tam |
|---|---|---|---|---|---|
| kalip | 0.934 / 0.51 / 0.66 | 0.459 | 7 / 95 | 0.595 | 0.541 |
| kalip+groq | 0.89 / 0.665 / 0.761 | 0.568 | 16 / 65 | 0.595 | 0.541 |
| yalniz_groq | 0.851 / 0.443 / 0.583 | 0.358 | 15 / 108 | 0.319 | 0.541 |

Kayıt örtüşmesi (söyleniş ilk 5 kayıt ∩ özgün soru ilk 5 kayıt, Jaccard): kalıp 0.456, kalıp + Groq 0.506; iyileşen 22, kötüleşen 4 / 148.
