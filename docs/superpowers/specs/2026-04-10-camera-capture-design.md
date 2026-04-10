# Real-Time Camera Capture for Driver's License Verification

## Overview

Add a WebRTC/getUserMedia camera capture option to the verification page's four image upload fields (license front, license back, government ID, selfie). Users can choose between camera capture and file upload per field. The backend decodes Base64 image data from camera captures into physical files that feed into the existing OCR pipeline unchanged.

## Approach

Per-field inline camera widget (Approach A). Each image field gets its own toggle between camera and file upload, with the camera preview appearing inline below the field.

## Frontend — Camera Widget

Each of the four image fields gets:
- Toggle row with "Use Camera" and "Upload File" buttons
- Camera mode: `<video>` preview, "Capture" button, post-capture `<img>` preview with "Retake" button
- File mode: existing `<input type="file">`
- Hidden `<canvas>` per field (for frame capture)
- Hidden `<input type="hidden">` per field to store Base64 data (e.g., `license_front_base64`)

Camera facing mode: rear (`environment`) for license/ID fields, front (`user`) for selfie field.

## Frontend — Form Submission

Update the existing `fetch()` handler to include Base64 data:
- For each image field: if the Base64 hidden input has a value, add it to `FormData` as `license_front_base64`, `license_back_base64`, `id_card_image_base64`, or `selfie_image_base64`
- File inputs are still sent as before; backend checks Base64 first, falls back to file

## Backend — Route Update

In `submit_verification()` (`user_bp.py`):
- For each image field, check `request.form` for a `*_base64` field
- If present: strip `data:image/jpeg;base64,` prefix, decode via `base64.b64decode()`, write as JPEG to uploads folder using the same naming convention (`user_{id}_{type}_{timestamp}.jpg`)
- If absent: fall back to `request.files` (existing behavior)
- Rest of pipeline (OCR, DB insert) remains unchanged — it only consumes file paths

## Styling

- Camera preview: max-width 100%, maintained aspect ratio
- Buttons: existing `.btn-primary` / `.btn-secondary` styles
- Toggle: pill-style row with active state
- Responsive: video/canvas scale down, buttons stack vertically below 768px
- All CSS/JS inline in `verification.html` (matching existing pattern)

## Files to Modify

1. `MyFlaskApp/user/templates/verification.html` — camera UI, CSS, JS
2. `MyFlaskApp/user/user_bp.py` — Base64 decode logic in `submit_verification()`

No new files required. No database changes.