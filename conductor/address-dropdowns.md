# Implementation Plan - Philippine Address Cascading Dropdowns

Implement a user-friendly address selection system using cascading dropdowns for Region, Province, City, and Barangay, powered by the PSGC Cloud API.

## 1. Database Schema Update

Add `province` and `barangay` columns to the `users` table to store the structured address data.

**SQL Changes:**
```sql
ALTER TABLE users ADD COLUMN province VARCHAR(100) AFTER city;
ALTER TABLE users ADD COLUMN barangay VARCHAR(100) AFTER province;
```

## 2. Frontend Utility Script

Create `MyFlaskApp/static/js/ph-address-selector.js` to handle dynamic data fetching and dropdown population.

**Key Features:**
- Fetch Regions, Provinces, Cities, and Barangays from `https://psgc.cloud/api`.
- Reusable function `initPhAddressSelector` that takes element IDs as configuration.
- Cascading logic: Changing a parent dropdown resets and repopulates child dropdowns.

## 3. User Profile Update

### Template Changes (`MyFlaskApp/user/templates/profile.html`)
- Replace the "State" text input with a "Region" `<select>`.
- Add a "Province" `<select>`.
- Replace the "City" text input with a "City/Municipality" `<select>`.
- Add a "Barangay" `<select>`.
- Keep the "Address" `<textarea>` for street/house number information.

### Backend Changes (`MyFlaskApp/user/user_bp.py`)
- Update the `profile` route's `POST` handler to extract `region` (mapping to `state`), `province`, `city`, and `barangay`.
- Update the `UPDATE users` SQL statement to include the new columns.

## 4. Booking Page Update (Custom Address)

### Template Changes (`MyFlaskApp/user/templates/book_vehicle.html`)
- In the "Custom Address" sections (Pickup/Return), replace the single text input with the same cascading dropdown structure.
- Add a text input for the specific street address.

### Script Changes
- Update the form submission logic to concatenate the dropdown values into the `custom_pickup_address` and `custom_return_address` fields before sending to the backend. This avoids changing the `bookings` table schema.

## 5. Verification & Testing
- Register a new user and set their address via the profile page.
- Verify that selecting a Region correctly populates the corresponding Provinces.
- Verify that data is correctly saved and retrieved from the database.
- Test the custom address booking flow with the new dropdowns.
