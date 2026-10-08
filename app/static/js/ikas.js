// ikas.html: İKAS yönetim panelinden açılış (CSP: satır içi betik yasak, bkz. app/main.py).
// İKAS adrese authorizedAppId, merchantId, signature, storeName, timestamp ekler; imza 120 sn geçerlidir.
// Parametreler okununca adresten silinir (geçmişte/yer imlerinde imzalı adres kalmasın).
const p = new URLSearchParams(location.search);
const girdi = {};
['storeName', 'merchantId', 'authorizedAppId', 'timestamp', 'signature'].forEach((k) => { girdi[k] = p.get(k) || ''; });
history.replaceState(null, '', location.pathname);
const kutu = document.getElementById('sonuc');
const donen = document.getElementById('yukleniyor');

function bitir(metin, panelLinki) {
  kutu.textContent = metin;
  donen.hidden = true;
  document.getElementById('panel').hidden = !panelLinki;
}

function belirteciSakla(t) {
  // İframe içinde depolama üçüncü taraf bağlamına bölünür; tarayıcı tamamen engellerse kullanıcıya söylenir.
  try {
    localStorage.setItem('auth_token', t);
    localStorage.setItem('token', t);
    return true;
  } catch (e) { return false; }
}

(async () => {
  if (!girdi.storeName || !girdi.signature) {
    bitir('Bu sayfa İKAS yönetim panelinden açılır. Uygulamayı İKAS panelinizde Uygulamalar bölümünden açın.', false);
    return;
  }
  try {
    const r = await fetch('/api/ikas/oturum', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(girdi) });
    const v = await r.json().catch(() => ({}));
    if (!r.ok) { bitir(typeof v.detail === 'string' ? v.detail : 'Giriş başarısız (' + r.status + ').', false); return; }
    if (!belirteciSakla(v.access_token)) {
      bitir('Tarayıcınız bu çerçevede veri saklamaya izin vermiyor. Üçüncü taraf çerez/depolama ayarını açın ya da uygulamayı yeni sekmede açın.', false);
      return;
    }
    if (v.senkron_bekliyor) {
      kutu.textContent = 'Mağaza verileriniz (son 12 ay sipariş özeti) okunuyor…';
      // Senkron başarısız olsa da panel açılır; durum panelde gösterilir.
      await fetch('/api/ikas/senkronize', { method: 'POST', headers: { Authorization: 'Bearer ' + v.access_token } }).catch(() => null);
    }
    kutu.textContent = 'Giriş yapıldı, panele yönlendiriliyorsunuz…';
    location.replace('/dashboard');
  } catch (e) {
    bitir('Sunucuya ulaşılamadı; biraz sonra tekrar deneyin.', false);
  }
})();
