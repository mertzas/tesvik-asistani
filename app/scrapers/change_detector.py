"""
Resmi kurum web sayfalarındaki değişiklikleri tarayan ve kozmetik değişiklikleri
(footer tarihi, session token, reklamlar, nav barları) anlamlı mevzuat/oran
değişikliklerinden ayıran modül.
"""
import re
import hashlib
from typing import Dict, Any, List
from bs4 import BeautifulSoup


COSMETIC_TAGS = {"script", "style", "nav", "footer", "header", "iframe", "form", "svg", "noscript", "aside"}

# Anlamsız dinamik metin kalıpları (ör. "Telif Hakkı 2026", "Sayfa yüklenme zamanı", vb.)
COSMETIC_PATTERNS = [
    r"copyright\s*©?\s*\d{4}",
    r"tüm hakları saklıdır",
    r"sayfa yuklenme süresi:?\s*[\d.]+",
    r"csrf[-_]?token\s*=\s*[a-zA-Z0-9_-]+",
    r"session[-_]?id\s*=\s*[a-zA-Z0-9_-]+",
    r"\d{2}[./-]\d{2}[./-]\d{4}\s+\d{2}:\d{2}:\d{2}",  # Tarih saat damgası 29.07.2026 20:30:00
]


def clean_html_cosmetic(html_or_text: str) -> str:
    """HTML veya metinden kozmetik gürültü elemanlarını (nav, footer, reklam,
    tarih damgası, token vb.) temizleyip anlamlı çekirdek metni döndürür."""
    if not html_or_text:
        return ""

    if "<" in html_or_text and ">" in html_or_text:
        soup = BeautifulSoup(html_or_text, "html.parser")
        for tag in soup.find_all(COSMETIC_TAGS):
            tag.decompose()
        text = soup.get_text(separator=" ")
    else:
        text = html_or_text

    # Satır içi kozmetik kalıpları temizle
    for pattern in COSMETIC_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Fazla boşlukları ve satır başlarını birleştir
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized = " ".join(lines)
    return normalized


def compute_content_hash(normalized_text: str) -> str:
    """Temizlenmiş metnin SHA256 özetini üretir."""
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def extract_key_tokens(text: str) -> Dict[str, set]:
    """Metindeki oranlar (%), tutarlar (TL), tarihler ve durum anahtar kelimelerini çıkarır."""
    text_l = text.lower()
    
    # Oranlar: %50, %60.5 vb.
    rates = set(re.findall(r"%\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*%", text_l))
    
    # Tutarlar: ₺500.000, 1.000.000 TL vb.
    amounts = set(re.findall(r"[\d.,]+\s*(?:tl|₺|lira|milyon|bin)", text_l))
    
    # Durum sinyalleri
    status_keywords = set()
    keywords_to_check = [
        "kapanmıştır", "durdurulmuştur", "son ermiştir", "başlamıştır",
        "yeni dönem", "başvuruya açık", "başvuruları başladı", "güncellenmiştir"
    ]
    for kw in keywords_to_check:
        if kw in text_l:
            status_keywords.add(kw)

    return {
        "rates": rates,
        "amounts": amounts,
        "status_keywords": status_keywords,
    }


def detect_semantic_diff(old_html_or_text: str, new_html_or_text: str) -> Dict[str, Any]:
    """Eski ve yeni metin arasındaki değişikliğin kozmetik mi yoksa anlamlı
    bir mevzuat/oran/durum değişikliği mi olduğunu tespit eder."""
    clean_old = clean_html_cosmetic(old_html_or_text)
    clean_new = clean_html_cosmetic(new_html_or_text)

    old_hash = compute_content_hash(clean_old)
    new_hash = compute_content_hash(clean_new)

    if old_hash == new_hash:
        return {
            "is_changed": False,
            "is_meaningful": False,
            "changed_elements": [],
            "old_hash": old_hash,
            "new_hash": new_hash,
            "reason": "İçerik hash'leri birebir aynı (değişiklik yok)."
        }

    tokens_old = extract_key_tokens(clean_old)
    tokens_new = extract_key_tokens(clean_new)

    changed_elements = []
    
    # Oran değişimi
    if tokens_old["rates"] != tokens_new["rates"]:
        changed_elements.append(f"Destek oranları değişti: Eski={tokens_old['rates']} -> Yeni={tokens_new['rates']}")

    # Tutar değişimi
    if tokens_old["amounts"] != tokens_new["amounts"]:
        changed_elements.append(f"Destek tutarları değişti: Eski={tokens_old['amounts']} -> Yeni={tokens_new['amounts']}")

    # Durum değişimi
    if tokens_old["status_keywords"] != tokens_new["status_keywords"]:
        changed_elements.append(f"Program durum sinyalleri değişti: Eski={tokens_old['status_keywords']} -> Yeni={tokens_new['status_keywords']}")

    is_meaningful = len(changed_elements) > 0 or abs(len(clean_new) - len(clean_old)) > 200

    return {
        "is_changed": True,
        "is_meaningful": is_meaningful,
        "changed_elements": changed_elements,
        "old_hash": old_hash,
        "new_hash": new_hash,
        "reason": "Anlamlı mevzuat/oran değişikliği tespit edildi." if is_meaningful else "Kozmetik/önemsiz metin değişikliği."
    }
