// dashboard.html sayfasının betiği (CSP: satır içi betik yasak, bkz. app/main.py CSP).
        // Sabit "http://localhost:8000" yaziliydi: farkli bir port/domain'de
        // (canliya cikinca veya farkli portta test ederken) TUM istekler
        // "Failed to fetch" ile kiriliyordu. Sayfanin kendi origin'ini
        // kullanmak her ortamda calisir.
        const API_BASE = window.location.origin + "/api";
        // Diger dashboard sayfalari (login.html/dashboard_pro.html) "token"
        // anahtarina yaziyor - hangi sayfadan giris yapilmis olursa olsun
        // (login yaptiktan sonra bu sayfalar artik her iki anahtara da
        // yaziyor, ama daha ONCE tek anahtara yazilmis eski oturumlar icin
        // de) burada ikisini de kontrol ediyoruz.
        let authToken = localStorage.getItem("auth_token") || localStorage.getItem("token");
        let currentOrg = null;

        // Auth check
        if (!authToken) {
            window.location.href = "/";
        }

        // Oturum iptal edildiyse (parola sıfırlandı, "tüm oturumları kapat" ya da süre doldu) API 401 döner.
        // Panel boş kalmasın: belirteci sil, giriş sayfasına açıklamayla dön. 401 yalnızca geçersiz belirteç
        // içindir (yanlış teyit parolası 403 döner).
        // Yalnızca GÜNCEL belirteçle yapılan istek 401 alırsa çıkılır: "tüm oturumları kapat" sırasında eski
        // belirteçle yolda kalmış bir istek, yeni belirteç alınmış oturumu kapatmasın.
        const _asilFetch = window.fetch.bind(window);
        window.fetch = async (...args) => {
            const kullanilan = authToken;
            const yanit = await _asilFetch(...args);
            const adres = String((args[0] && args[0].url) || args[0]);
            const baslik = (args[1] && args[1].headers && args[1].headers.Authorization) || "";
            if (yanit.status === 401 && adres.includes("/api/")
                    && baslik === `Bearer ${kullanilan}` && kullanilan === authToken) {
                oturumBitti();
            }
            return yanit;
        };
        function oturumBitti() {
            localStorage.removeItem("auth_token");
            localStorage.removeItem("token");
            window.location.href = "/?oturum=bitti";
        }

        // Load dashboard on page load
        document.addEventListener("DOMContentLoaded", async () => {
            await loadOrganization();
            await confirmCheckoutIfReturning();
            loadAnalytics();
            loadPricing();
            loadFinancialProfile();
            loadVeriDurumu();
            setupMenuListeners();
            document.getElementById("tum-oturumlari-kapat").addEventListener("click", tumOturumlariKapat);
            epostaDurumuYukle();
        });

        // E-posta doğrulama uyarısı (giriş doğrulamaya bağlı değil; yalnızca hatırlatır).
        async function epostaDurumuYukle() {
            try {
                const r = await fetch("/api/auth/me", { headers: { Authorization: `Bearer ${authToken}` } });
                if (!r.ok) return;
                const me = await r.json();
                // İKAS kurulumunda e-posta başka hesapta kayıtlıysa yer tutucu adres verilir; doğrulanacak posta kutusu yok.
                if (me.email_dogrulandi || (me.email || "").endsWith("@magaza.ikas.invalid")) return;
                document.getElementById("eposta-uyari").style.display = "block";
                document.getElementById("eposta-dogrulama-gonder").onclick = async () => {
                    const sonuc = document.getElementById("eposta-uyari-sonuc");
                    const g = await fetch("/api/auth/dogrulama-gonder", { method: "POST", headers: { Authorization: `Bearer ${authToken}` } });
                    const v = await g.json().catch(() => ({}));
                    sonuc.textContent = g.ok ? v.mesaj : (typeof v.detail === "string" ? v.detail : "Gönderilemedi");
                };
            } catch (e) { /* uyarı isteğe bağlı */ }
        }

        // Menu navigation
        function setupMenuListeners() {
            document.querySelectorAll(".menu-link").forEach(link => {
                link.addEventListener("click", (e) => {
                    if (e.target.id === "logout-btn") {
                        e.preventDefault();
                        logout();
                        return;
                    }

                    e.preventDefault();
                    const section = e.target.dataset.section;
                    showSection(section);

                    // Update active menu item
                    document.querySelectorAll(".menu-link").forEach(l => l.classList.remove("active"));
                    e.target.classList.add("active");
                });
            });
        }

        function showSection(sectionId) {
            document.querySelectorAll(".section").forEach(s => s.classList.add("hidden"));
            document.getElementById(sectionId).classList.remove("hidden");
            // Geçmiş ve Ayarlar sekmeleri boş div'di (denetim 2026-10-07); açılınca doldurulur.
            if (sectionId === "history") loadHistory();
            if (sectionId === "settings") loadSettings();
            if (sectionId === "basvurular") basvurularYukle();
            if (sectionId === "profil") ikasKartiYukle();
        }

        // ---- İKAS mağaza verisi (yalnızca bağlantı kaydı varsa görünür) ----
        const IKAS_DURUM_METNI = {
            bagli: "Bağlı",
            beklemede: "Onay bekleniyor",
            hata: "Hata — yeniden bağlanmanız gerekebilir",
            kaldirildi: "Uygulama İKAS'tan kaldırıldı",
        };
        function trSayi(x, basamak = 0) {
            return Number(x || 0).toLocaleString("tr-TR", { minimumFractionDigits: basamak, maximumFractionDigits: basamak });
        }
        async function ikasKartiYukle() {
            const kart = document.getElementById("ikas-kart");
            try {
                const r = await fetch(`${API_BASE}/ikas/durum`, { headers: { Authorization: `Bearer ${authToken}` } });
                if (!r.ok) return;
                const d = await r.json();
                if (d.baglanti_durumu === "bagli_degil") { kart.style.display = "none"; return; }
                kart.style.display = "block";
                const son = d.son_senkron_zamani ? new Date(d.son_senkron_zamani + (d.son_senkron_zamani.endsWith("Z") ? "" : "Z")).toLocaleString("tr-TR") : "henüz yok";
                document.getElementById("ikas-durum").textContent =
                    `Mağaza: ${d.store_name} · Durum: ${IKAS_DURUM_METNI[d.baglanti_durumu] || d.baglanti_durumu} · Son senkron: ${son}`
                    + (d.son_senkron_hata ? ` · Son hata: ${d.son_senkron_hata}` : "")
                    + (d.mock_mode ? " · (deneme modu: örnek veri)" : "");
                const o = d.ozet || {};
                const kutular = [
                    ["Satış siparişi (12 ay)", trSayi(o.siparis_sayisi)],
                    ["Ciro (TL siparişler)", trSayi(o.yillik_ciro, 2) + " TL"],
                    ["Yurt dışı teslimat", `${trSayi(o.yurt_disi_siparis)} sipariş` + ((o.yurt_disi_ulkeler || []).length ? ` (${o.yurt_disi_ulkeler.join(", ")})` : "")],
                    ["Döviz cinsinden satış", Object.entries(o.doviz_toplamlari || {}).map(([k, t]) => `${trSayi(t, 2)} ${k}`).join(", ") || "yok"],
                ];
                document.getElementById("ikas-ozet").innerHTML = kutular.map(([b, v]) =>
                    `<div class="stat-card"><h3>${escapeHtml(b)}</h3><div style="font-size:18px; font-weight:bold; color:#333;">${escapeHtml(v)}</div></div>`).join("");
                document.getElementById("ikas-notlar").innerHTML = (o.notlar || []).map(n => `<li>${escapeHtml(n)}</li>`).join("");
                document.getElementById("ikas-yenile").disabled = d.baglanti_durumu !== "bagli";
            } catch (e) { /* kart isteğe bağlı */ }
        }
        async function ikasYenile() {
            const mesaj = document.getElementById("ikas-mesaj");
            const dugme = document.getElementById("ikas-yenile");
            dugme.disabled = true;
            mesaj.textContent = "Mağaza verileri okunuyor…";
            try {
                const r = await fetch(`${API_BASE}/ikas/senkronize`, { method: "POST", headers: { Authorization: `Bearer ${authToken}` } });
                const v = await r.json().catch(() => ({}));
                mesaj.textContent = r.ok ? "Güncellendi. Profilinizdeki yıllık ciro mağaza verisinden yenilendi."
                                         : (typeof v.detail === "string" ? v.detail : "Yenilenemedi (" + r.status + ")");
                if (r.ok) { await ikasKartiYukle(); loadFinancialProfile(); }
            } catch (e) { mesaj.textContent = "Sunucuya ulaşılamadı."; }
            finally { dugme.disabled = false; }
        }
        // confirm() yerine iki tıklama: İKAS paneli uygulamayı iframe'de açar; sandbox'ta modal pencereler engellenebilir.
        let ikasKesOnay = 0;
        async function ikasBaglantiKes() {
            const mesaj = document.getElementById("ikas-mesaj");
            if (Date.now() - ikasKesOnay > 8000) {
                ikasKesOnay = Date.now();
                mesaj.textContent = "Saklı erişim anahtarları ve sipariş özeti silinecek (profilinizdeki ciro kalır). Onaylamak için 8 saniye içinde tekrar tıklayın.";
                return;
            }
            ikasKesOnay = 0;
            const r = await fetch(`${API_BASE}/ikas/baglanti`, { method: "DELETE", headers: { Authorization: `Bearer ${authToken}` } });
            const v = await r.json().catch(() => ({}));
            document.getElementById("ikas-mesaj").textContent = v.mesaj || v.detail || "";
            if (r.ok) setTimeout(ikasKartiYukle, 2500);
        }

        // ---- Ayarlar: hesap bilgisi, AI rıza anahtarı, hesap silme ----
        function loadSettings() {
            if (!currentOrg) return;
            document.getElementById("ayar-email").textContent = currentOrg.email || "—";
            document.getElementById("ayar-plan").textContent = (currentOrg.plan || "free").toUpperCase();
            const cb = document.getElementById("ayar-riza");
            cb.checked = !!currentOrg.ai_yurtdisi_riza;
            document.getElementById("ayar-riza-metin").textContent = cb.checked ? "Açık" : "Kapalı";
        }

        async function rizaDegistir(cb) {
            const mesaj = document.getElementById("ayar-riza-mesaj");
            cb.disabled = true;
            try {
                const res = await fetch(`${API_BASE}/organizations/ai-riza`, {
                    method: "POST",
                    headers: { "Authorization": `Bearer ${authToken}`, "Content-Type": "application/json" },
                    body: JSON.stringify({ riza: cb.checked })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(hataMetni(data));
                currentOrg.ai_yurtdisi_riza = !!data.ai_yurtdisi_riza;
                cb.checked = currentOrg.ai_yurtdisi_riza;
                document.getElementById("ayar-riza-metin").textContent = cb.checked ? "Açık" : "Kapalı";
                mesaj.innerHTML = `<div class="success">${escapeHtml(data.mesaj || "Kaydedildi.")}</div>`;
            } catch (e) {
                cb.checked = !cb.checked;
                mesaj.innerHTML = `<div class="error">Hata: ${escapeHtml(e.message)}</div>`;
            } finally {
                cb.disabled = false;
            }
        }

        async function tumOturumlariKapat() {
            const mesaj = document.getElementById("oturum-mesaj");
            try {
                const res = await fetch(`${API_BASE}/auth/tum-oturumlari-kapat`, {
                    method: "POST",
                    headers: { "Authorization": `Bearer ${authToken}` }
                });
                const data = await res.json();
                if (!res.ok) throw new Error(hataMetni(data));
                authToken = data.access_token;
                localStorage.setItem("auth_token", authToken);
                localStorage.setItem("token", authToken);
                mesaj.innerHTML = '<div class="success">Diğer tüm oturumlar kapatıldı.</div>';
            } catch (e) {
                mesaj.innerHTML = `<div class="error">Hata: ${escapeHtml(e.message)}</div>`;
            }
        }

        async function hesabiSil() {
            const mesaj = document.getElementById("sil-mesaj");
            const parola = document.getElementById("sil-parola").value;
            const onay = document.getElementById("sil-onay").checked;
            if (!parola || !onay) {
                mesaj.innerHTML = '<div class="error">Parolanızı girin ve onay kutusunu işaretleyin.</div>';
                return;
            }
            if (!confirm("Hesabınız ve tüm verileriniz kalıcı olarak silinecek. Devam edilsin mi?")) return;
            try {
                const res = await fetch(`${API_BASE}/organizations/me`, {
                    method: "DELETE",
                    headers: { "Authorization": `Bearer ${authToken}`, "Content-Type": "application/json" },
                    body: JSON.stringify({ password: parola, onay: true })
                });
                const data = await res.json();
                if (!res.ok) {
                    mesaj.innerHTML = `<div class="error">${escapeHtml(hataMetni(data))}</div>`;
                    return;
                }
                localStorage.removeItem("auth_token");
                localStorage.removeItem("token");
                alert(data.message || "Hesabınız silindi.");
                window.location.href = "/";
            } catch (e) {
                mesaj.innerHTML = `<div class="error">Hata: ${escapeHtml(e.message)}</div>`;
            }
        }

        // ---- Geçmiş sorgular ----
        async function loadHistory() {
            const div = document.getElementById("history-content");
            div.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            try {
                const res = await fetch(`${API_BASE}/queries/history?limit=30`, {
                    headers: { "Authorization": `Bearer ${authToken}` }
                });
                if (!res.ok) {
                    const err = await res.json();
                    div.innerHTML = `<div class="error">${escapeHtml(hataMetni(err))}</div>`;
                    return;
                }
                const liste = await res.json();
                if (!liste.length) {
                    div.innerHTML = `<div class="bos-durum">Henüz sorgunuz yok. <a href="#" data-tikla="bolumeGit" data-arg="search">Arama</a> sekmesinden ilk sorunuzu sorun.</div>`;
                    return;
                }
                div.innerHTML = liste.map(q => `
                    <div class="result-card">
                        <div class="kurum">${new Date(q.created_at).toLocaleString("tr-TR")}</div>
                        <div class="baslik">${escapeHtml(q.question)}</div>
                        <div class="ozet">${(q.results || []).slice(0, 3).map(r => `• ${escapeHtml(r.kurum)} — ${escapeHtml(r.baslik)}`).join("<br>") || "Eşleşen kayıt yok"}</div>
                        <button type="button" class="kucuk-btn" data-tikla="tekrarSor" data-arg="${escapeHtml(q.question)}">🔁 Tekrar sor</button>
                    </div>`).join("");
            } catch (e) {
                div.innerHTML = `<div class="error">Hata: ${escapeHtml(e.message)}</div>`;
            }
        }

        function tekrarSor(soru) {
            document.getElementById("search-input").value = soru;
            document.querySelector('[data-section=search]').click();
            performSearch();
        }

        async function loadOrganization() {
            try {
                const res = await fetch(`${API_BASE}/organizations/me`, {
                    headers: { "Authorization": `Bearer ${authToken}` }
                });

                if (!res.ok) throw new Error("Failed to load org");

                currentOrg = await res.json();
                document.getElementById("user-email").textContent = currentOrg.email;
                document.getElementById("plan-badge").textContent = currentOrg.plan.toUpperCase();
            } catch (e) {
                console.error("Error loading organization:", e);
            }
        }

        async function performSearch() {
            const question = document.getElementById("search-input").value.trim();
            if (!question) {
                alert("Lütfen bir soru girin");
                return;
            }

            const resultsDiv = document.getElementById("search-results");
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

            try {
                // Akışlı uç nokta: danışman yanıtı parça parça gelir (tam yanıt 35-60 sn;
                // eskiden bu süre boyunca yalnızca spinner görünüyor ve yanıt hiç
                // render edilmiyordu). Olaylar: kayitlar -> parca... -> son | hata.
                const res = await fetch(`${API_BASE}/sor/akis`, {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${authToken}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ question })
                });

                if (!res.ok) {
                    const error = await res.json();
                    resultsDiv.innerHTML = `<div class="error">${escapeHtml(error.detail)}</div>`;
                    return;
                }

                resultsDiv.innerHTML = `
                    <div class="ai-cevap">
                        <div class="ai-baslik"><span>🤖 Danışman yanıtı</span><span class="ai-durum" id="ai-durum">hazırlanıyor…</span></div>
                        <div class="ai-metin" id="ai-metin"><div class="loading"><div class="spinner"></div></div></div>
                    </div>
                    <div id="kayit-listesi"></div>`;
                const metinDiv = document.getElementById("ai-metin");
                const durumSpan = document.getElementById("ai-durum");
                let metin = "";
                let hata = null;

                await sseOku(res, (tip, veri) => {
                    if (tip === "kayitlar") {
                        renderKayitlar(veri, document.getElementById("kayit-listesi"));
                    } else if (tip === "parca") {
                        metin += veri.metin;
                        metinDiv.innerHTML = mdToHtml(metin) + '<span class="imlec"></span>';
                        durumSpan.textContent = "yazıyor…";
                    } else if (tip === "hata") {
                        hata = veri.detail;
                    }
                });

                if (hata) {
                    metinDiv.innerHTML = (metin ? mdToHtml(metin) : "") + `<div class="error">${escapeHtml(hata)}</div>`;
                    durumSpan.textContent = "hata";
                } else if (!metin) {
                    metinDiv.innerHTML = '<div class="error">Yanıt alınamadı. Lütfen tekrar deneyin.</div>';
                    durumSpan.textContent = "";
                } else {
                    metinDiv.innerHTML = mdToHtml(metin);
                    durumSpan.textContent = "";
                }

                // Refresh stats
                await loadAnalytics();
            } catch (e) {
                resultsDiv.innerHTML = `<div class="error">Hata: ${escapeHtml(e.message)}</div>`;
            }
        }

        function renderKayitlar(kayitlar, hedef) {
            if (!kayitlar || !kayitlar.length) {
                hedef.innerHTML = '<div class="bos-durum">Bu soruyla eşleşen kayıt bulunamadı. Kurum adı, sektör veya ihtiyaç ' +
                    '(ör. "makine yatırımı", "ihracat", "istihdam") yazarak tekrar deneyin; profilinizi doldurmak eşleşmeyi iyileştirir.</div>';
                return;
            }
            hedef.innerHTML = kayitlar.map(r => `
                <div class="result-card">
                    <div class="kurum">${escapeHtml(r.kurum)}</div>
                    <div class="baslik">${escapeHtml(r.baslik)}</div>
                    <div class="ozet">${escapeHtml(r.ozet)}</div>
                    <div class="meta">
                        <span>👥 ${escapeHtml(r.hedef_kitle || "Genel")}</span>
                        ${r.baslama_tarihi ? `<span>📅 Başlangıç: ${new Date(r.baslama_tarihi).toLocaleDateString('tr-TR')}</span>` : ""}
                        ${r.bitis_tarihi ? `<span>⏰ Bitiş: ${new Date(r.bitis_tarihi).toLocaleDateString('tr-TR')}</span>` : ""}
                    </div>
                </div>
            `).join("");
        }

        // Sunucudan gelen SSE gövdesini (event:/data: blokları) olay olay okur.
        async function sseOku(res, onEvent) {
            const reader = res.body.getReader();
            const dec = new TextDecoder();
            let buf = "";
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buf += dec.decode(value, { stream: true });
                let idx;
                while ((idx = buf.indexOf("\n\n")) >= 0) {
                    const blok = buf.slice(0, idx);
                    buf = buf.slice(idx + 2);
                    let tip = "message", data = "";
                    for (const satir of blok.split("\n")) {
                        if (satir.startsWith("event:")) tip = satir.slice(6).trim();
                        else if (satir.startsWith("data:")) data += satir.slice(5).trim();
                    }
                    if (data) onEvent(tip, JSON.parse(data));
                }
            }
        }

        function escapeHtml(s) {
            return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
        }

        // Sunucu hata gövdesi: detail düz metin (HTTPException) veya liste (422 doğrulama) olabilir.
        function hataMetni(err) {
            const d = err && err.detail;
            if (typeof d === "string") return d;
            if (Array.isArray(d)) return d.map(x => (x && x.msg) ? x.msg : JSON.stringify(x)).join(" ");
            return "Bilinmeyen hata";
        }

        // href'e yalnızca http(s) bağlantı basılır (javascript:/data: şemaları engellenir).
        function guvenliUrl(u) {
            return /^https?:\/\/[^\s"'<>]+$/i.test(String(u || "")) ? escapeHtml(u) : "";
        }

        // Danışman yanıtı Markdown gelir (başlık, kalın, liste, tablo). Önce HTML kaçışı,
        // sonra sınırlı Markdown -> HTML; harici kütüphane ve ham HTML yok (XSS yüzeyi yok).
        function inlineMd(s) {
            s = escapeHtml(s);
            s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
            s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
            s = s.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");
            s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
            s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
            return s;
        }

        function mdToHtml(md) {
            const lines = md.split("\n");
            let html = "", acik = null, i = 0;
            const kapat = () => { if (acik) { html += `</${acik}>`; acik = null; } };
            const tabloSatiri = l => /^\s*\|.*\|\s*$/.test(l);
            const hucreler = l => l.trim().replace(/^\||\|$/g, "").split("|").map(c => inlineMd(c.trim()));
            while (i < lines.length) {
                const line = lines[i];
                const h = line.match(/^(#{1,6})\s+(.*)$/);
                if (h) { kapat(); const n = h[1].length; html += `<h${n}>${inlineMd(h[2])}</h${n}>`; i++; continue; }
                if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { kapat(); html += "<hr>"; i++; continue; }
                if (tabloSatiri(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
                    kapat();
                    let t = "<table><thead><tr>" + hucreler(line).map(c => `<th>${c}</th>`).join("") + "</tr></thead><tbody>";
                    i += 2;
                    while (i < lines.length && tabloSatiri(lines[i])) {
                        t += "<tr>" + hucreler(lines[i]).map(c => `<td>${c}</td>`).join("") + "</tr>";
                        i++;
                    }
                    html += t + "</tbody></table>";
                    continue;
                }
                const bq = line.match(/^\s*>\s?(.*)$/);
                if (bq) { if (acik !== "blockquote") { kapat(); acik = "blockquote"; html += "<blockquote>"; } else { html += "<br>"; } html += inlineMd(bq[1]); i++; continue; }
                const ul = line.match(/^\s*[-*•]\s+(.*)$/);
                if (ul) {
                    if (acik !== "ul") { kapat(); acik = "ul"; html += "<ul>"; }
                    // Görev listesi: "- [x] ..." / "- [ ] ..." (başvuru taslağının belge bölümü)
                    const madde = ul[1].replace(/^\[[xX]\]\s*/, "☑ ").replace(/^\[ \]\s*/, "☐ ");
                    html += `<li>${inlineMd(madde)}</li>`; i++; continue;
                }
                const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
                if (ol) { if (acik !== "ol") { kapat(); acik = "ol"; html += "<ol>"; } html += `<li>${inlineMd(ol[1])}</li>`; i++; continue; }
                if (!line.trim()) { kapat(); i++; continue; }
                if (acik !== "p") { kapat(); acik = "p"; html += "<p>"; } else { html += "<br>"; }
                html += inlineMd(line);
                i++;
            }
            kapat();
            return html;
        }

        async function loadAnalytics() {
            try {
                const res = await fetch(`${API_BASE}/analytics/usage`, {
                    headers: { "Authorization": `Bearer ${authToken}` }
                });

                if (!res.ok) throw new Error("Failed to load analytics");

                const data = await res.json();

                // Update stats cards
                const stats = data.usage_stats;
                document.getElementById("queries-total").textContent = stats.queries_this_month;
                document.getElementById("queries-remaining").textContent =
                    stats.queries_limit ? (stats.queries_limit - stats.queries_this_month) : "∞";
                document.getElementById("active-members").textContent = stats.users_active;

                // Display full analytics
                const analyticsDiv = document.getElementById("analytics-content");
                analyticsDiv.innerHTML = `
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
                        <div class="stat-card">
                            <h3>Bu Ay Sorgu Sayısı</h3>
                            <div class="value">${stats.queries_this_month}</div>
                            ${stats.queries_limit ? `<p style="color: #999; margin-top: 10px;">Limit: ${stats.queries_limit}</p>` : "<p style='color: #999; margin-top: 10px;'>Sınırsız</p>"}
                        </div>
                        <div class="stat-card">
                            <h3>API Çağrıları</h3>
                            <div class="value">${stats.api_calls_this_month}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Aktif Üyeler</h3>
                            <div class="value">${stats.users_active}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Kullanılan Depolama</h3>
                            <div class="value">${stats.storage_used_mb.toFixed(2)} MB</div>
                        </div>
                    </div>
                `;
            } catch (e) {
                console.error("Error loading analytics:", e);
            }
        }

        async function loadPricing() {
            const pricingDiv = document.getElementById("pricing-plans");
            pricingDiv.innerHTML = `
                <div class="plan ${currentOrg?.plan === "free" ? "active" : ""}">
                    <h3>Free</h3>
                    <div class="price">₺0<span style="font-size: 14px; color: #999;">/ay</span></div>
                    <ul>
                        <li>✓ 5 sorgu/ay</li>
                        <li>✓ Temel kurumlar</li>
                        <li>✓ Email desteği</li>
                        <li>✗ API erişimi</li>
                        <li>✗ Webhooks</li>
                    </ul>
                    <button ${currentOrg?.plan === "free" ? "disabled" : ""} data-tikla="downgradeToFree">
                        ${currentOrg?.plan === "free" ? "Mevcut Plan" : "Free'ye Dön"}
                    </button>
                </div>

                <div class="plan ${currentOrg?.plan === "pro" ? "active" : ""}">
                    <h3>Pro</h3>
                    <div class="price">₺299<span style="font-size: 14px; color: #999;">/ay</span></div>
                    <ul>
                        <li>✓ Kişiselleştirilmiş teşvik eşleştirme</li>
                        <li>✓ Stok/reklam bütçe önerisi</li>
                        <li>✓ Sınırsız sorgu</li>
                        <li>✓ API erişimi</li>
                        <li>✓ Priority support</li>
                    </ul>
                    <button data-tikla="upgradePlan" data-arg="pro">
                        ${currentOrg?.plan === "pro" ? "Mevcut Plan" : "Yükselt"}
                    </button>
                </div>

                <div class="plan ${currentOrg?.plan === "business" ? "active" : ""}">
                    <h3>Business</h3>
                    <div class="price">₺999<span style="font-size: 14px; color: #999;">/ay</span></div>
                    <ul>
                        <li>✓ Pro'daki her şey</li>
                        <li>✓ 10 takım üyesine kadar</li>
                        <li>✓ Webhooks</li>
                        <li>✓ Dedicated support</li>
                    </ul>
                    <button data-tikla="upgradePlan" data-arg="business">
                        ${currentOrg?.plan === "business" ? "Mevcut Plan" : "Yükselt"}
                    </button>
                </div>
            `;
        }

        async function upgradePlan(plan) {
            if (currentOrg?.plan === plan) return;

            try {
                const res = await fetch(`${API_BASE}/organizations/upgrade`, {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${authToken}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ plan })
                });

                if (!res.ok) {
                    const err = await res.json();
                    alert(err.detail || "Ödeme sayfası oluşturulamadı");
                    return;
                }

                const data = await res.json();
                window.location.href = data.checkout_url;
            } catch (e) {
                alert(`Hata: ${e.message}`);
            }
        }

        async function confirmCheckoutIfReturning() {
            const params = new URLSearchParams(window.location.search);
            const sessionId = params.get("checkout_session_id");
            if (!sessionId) return;

            try {
                const res = await fetch(`${API_BASE}/organizations/confirm-checkout?session_id=${encodeURIComponent(sessionId)}`, {
                    method: "POST",
                    headers: { "Authorization": `Bearer ${authToken}` }
                });

                window.history.replaceState({}, "", "/dashboard");

                if (res.ok) {
                    await loadOrganization();
                    loadPricing();
                    alert("Ödeme başarılı! Planınız güncellendi.");
                } else {
                    const err = await res.json();
                    alert(`Ödeme doğrulanamadı: ${err.detail}`);
                }
            } catch (e) {
                console.error("Checkout confirmation error:", e);
            }
        }

        async function downgradeToFree() {
            if (!confirm("Free plana dönmek istediğinize emin misiniz? Ödemeli özelliklere erişiminiz sona erecek.")) return;

            try {
                const res = await fetch(`${API_BASE}/organizations/downgrade`, {
                    method: "POST",
                    headers: { "Authorization": `Bearer ${authToken}` }
                });
                if (!res.ok) {
                    const err = await res.json();
                    alert(err.detail || "İşlem başarısız");
                    return;
                }
                await loadOrganization();
                loadPricing();
            } catch (e) {
                alert(`Hata: ${e.message}`);
            }
        }

        function requirePlanUpgradeMessage(container) {
            container.innerHTML = `<div class="error">Bu özellik PRO ve üzeri planlarda kullanılabilir. <a href="#" data-tikla="bolumeGit" data-arg="pricing">Planınızı yükseltin</a>.</div>`;
        }

        // ---- Veri tazeligi ----
        // Kullaniciya gosterilen hal fiyatlari, TUFE ve kar oranlari bir
        // veritabani anlik goruntusu; ne zaman cekildigini gormeden bunlara
        // dayanip karar vermek yaniltici olur.
        const VERI_DURUM_METNI = {
            taze:       { simge: "✓", metin: "Veriler guncel" },
            eskiyor:    { simge: "○", metin: "Bazi veriler eskiyor" },
            bayat:      { simge: "!", metin: "Bazi veriler bayat" },
            veri_yok:   { simge: "!", metin: "Eksik veri kaynagi" },
            bilinmiyor: { simge: "?", metin: "Veri durumu bilinmiyor" },
        };

        function guncellemeMetni(kaynak) {
            if (!kaynak.son_guncelleme) return "hic guncellenmemis";
            const t = new Date(kaynak.son_guncelleme);
            const tarih = t.toLocaleDateString("tr-TR");
            if (kaynak.yas_gun === 0) return `${tarih} (bugun)`;
            return `${tarih} (${kaynak.yas_gun} gun once)`;
        }

        async function loadVeriDurumu() {
            const rozet = document.getElementById("veri-rozet");
            const detay = document.getElementById("veri-detay");
            if (!rozet || !detay) return;

            let veri;
            try {
                // Kimlik dogrulamasiz endpoint - token gerekmiyor.
                const res = await fetch(`${API_BASE}/veri-durumu`);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                veri = await res.json();
            } catch (e) {
                // Sessizce kaybolmasin: kullanici "veri guncel" sanmamali.
                console.warn("Veri durumu alinamadi:", e);
                veri = { genel_durum: "bilinmiyor", kaynaklar: [] };
            }

            const d = veri.genel_durum || "bilinmiyor";
            const etiket = VERI_DURUM_METNI[d] || VERI_DURUM_METNI.bilinmiyor;
            rozet.className = `veri-rozet ${d}`;
            rozet.textContent = `${etiket.simge} ${etiket.metin}`;
            rozet.style.display = "inline-flex";

            const satirlar = (veri.kaynaklar || []).map(k => `
                <tr>
                    <td><span class="nokta ${escapeHtml(k.durum)}"></span>${escapeHtml(k.baslik)}</td>
                    <td>${guncellemeMetni(k)}</td>
                    <td>${(k.kayit_sayisi || 0).toLocaleString("tr-TR")} kayit</td>
                    <td>${k.uyari ? `<span class="uyari-metni">${escapeHtml(k.uyari)}</span>` : "&mdash;"}</td>
                </tr>`).join("");

            detay.innerHTML = satirlar
                ? `<table>
                     <tr><th>Kaynak</th><th>Son guncelleme</th><th>Hacim</th><th>Not</th></tr>
                     ${satirlar}
                   </table>
                   <p style="margin:12px 0 0;color:#6b7380">
                     Bu tarihler, onerilerin dayandigi verilerin ne zaman cekildigini
                     gosterir. Eski bir kaynak sonuclari tamamen gecersiz kilmaz ama
                     karar verirken bunu hesaba katin.
                   </p>`
                : `<p style="margin:0;color:#a32020">Veri durumu su an okunamiyor.</p>`;

            rozet.onclick = () => {
                detay.style.display = detay.style.display === "block" ? "none" : "block";
            };
        }

        // ---- Başvuru kontrol listesi (app/basvuru_listesi.py) ----
        // Maddeler kaydın şart/belge/başvuru yeri alanlarından gelir; işaretler sunucuda saklanır.
        // Yazdırma: tarayıcının yazdır penceresi (PDF olarak kaydet dahil); @media print yalnızca listeyi basar.
        const KL_TUR_BASLIK = { sart: "Şartlar", belge: "Belgeler", basvuru: "Başvuru" };
        let klAcikTesvik = null;

        function klYuzde(d) { return d.toplam ? Math.round(100 * d.tamamlanan / d.toplam) : 0; }

        async function basvurularYukle() {
            const kutu = document.getElementById("basvuru-listeleri");
            const detay = document.getElementById("kontrol-yazdir");
            detay.hidden = true;
            kutu.hidden = false;
            klAcikTesvik = null;
            kutu.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            try {
                const res = await fetch(`${API_BASE}/basvuru-listesi`, { headers: { "Authorization": `Bearer ${authToken}` } });
                const d = await res.json();
                if (!res.ok) throw new Error(hataMetni(d));
                if (!d.listeler.length) {
                    kutu.innerHTML = `<div class="bos-durum">Henüz kontrol listesi açmadınız. <a href="#" data-tikla="bolumeGit" data-arg="profil">Profil &amp; Öneriler</a> bölümünde destekleri bulup kartlardaki “Kontrol listesi” düğmesini kullanın.</div>`;
                    return;
                }
                kutu.innerHTML = d.listeler.map(l => {
                    const yuzde = klYuzde(l);
                    return `<div class="bl-kart">
                        <div><div class="bl-baslik">${escapeHtml(l.baslik)}</div>
                             <div class="bl-kurum">${escapeHtml(l.kurum)} · ${l.tamamlanan}/${l.toplam} tamam${l.aktif_mi === false ? " · başvuru dönemi kapalı" : ""}</div></div>
                        <div class="ilerleme" title="%${yuzde}"><span style="width:${yuzde}%"></span></div>
                        <button type="button" class="ikincil-btn" data-tikla="kontrolListesiAc" data-arg="${escapeHtml(String(l.tesvik_id))}">Aç</button>
                    </div>`;
                }).join("");
            } catch (e) {
                kutu.innerHTML = `<div class="error">Hata: ${escapeHtml(e.message)}</div>`;
            }
        }

        async function kontrolListesiAc(tesvikId) {
            bolumeGit("basvurular");
            const detay = document.getElementById("kontrol-yazdir");
            try {
                const yol = `${API_BASE}/basvuru-listesi/${encodeURIComponent(tesvikId)}`;
                let res = await fetch(yol, { headers: { "Authorization": `Bearer ${authToken}` } });
                let d = await res.json();
                if (!res.ok) throw new Error(hataMetni(d));
                if (!d.takipte && d.toplam) {  // kartta açılan liste "Başvurularım"da görünsün
                    res = await fetch(yol, { method: "PUT", body: JSON.stringify({ isaretli: [] }),
                        headers: { "Authorization": `Bearer ${authToken}`, "Content-Type": "application/json" } });
                    if (res.ok) d = await res.json();
                }
                kontrolListesiCiz(d);
            } catch (e) {
                detay.hidden = false;
                detay.innerHTML = `<div class="error">Hata: ${escapeHtml(e.message)}</div>`;
            }
        }

        let klAcikTaslak = null;

        async function taslakOlustur(el) {
            if (klAcikTesvik === null) return;
            if (klAcikTaslak && !confirm("Mevcut taslağın yerine yenisi oluşturulsun mu? (Günlük sınırdan düşer.)")) return;
            const mesaj = document.getElementById("kl-taslak-mesaj");
            el.disabled = true;
            mesaj.innerHTML = '<div class="loading"><div class="spinner"></div></div><div class="bolum-aciklama">Taslak hazırlanıyor, bu 30-60 saniye sürebilir…</div>';
            try {
                const res = await fetch(`${API_BASE}/basvuru-listesi/${klAcikTesvik}/taslak`, {
                    method: "POST", headers: { "Authorization": `Bearer ${authToken}` }
                });
                const d = await res.json();
                if (!res.ok) {
                    const ek = res.status === 403 && /rıza/.test(d.detail || "")
                        ? ' <a href="#" data-tikla="bolumeGit" data-arg="settings">Ayarlara git</a>' : "";
                    mesaj.innerHTML = `<div class="error">${escapeHtml(hataMetni(d))}${ek}</div>`;
                    return;
                }
                kontrolListesiCiz(d);
            } catch (e) {
                mesaj.innerHTML = `<div class="error">Hata: ${escapeHtml(e.message)}</div>`;
            } finally {
                el.disabled = false;
            }
        }

        async function taslakKopyala() {
            const mesaj = document.getElementById("kl-taslak-mesaj");
            try {
                await navigator.clipboard.writeText(klAcikTaslak || "");
                mesaj.innerHTML = '<div class="success">Taslak metni panoya kopyalandı.</div>';
            } catch (e) {
                mesaj.innerHTML = '<div class="error">Kopyalanamadı; metni seçip elle kopyalayın.</div>';
            }
        }

        function kontrolListesiCiz(d) {
            klAcikTesvik = d.tesvik.id;
            klAcikTaslak = d.taslak || null;
            const detay = document.getElementById("kontrol-yazdir");
            document.getElementById("basvuru-listeleri").hidden = true;
            detay.hidden = false;
            const gruplar = ["sart", "belge", "basvuru"].map(tur => {
                const m = d.maddeler.filter(x => x.tur === tur);
                if (!m.length) return "";
                return `<div class="kl-grup"><h4>${KL_TUR_BASLIK[tur]}</h4>${m.map(x => `
                    <label class="kl-madde${x.isaretli ? " tamam" : ""}">
                        <input type="checkbox" data-degisim="kontrolMaddesi" data-arg="${escapeHtml(x.anahtar)}"${x.isaretli ? " checked" : ""}>
                        <span>${escapeHtml(x.metin)}</span>
                    </label>`).join("")}</div>`;
            }).join("");
            const kaynak = guvenliUrl(d.tesvik.kaynak_url);
            detay.innerHTML = `
                <div class="yazdirma-baslik">Teşvik Asistanı — Başvuru kontrol listesi · ${new Date().toLocaleDateString("tr-TR")}</div>
                <div class="kl-ust">
                    <div><h3>${escapeHtml(d.tesvik.baslik)}</h3>
                         <div class="bl-kurum">${escapeHtml(d.tesvik.kurum)} · <span id="kl-sayac">${d.tamamlanan}/${d.toplam}</span> tamam</div></div>
                    <div class="kl-eylemler yazdirma-gizle">
                        <button type="button" class="birincil-btn" data-tikla="kontrolListesiYazdir">Yazdır / PDF</button>
                        <button type="button" class="ikincil-btn" data-tikla="basvurularYukle">Tüm listeler</button>
                        <button type="button" class="ikincil-btn" data-tikla="kontrolListesiKaldir" data-arg="${escapeHtml(String(d.tesvik.id))}">Listeyi kaldır</button>
                    </div>
                </div>
                <div class="ilerleme"><span id="kl-cubuk" style="width:${klYuzde(d)}%"></span></div>
                ${d.uyari ? `<div class="onizleme-notu">${escapeHtml(d.uyari)}</div>` : gruplar}
                <div class="kl-taslak">
                    <h4>Başvuru ön taslağı</h4>
                    ${d.taslak ? `
                        <div class="kl-taslak-metin">${mdToHtml(d.taslak)}</div>
                        <div class="kl-taslak-alt yazdirma-gizle">Oluşturma: ${escapeHtml(new Date(d.taslak_tarihi).toLocaleString("tr-TR"))} ·
                            <button type="button" class="ikincil-btn" data-tikla="taslakKopyala">Metni kopyala</button>
                            <button type="button" class="ikincil-btn" data-tikla="taslakOlustur">Yeniden oluştur</button></div>`
                    : `<p class="yazdirma-gizle">Profilinizden ve bu programın bilgilerinden, kurumun başvuru formuna aktarabileceğiniz
                            düzenlenebilir bir metin taslağı hazırlanır. Bilinmeyen yerler “[DOLDURUN]” olarak bırakılır, rakam uydurulmaz.
                            Yapay zekâ (Anthropic, ABD) kullanılır ve açık rızanız gerekir; günde en çok 5 taslak.</p>
                        <button type="button" class="birincil-btn yazdirma-gizle" data-tikla="taslakOlustur">Taslak oluştur</button>`}
                    <div id="kl-taslak-mesaj" class="yazdirma-gizle"></div>
                </div>
                <div class="kl-not">Liste, kaydımızdaki şart ve belge bilgisinden üretilir; kesin ve güncel koşullar için
                    ${kaynak ? `<a href="${kaynak}" target="_blank" rel="noopener">resmi kaynağı</a>` : "kurumun resmi sayfasını"} kontrol edin.
                    ${d.tesvik.aktif_mi === false ? " Bu programın başvuru dönemi şu an kapalı." : ""}</div>
                <div id="kl-mesaj" class="yazdirma-gizle"></div>`;
        }

        async function kontrolMaddesi(el) {
            if (klAcikTesvik === null) return;
            const kutular = [...document.querySelectorAll('#kontrol-yazdir input[data-degisim="kontrolMaddesi"]')];
            const isaretli = kutular.filter(k => k.checked).map(k => k.dataset.arg);
            el.closest(".kl-madde").classList.toggle("tamam", el.checked);
            const mesaj = document.getElementById("kl-mesaj");
            try {
                const res = await fetch(`${API_BASE}/basvuru-listesi/${klAcikTesvik}`, {
                    method: "PUT", body: JSON.stringify({ isaretli }),
                    headers: { "Authorization": `Bearer ${authToken}`, "Content-Type": "application/json" }
                });
                const d = await res.json();
                if (!res.ok) {
                    mesaj.innerHTML = `<div class="error">${escapeHtml(hataMetni(d))}</div>`;
                    if (res.status === 400) kontrolListesiAc(klAcikTesvik);  // kayıt güncellenmiş: listeyi yenile
                    return;
                }
                mesaj.innerHTML = "";
                document.getElementById("kl-sayac").textContent = `${d.tamamlanan}/${d.toplam}`;
                document.getElementById("kl-cubuk").style.width = `${klYuzde(d)}%`;
            } catch (e) {
                el.checked = !el.checked;
                el.closest(".kl-madde").classList.toggle("tamam", el.checked);
                mesaj.innerHTML = `<div class="error">Kaydedilemedi: ${escapeHtml(e.message)}</div>`;
            }
        }

        function kontrolListesiYazdir() {
            // Listeyi body'nin doğrudan çocuğu olan bir alana kopyala; @media print yalnızca onu gösterir.
            let alan = document.getElementById("yazdir-alani");
            if (!alan) {
                alan = document.createElement("div");
                alan.id = "yazdir-alani";
                document.body.appendChild(alan);
            }
            const kaynak = document.getElementById("kontrol-yazdir");
            // Kullanıcının işaretleri "checked" özelliğinde durur, özniteliğe yansımaz: kopyada görünsün diye eşitle.
            kaynak.querySelectorAll("input[type=checkbox]").forEach(k => k.toggleAttribute("checked", k.checked));
            alan.innerHTML = kaynak.innerHTML;
            document.body.classList.add("kl-yazdiriliyor");
            const temizle = () => {
                document.body.classList.remove("kl-yazdiriliyor");
                alan.innerHTML = "";
                window.removeEventListener("afterprint", temizle);
            };
            window.addEventListener("afterprint", temizle);
            window.print();
        }

        async function kontrolListesiKaldir(tesvikId) {
            if (!confirm("Bu kontrol listesi ve işaretleriniz kaldırılsın mı?")) return;
            await fetch(`${API_BASE}/basvuru-listesi/${encodeURIComponent(tesvikId)}`, {
                method: "DELETE", headers: { "Authorization": `Bearer ${authToken}` }
            });
            basvurularYukle();
        }

        // ---- Kayıt sonrası karşılama rehberi ----
        // Profil yoksa (GET /api/profil 404) gösterilir; kullanıcı kapatırsa bu tarayıcıda bir daha açılmaz.
        // Depolama erişimi engellenmiş olabilir (gizli pencere vb.): her okuma/yazma try/catch içinde.
        const KARSILAMA_ANAHTARI = "karsilama_kapandi";
        function karsilamaKapatildiMi() {
            try { return localStorage.getItem(KARSILAMA_ANAHTARI) === "1"; } catch (e) { return false; }
        }
        function karsilamaGuncelle(profilVar) {
            const kart = document.getElementById("karsilama");
            if (!kart) return;
            if (profilVar) {
                document.getElementById("karsilama-adim-profil").classList.add("tamam");
                return;  // açıksa açık kalır (2. ve 3. adım için); profil sonradan kaydedildiyse işaretlenir
            }
            kart.hidden = karsilamaKapatildiMi();
        }
        function karsilamaKapat() {
            document.getElementById("karsilama").hidden = true;
            try { localStorage.setItem(KARSILAMA_ANAHTARI, "1"); } catch (e) { /* yalnızca bu oturumda gizli kalır */ }
        }
        function karsilamaEslesme() {
            bolumeGit("profil");
            bulUygunDestekler();
        }

        async function loadFinancialProfile() {
            try {
                const res = await fetch(`${API_BASE}/profil`, {
                    headers: { "Authorization": `Bearer ${authToken}` }
                });
                if (res.status === 404) karsilamaGuncelle(false);
                if (!res.ok) return;
                karsilamaGuncelle(true);
                const p = await res.json();
                document.getElementById("p-sektor").value = p.sektor || "genel";
                document.getElementById("p-bolge").value = p.bolge || "";
                document.getElementById("p-calisan").value = p.calisan_sayisi ?? "";
                document.getElementById("p-ciro").value = p.yillik_ciro ?? "";
                document.getElementById("p-stok").value = p.giderler?.stok ?? "";
                document.getElementById("p-reklam").value = p.giderler?.reklam ?? "";
                document.getElementById("p-toplam-gider").value = p.giderler?.toplam ?? "";
                document.getElementById("p-arazi").value = p.arazi_buyuklugu_dekar ?? "";
                document.getElementById("p-urun").value = p.urun_turu ?? "";
                document.getElementById("p-tarim-kategori").value = p.tarim_kategori ?? "";
                onTarimKategoriDegisti();
                document.getElementById("p-urun").value = p.urun_turu ?? "";
                document.getElementById("p-ilk-yil").checked = !!p.ilk_yil_mi;
                document.getElementById("p-nace").value = p.nace_kodu ?? "";
                document.getElementById("p-sirket-turu").value = p.sirket_turu ?? "";
                document.getElementById("p-kurulus").value = p.kurulus_tarihi ?? "";
                const trlSec = document.getElementById("p-trl");
                trlSec.value = p.trl ? (p.trl <= 3 ? "1" : p.trl <= 6 ? "4" : "7") : "";
                document.querySelectorAll(".p-ozellik").forEach(cb => {
                    cb.checked = (p.ozellikler || []).includes(cb.value);
                });
                document.getElementById("p-kurulus-gideri").value = p.giderler?.kurulus ?? "";
                document.querySelectorAll(".p-hedef").forEach(cb => {
                    cb.checked = (p.hedefler || []).includes(cb.value);
                });
                toggleTarimAlanlari();
                toggleIlkYilAlani();
            } catch (e) {
                console.error("Error loading profile:", e);
            }
        }

        function toggleTarimAlanlari() {
            const isTarim = document.getElementById("p-sektor").value === "tarim";
            document.getElementById("tarim-alanlari").style.display = isTarim ? "grid" : "none";
            document.getElementById("tarim-hedefler").style.display = isTarim ? "flex" : "none";
        }

        function toggleIlkYilAlani() {
            const isIlkYil = document.getElementById("p-ilk-yil").checked;
            document.getElementById("ilk-yil-alani").style.display = isIlkYil ? "block" : "none";
        }

        // Kategoriye gore urun input'unun placeholder'ini ve oneri listesini
        // (datalist) daraltir - "sera" secildiginde "muz, domates" gibi, "hayvancilik"
        // secildiginde "sut, bal, et" gibi. Kullanicinin serbest yazmasina hala izin
        // veriyoruz (datalist zorunlu secim degil), sadece rehberlik ediyoruz.
        const KATEGORI_URUN_ONERILERI = {
            hayvancilik: ["hayvancılık", "süt", "bal", "et"],
            sebze_meyve: ["çilek", "muz", "domates", "biber", "salatalık", "patlıcan", "elma", "armut", "üzüm"],
            tahil_baklagil: ["buğday", "arpa", "mercimek", "nohut"],
            organik: ["çilek", "domates", "buğday", "elma"],
            sera: ["domates", "biber", "salatalık", "çilek", "muz"],
            sulama: [],
            makinelestirme: [],
            genel: [],
        };

        function onTarimKategoriDegisti() {
            const kategori = document.getElementById("p-tarim-kategori").value;
            const urunInput = document.getElementById("p-urun");
            const oneriler = KATEGORI_URUN_ONERILERI[kategori] || [];

            const datalist = document.getElementById("p-urun-liste");
            if (oneriler.length) {
                datalist.innerHTML = oneriler.map(u => `<option value="${escapeHtml(u)}">`).join("");
                urunInput.placeholder = `Örn: ${oneriler.slice(0, 3).join(", ")}`;
            } else {
                datalist.innerHTML = `
                    <option value="çilek"><option value="muz"><option value="domates"><option value="biber">
                    <option value="salatalık"><option value="patlıcan"><option value="elma"><option value="armut">
                    <option value="üzüm"><option value="zeytin"><option value="buğday"><option value="arpa">
                    <option value="mercimek"><option value="nohut"><option value="fındık"><option value="antep fıstığı">
                    <option value="hayvancılık"><option value="süt"><option value="bal">`;
                urunInput.placeholder = "Örn: çilek, muz, domates, buğday";
            }
        }

        function readProfilForm() {
            const hedefler = Array.from(document.querySelectorAll(".p-hedef:checked")).map(cb => cb.value);
            const stok = document.getElementById("p-stok").value;
            const reklam = document.getElementById("p-reklam").value;
            const toplamGider = document.getElementById("p-toplam-gider").value;
            const arazi = document.getElementById("p-arazi").value;
            const urun = document.getElementById("p-urun").value;
            const tarimKategori = document.getElementById("p-tarim-kategori").value;
            const ilkYil = document.getElementById("p-ilk-yil").checked;
            const kurulusGideri = document.getElementById("p-kurulus-gideri").value;

            let giderler = null;
            if (stok || reklam) {
                giderler = { stok: stok ? Number(stok) : null, reklam: reklam ? Number(reklam) : null };
            } else if (toplamGider) {
                giderler = { toplam: Number(toplamGider) };
            }
            if (ilkYil && kurulusGideri) {
                giderler = { ...(giderler || {}), kurulus: Number(kurulusGideri) };
            }

            return {
                sektor: document.getElementById("p-sektor").value,
                bolge: document.getElementById("p-bolge").value || null,
                calisan_sayisi: document.getElementById("p-calisan").value ? Number(document.getElementById("p-calisan").value) : null,
                yillik_ciro: document.getElementById("p-ciro").value ? Number(document.getElementById("p-ciro").value) : null,
                hedefler: hedefler.length ? hedefler : null,
                giderler: giderler,
                arazi_buyuklugu_dekar: arazi ? Number(arazi) : null,
                urun_turu: urun || null,
                tarim_kategori: tarimKategori || null,
                ilk_yil_mi: document.getElementById("p-ilk-yil").checked,
                nace_kodu: document.getElementById("p-nace").value.trim() || null,
                sirket_turu: document.getElementById("p-sirket-turu").value || null,
                kurulus_tarihi: document.getElementById("p-kurulus").value || null,
                trl: document.getElementById("p-trl").value ? Number(document.getElementById("p-trl").value) : null,
                ozellikler: Array.from(document.querySelectorAll(".p-ozellik:checked")).map(cb => cb.value),
            };
        }

        document.addEventListener("DOMContentLoaded", () => {
            const sektorSelect = document.getElementById("p-sektor");
            if (sektorSelect) {
                sektorSelect.addEventListener("change", toggleTarimAlanlari);
            }
            const ilkYilCheckbox = document.getElementById("p-ilk-yil");
            if (ilkYilCheckbox) {
                ilkYilCheckbox.addEventListener("change", toggleIlkYilAlani);
            }
            const form = document.getElementById("profil-form");
            if (form) {
                form.addEventListener("submit", async (e) => {
                    e.preventDefault();
                    const mesajDiv = document.getElementById("profil-mesaj");
                    mesajDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
                    try {
                        const res = await fetch(`${API_BASE}/profil`, {
                            method: "PUT",
                            headers: {
                                "Authorization": `Bearer ${authToken}`,
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify(readProfilForm())
                        });
                        if (!res.ok) {
                            const err = await res.json();
                            mesajDiv.innerHTML = `<div class="error">${escapeHtml(hataMetni(err))}</div>`;
                            return;
                        }
                        mesajDiv.innerHTML = `<div class="success">Profil kaydedildi.</div>`;
                        karsilamaGuncelle(true);
                    } catch (e2) {
                        mesajDiv.innerHTML = `<div class="error">Hata: ${e2.message}</div>`;
                    }
                });
            }
        });

        async function bulUygunDestekler() {
            const section = document.getElementById("eslesme-section");
            const ozetDiv = document.getElementById("eslesme-ozet");
            const resultsDiv = document.getElementById("eslesme-results");
            section.style.display = "block";
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            ozetDiv.innerHTML = "";

            try {
                const res = await fetch(`${API_BASE}/eslesme`, {
                    headers: { "Authorization": `Bearer ${authToken}` }
                });

                if (res.status === 403) {
                    requirePlanUpgradeMessage(resultsDiv);
                    return;
                }
                if (res.status === 404) {
                    resultsDiv.innerHTML = `<div class="error">Önce yukarıdan profilinizi kaydedin.</div>`;
                    return;
                }
                if (!res.ok) {
                    const err = await res.json();
                    resultsDiv.innerHTML = `<div class="error">${escapeHtml(hataMetni(err))}</div>`;
                    return;
                }

                const data = await res.json();

                if (data.tahmini_toplam_destek_max > 0) {
                    ozetDiv.textContent = `Tahmini toplam alınabilecek destek: ₺${data.tahmini_toplam_destek_min.toLocaleString('tr-TR')} - ₺${data.tahmini_toplam_destek_max.toLocaleString('tr-TR')}`;
                    if (data.onizleme) {
                        // FREE plan önizlemesi: sunucu ilk 3 eşleşmeyi döner, toplamı bildirir.
                        ozetDiv.innerHTML = escapeHtml(ozetDiv.textContent) +
                            `<div class="onizleme-notu">FREE plan önizlemesi: ${data.toplam_eslesme} eşleşmeden ilk ${data.eslesen_tesvikler.length} gösteriliyor. ` +
                            `<a href="#" data-tikla="bolumeGit" data-arg="pricing">PRO'ya geçin</a>, tüm listeyi ve bütçe önerisini görün.</div>`;
                    }
                }

                if (!data.eslesen_tesvikler.length) {
                    resultsDiv.innerHTML = `<div class="error">Profilinize uygun destek bulunamadı. Sektör/hedef bilgilerinizi güncelleyin.</div>`;
                    return;
                }

                // Kıyaslama Tablosu: Aynı DAR alt_kategori'deki (hayvancilik, organik,
                // sulama vb.) 3+ destek varsa karşılaştır. Genel 'kategori' (örn. hepsi
                // "tarim") burada YETERİNCE AYIRT EDİCİ DEĞİL - Hayvancılık, Organik,
                // Sulama gibi birbirinden tamamen farklı destekler hepsi "tarim"
                // kategorisinde olduğu için kategoriye göre gruplarsak alakasız
                // destekler aynı tabloya düşer. alt_kategori olmayan (KOSGEB/TÜBİTAK/KGF
                // gibi) kayıtları da gruplamaya hiç dahil etmiyoruz.
                const kategoriGrouplar = {};
                data.eslesen_tesvikler.forEach(t => {
                    const altKategori = t.alt_kategori;
                    if (!altKategori) return;
                    if (!kategoriGrouplar[altKategori]) kategoriGrouplar[altKategori] = [];
                    kategoriGrouplar[altKategori].push(t);
                });

                let kiyaslamaTablosuHtml = '';
                for (const [kategori, destekler] of Object.entries(kategoriGrouplar)) {
                    if (destekler.length >= 3) {
                        kiyaslamaTablosuHtml += `
                        <div style="margin-top:30px; padding:20px; background:#f8f9fa; border-radius:8px; border-left:4px solid #667eea;">
                            <h3 style="margin:0 0 15px 0; color:#333;">🔄 ${kategori.charAt(0).toUpperCase() + kategori.slice(1)} Destekleri - Karşılaştırma</h3>
                            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                                <thead>
                                    <tr style="background:#667eea; color:white;">
                                        <th style="padding:10px; text-align:left;">Destek</th>
                                        <th style="padding:10px; text-align:left;">Kurum</th>
                                        <th style="padding:10px; text-align:center;">Tutar Aralığı</th>
                                        <th style="padding:10px; text-align:center;">Başvuru</th>
                                        <th style="padding:10px; text-align:left;">Başvuru Yeri</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${destekler.map((t, i) => `
                                    <tr style="border-bottom:1px solid #ddd; background:${i % 2 === 0 ? 'white' : '#fafafa'};">
                                        <td style="padding:10px;"><strong>${escapeHtml(t.baslik)}</strong></td>
                                        <td style="padding:10px;">${escapeHtml(t.kurum)}</td>
                                        <td style="padding:10px; text-align:center; font-size:12px;">${t.tutari_min && t.tutari_max ? `₺${(t.tutari_min/1000).toFixed(0)}K - ₺${(t.tutari_max/1000).toFixed(0)}K` : escapeHtml(t.tesvil_tutari || '-')}</td>
                                        <td style="padding:10px; text-align:center; font-size:12px; color:#666;">${t.basvuru_suresi ? escapeHtml(t.basvuru_suresi.split(' ')[0]) : '-'}</td>
                                        <td style="padding:10px; font-size:12px;">${escapeHtml(t.basvuru_yeri || '-')}</td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>`;
                    }
                }

                // Kayıt metinleri web kazımasından gelir (üçüncü taraf içerik): her alan HTML'den
                // kaçırılır, bağlantılar yalnızca http(s) ise basılır (denetim 2026-10-07).
                resultsDiv.innerHTML = data.eslesen_tesvikler.map((t, idx) => `
                    <div class="result-card">
                        <div class="kurum">${escapeHtml(t.kurum)} · Skor: ${(t.skor * 100).toFixed(0)}%</div>
                        <div class="baslik">${escapeHtml(t.baslik)}</div>
                        ${t.aktif_mi === true
                            ? `<div style="display:inline-block; margin:4px 0 8px; padding:3px 10px; border-radius:100px; background:#e4efe9; color:#0f4438; font-size:12px; font-weight:bold;">✓ Aktif olduğu doğrulandı</div>`
                            : `<div style="display:inline-block; margin:4px 0 8px; padding:3px 10px; border-radius:100px; background:#fdf3e2; color:#7a4b22; font-size:12px; font-weight:bold;" title="Bu programın hala başvuruya açık olduğu tarafımızca doğrulanmadı.">⚠ Aktifliği doğrulanmadı — kurumdan teyit edin</div>`}
                        <div class="ozet">${escapeHtml(t.ozet)}</div>
                        ${t.tesvil_tutari ? `<div class="meta"><span>💰 ${escapeHtml(t.tesvil_tutari)}</span></div>` : ""}
                        ${t.tutari_tahmini_profil ? `<div class="meta"><span>🎯 Tahmini: ₺${t.tutari_tahmini_profil.toLocaleString('tr-TR', {maximumFractionDigits:0})}</span></div>` : ""}
                        ${t.gerekce.length ? `<div class="meta" style="flex-direction:column; align-items:flex-start; gap:5px; margin-top:8px;">${t.gerekce.map(g => `<span>✓ ${escapeHtml(g)}</span>`).join("")}</div>` : ""}
                        ${t.eksik_kriterler.length ? `<div class="meta" style="flex-direction:column; align-items:flex-start; gap:5px; margin-top:8px; color:#856404;">${t.eksik_kriterler.map(g => `<span>⚠ ${escapeHtml(g)}</span>`).join("")}</div>` : ""}

                        <details style="margin-top:15px; padding-top:15px; border-top:1px solid #eee;">
                            <summary style="cursor:pointer; font-weight:bold; color:#667eea;">📋 Başvuru Rehberi</summary>
                            <div style="margin-top:10px; font-size:13px; line-height:1.6;">
                                ${t.tutari_hesaplama_formulu ? `<div style="margin-bottom:10px;"><strong>Tutar Hesaplama:</strong> ${escapeHtml(t.tutari_hesaplama_formulu)}</div>` : ""}
                                ${t.basvuru_suresi ? `<div style="margin-bottom:8px;"><strong>Başvuru Süresi:</strong> ${escapeHtml(t.basvuru_suresi)}</div>` : ""}
                                ${t.basvuru_yeri ? `<div style="margin-bottom:8px;"><strong>Başvuru Yeri:</strong> ${escapeHtml(t.basvuru_yeri)}</div>` : ""}
                                ${t.destek_verilme_suresi ? `<div style="margin-bottom:8px;"><strong>Destek Verilme Süresi:</strong> ${escapeHtml(t.destek_verilme_suresi)}</div>` : ""}
                                ${t.basvuru_sartlari && t.basvuru_sartlari.length ? `<div style="margin-bottom:8px;"><strong>Şartlar:</strong><ul style="margin:5px 0 0 20px;">${t.basvuru_sartlari.map(s => `<li>${escapeHtml(s)}</li>`).join("")}</ul></div>` : ""}
                                ${t.gerekli_belgeler && t.gerekli_belgeler.length ? `<div><strong>Gerekli Belgeler:</strong><ul style="margin:5px 0 0 20px;">${t.gerekli_belgeler.map(b => `<li>${escapeHtml(b)}</li>`).join("")}</ul></div>` : ""}
                                ${!t.basvuru_suresi && !t.basvuru_yeri && !(t.basvuru_sartlari && t.basvuru_sartlari.length) ? `
                                <div style="color:#856404;">Bu destek için şart/belge/tarih detayı henüz sistemimizde işlenmedi.${guvenliUrl(t.kaynak_url) ? ` Güncel ve kesin bilgi için <a href="${guvenliUrl(t.kaynak_url)}" target="_blank" rel="noopener">resmi kaynağı</a> inceleyin.` : " Kurumun resmi web sitesinden kontrol edin."}</div>
                                ` : ""}
                            </div>
                        </details>

                        ${guvenliUrl(t.kaynak_url) ? `<a href="${guvenliUrl(t.kaynak_url)}" target="_blank" rel="noopener" style="display:inline-block; margin-top:10px; padding:7px 14px; background:#667eea; color:white; text-decoration:none; border-radius:5px; font-size:12px; font-weight:bold;">🔗 Resmi Kaynak</a>` : ""}
                        <button type="button" class="ikincil-btn" data-tikla="kontrolListesiAc" data-arg="${escapeHtml(String(t.id))}" style="margin-top:10px; padding:6px 12px; font-size:12px;">☑ Kontrol listesi</button>
                    </div>
                `).join("") + kiyaslamaTablosuHtml;
            } catch (e) {
                resultsDiv.innerHTML = `<div class="error">Hata: ${e.message}</div>`;
            }
        }

        async function butceOnerisiAl() {
            const section = document.getElementById("butce-section");
            const resultsDiv = document.getElementById("butce-results");
            section.style.display = "block";
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

            try {
                const res = await fetch(`${API_BASE}/butce-onerisi`, {
                    headers: { "Authorization": `Bearer ${authToken}` }
                });

                if (res.status === 403) {
                    requirePlanUpgradeMessage(resultsDiv);
                    return;
                }
                if (res.status === 404) {
                    resultsDiv.innerHTML = `<div class="error">Önce yukarıdan profilinizi kaydedin.</div>`;
                    return;
                }
                if (!res.ok) {
                    const err = await res.json();
                    resultsDiv.innerHTML = `<div class="error">${escapeHtml(hataMetni(err))}</div>`;
                    return;
                }

                const b = await res.json();
                const fmt = (n) => `₺${Number(n).toLocaleString('tr-TR', { maximumFractionDigits: 0 })}`;

                const girdiEtiketleri = {
                    gubre: "Gübre", ilac: "Tarımsal İlaç", yem: "Hayvan Yemi",
                    bina_sera: "Bina/Sera Yapımı", makine_bakim: "Makine Bakımı",
                };

                let girdiKartiHtml = "";
                if (b.tarim_girdi_enflasyonu) {
                    const siraliGirdiler = Object.entries(b.tarim_girdi_enflasyonu)
                        .filter(([, v]) => v != null)
                        .sort(([, a], [, c]) => c - a);

                    girdiKartiHtml = `
                    <div class="stat-card" style="margin-top:20px;">
                        <h3>📦 Tarımsal Girdi Fiyat Artışı <span style="font-weight:normal; color:#999; font-size:12px;">(Son 1 Yıl, TÜİK)</span></h3>
                        <div class="girdi-enflasyon-grid">
                            ${siraliGirdiler.map(([anahtar, deger], i) => `
                                <div class="girdi-enflasyon-item ${i === 0 ? "en-yuksek" : ""}">
                                    <div class="deger">%${deger}</div>
                                    <div class="etiket">${girdiEtiketleri[anahtar] || anahtar}</div>
                                </div>
                            `).join("")}
                        </div>
                    </div>`;
                }

                let urunFiyatiHtml = "";
                if (b.guncel_urun_fiyati && b.guncel_urun_fiyati.kaynak_tipi === "hal_cilek") {
                    const uf = b.guncel_urun_fiyati;
                    const kaliteEtiketleri = { sofralik_standart: "Sofralık Standart", sofralik_premium: "Sofralık Premium", sanayilik_recellik: "Sanayilik/Reçellik" };
                    urunFiyatiHtml = `
                    <div class="stat-card" style="margin-top:20px; border-left-color:#2ecc71;">
                        <h3>🍓 Güncel Hal Fiyatı <span style="font-weight:normal; color:#999; font-size:12px;">(${uf.veri_tarihi})</span></h3>
                        <div style="display:flex; gap:30px; flex-wrap:wrap; margin-top:12px;">
                            ${uf.kalite_bazli_fiyatlar.map(k => `
                                <div>
                                    <div style="font-size:20px; font-weight:bold; color:#27ae60;">₺${k.fiyat_kg.toFixed(2)}/kg</div>
                                    <div style="font-size:11px; color:#999;">${kaliteEtiketleri[k.kalite_sinifi] || k.kalite_sinifi}${k.hacim_kg != null ? ` · ${fmt(k.hacim_kg)} kg hacim` : ""}</div>
                                </div>
                            `).join("")}
                        </div>
                        <p style="font-size:11px; color:#999; margin-top:10px;">${uf.kaynak}. Bölgenize ve kalite sınıfınıza göre gerçek teklifler farklılık gösterebilir.</p>
                    </div>`;
                } else if (b.guncel_urun_fiyati && b.guncel_urun_fiyati.kaynak_tipi === "hal_genel") {
                    const uf = b.guncel_urun_fiyati;
                    urunFiyatiHtml = `
                    <div class="stat-card" style="margin-top:20px; border-left-color:#2ecc71;">
                        <h3>🧺 Güncel Hal Fiyatı — ${uf.urun_adi} <span style="font-weight:normal; color:#999; font-size:12px;">(${uf.veri_tarihi})</span></h3>
                        <div style="display:flex; gap:24px; flex-wrap:wrap; margin-top:12px;">
                            ${uf.kalemler.map(k => `
                                <div>
                                    <div style="font-size:18px; font-weight:bold; color:#27ae60;">₺${k.fiyat_kg.toFixed(2)}/kg</div>
                                    <div style="font-size:11px; color:#999;">${k.urun_cinsi} · ${k.urun_turu}${k.miktar_kg != null ? ` · ${fmt(k.miktar_kg)} kg` : ""}</div>
                                </div>
                            `).join("")}
                        </div>
                        <p style="font-size:11px; color:#999; margin-top:10px;">${uf.kaynak}. Bölgenize ve çeşide göre gerçek teklifler farklılık gösterebilir.</p>
                    </div>`;
                } else if (b.guncel_urun_fiyati) {
                    const uf = b.guncel_urun_fiyati;
                    urunFiyatiHtml = `
                    <div class="stat-card" style="margin-top:20px; border-left-color:#2ecc71;">
                        <h3>🌾 Güncel Ürün Fiyatı <span style="font-weight:normal; color:#999; font-size:12px;">(TMO ${uf.sezon} sezonu)</span></h3>
                        <div style="display:flex; gap:30px; flex-wrap:wrap; margin-top:12px;">
                            <div>
                                <div style="font-size:20px; font-weight:bold; color:#27ae60;">${fmt(uf.alim_fiyati_ton)}/ton</div>
                                <div style="font-size:11px; color:#999;">TMO garanti alım fiyatı</div>
                            </div>
                            <div>
                                <div style="font-size:20px; font-weight:bold; color:#27ae60;">${fmt(uf.destekli_gelir_ton)}/ton</div>
                                <div style="font-size:11px; color:#999;">Destekler dahil tahmini gelir</div>
                            </div>
                        </div>
                        <p style="font-size:11px; color:#999; margin-top:10px;">${uf.urun_adi} için ${uf.kaynak}. Piyasada bu taban fiyatın üzerinde teklif de alabilirsiniz — özel alıcılarla pazarlık ederken bu rakamı referans olarak kullanın.</p>
                    </div>`;
                }

                let ihracatFiyatiHtml = "";
                if (b.guncel_ihracat_fiyati) {
                    const ifz = b.guncel_ihracat_fiyati;
                    ihracatFiyatiHtml = `
                    <div class="stat-card" style="margin-top:20px; border-left-color:#e67e22;">
                        <h3>🚢 İhracat Referans Fiyatı <span style="font-weight:normal; color:#999; font-size:12px;">(${ifz.veri_tarihi})</span></h3>
                        <div style="display:flex; gap:24px; flex-wrap:wrap; margin-top:12px;">
                            ${ifz.kalemler.map(k => `
                                <div>
                                    <div style="font-size:18px; font-weight:bold; color:#d35400;">₺${k.fiyat_kg.toFixed(2)}/kg</div>
                                    <div style="font-size:11px; color:#999;">${k.urun_cinsi} · ${k.urun_turu}${k.miktar_kg != null ? ` · ${fmt(k.miktar_kg)} kg` : ""}</div>
                                </div>
                            `).join("")}
                        </div>
                        <p style="font-size:11px; color:#999; margin-top:10px;">${ifz.kaynak}. Gümrük/ihracat beyanında kullanılan resmi referans fiyattır, gerçek satış fiyatınız farklı olabilir.</p>
                    </div>`;
                }

                let disTicaretHtml = "";
                if (b.tarim_dis_ticaret) {
                    const dt = b.tarim_dis_ticaret;
                    const acikMi = dt.denge_milyon_usd < 0;
                    disTicaretHtml = `
                    <div class="stat-card" style="margin-top:20px; border-left-color:${acikMi ? "#e74c3c" : "#27ae60"};">
                        <h3>🌍 Tarım Sektörü Dış Ticareti <span style="font-weight:normal; color:#999; font-size:12px;">(TÜİK/EVDS, aylık)</span></h3>
                        <div style="display:flex; gap:24px; flex-wrap:wrap; margin-top:12px;">
                            <div>
                                <div style="font-size:18px; font-weight:bold; color:#27ae60;">$${dt.ihracat_milyon_usd.toLocaleString('tr-TR')}M</div>
                                <div style="font-size:11px; color:#999;">İhracat</div>
                            </div>
                            <div>
                                <div style="font-size:18px; font-weight:bold; color:#e74c3c;">$${dt.ithalat_milyon_usd.toLocaleString('tr-TR')}M</div>
                                <div style="font-size:11px; color:#999;">İthalat</div>
                            </div>
                            <div>
                                <div style="font-size:18px; font-weight:bold; color:${acikMi ? "#e74c3c" : "#27ae60"};">${acikMi ? "-" : "+"}$${Math.abs(dt.denge_milyon_usd).toLocaleString('tr-TR')}M</div>
                                <div style="font-size:11px; color:#999;">${acikMi ? "Dış ticaret açığı" : "Dış ticaret fazlası"}</div>
                            </div>
                        </div>
                        <p style="font-size:11px; color:#999; margin-top:10px;">Sektörün genel rekabet gücüne dair bir referanstır, işletmenizin ihracat/ithalat durumunu yansıtmaz.</p>
                    </div>`;
                }

                let urunVeriYokHtml = "";
                if (b.urun_veri_yok_mesaji) {
                    urunVeriYokHtml = `
                    <div class="stat-card" style="margin-top:20px; border-left-color:#95a5a6; background:#f8f9fa;">
                        <h3 style="display:flex; align-items:center; gap:8px;">🌱 Ürün Bazlı Veri Yok</h3>
                        <p style="font-size:13px; color:#666; margin-top:8px; line-height:1.5;">${b.urun_veri_yok_mesaji}</p>
                    </div>`;
                }

                let bolgeselTavsiyeHtml = "";
                if (b.bolgesel_tavsiye) {
                    const bt = b.bolgesel_tavsiye;
                    bolgeselTavsiyeHtml = `
                    <div class="stat-card" style="margin-top:20px; border-left-color:#8e44ad;">
                        <h3 style="display:flex; align-items:center; gap:8px;">📍 ${bt.bolge_adi} - Bölgesel Tarım Tavsiyesi</h3>
                        <div style="display:flex; flex-wrap:wrap; gap:6px; margin:10px 0;">
                            ${bt.one_cikan_urunler.map(u => `<span style="background:#f3e5f5; color:#6c3483; padding:4px 10px; border-radius:12px; font-size:12px;">${u}</span>`).join("")}
                        </div>
                        <p style="font-size:13px; color:#444; line-height:1.6;">${bt.tavsiye}</p>
                        <p style="font-size:11px; color:#999; margin-top:8px;">${bt.kaynak}</p>
                    </div>`;
                }

                let enYuksekBanner = "";
                if (b.en_yuksek_artan_girdi) {
                    enYuksekBanner = `
                    <div class="note-item note-highlight" style="margin-top:20px;">
                        <span class="note-icon">🔥</span>
                        <span><strong>En hızlı artan gideriniz: ${b.en_yuksek_artan_girdi.etiket}</strong> — son 1 yılda %${b.en_yuksek_artan_girdi.artis} arttı.
                        Bütçenizde bu kalem için pay ayırırken önceliklendirin; tam gübre/ilaç türü ve dozu için İl/İlçe Tarım Müdürlüğü'nden toprak tahlili bazlı tavsiye alın.</span>
                    </div>`;
                }

                // Notlari turune gore ikon/renk ile ayri kutucuklara bol; tarim girdi
                // ozeti ayri bir kart+banner ile zaten gosterildigi icin metin
                // tekrarini onlemek adina o notu genel listeden cikar.
                const notIkonla = (metin) => {
                    if (metin.includes("TUIK Tarimsal Girdi") || metin.includes("Tarımsal Girdi")) return null;
                    if (metin.includes("altinda") || metin.includes("altında")) return { tip: "note-info", ikon: "📉" };
                    if (metin.includes("uzerinde") || metin.includes("üzerinde")) return { tip: "note-warning", ikon: "📈" };
                    if (metin.includes("araligina uygun") || metin.includes("aralığına uygun")) return { tip: "note-good", ikon: "✅" };
                    if (metin.includes("Ilk yil") || metin.includes("İlk yil") || metin.includes("İlk yıl")) return { tip: "note-warning", ikon: "🏗️" };
                    if (metin.includes("TUFE") || metin.includes("TÜFE")) return { tip: "note-info", ikon: "📊" };
                    if (metin.includes("kar orani") || metin.includes("kâr oranı")) return { tip: "note-info", ikon: "💹" };
                    if (metin.includes("benchmark bulunamadi") || metin.includes("benchmark bulunamadı")) return { tip: "note-info", ikon: "ℹ️" };
                    return { tip: "note-info", ikon: "ℹ️" };
                };

                const notlarHtml = b.notlar
                    .map((metin) => {
                        const stil = notIkonla(metin);
                        if (!stil) return "";
                        return `<div class="note-item ${stil.tip}"><span class="note-icon">${stil.ikon}</span><span>${metin}</span></div>`;
                    })
                    .filter(Boolean)
                    .join("");

                const analistPaneliHtml = b.analist_onerileri && b.analist_onerileri.length ? `
                    <div class="analist-paneli">
                        <div class="baslik">📋 Analist Önerileri</div>
                        <div class="alt-baslik">Profilinize göre otomatik oluşturulan, sektör ortalamalarına dayalı yol gösterici öneriler — muhasebe/yatırım danışmanlığı yerine geçmez.</div>
                        <div class="analist-oneri-list">
                            ${b.analist_onerileri.map((oneri, i) => `
                                <div class="analist-oneri-item">
                                    <span class="sira">${i + 1}</span>
                                    <span>${oneri}</span>
                                </div>
                            `).join("")}
                        </div>
                    </div>
                ` : "";

                resultsDiv.innerHTML = `
                    ${analistPaneliHtml}
                    <div class="stats">
                        <div class="stat-card">
                            <h3>Sektör Ortalamasına Göre Stok Maliyeti</h3>
                            <p style="color:#888; font-size:12px; margin:2px 0 6px;">Cironuza göre sektör aralığı; harcama hedefi değil, kıyas ölçüsüdür.</p>
                            <div class="value" style="font-size:20px;">${fmt(b.stok_maliyeti_min)} - ${fmt(b.stok_maliyeti_max)}</div>
                            ${b.gelecek_yil_stok_min != null ? `<p style="color:#2980b9; margin-top:8px;">Önümüzdeki 12 ay (TÜFE düzeltmeli): <b>${fmt(b.gelecek_yil_stok_min)} - ${fmt(b.gelecek_yil_stok_max)}</b></p>` : ""}
                            ${b.mevcut_stok_gideri != null ? `<p style="color:#999; margin-top:8px;">Mevcut gideriniz: ${fmt(b.mevcut_stok_gideri)}${b.gider_sapma_yuzdesi != null ? ` <span style="font-weight:bold; color:${b.gider_sapma_yuzdesi < 0 ? '#e67e22' : '#c0392b'};">(sektör ortalamasından %${Math.abs(b.gider_sapma_yuzdesi).toFixed(0)} ${b.gider_sapma_yuzdesi < 0 ? 'düşük' : 'yüksek'})</span>` : ""}</p>` : ""}
                        </div>
                        <div class="stat-card">
                            <h3>Sektör Ortalamasına Göre Reklam Bütçesi</h3>
                            <p style="color:#888; font-size:12px; margin:2px 0 6px;">Cironuza göre sektör aralığı; harcama hedefi değil, kıyas ölçüsüdür.</p>
                            <div class="value" style="font-size:20px;">${fmt(b.reklam_butcesi_min)} - ${fmt(b.reklam_butcesi_max)}</div>
                            ${b.gelecek_yil_reklam_min != null ? `<p style="color:#2980b9; margin-top:8px;">Önümüzdeki 12 ay (TÜFE düzeltmeli): <b>${fmt(b.gelecek_yil_reklam_min)} - ${fmt(b.gelecek_yil_reklam_max)}</b></p>` : ""}
                            ${b.mevcut_reklam_gideri != null ? `<p style="color:#999; margin-top:8px;">Mevcut gideriniz: ${fmt(b.mevcut_reklam_gideri)}</p>` : ""}
                        </div>
                        ${b.yillik_tufe != null ? `
                        <div class="stat-card">
                            <h3>Yıllık TÜFE</h3>
                            <div class="value" style="font-size:20px;">%${b.yillik_tufe}</div>
                        </div>` : ""}
                        ${b.sektor_net_kar_orani != null ? `
                        <div class="stat-card">
                            <h3>Sektör Net Kâr Oranı</h3>
                            <div class="value" style="font-size:20px;">%${(b.sektor_net_kar_orani * 100).toFixed(1)}</div>
                            <p style="color:#999; margin-top:8px;">TCMB Sektör Bilançoları (net kâr / net satış)</p>
                        </div>` : ""}
                    </div>
                    ${girdiKartiHtml}
                    ${urunFiyatiHtml}
                    ${ihracatFiyatiHtml}
                    ${disTicaretHtml}
                    ${urunVeriYokHtml}
                    ${bolgeselTavsiyeHtml}
                    ${enYuksekBanner}
                    ${notlarHtml ? `<div class="note-list" style="margin-top:14px;">${notlarHtml}</div>` : ""}
                `;
            } catch (e) {
                resultsDiv.innerHTML = `<div class="error">Hata: ${e.message}</div>`;
            }
        }

        function logout() {
            localStorage.removeItem("auth_token");
            window.location.href = "/";
        }

        // Search on Enter
        document.addEventListener("DOMContentLoaded", () => {
            const searchInput = document.getElementById("search-input");
            if (searchInput) {
                searchInput.addEventListener("keypress", (e) => {
                    if (e.key === "Enter") performSearch();
                });
            }
        });

        // CSP (script-src 'self'): satır içi onclick/onchange yasak. Öğeler data-tikla / data-degisim ile adlandırılır,
        // tek dinleyici yalnızca bu listedeki işlevleri çağırır (sonradan innerHTML ile basılan öğeler de dahil).
        // data-arg: işleve giden tek argüman.
        function bolumeGit(bolum) {
            const link = document.querySelector(`[data-section="${bolum}"]`);
            if (link) link.click();
        }
        const EYLEMLER = {
            performSearch: () => performSearch(),
            bulUygunDestekler: () => bulUygunDestekler(),
            butceOnerisiAl: () => butceOnerisiAl(),
            hesabiSil: () => hesabiSil(),
            downgradeToFree: () => downgradeToFree(),
            upgradePlan: (el) => upgradePlan(el.dataset.arg),
            tekrarSor: (el) => tekrarSor(el.dataset.arg),
            bolumeGit: (el) => bolumeGit(el.dataset.arg),
            onTarimKategoriDegisti: () => onTarimKategoriDegisti(),
            rizaDegistir: (el) => rizaDegistir(el),
            karsilamaKapat: () => karsilamaKapat(),
            karsilamaEslesme: () => karsilamaEslesme(),
            kontrolListesiAc: (el) => kontrolListesiAc(el.dataset.arg),
            kontrolMaddesi: (el) => kontrolMaddesi(el),
            kontrolListesiYazdir: () => kontrolListesiYazdir(),
            kontrolListesiKaldir: (el) => kontrolListesiKaldir(el.dataset.arg),
            basvurularYukle: () => basvurularYukle(),
            taslakOlustur: (el) => taslakOlustur(el),
            taslakKopyala: () => taslakKopyala(),
            ikasYenile: () => ikasYenile(),
            ikasBaglantiKes: () => ikasBaglantiKes(),
        };
        function eylemBagla(olay, oznitelik) {
            document.addEventListener(olay, (e) => {
                const el = e.target.closest(`[${oznitelik}]`);
                if (!el || el.disabled) return;
                const islev = EYLEMLER[el.getAttribute(oznitelik)];
                if (!islev) return;
                if (el.tagName === "A") e.preventDefault();
                islev(el, e);
            });
        }
        eylemBagla("click", "data-tikla");
        eylemBagla("change", "data-degisim");
