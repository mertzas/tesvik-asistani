import pytest
from app.scrapers.change_detector import clean_html_cosmetic, compute_content_hash, detect_semantic_diff

def test_cosmetic_cleaning():
    html = """
    <html>
        <head><title>KOSGEB Destekleri</title></head>
        <body>
            <nav><a href="/home">Anasayfa</a></nav>
            <main>
                <h1>KOSGEB İş Geliştirme Desteği</h1>
                <p>Destek üst limiti ₺500.000 TL'dir. Destek oranı %60 olarak uygulanır.</p>
            </main>
            <footer>Copyright 2026 KOSGEB. Sayfa yuklenme süresi: 0.12s</footer>
            <script>console.log('test');</script>
        </body>
    </html>
    """
    clean = clean_html_cosmetic(html)
    assert "Copyright 2026" not in clean
    assert "console.log" not in clean
    assert "KOSGEB İş Geliştirme Desteği" in clean
    assert "₺500.000 TL" in clean
    assert "%60" in clean

def test_cosmetic_diff_ignored():
    old_html = """
    <div>
        <h2>Destek Programı</h2>
        <p>Destek oranı %50 olarak uygulanır.</p>
        <footer>Telif Hakkı 2025</footer>
    </div>
    """
    new_html = """
    <div>
        <h2>Destek Programı</h2>
        <p>Destek oranı %50 olarak uygulanır.</p>
        <footer>Telif Hakkı 2026 - Güncelleme saati 14:00:00</footer>
    </div>
    """
    res = detect_semantic_diff(old_html, new_html)
    assert res["is_meaningful"] is False or res["is_changed"] is False

def test_meaningful_diff_detected():
    old_html = "<div><p>KOSGEB Destek oranı %50 olarak verilir. Üst limit 500.000 TL.</p></div>"
    new_html = "<div><p>KOSGEB Destek oranı %60 olarak verilir. Üst limit 750.000 TL. Program başvuruya kapanmıştır.</p></div>"
    
    res = detect_semantic_diff(old_html, new_html)
    assert res["is_changed"] is True
    assert res["is_meaningful"] is True
    assert len(res["changed_elements"]) > 0
    assert any("oranları" in e for e in res["changed_elements"])
