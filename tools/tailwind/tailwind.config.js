// Çilek panelinin Tailwind CSS'i önceden derlenir (CSP: script-src 'self'; cdn.tailwindcss.com çalışma
// zamanı derleyicisi hem dış betik hem satır içi <style> enjeksiyonu demekti). Çıktı depoya girer, uygulama
// çalışırken Node gerekmez. Sınıf eklenip değiştirildiğinde proje kökünden yeniden derleyin:
//
//   npx tailwindcss@3.4.17 -c tools/tailwind/tailwind.config.js -i tools/tailwind/cilek.input.css -o app/static/css/cilek.css --minify
//
// tests/test_csp.py, sayfadaki her Tailwind sınıfının derlenmiş CSS'te bulunduğunu denetler (unutulan derleme kırmızı yanar).
module.exports = {
  content: [
    "./app/static/cilek_dashboard.html",
    "./app/static/js/cilek.js",
  ],
  theme: { extend: {} },
  plugins: [],
};
