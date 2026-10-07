// index.html sayfasının betiği (CSP: satır içi betik yasak, bkz. app/main.py CSP).
        // Sabit "http://localhost:8000" yaziliydi: farkli bir port/domain'de
        // (canliya cikinca veya farkli portta test ederken) TUM istekler
        // "Failed to fetch" ile kiriliyordu. Sayfanin kendi origin'ini
        // kullanmak her ortamda calisir.
        const API_BASE = window.location.origin + "/api";

        // 422 doğrulama hatalarında detail bir dizidir; düz metne çevir ("[object Object]" görünmesin).
        function hataMetni(err, varsayilan) {
            const d = err && err.detail;
            if (typeof d === "string") return d;
            if (Array.isArray(d)) return d.map(x => (x && x.msg) ? x.msg.replace(/^Value error, /, "") : JSON.stringify(x)).join("; ");
            return varsayilan;
        }

        function switchForm(form) {
            document.querySelectorAll(".form-container").forEach(f => f.classList.remove("active"));
            document.getElementById(`${form}-form`).classList.add("active");
            document.querySelectorAll(".error, .success").forEach(el => el.style.display = "none");
        }

        function togglePassword(id) {
            const field = document.getElementById(id);
            field.type = field.type === "password" ? "text" : "password";
        }

        async function handleLogin(event) {
            event.preventDefault();
            const email = document.getElementById("login-email").value;
            const password = document.getElementById("login-password").value;
            const btn = document.getElementById("login-btn");
            const errorDiv = document.getElementById("login-error");

            btn.disabled = true;
            btn.innerHTML += '<span class="loading"></span>';

            try {
                const res = await fetch(`${API_BASE}/auth/login`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password })
                });

                if (!res.ok) {
                    const error = await res.json();
                    errorDiv.textContent = hataMetni(error, "Giriş başarısız");
                    errorDiv.style.display = "block";
                    return;
                }

                const data = await res.json();
                // İki farklı localStorage anahtarına da yazıyoruz: bazı
                // dashboard sayfaları (dashboard.html) "auth_token", bazıları
                // (dashboard_pro.html, cilek_dashboard.html) "token" okuyor -
                // bu tutarsızlık "Invalid token" hatasına yol açıyordu.
                // Gerçek düzeltme (tüm sayfaları tek anahtara taşımak) daha
                // büyük bir refactor; şimdilik her iki anahtarı da yazarak
                // hangi dashboard'a gidilirse gidilsin oturumun çalışmasını
                // garanti ediyoruz.
                localStorage.setItem("auth_token", data.access_token);
                localStorage.setItem("token", data.access_token);
                window.location.href = "/dashboard";
            } catch (e) {
                errorDiv.textContent = `Hata: ${e.message}`;
                errorDiv.style.display = "block";
            } finally {
                btn.disabled = false;
                btn.innerHTML = "Giriş Yap";
            }
        }

        async function handleSignup(event) {
            event.preventDefault();
            const name = document.getElementById("signup-name").value;
            const email = document.getElementById("signup-email").value;
            const company = document.getElementById("signup-company").value;
            const password = document.getElementById("signup-password").value;
            const passwordConfirm = document.getElementById("signup-password-confirm").value;
            const btn = document.getElementById("signup-btn");
            const errorDiv = document.getElementById("signup-error");

            if (password !== passwordConfirm) {
                errorDiv.textContent = "Şifreler eşleşmiyor";
                errorDiv.style.display = "block";
                return;
            }

            btn.disabled = true;
            btn.innerHTML += '<span class="loading"></span>';

            try {
                const res = await fetch(`${API_BASE}/auth/signup`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ full_name: name, email, company_name: company, password })
                });

                if (!res.ok) {
                    const error = await res.json();
                    errorDiv.textContent = hataMetni(error, "Kayıt başarısız");
                    errorDiv.style.display = "block";
                    return;
                }

                const data = await res.json();
                // Doğrulama zorunlu kayıt: 202 + mesaj, belirteç yok. Hesap var/yok aynı yanıt (numaralandırma yok).
                if (res.status === 202 || !data.access_token) {
                    const bilgi = document.getElementById("signup-success");
                    bilgi.textContent = data.mesaj || "Kaydınızı tamamlamak için e-postanızı kontrol edin.";
                    bilgi.style.display = "block";
                    errorDiv.style.display = "none";
                    event.target.reset();
                    return;
                }
                // İki farklı localStorage anahtarına da yazıyoruz: bazı
                // dashboard sayfaları (dashboard.html) "auth_token", bazıları
                // (dashboard_pro.html, cilek_dashboard.html) "token" okuyor -
                // bu tutarsızlık "Invalid token" hatasına yol açıyordu.
                // Gerçek düzeltme (tüm sayfaları tek anahtara taşımak) daha
                // büyük bir refactor; şimdilik her iki anahtarı da yazarak
                // hangi dashboard'a gidilirse gidilsin oturumun çalışmasını
                // garanti ediyoruz.
                localStorage.setItem("auth_token", data.access_token);
                localStorage.setItem("token", data.access_token);
                window.location.href = "/dashboard";
            } catch (e) {
                errorDiv.textContent = `Hata: ${e.message}`;
                errorDiv.style.display = "block";
            } finally {
                btn.disabled = false;
                btn.innerHTML = "Kaydol";
            }
        }

        // Panel 401 alınca (parola sıfırlandı / tüm oturumlar kapatıldı / süre doldu) buraya ?oturum=bitti ile döner.
        if (new URLSearchParams(window.location.search).get("oturum") === "bitti") {
            const bilgi = document.getElementById("login-success");
            bilgi.textContent = "Oturumunuz sona erdi. Lütfen yeniden giriş yapın.";
            bilgi.style.display = "block";
        }

        // CSP (script-src 'self'): satır içi onclick/onsubmit yasak; öğeler data-tikla / data-gonder ile adlandırılır.
        const EYLEMLER = {
            switchForm: (el) => switchForm(el.dataset.arg),
            togglePassword: (el) => togglePassword(el.dataset.arg),
            handleLogin: (el, e) => handleLogin(e),
            handleSignup: (el, e) => handleSignup(e),
        };
        function eylemBagla(olay, oznitelik) {
            document.addEventListener(olay, (e) => {
                const el = e.target.closest(`[${oznitelik}]`);
                if (!el) return;
                const islev = EYLEMLER[el.getAttribute(oznitelik)];
                if (islev) islev(el, e);
            });
        }
        eylemBagla("click", "data-tikla");
        eylemBagla("submit", "data-gonder");

        if (localStorage.getItem("auth_token")) {
            window.location.href = "/dashboard";
        }
