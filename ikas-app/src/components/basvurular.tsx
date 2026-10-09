'use client';

// Başvuru kontrol listesi + ön taslak (FastAPI app/basvuru_listesi.py; varsayılan yapay zekâsız şablon, app/sablon_taslak.py). Yazdırma yok: İKAS paneli
// iframe'inde yazdırma güvenilir değil; taslak kopyalanır ya da tüm dosya Word olarak indirilir.

import React, { useCallback, useEffect, useState } from 'react';
import { api, wordIndir, type Cevap, type Liste, type ListeOzeti, type Madde, type TaslakKapsami } from '@/lib/api';
import { cagriOzeti, tarih, tarihSaat } from '@/lib/bicim';
import { BOLUM, CEVAP_ETIKETI, gruplar, kaydedilecek, uygunlukOzeti } from '@/lib/kontrol';
import { TaslakSihirbazi } from './sihirbaz';
import { Bilgi, Dugme, Kart, Yukleniyor } from './ui';

/** Maddenin kaynağı: resmî sayfadan birebir alıntı (açılır) ya da "kurumdan teyit edin". */
function Kaynak({ m }: { m: Madde }) {
  if (m.dogrulandi === false)
    return (
      <span
        className="ml-1 whitespace-nowrap rounded-full bg-uyari-zemin px-2 py-0.5 text-xs text-uyari"
        title="Bu madde kurumun resmi sayfasında bulunamadı; uygulama esaslarından ya da kurumdan teyit edin."
      >
        kurumdan teyit edin
      </span>
    );
  if (!m.alinti) return null;
  return (
    <details className="ml-1 inline text-xs text-soluk">
      <summary className="inline cursor-pointer text-vurgu">kaynak</summary>
      <span className="mt-1 block rounded-md bg-zemin px-2 py-1">
        <q className="italic">{m.alinti}</q>{' '}
        {m.kaynak_url && (
          <a href={m.kaynak_url} target="_blank" rel="noopener noreferrer" className="underline">
            resmi sayfa
          </a>
        )}
      </span>
    </details>
  );
}

const CEVAP_RENGI: Record<Cevap, string> = {
  evet: 'bg-iyi text-white',
  hayir: 'bg-hata text-white',
  bilmiyorum: 'bg-uyari text-white',
};

/** Taslak neye hazırlanıyor: ne için, nereye girilir, ne değildir (app/sablon_taslak.taslak_kapsami). */
function Kapsam({ k }: { k: TaslakKapsami }) {
  if (!k.gerekli)
    return (
      <p className="mt-2 rounded-md bg-iyi-zemin px-3 py-2 text-sm text-iyi">
        <strong>Bu programda başvuru metni yazılmaz.</strong> {k.aciklama}
      </p>
    );
  return (
    <div className="mt-2 rounded-md bg-zemin px-3 py-2 text-sm leading-relaxed">
      <p>
        <strong>Ne için:</strong> {k.ne_icin}
        {k.form_kaynak && (
          <>
            {' '}(
            <a href={k.form_kaynak} target="_blank" rel="noopener noreferrer" className="text-vurgu underline">
              resmi form
            </a>
            )
          </>
        )}
      </p>
      {k.nereye && (
        <p>
          <strong>Nereye girilir:</strong> {k.nereye}
        </p>
      )}
      <p>
        <strong>Ne değildir:</strong> {k.ne_degil}
      </p>
      {k.aciklama && <p className="mt-1 text-soluk">{k.aciklama}</p>}
    </div>
  );
}

export function BasvurularSekmesi({ secili, onSec }: { secili: number | null; onSec: (id: number | null) => void }) {
  const [listeler, setListeler] = useState<ListeOzeti[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  const listeleriYukle = useCallback(() => {
    api
      .listeler()
      .then((r) => setListeler(r.listeler))
      .catch((e) => setHata(e instanceof Error ? e.message : 'Listeler yüklenemedi.'));
  }, []);

  useEffect(listeleriYukle, [listeleriYukle]);

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="flex min-w-0 flex-col gap-2">
        <h2 className="text-sm font-bold">Takip ettiğim başvurular</h2>
        {hata && <Bilgi tur="hata">{hata}</Bilgi>}
        {!listeler && !hata && <Yukleniyor />}
        {listeler?.length === 0 && (
          <p className="text-sm text-soluk">Henüz yok. &quot;Uygun destekler&quot; bölümünden bir programın kontrol listesini açın.</p>
        )}
        {listeler?.map((l) => (
          <button
            key={l.tesvik_id}
            onClick={() => onSec(l.tesvik_id)}
            className={`rounded-md border px-3 py-2 text-left text-sm ${
              secili === l.tesvik_id ? 'border-vurgu bg-yuzey' : 'border-cizgi bg-yuzey hover:border-vurgu'
            }`}
          >
            <span className="block font-semibold">{l.baslik}</span>
            <span className="block text-xs text-soluk tabular-nums">
              {l.kurum} · {l.tamamlanan}/{l.toplam} tamamlandı
            </span>
          </button>
        ))}
      </aside>

      <div className="min-w-0">
        {secili === null ? (
          <Kart>
            <p className="text-sm text-soluk">Bir başvuru seçin.</p>
          </Kart>
        ) : (
          <ListeAyrinti
            key={secili}
            tesvikId={secili}
            onDegisti={listeleriYukle}
            onKaldirildi={() => {
              onSec(null);
              listeleriYukle();
            }}
          />
        )}
      </div>
    </div>
  );
}

function ListeAyrinti({ tesvikId, onDegisti, onKaldirildi }: { tesvikId: number; onDegisti: () => void; onKaldirildi: () => void }) {
  const [liste, setListe] = useState<Liste | null>(null);
  const [mesaj, setMesaj] = useState<{ tur: 'iyi' | 'uyari' | 'hata'; metin: string } | null>(null);
  const [taslakYaziliyor, setTaslakYaziliyor] = useState(false);
  const [sihirbaz, setSihirbaz] = useState(false);

  useEffect(() => {
    api
      .liste(tesvikId)
      .then(setListe)
      .catch((e) => setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Liste yüklenemedi.' }));
  }, [tesvikId]);

  if (!liste) return mesaj ? <Bilgi tur={mesaj.tur}>{mesaj.metin}</Bilgi> : <Yukleniyor />;
  const t = liste.tesvik;

  async function kaydet(degisen: { anahtar: string; isaretli?: boolean; cevap?: Cevap }) {
    if (!liste) return;
    const { isaretli, uygunluk } = kaydedilecek(liste.maddeler, degisen);
    try {
      setListe(await api.isaretle(tesvikId, isaretli, uygunluk));
      onDegisti();
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Kaydedilemedi.' });
    }
  }

  async function taslakYaz() {
    setTaslakYaziliyor(true);
    setMesaj({ tur: 'uyari', metin: 'Taslak hazırlanıyor…' });
    try {
      setListe(await api.taslak(tesvikId));
      setMesaj({ tur: 'iyi', metin: 'Taslak hazır. [DOLDURUN] ile işaretli yerleri kendi bilgilerinizle tamamlayın.' });
      onDegisti();
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Taslak yazılamadı.' });
    } finally {
      setTaslakYaziliyor(false);
    }
  }

  async function kopyala() {
    if (!liste?.taslak) return;
    try {
      await navigator.clipboard.writeText(liste.taslak);
      setMesaj({ tur: 'iyi', metin: 'Taslak panoya kopyalandı.' });
    } catch {
      const alan = document.getElementById('taslak-metni') as HTMLTextAreaElement | null;
      alan?.select();
      setMesaj({ tur: 'uyari', metin: 'Tarayıcı panoya erişime izin vermedi; metin seçildi, Ctrl+C ile kopyalayın.' });
    }
  }

  async function word() {
    try {
      await wordIndir(tesvikId);
      setMesaj({ tur: 'iyi', metin: 'Word dosyası indirildi. İndirme başlamadıysa uygulamayı yeni sekmede açıp tekrar deneyin.' });
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Word dosyası hazırlanamadı.' });
    }
  }

  async function kaldir() {
    try {
      await api.birak(tesvikId);
      onKaldirildi();
    } catch (e) {
      setMesaj({ tur: 'hata', metin: e instanceof Error ? e.message : 'Kaldırılamadı.' });
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Kart>
        <p className="text-xs font-semibold uppercase tracking-wide text-soluk">{t.kurum}</p>
        <h2 className="mt-0.5 text-lg font-bold">{t.baslik}</h2>
        <p className="mt-1 text-sm text-soluk">
          {/* Dönem, çağrı kaydı varsa yalnız "Başvuru dönemleri"nden gelir (eski serbest metin çağrıyla çelişebiliyordu). */}
          {[t.basvuru_yeri && `Başvuru yeri: ${t.basvuru_yeri}`, !liste.cagrilar.length && t.basvuru_suresi && `Dönem: ${t.basvuru_suresi}`]
            .filter(Boolean).join(' · ')}
          {t.aktif_mi === false && ' · Bu program şu an başvuruya kapalı görünüyor'}
        </p>
        {t.kaynak_url && (
          <a href={t.kaynak_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-sm text-vurgu underline">
            Kurumun resmi sayfası
          </a>
        )}
      </Kart>

      {mesaj && <Bilgi tur={mesaj.tur}>{mesaj.metin}</Bilgi>}

      <Kart>
        <h3 className="font-bold">Başvuru dönemleri</h3>
        {liste.cagrilar.length === 0 ? (
          <p className="mt-1 text-sm text-soluk">
            Bu program için doğrulanmış başvuru dönemi kaydımız yok; tarihleri kurumun resmi sayfasından kontrol edin.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {liste.cagrilar.map((c) => (
              <li key={c.id} className="text-sm">
                <span className={`font-semibold ${c.durum === 'acik' ? 'text-iyi' : c.durum === 'kapandi' ? 'text-soluk' : ''}`}>
                  {c.ad}: {cagriOzeti(c)}
                </span>
                {c.notlar && <span className="block text-soluk">{c.notlar}</span>}
                <span className="block text-xs text-soluk">
                  Kaynak:{' '}
                  <a href={c.kaynak_url} target="_blank" rel="noopener noreferrer" className="underline">
                    resmi duyuru
                  </a>{' '}
                  · doğrulama {tarih(c.dogrulama_tarihi)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Kart>

      {liste.uyari && (
        <Kart>
          <p className="text-sm text-soluk">{liste.uyari}</p>
        </Kart>
      )}
      {gruplar(liste.maddeler).map(([bolum, maddeler]) => (
        <Kart key={bolum} className={bolum === 'bilinmesi' ? 'bg-uyari-zemin' : ''}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-bold">{BOLUM[bolum].baslik}</h3>
            {(bolum === 'belge' || bolum === 'adim') && (
              <span className="text-sm tabular-nums text-soluk">
                hazırlık {liste.tamamlanan}/{liste.toplam}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs text-soluk">{BOLUM[bolum].aciklama}</p>
          {bolum === 'sart' && (
            <p
              className={`mt-2 rounded-md px-3 py-2 text-sm ${uygunlukOzeti(liste.uygunluk).uyari ? 'bg-hata-zemin text-hata' : 'text-soluk'}`}
            >
              {uygunlukOzeti(liste.uygunluk).metin}
            </p>
          )}
          {bolum === 'sart' ? (
            <ul className="mt-3 flex flex-col gap-3">
              {maddeler.map((m) => (
                <li key={m.anahtar} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="min-w-0 flex-1 basis-64">
                    {m.metin}
                    <Kaynak m={m} />
                  </span>
                  <span className="inline-flex overflow-hidden rounded-md border border-cizgi" role="radiogroup" aria-label="Bu şartı sağlıyor musunuz?">
                    {(Object.keys(CEVAP_ETIKETI) as Cevap[]).map((c) => (
                      <button
                        key={c}
                        type="button"
                        role="radio"
                        aria-checked={m.cevap === c}
                        onClick={() => kaydet({ anahtar: m.anahtar, cevap: c })}
                        className={`border-l border-cizgi px-3 py-1 text-xs font-semibold first:border-l-0 ${
                          m.cevap === c ? CEVAP_RENGI[c] : 'bg-yuzey text-soluk hover:bg-zemin'
                        }`}
                      >
                        {CEVAP_ETIKETI[c]}
                      </button>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          ) : bolum === 'bilinmesi' ? (
            <ul className="mt-2 flex flex-col gap-1.5 text-sm">
              {maddeler.map((m) => (
                <li key={m.anahtar}>
                  {m.tur === 'kural' ? '⚠ ' : '• '}
                  {m.metin}
                  <Kaynak m={m} />
                </li>
              ))}
            </ul>
          ) : (
            <ol className={`mt-3 flex flex-col gap-2 ${bolum === 'adim' ? 'list-decimal pl-5 marker:font-bold marker:text-vurgu' : ''}`}>
              {maddeler.map((m) => (
                <li key={m.anahtar} className="text-sm">
                  <label className="flex min-w-0 items-start gap-2">
                    <input
                      type="checkbox"
                      checked={m.isaretli}
                      aria-label={bolum === 'belge' ? 'hazır' : 'yapıldı'}
                      onChange={(e) => kaydet({ anahtar: m.anahtar, isaretli: e.target.checked })}
                      className="mt-0.5 h-4 w-4 shrink-0 accent-vurgu"
                    />
                    <span className={`min-w-0 [overflow-wrap:anywhere] ${m.isaretli ? 'text-soluk line-through' : ''}`}>{m.metin}</span>
                  </label>
                  <Kaynak m={m} />
                </li>
              ))}
            </ol>
          )}
        </Kart>
      ))}

      <Kart>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-bold">
            Başvuru metni taslağı{liste.taslak_kapsami.resmi_form ? ` — ${liste.taslak_kapsami.resmi_form}` : ''}
          </h3>
          <div className="flex flex-wrap gap-2">
            {liste.taslak && (
              <Dugme tur="ikincil" onClick={kopyala}>
                Kopyala
              </Dugme>
            )}
            {(liste.taslak_kapsami.gerekli || liste.taslak) && (
              <>
                <Dugme tur="ikincil" onClick={taslakYaz} disabled={taslakYaziliyor}>
                  {liste.taslak ? 'Yeniden yaz' : 'Hızlı taslak'}
                </Dugme>
                <Dugme onClick={() => setSihirbaz(true)} disabled={sihirbaz}>
                  {liste.taslak_cevaplar ? 'Cevapları düzenle' : 'Sihirbazla doldur'}
                </Dugme>
              </>
            )}
          </div>
        </div>
        <Kapsam k={liste.taslak_kapsami} />
        {liste.taslak ? (
          <>
            <p className="mt-1 text-xs text-soluk">Oluşturma: {tarihSaat(liste.taslak_tarihi)} · Resmi başvuru formu değildir.</p>
            <textarea
              id="taslak-metni"
              readOnly
              value={liste.taslak}
              className="mt-3 h-96 w-full resize-y rounded-md border border-cizgi bg-zemin p-3 font-mono text-xs leading-relaxed"
            />
          </>
        ) : liste.taslak_kapsami.gerekli ? (
          <p className="mt-2 text-sm text-soluk">
            Sihirbaz projenizi, takviminizi ve bütçenizi sorar; resmi formu tanımlı programlarda sorular formun kendi
            bölümleridir. Bilinmeyen yerler [DOLDURUN] olarak bırakılır, rakam uydurulmaz.
          </p>
        ) : (
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-vurgu">Yine de bir metin taslağı hazırlamak istiyorum</summary>
            <div className="mt-2 flex flex-wrap gap-2">
              <Dugme tur="ikincil" onClick={taslakYaz} disabled={taslakYaziliyor}>
                Hızlı taslak
              </Dugme>
              <Dugme tur="ikincil" onClick={() => setSihirbaz(true)} disabled={sihirbaz}>
                Sihirbazla doldur
              </Dugme>
            </div>
          </details>
        )}
      </Kart>

      {sihirbaz && (
        <TaslakSihirbazi
          tesvikId={tesvikId}
          onKapat={() => setSihirbaz(false)}
          onBitti={(l) => {
            setListe(l);
            setSihirbaz(false);
            setMesaj({ tur: 'iyi', metin: 'Taslak cevaplarınızla yazıldı; cevaplar kaydedildi.' });
            onDegisti();
          }}
        />
      )}

      <div className="flex flex-wrap gap-2">
        <Dugme onClick={word}>Word (.docx) indir</Dugme>
        <Dugme tur="tehlike" onClick={kaldir}>
          Bu başvuruyu takipten çıkar
        </Dugme>
      </div>
    </div>
  );
}
