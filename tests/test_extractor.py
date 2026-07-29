import pytest
from app.extractor import verify_grounding, extract_structured_info

def test_verify_grounding_accepts_valid_quote():
    raw_text = "KOSGEB İş Geliştirme Desteği kapsamında üst limit 500.000 TL'dir. Destek oranı %60 olarak belirlenmiştir."
    extracted = {
        "destek_orani_yuzde": 60.0,
        "azami_tutar_tl": 500000.0,
        "field_evidence": {
            "destek_orani_yuzde": {"quote": "destek oranı %60", "confidence": 0.95},
            "azami_tutar_tl": {"quote": "üst limit 500.000 TL", "confidence": 0.98}
        }
    }

    verified_data, evidence, confidence = verify_grounding(raw_text, extracted)
    assert verified_data["destek_orani_yuzde"] == 60.0
    assert verified_data["azami_tutar_tl"] == 500000.0
    assert evidence["destek_orani_yuzde"]["verified"] is True
    assert confidence >= 0.90

def test_verify_grounding_rejects_hallucinated_quote():
    raw_text = "Tarım Bakanlığı sera yapımı için faizsiz kredi vermektedir."
    extracted = {
        "destek_orani_yuzde": 90.0,  # Metinde yok!
        "field_evidence": {
            "destek_orani_yuzde": {"quote": "destek oranı yüzde 90 olarak uygulanacaktır", "confidence": 0.95}
        }
    }

    verified_data, evidence, confidence = verify_grounding(raw_text, extracted)
    # Metinde geçmediği için iptal edilmeli
    assert "destek_orani_yuzde" not in verified_data
    assert evidence["destek_orani_yuzde"]["verified"] is False

def test_verify_grounding_rejects_low_confidence():
    raw_text = "Başvuru üst limiti 100.000 TL."
    extracted = {
        "azami_tutar_tl": 100000.0,
        "field_evidence": {
            "azami_tutar_tl": {"quote": "üst limiti 100.000 TL", "confidence": 0.50}  # 0.50 < 0.85
        }
    }

    verified_data, evidence, confidence = verify_grounding(raw_text, extracted)
    assert "azami_tutar_tl" not in verified_data
    assert evidence["azami_tutar_tl"]["verified"] is False
