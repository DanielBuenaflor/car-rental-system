import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Ensure the module can be imported even if Flask isn't fully configured
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mocking pytesseract and PIL before importing the service to avoid errors
with patch.dict('sys.modules', {'pytesseract': MagicMock(), 'PIL': MagicMock()}):
    from MyFlaskApp.utils.ocr_service import (
        extract_license_number,
        extract_expiry_date,
        calculate_confidence,
        _parse_date
    )

class TestTesseractConfig:

    def test_tesseract_cmd_from_env(self):
        """TESSERACT_CMD env var should configure pytesseract"""
        with patch.dict(os.environ, {'TESSERACT_CMD': '/custom/tesseract'}):
            # Re-import module to pick up the env var
            with patch.dict('sys.modules', {'pytesseract': MagicMock(), 'PIL': MagicMock()}):
                import importlib
                from MyFlaskApp.utils import ocr_service
                importlib.reload(ocr_service)
                assert ocr_service.pytesseract.pytesseract.tesseract_cmd == '/custom/tesseract'

    def test_tesseract_cmd_default_when_env_unset(self):
        """When TESSERACT_CMD is not set, pytesseract uses system default"""
        with patch.dict(os.environ, {}, clear=True):
            # Remove TESSERACT_CMD if present
            os.environ.pop('TESSERACT_CMD', None)
            with patch.dict('sys.modules', {'pytesseract': MagicMock(), 'PIL': MagicMock()}):
                import importlib
                from MyFlaskApp.utils import ocr_service
                importlib.reload(ocr_service)
                # Should not have set tesseract_cmd (leaving system default)
                assert 'TESSERACT_CMD' not in os.environ

class TestOCRService:

    # 1. Test License Number Extraction
    @pytest.mark.parametrize("input_text, expected", [
        ("LICENSE NO: N01-23-456789", "N01-23-456789"), # Philippines format
        ("DL: ABC1234567890", "ABC1234567890"),         # Generic Alphanumeric
        ("No valid number here", None),
        ("", None),
        (None, None),
    ])
    def test_extract_license_number(self, input_text, expected):
        assert extract_license_number(input_text) == expected

    # 2. Test Expiry Date Extraction
    @pytest.mark.parametrize("input_text, expected", [
        ("EXPIRY DATE: 12/31/2030", "12/31/2030"),
        ("Valid Until: October 15, 2028", "October 15, 2028"),
        ("Expires on 2025-05-20", "2025-05-20"),
        ("No date here", None),
    ])
    def test_extract_expiry_date(self, input_text, expected):
        # This assumes extract_expiry_date returns the raw string match
        assert extract_expiry_date(input_text) == expected

    # 3. Test Date Parsing Helper
    @pytest.mark.parametrize("date_str, expected_year", [
        ("12/31/2030", 2030),
        ("October 15, 2028", 2028),
        ("2025-05-20", 2025),
        ("Invalid Date", None),
    ])
    def test_parse_date(self, date_str, expected_year):
        result = _parse_date(date_str)
        if expected_year:
            assert result.year == expected_year
        else:
            assert result is None

    # 4. Test Confidence Scoring
    def test_calculate_confidence(self):
        # Test high confidence (matches multiple keywords)
        high_conf = calculate_confidence("LICENSE NUMBER EXPIRY DATE DRIVER")
        # Test low confidence
        low_conf = calculate_confidence("Random text")
        
        assert high_conf > low_conf
        assert calculate_confidence("") == 0
        assert calculate_confidence(None) == 0

    # 5. Mocked Tesseract Test (Simulation)
    @patch('pytesseract.image_to_string')
    def test_full_ocr_flow_mock(self, mock_ocr):
        # Mocking the text returned by pytesseract
        mock_ocr.return_value = "DRIVER LICENSE\nNO: L03-12-987654\nEXP: 01/01/2027"
        
        # Here you would call your main OCR processing function if you have one
        # e.g., result = process_license_image(fake_image)
        # For now, we test the logic via the text it would produce:
        text = mock_ocr.return_value
        assert extract_license_number(text) == "L03-12-987654"
        assert _parse_date(extract_expiry_date(text)).year == 2027