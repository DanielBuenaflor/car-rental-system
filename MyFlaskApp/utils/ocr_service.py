"""
OCR Service Module for License Verification
Uses Tesseract OCR to extract license information from images
"""

import os
import re
import cv2
import pytesseract
import logging
import requests
from PIL import Image
from datetime import datetime

# Configure logging for defensive logging
logger = logging.getLogger(__name__)

# Configure Tesseract path from environment variable, falling back to system default
tesseract_cmd = os.environ.get('TESSERACT_CMD')
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

# Configure OCR.space API key
ocr_api_key = os.environ.get('OCR_API_KEY')


class LicenseOCRService:
    """OCR service for extracting license information from images"""
    
    @staticmethod
    def preprocess_image(image_path):
        """
        Preprocess image for better OCR accuracy.

        Input:
            image_path (str): Path to the license image file

        Process:
            1. Load image using OpenCV
            2. Convert to grayscale for thresholding
            3. Resize if image is too small (below 800px height)
            4. Apply adaptive Gaussian thresholding to handle uneven lighting
            5. Denoise using non-local means denoising

        Output:
            numpy.ndarray: Preprocessed image array ready for OCR, or None if processing fails
        """
        logger.info(f"[OCR] Starting image preprocessing for: {image_path}")
        try:
            loaded_image = cv2.imread(image_path)
            if loaded_image is None:
                logger.error(f"[OCR] Failed to load image from path: {image_path}")
                return None
            logger.debug(f"[OCR] Image loaded successfully. Original shape: {loaded_image.shape}")

            # Convert to grayscale
            grayscale_image = cv2.cvtColor(loaded_image, cv2.COLOR_BGR2GRAY)
            logger.debug("[OCR] Image converted to grayscale")

            # Resize if image is too small (improves OCR accuracy)
            image_height, image_width = grayscale_image.shape
            if image_height < 800:
                scale_factor = 800 / image_height
                grayscale_image = cv2.resize(grayscale_image, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
                logger.debug(f"[OCR] Image resized with scale factor: {scale_factor:.2f}")

            # Apply adaptive thresholding
            thresholded_image = cv2.adaptiveThreshold(
                grayscale_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            logger.debug("[OCR] Adaptive thresholding applied (Gaussian, blockSize=11, C=2)")

            # Denoise
            denoised_image = cv2.fastNlMeansDenoising(thresholded_image, None, 10, 7, 21)
            logger.debug("[OCR] Image denoising completed")
            logger.info("[OCR] Image preprocessing completed successfully")

            return denoised_image
        except Exception as preprocessing_error:
            logger.error(f"[OCR] Image preprocessing error: {preprocessing_error}")
            print(f"Image preprocessing error: {preprocessing_error}")
            return None

    @staticmethod
    def extract_text_ocr_space(image_path):
        """
        Extract text from image using OCR.space API.

        Input:
            image_path (str): Path to the license image file

        Process:
            1. Check if OCR_API_KEY is configured
            2. POST image to OCR.space API
            3. Parse JSON response for extracted text

        Output:
            str: Extracted text from license image, or None if API fails
        """
        if not ocr_api_key:
            logger.warning("[OCR] OCR.space API key not configured. Skipping API call.")
            return None

        logger.info(f"[OCR] Calling OCR.space API for: {image_path}")
        try:
            with open(image_path, 'rb') as f:
                response = requests.post(
                    'https://api.ocr.space/parse/image',
                    files={'file': f},
                    data={
                        'apikey': ocr_api_key,
                        'language': 'eng',
                        'isOverlayRequired': False
                    },
                    timeout=30
                )

            result = response.json()
            logger.debug(f"[OCR] OCR.space response: OCRExitCode={result.get('OCRExitCode')}")

            if result.get('IsErroredOnProcessing'):
                error_msg = result.get('ErrorMessage', 'Unknown error')
                logger.error(f"[OCR] OCR.space API error: {error_msg}")
                return None

            parsed_results = result.get('ParsedResults', [])
            if not parsed_results:
                logger.warning("[OCR] OCR.space returned no parsed results")
                return None

            parsed_text = parsed_results[0].get('ParsedText', '').strip()
            if parsed_text:
                logger.info(f"[OCR] OCR.space extracted {len(parsed_text)} characters")
            else:
                logger.warning("[OCR] OCR.space returned empty text")

            return parsed_text if parsed_text else None

        except requests.exceptions.Timeout:
            logger.error("[OCR] OCR.space API timeout")
            return None
        except requests.exceptions.RequestException as request_error:
            logger.error(f"[OCR] OCR.space API request failed: {request_error}")
            return None
        except Exception as api_error:
            logger.error(f"[OCR] OCR.space API error: {api_error}")
            return None
    
    @staticmethod
    def extract_text(image_path):
        """
        Extract text from license image using OCR.space API with Tesseract fallback.

        Input:
            image_path (str): Path to the license image file

        Process:
            1. Try OCR.space API first for better accuracy
            2. If API fails or returns insufficient text (<10 chars), fallback to Tesseract
            3. For Tesseract: preprocess image, run OCR, fallback to original if poor results

        Output:
            str: Extracted text from license image, or None if extraction fails

        Tesseract Configuration (fallback):
            --oem 3: Use LSTM neural net mode (most accurate)
            --psm 6: Assume a single uniform block of text
            -l eng: English language
        """
        logger.info(f"[OCR] Starting text extraction for: {image_path}")

        ocr_space_result = LicenseOCRService.extract_text_ocr_space(image_path)
        if ocr_space_result and len(ocr_space_result.strip()) >= 10:
            logger.info(f"[OCR] OCR.space succeeded: {len(ocr_space_result)} characters")
            return ocr_space_result.strip()

        logger.warning("[OCR] OCR.space failed or returned insufficient text. Falling back to Tesseract.")

        try:
            preprocessed_image = LicenseOCRService.preprocess_image(image_path)
            if preprocessed_image is None:
                logger.error(f"[OCR] Preprocessing failed for: {image_path}")
                return None

            # OCR configuration optimized for documents
            tesseract_config = r'--oem 3 --psm 6 -l eng'
            logger.debug(f"[OCR] Using Tesseract config: {tesseract_config}")
            
            # Extract text from preprocessed image
            extracted_text = pytesseract.image_to_string(preprocessed_image, config=tesseract_config)
            extracted_text_length = len(extracted_text.strip()) if extracted_text else 0
            logger.debug(f"[OCR] Text extracted from preprocessed image: {extracted_text_length} characters")
            
            # Also try with original image as fallback
            if not extracted_text or extracted_text_length < 10:
                logger.warning(f"[OCR] Preprocessed image yielded poor results ({extracted_text_length} chars). Trying original image...")
                original_extracted_text = pytesseract.image_to_string(image_path, config=tesseract_config)
                original_text_length = len(original_extracted_text.strip()) if original_extracted_text else 0
                
                if original_extracted_text and original_text_length > extracted_text_length:
                    logger.info(f"[OCR] Original image produced better results: {original_text_length} chars vs {extracted_text_length} chars")
                    extracted_text = original_extracted_text
                else:
                    logger.info("[OCR] Preprocessed image result was better or equal to original")
            
            final_text = extracted_text.strip() if extracted_text else None
            if final_text:
                logger.info(f"[OCR] Text extraction successful: {len(final_text)} characters")
            else:
                logger.warning("[OCR] Text extraction returned empty result")
            return final_text
            
        except Exception as extraction_error:
            logger.error(f"[OCR] Text extraction error: {extraction_error}")
            print(f"OCR text extraction error: {extraction_error}")
            return None
    
    @staticmethod
    def extract_license_number(ocr_text):
        """
        Extract license number from OCR text using regex pattern matching.
        
        Input:
            ocr_text (str): Raw text extracted from license image via OCR
            
        Process:
            1. Normalize text to uppercase for consistent matching
            2. First try label-based patterns (LICENSE NO:, DL:, etc.) for higher accuracy
            3. Fall back to general patterns (Philippines format, generic alphanumeric)
            4. Clean extracted number by removing spaces and hyphens
            5. Validate length (5-20 characters)
            
        Output:
            str: Cleaned license number string, or None if no valid pattern found
            
        Supported Patterns:
            - Philippines LTO format: ABC123456789 or ABC 12 3456789
            - Generic: Letters followed by numbers, various separators
            - Alphanumeric: 6-15 mixed characters
        """
        logger.debug("[OCR] Starting license number extraction")
        if not ocr_text:
            logger.warning("[OCR] Cannot extract license number: input text is empty")
            return None
        
        normalized_text = ocr_text.upper()
        logger.debug(f"[OCR] Normalized text length: {len(normalized_text)} characters")
        
        # Label-based patterns - higher confidence matches with explicit labels
        label_based_patterns = [
            r'(?:LICENSE|LIC|DRIVER|DL|ID|NO|NUMBER|#)[:\s.\-]*([A-Z0-9\-]{5,20})',
            r'(?:LICENSE\s+NO|LIC\s+NO|ID\s+NO)[:\s.\-]*([A-Z0-9\-]{5,20})',
        ]
        
        logger.debug("[OCR] Trying label-based patterns first for higher accuracy")
        for pattern_index, label_pattern in enumerate(label_based_patterns):
            pattern_match = re.search(label_pattern, normalized_text, re.IGNORECASE)
            if pattern_match:
                extracted_number = pattern_match.group(1).strip().replace(' ', '').replace('-', '')
                if len(extracted_number) >= 5:
                    logger.info(f"[OCR] License number extracted via label pattern {pattern_index + 1}: {extracted_number}")
                    return extracted_number
        
        # General patterns for license numbers without explicit labels
        general_patterns = [
            # Philippines LTO format: 3 letters + 2 numbers + 5-7 digits
            r'([A-Z]{3}\s*\d{2}\s*\d{5,7})',
            # Generic: letters followed by numbers (1-4 letters, 6-10 digits)
            r'([A-Z]{1,4}[-\s]?\d{6,10})',
            # Numbers followed by letters (6-10 digits, 1-3 letters)
            r'(\d{6,10}[-\s]?[A-Z]{1,3})',
            # Fallback: mixed alphanumeric 6-15 characters
            r'([A-Z0-9]{6,15})',
        ]
        
        logger.debug("[OCR] Trying general patterns as fallback")
        for pattern_index, general_pattern in enumerate(general_patterns):
            pattern_matches = re.findall(general_pattern, normalized_text)
            for matched_text in pattern_matches:
                cleaned_number = matched_text.strip().replace(' ', '').replace('-', '')
                if 5 <= len(cleaned_number) <= 20:
                    logger.info(f"[OCR] License number extracted via general pattern {pattern_index + 1}: {cleaned_number}")
                    return cleaned_number
        
        logger.warning("[OCR] No license number pattern matched in extracted text")
        return None
    
    @staticmethod
    def extract_expiry_date(ocr_text):
        """
        Extract expiry date from OCR text using regex pattern matching.
        
        Input:
            ocr_text (str): Raw text extracted from license image via OCR
            
        Process:
            1. Search for explicit expiry labels (EXPIRY, VALID UNTIL, etc.)
            2. Try multiple date formats (numeric, month names, various separators)
            3. Parse matched date string to datetime object
            4. Normalize to ISO format YYYY-MM-DD for consistency
            
        Output:
            str: Expiry date in YYYY-MM-DD format, or raw matched string if parsing fails, or None
            
        Supported Patterns:
            - EXPIRY/EXPIRES/VALID UNTIL labels followed by date
            - Numeric: 12/31/2030, 31-12-2030, etc.
            - Named months: October 15, 2028, OCT 15 2028, etc.
        """
        logger.debug("[OCR] Starting expiry date extraction")
        if not ocr_text:
            logger.warning("[OCR] Cannot extract expiry date: input text is empty")
            return None
        
        # Date extraction patterns - ordered by specificity
        date_patterns = [
            # Explicit labels with numeric dates (highest priority)
            r'(?:EXPIRY|EXPIRES|EXPIRATION|VALID\s*UNTIL|VALID\s*THRU)[:\s.\-]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            # Explicit labels with named month dates
            r'(?:EXPIRY|EXPIRES|EXPIRATION|VALID\s*UNTIL|VALID\s*THRU)[:\s.\-]*((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[.\s]*\d{1,2},?[.\s]*\d{4})',
            # Generic numeric date patterns
            r'(\d{1,2}[/-]\d{1,2}[/-](?:20)?\d{2})',
            # Generic named month patterns
            r'((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[.\s]*\d{1,2},?[.\s]*\d{4})',
        ]
        
        for pattern_index, date_pattern in enumerate(date_patterns):
            date_match = re.search(date_pattern, ocr_text, re.IGNORECASE)
            if date_match:
                matched_date_string = date_match.group(1).strip()
                logger.debug(f"[OCR] Date pattern {pattern_index + 1} matched: '{matched_date_string}'")
                
                # Try to normalize to YYYY-MM-DD
                try:
                    parsed_datetime = LicenseOCRService._parse_date(matched_date_string)
                    normalized_date = parsed_datetime.strftime('%Y-%m-%d')
                    logger.info(f"[OCR] Expiry date extracted and normalized: {normalized_date}")
                    return normalized_date
                except Exception as parse_error:
                    logger.warning(f"[OCR] Could not parse date '{matched_date_string}': {parse_error}")
                    return matched_date_string
        
        logger.warning("[OCR] No expiry date pattern matched in extracted text")
        return None
    
    @staticmethod
    def _parse_date(date_string):
        """
        Parse various date string formats to datetime object.
        
        Input:
            date_string (str): Date string in various formats
            
        Process:
            1. Strip whitespace from input
            2. Try multiple date formats in order of likelihood
            3. Handle 2-digit years by assuming 2000s for years < 50, 1900s otherwise
            
        Output:
            datetime: Parsed datetime object
            
        Raises:
            ValueError: If no format successfully parses the date string
            
        Supported Formats:
            - ISO/Standard: %Y-%m-%d, %d/%m/%Y, %m/%d/%Y
            - Short year: %d/%m/%y, %m/%d/%y (auto-converts 2-digit years)
            - Named months: %b %d, %Y (e.g., "Oct 15, 2025")
            - Full months: %B %d, %Y (e.g., "October 15, 2025")
        """
        cleaned_date_string = date_string.strip()
        logger.debug(f"[OCR] Parsing date string: '{cleaned_date_string}'")
        
        supported_date_formats = [
            '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d',
            '%d-%m-%Y', '%m-%d-%Y', '%Y-%m-%d',
            '%d/%m/%y', '%m/%d/%y', '%y/%m/%d',
            '%d-%m-%y', '%m-%d-%y', '%y-%m-%d',
            '%b %d, %Y', '%B %d, %Y',
            '%b %d %Y', '%B %d %Y',
            '%b. %d, %Y', '%b. %d %Y',
        ]
        
        for date_format in supported_date_formats:
            try:
                parsed_datetime = datetime.strptime(cleaned_date_string, date_format)
                
                # Handle 2-digit years (e.g., '25' -> 2025, '98' -> 1998)
                if parsed_datetime.year < 50:
                    parsed_datetime = parsed_datetime.replace(year=parsed_datetime.year + 2000)
                    logger.debug(f"[OCR] Converted 2-digit year to 2000s: {parsed_datetime.year}")
                elif parsed_datetime.year < 100:
                    parsed_datetime = parsed_datetime.replace(year=parsed_datetime.year + 1900)
                    logger.debug(f"[OCR] Converted 2-digit year to 1900s: {parsed_datetime.year}")
                
                logger.debug(f"[OCR] Successfully parsed date using format '{date_format}': {parsed_datetime}")
                return parsed_datetime
                
            except ValueError:
                continue
        
        parse_error_message = f"Could not parse date: {cleaned_date_string}"
        logger.error(f"[OCR] {parse_error_message}")
        raise ValueError(parse_error_message)
    
    @staticmethod
    def calculate_confidence(extracted_license_number, extracted_expiry_date, extracted_text_length):
        """
        Calculate confidence score based on extraction quality.
        
        Input:
            extracted_license_number (str or None): License number if extracted, None otherwise
            extracted_expiry_date (str or None): Expiry date if extracted, None otherwise  
            extracted_text_length (int): Total length of raw OCR text (image quality indicator)
            
        Process:
            1. Base score of 0.0
            2. Add 0.5 if license number found (critical field)
            3. Add 0.1 bonus if license number has reasonable length (6-15 chars)
            4. Add 0.3 if expiry date found (secondary field)
            5. Add 0.1 if substantial text extracted (indicates good image quality)
            6. Cap at maximum 1.0
            
        Output:
            float: Confidence score between 0.0 and 1.0
            
        Scoring Breakdown:
            - 0.0-0.4: Poor extraction (likely image quality issue)
            - 0.5-0.6: License only (acceptable for some use cases)
            - 0.7-0.8: License + date (good extraction)
            - 0.9-1.0: License + date + good image quality (excellent)
        """
        logger.debug(f"[OCR] Calculating confidence score. License: {extracted_license_number is not None}, Expiry: {extracted_expiry_date is not None}, Text length: {extracted_text_length}")
        
        confidence_score = 0.0
        
        # License number found (highest weight - critical field)
        if extracted_license_number:
            confidence_score += 0.5
            # Bonus for reasonable length (validates format plausibility)
            if 6 <= len(extracted_license_number) <= 15:
                confidence_score += 0.1
                logger.debug(f"[OCR] License length bonus applied: {len(extracted_license_number)} chars")
        
        # Expiry date found (medium weight - important but sometimes missing)
        if extracted_expiry_date:
            confidence_score += 0.3
        
        # Substantial text extracted (low weight - indicates image quality)
        if extracted_text_length > 50:
            confidence_score += 0.1
            logger.debug(f"[OCR] Text length bonus applied: {extracted_text_length} chars > 50")
        
        final_score = min(confidence_score, 1.0)
        logger.info(f"[OCR] Confidence score calculated: {final_score:.2f}")
        return final_score
    
    @staticmethod
    def validate_license(front_image_path, back_image_path=None, 
                         expected_license_number=None, expected_expiry=None):
        """
        Main validation method: Extract and validate license information from images.
        
        Input:
            front_image_path (str): Path to front side of license image
            back_image_path (str, optional): Path to back side of license image
            expected_license_number (str, optional): Expected license number for comparison
            expected_expiry (str, optional): Expected expiry date for comparison
            
        Process:
            1. Validate front image exists and is accessible
            2. Extract text from front image using OCR
            3. Extract license number and expiry date from text
            4. Calculate confidence score for extraction quality
            5. Compare extracted values with expected values (if provided)
            6. Check if license is expired
            7. Optionally process back image for additional validation data
            8. Compile all results into validation report
            
        Output:
            dict: Validation result containing:
                - success (bool): Whether OCR operation completed without errors
                - extracted_license_number (str or None): Extracted license number
                - extracted_expiry (str or None): Extracted expiry date
                - extracted_text (str): Full OCR text for admin review
                - confidence_score (float): 0-1 score indicating extraction quality
                - license_match (bool or None): Whether extracted matches expected
                - expiry_match (bool or None): Whether expiry matches expected
                - is_expired (bool or None): Whether license has expired
                - errors (list): Any error messages encountered
        """
        logger.info(f"[OCR] Starting license validation. Front image: {front_image_path}, Back image: {back_image_path}")
        
        validation_result = {
            'success': False,
            'extracted_license_number': None,
            'extracted_expiry': None,
            'extracted_text': None,
            'confidence_score': 0.0,
            'license_match': None,
            'expiry_match': None,
            'is_expired': None,
            'errors': []
        }
        
        # Validate front image exists before processing
        if not front_image_path or not os.path.exists(front_image_path):
            error_message = "License front image not found"
            logger.error(f"[OCR] {error_message}: {front_image_path}")
            validation_result['errors'].append(error_message)
            return validation_result
        
        logger.info(f"[OCR] Front image validated. Beginning text extraction...")
        
        try:
            # Extract text from front image
            front_extracted_text = LicenseOCRService.extract_text(front_image_path)
            
            if not front_extracted_text:
                error_message = "Could not extract text from license image - image may be unclear"
                logger.error(f"[OCR] {error_message}")
                validation_result['errors'].append(error_message)
                return validation_result
            
            logger.info(f"[OCR] Front text extracted successfully: {len(front_extracted_text)} characters")
            validation_result['extracted_text'] = front_extracted_text
            validation_result['success'] = True
            
            # Extract license number from text
            extracted_license = LicenseOCRService.extract_license_number(front_extracted_text)
            validation_result['extracted_license_number'] = extracted_license
            
            # Extract expiry date from text
            extracted_expiry_date = LicenseOCRService.extract_expiry_date(front_extracted_text)
            validation_result['extracted_expiry'] = extracted_expiry_date
            
            # Calculate confidence score based on extraction results
            validation_result['confidence_score'] = LicenseOCRService.calculate_confidence(
                extracted_license, extracted_expiry_date, len(front_extracted_text)
            )
            logger.info(f"[OCR] Validation complete. License: {extracted_license}, Expiry: {extracted_expiry_date}, Confidence: {validation_result['confidence_score']:.2f}")
            
            # Compare extracted license with expected value (if provided)
            if expected_license_number and extracted_license:
                # Normalize both for comparison (remove spaces, hyphens, uppercase)
                normalized_expected = expected_license_number.upper().replace(' ', '').replace('-', '')
                normalized_extracted = extracted_license.upper().replace(' ', '').replace('-', '')
                validation_result['license_match'] = normalized_expected == normalized_extracted
                logger.debug(f"[OCR] License comparison: expected={normalized_expected}, extracted={normalized_extracted}, match={validation_result['license_match']}")
            
            # Compare extracted expiry with expected value (if provided)
            if expected_expiry and extracted_expiry_date:
                try:
                    expected_datetime = LicenseOCRService._parse_date(expected_expiry)
                    extracted_datetime = LicenseOCRService._parse_date(extracted_expiry_date)
                    validation_result['expiry_match'] = expected_datetime == extracted_datetime
                    validation_result['is_expired'] = extracted_datetime < datetime.now()
                    logger.debug(f"[OCR] Expiry comparison: expected={expected_datetime}, extracted={extracted_datetime}, expired={validation_result['is_expired']}")
                except Exception as date_comparison_error:
                    logger.warning(f"[OCR] Could not compare expiry dates: {date_comparison_error}")
            elif extracted_expiry_date:
                # Check if expired even without expected date for validation
                try:
                    extracted_datetime = LicenseOCRService._parse_date(extracted_expiry_date)
                    validation_result['is_expired'] = extracted_datetime < datetime.now()
                    logger.debug(f"[OCR] Expiry check without expected date: expired={validation_result['is_expired']}")
                except Exception as expiry_check_error:
                    logger.warning(f"[OCR] Could not check expiry status: {expiry_check_error}")
            
            # Process back image if provided for additional validation data
            if back_image_path and os.path.exists(back_image_path):
                logger.info(f"[OCR] Processing back image: {back_image_path}")
                back_extracted_text = LicenseOCRService.extract_text(back_image_path)
                if back_extracted_text:
                    # Append back image text to result for admin review
                    validation_result['extracted_text'] += "\n\n--- BACK ---\n" + back_extracted_text
                    logger.info(f"[OCR] Back image processed: {len(back_extracted_text)} characters extracted")
                else:
                    logger.warning("[OCR] Could not extract text from back image")
            
            logger.info(f"[OCR] License validation completed successfully. Errors: {len(validation_result['errors'])}")
            return validation_result
            
        except Exception as validation_error:
            error_message = f"OCR processing error: {str(validation_error)}"
            logger.error(f"[OCR] {error_message}")
            validation_result['errors'].append(error_message)
            return validation_result


# Convenience function for direct use
def ocr_license(front_image_path, back_image_path=None, 
                expected_license_number=None, expected_expiry=None):
    """
    Convenience function to perform OCR on a driver's license image.
    
    Input:
        front_image_path (str): Path to front side of license image
        back_image_path (str, optional): Path to back side of license image  
        expected_license_number (str, optional): Expected license number for verification
        expected_expiry (str, optional): Expected expiry date for verification
        
    Process:
        Delegates to LicenseOCRService.validate_license() for processing.
        Provides a simplified interface for direct OCR calls without instantiating the class.
        
    Output:
        dict: Validation result with extracted data, confidence scores, and match status
        
    Example:
        >>> result = ocr_license('/path/to/license.jpg', expected_license_number='N01123456789')
        >>> print(result['extracted_license_number'])
        'N01123456789'
        >>> print(result['confidence_score'])
        0.9
    """
    logger.info(f"[OCR] Convenience function called for: {front_image_path}")
    return LicenseOCRService.validate_license(
        front_image_path=front_image_path,
        back_image_path=back_image_path,
        expected_license_number=expected_license_number,
        expected_expiry=expected_expiry
    )
