// sifre_sifirla.html sayfasının betiği (CSP: satır içi betik yasak, bkz. app/main.py CSP).
// Sıfırlama belirteci URL'nin # (fragment) kısmında gelir: sunucuya, günlüklere ve Referer'a gitmez.
// Okunur okunmaz adres çubuğundan ve geçmişten silinir.
const belirtec = new URLSearchParams(location.hash.slice(1)).get('t');
if (belirtec) history.replaceState(null, '', location.pathname);

const $ = id => document.getElementById(id);
function goster(kutu, metin) {
  $('hata').style.display = 'none'; $('tamam').style.display = 'none';
  $(kutu).textContent = metin; $(kutu).style.display = 'block';
}
async function gonder(yol, govde) {
  const r = await fetch(yol, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(govde) });
  const veri = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = veri.detail;
    throw new Error(typeof d === 'string' ? d : (Array.isArray(d) && d[0] && d[0].msg) ? d[0].msg.replace(/^Value error, /, '') : 'İstek başarısız (' + r.status + ')');
  }
  return veri;
}

if (belirtec) {
  $('baslik').textContent = 'Yeni parola belirle';
  $('alt').textContent = 'Hesabınız için yeni bir parola girin. Bağlantı tek kullanımlıktır.';
  $('istek-formu').style.display = 'none';
  $('yeni-formu').style.display = 'block';
}

$('istek-formu').addEventListener('submit', async e => {
  e.preventDefault(); $('istek-dugme').disabled = true;
  try { goster('tamam', (await gonder('/api/auth/sifre-unuttum', { email: $('eposta').value.trim() })).mesaj); }
  catch (err) { goster('hata', err.message); }
  finally { $('istek-dugme').disabled = false; }
});

$('yeni-formu').addEventListener('submit', async e => {
  e.preventDefault();
  if ($('parola').value !== $('parola2').value) { goster('hata', 'Parolalar eşleşmiyor'); return; }
  $('yeni-dugme').disabled = true;
  try {
    goster('tamam', (await gonder('/api/auth/sifre-sifirla', { token: belirtec, new_password: $('parola').value })).mesaj);
    $('yeni-formu').style.display = 'none';
  } catch (err) { goster('hata', err.message); $('yeni-dugme').disabled = false; }
});
