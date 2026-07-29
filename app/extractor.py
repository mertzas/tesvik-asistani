"""
Yerel Ollama veya kural tabanlı doğrulama ile Türkçe mevzuat metinlerinden
yapılandırılmış bilgi (destek oranı, üst limit, başvuru şartları) çıkaran ve
SIRTINI KAYNAK METNE DAYAYAN (Zero-Hallucination Grounding) Çıkarım Motoru.

KRİTİK KURAL: Çıkarılan her alanın `quote` (birebir kaynak alıntısı) ve `confidence`
(güven skoru >= 0.85) bilgisi olmalıdır. Kaynak metinde bulunamayan alıntılar
İPTAL EDİLİR ve veritabanına YAZILMAZ.
"""
import json
import re
import requests
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models import Tesvik, SessionLocal

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4"  # veya llama3 / qwen2.5
OLLAMA_TIMEOUT_SEC = 60
MIN_CONFIDENCE_THRESHOLD = 0.85


EXTRACTION_PROMPT_TEMPLATE = """Sen Türkiye devlet teşvikleri ve mevzuatı konusunda uzmanlaşmış bir Veri Çıkarım Asistanısın.

GÖREVİN: Aşağıda verilen resmi teşvik/mevzuat metninden yapılandırılmış bilgileri çıkarmak ve çıkardığın HER BİR BİLGİ İÇİN metindeki BİREBİR ALINTIYI (quote) sunmaktır.

METİN:
{text}

MUTLAK KURALLAR:
1. Metinde geçmeyen hiçbir bilgiyi icat etme veya tahmin etme. Emin değilsen null ver.
2. Çıkardığın her sayısal veya metinsel alan için `field_evidence` altında metinde geçen BİREBİR ALINTIYI (`quote`) ve 0.0-1.0 arası `confidence` skorunu ver.
3. Yanıtını SADECE aşağıdaki JSON formatında döndür (başka açıklama yazma):

```json
{{
  "program_aktif_mi": true,
  "destek_orani_yuzde": 60.0,
  "azami_tutar_tl": 500000.0,
  "basvuru_sartlari": ["KOBİ ölçeğinde olmak", "En az 2 yıldır faal olmak"],
  "gerekli_belgeler": ["İmza sirküleri", "Faaliyet belgesi"],
  "basvuru_donemi": "30 Eylül 2026 tarihine kadar",
  "field_evidence": {{
    "destek_orani_yuzde": {{"quote": "destek oranı %60 olarak uygulanır", "confidence": 0.95}},
    "azami_tutar_tl": {{"quote": "üst limit 500.000 TL'dir", "confidence": 0.98}},
    "basvuru_sartlari": {{"quote": "en az 2 yıldır faal olmak", "confidence": 0.90}},
    "program_aktif_mi": {{"quote": "başvurular devam etmektedir", "confidence": 0.92}}
  }}
}}
```"""


def _normalize_for_match(text: str) -> str:
    """Alıntı eşlemesi için noktalama ve boşlukları sadelleştirir."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", (text or "").lower())).strip()


def verify_grounding(raw_text: str, extracted_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], float]:
    """Çıkarılan her alanın kaynak metinde BİREBİR veya yüksek oranda geçip geçmediğini
    ve güven skorunun THRESHOLD üzerinde olup olmadığını doğrular.
    Doğrulanmayan alanlar İPTAL EDİLİR."""
    raw_normalized = _normalize_for_match(raw_text)
    evidence = extracted_data.get("field_evidence", {})

    verified_data = {}
    valid_evidence = {}
    confidence_scores = []

    fields_to_check = ["program_aktif_mi", "destek_orani_yuzde", "azami_tutar_tl", "basvuru_sartlari", "gerekli_belgeler", "basvuru_donemi"]

    for field in fields_to_check:
        val = extracted_data.get(field)
        if val is None or val == []:
            continue

        field_ev = evidence.get(field, {})
        quote = field_ev.get("quote", "")
        confidence = float(field_ev.get("confidence", 0.0))

        # Kanıt ve güven kontrolü
        quote_normalized = _normalize_for_match(quote)
        is_quote_present = len(quote_normalized) > 3 and quote_normalized in raw_normalized

        if is_quote_present and confidence >= MIN_CONFIDENCE_THRESHOLD:
            verified_data[field] = val
            valid_evidence[field] = {"quote": quote, "confidence": confidence, "verified": True}
            confidence_scores.append(confidence)
        else:
            # Doğrulanamadı -> İptal et (Zero-Hallucination Policy)
            valid_evidence[field] = {"quote": quote, "confidence": confidence, "verified": False, "reason": "Kaynak metinde bulunamadı veya güven skoru düşük."}

    avg_confidence = round(sum(confidence_scores) / len(confidence_scores), 2) if confidence_scores else 0.0
    return verified_data, valid_evidence, avg_confidence


def _heuristic_rule_extraction(raw_text: str) -> Dict[str, Any]:
    """Ollama kapalıysa/erişilemezse çalışan kural tabanlı (heuristic) yedek çıkarıcı."""
    raw_l = raw_text.lower()
    
    # Oran
    rate_match = re.search(r"%\s*(\d+(?:[.,]\d+)?)", raw_text)
    destek_orani = float(rate_match.group(1).replace(",", ".")) if rate_match else None
    
    # Tutar: 1.500.000 TL, 500.000 TL vb.
    amount_match = re.search(r"([\d]{1,3}(?:\.[\d]{3})*(?:,\d+)?)\s*(?:tl|₺|lira)", raw_l)
    azami_tutar = None
    amount_quote = None
    if amount_match:
        try:
            azami_tutar = float(amount_match.group(1).replace(".", "").replace(",", "."))
            amount_quote = amount_match.group(0)
        except ValueError:
            pass

    # Aktiflik
    aktif_mi = True
    status_quote = None
    close_keywords = ["kapanmıştır", "son ermiştir", "durdurulmuştur"]
    open_keywords = ["devam etmektedir", "başvuruları başladı", "açıktır", "alınır", "uygulanır", "verilir"]

    for kw in close_keywords:
        if kw in raw_l:
            aktif_mi = False
            status_quote = kw
            break

    if status_quote is None:
        for kw in open_keywords:
            if kw in raw_l:
                status_quote = kw
                break

    evidence = {}
    if destek_orani:
        evidence["destek_orani_yuzde"] = {"quote": rate_match.group(0), "confidence": 0.95}
    if azami_tutar and amount_quote:
        evidence["azami_tutar_tl"] = {"quote": amount_quote, "confidence": 0.95}
    if status_quote:
        evidence["program_aktif_mi"] = {"quote": status_quote, "confidence": 0.90}

    return {
        "program_aktif_mi": aktif_mi,
        "destek_orani_yuzde": destek_orani,
        "azami_tutar_tl": azami_tutar,
        "basvuru_sartlari": [],
        "gerekli_belgeler": [],
        "basvuru_donemi": None,
        "field_evidence": evidence
    }


def extract_structured_info(raw_text: str) -> Tuple[Dict[str, Any], Dict[str, Any], float]:
    """Resmi metinden yapılandırılmış bilgi çıkarır ve doğrulama filtresinden geçirir."""
    if not raw_text or len(raw_text.strip()) < 20:
        return {}, {}, 0.0

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(text=raw_text[:3000])

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"},
            timeout=OLLAMA_TIMEOUT_SEC,
        )
        if resp.status_code == 200:
            content = resp.json().get("response", "")
            raw_data = json.loads(content)
            return verify_grounding(raw_text, raw_data)
    except Exception:
        pass

    # Fallback heuristic
    raw_data = _heuristic_rule_extraction(raw_text)
    return verify_grounding(raw_text, raw_data)


def process_tesvik_extraction(tesvik_id: int, db: Session) -> Optional[Tesvik]:
    """Bir teşvik kaydının metinlerini çıkarım motorundan geçirir ve sonuçları kaydeder."""
    tesvik = db.query(Tesvik).filter(Tesvik.id == tesvik_id).first()
    if not tesvik:
        return None

    full_text = f"{tesvik.baslik}\n\n{tesvik.ozet or ''}\n\n{tesvik.detay or ''}"
    verified_data, evidence, confidence = extract_structured_info(full_text)

    if "program_aktif_mi" in verified_data:
        tesvik.aktif_mi = verified_data["program_aktif_mi"]
    if "azami_tutar_tl" in verified_data:
        tesvik.tutari_max = verified_data["azami_tutar_tl"]
        if tesvik.tutari_min is None:
            tesvik.tutari_min = round(verified_data["azami_tutar_tl"] * 0.1, 2)
    if "basvuru_sartlari" in verified_data:
        tesvik.basvuru_sartlari = verified_data["basvuru_sartlari"]
    if "gerekli_belgeler" in verified_data:
        tesvik.gerekli_belgeler = verified_data["gerekli_belgeler"]
    if "basvuru_donemi" in verified_data:
        tesvik.basvuru_suresi = verified_data["basvuru_donemi"]

    tesvik.cikarim_guven_skoru = confidence
    tesvik.cikarim_kanitlari = evidence
    db.commit()
    return tesvik
