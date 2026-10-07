// eposta_dogrula.html sayfasının betiği (CSP: satır içi betik yasak, bkz. app/main.py CSP).
// Belirteç URL'nin # kısmında gelir (sunucuya/Referer'a gitmez); okununca adresten silinir.
const belirtec = new URLSearchParams(location.hash.slice(1)).get('t');
if (belirtec) history.replaceState(null, '', location.pathname);
const kutu = document.getElementById('sonuc');
const form = document.getElementById('parola-formu');

async function dogrula(parola) {
  const govde = { token: belirtec };
  if (parola) govde.password = parola;
  const r = await fetch('/api/auth/eposta-dogrula', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(govde) });
  const v = await r.json().catch(() => ({}));
  if (r.status === 428) {
    kutu.textContent = v.detail;
    form.hidden = false;
    document.getElementById('panel').hidden = true;
    document.getElementById('parola').focus();
    return;
  }
  if (!r.ok) {
    kutu.textContent = typeof v.detail === 'string' ? v.detail : 'Doğrulama başarısız (' + r.status + ')';
    return;
  }
  kutu.textContent = v.mesaj;
  form.hidden = true;
  if (v.access_token) {
    localStorage.setItem('auth_token', v.access_token);
    localStorage.setItem('token', v.access_token);
  }
  document.getElementById('panel').hidden = false;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const dugme = document.getElementById('etkinlestir');
  dugme.disabled = true;
  try { await dogrula(document.getElementById('parola').value); }
  catch (err) { kutu.textContent = 'Sunucuya ulaşılamadı; biraz sonra tekrar deneyin.'; }
  finally { dugme.disabled = false; }
});

(async () => {
  if (!belirtec) { kutu.textContent = 'Doğrulama bağlantısı eksik. E-postanızdaki bağlantıyı kullanın.'; return; }
  try { await dogrula(null); }
  catch (e) { kutu.textContent = 'Sunucuya ulaşılamadı; biraz sonra tekrar deneyin.'; }
})();
