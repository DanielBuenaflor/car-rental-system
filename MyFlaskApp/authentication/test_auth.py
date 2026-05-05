# ============================================================================
# TESTS FOR MyFlaskApp/authentication/auth.py
# ============================================================================
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Pre-load heavy/optional dependencies as stubs so create_app() doesn't
# fail when they are not installed in the test environment.
for _mod in ("cv2", "pytesseract", "PIL"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from MyFlaskApp import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app():
    """Create a Flask app configured for testing."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SERVER_NAME"] = "localhost"
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database connection, cursor, and get_db_connection."""
    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.commit.return_value = None
    conn.rollback.return_value = None
    return conn, cursor


@pytest.fixture
def mock_mail_send():
    """Patch mail.send so no real emails are sent."""
    with patch("MyFlaskApp.authentication.auth.mail.send") as mock_send:
        yield mock_send


# ---------------------------------------------------------------------------
# Helper: build a fake user row (dictionary cursor style)
# ---------------------------------------------------------------------------
def make_user_row(
    id=1,
    first_name="John",
    last_name="Doe",
    email="john@example.com",
    password=None,      # set below if needed
    role="user",
    is_active=1,
    is_email_verified=1,
):
    from werkzeug.security import generate_password_hash
    return {
        "id": id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password": password or generate_password_hash("Password1"),
        "role": role,
        "is_active": is_active,
        "is_email_verified": is_email_verified,
    }


# ===========================================================================
# 1.  HELPER FUNCTION TESTS
# ===========================================================================
class TestIsValidEmail:
    def test_valid_email(self):
        from MyFlaskApp.authentication.auth import is_valid_email
        assert is_valid_email("user@example.com") is True

    def test_invalid_no_at(self):
        from MyFlaskApp.authentication.auth import is_valid_email
        assert is_valid_email("userexample.com") is False

    def test_invalid_no_domain(self):
        from MyFlaskApp.authentication.auth import is_valid_email
        assert is_valid_email("user@.com") is False

    def test_empty_string(self):
        from MyFlaskApp.authentication.auth import is_valid_email
        assert is_valid_email("") is False

    def test_invalid_special_chars(self):
        from MyFlaskApp.authentication.auth import is_valid_email
        assert is_valid_email("user @example.com") is False


class TestGenerateOtp:
    def test_returns_six_digits(self):
        from MyFlaskApp.authentication.auth import generate_otp
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()

    def test_generates_different_codes(self):
        from MyFlaskApp.authentication.auth import generate_otp
        # Extremely unlikely to get 10 identical 6-digit codes
        codes = {generate_otp() for _ in range(10)}
        assert len(codes) > 1


# ===========================================================================
# 2.  LOGIN TESTS
# ===========================================================================
class TestHandleLogin:
    """Tests for the handle_login handler via POST /login (JSON)."""

    def test_login_success(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        user = make_user_row()
        cursor.fetchone.return_value = user

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/login", json={
                "email": "john@example.com",
                "password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is True
        assert data["message"] == "Login successful!"

    def test_login_missing_fields(self, client, mock_db, mock_mail_send):
        resp = client.post("/login", json={"email": "", "password": ""})
        data = resp.get_json()
        assert data["success"] is False
        assert "required" in data["message"].lower()

    def test_login_user_not_found(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/login", json={
                "email": "nobody@example.com",
                "password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is False
        assert "invalid" in data["message"].lower()

    def test_login_wrong_password(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = make_user_row()

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/login", json={
                "email": "john@example.com",
                "password": "WrongPass1",
            })

        data = resp.get_json()
        assert data["success"] is False
        assert "invalid" in data["message"].lower()

    def test_login_unverified_email(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = make_user_row(is_email_verified=0)

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/login", json={
                "email": "john@example.com",
                "password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is False
        assert data.get("needs_verification") is True

    def test_login_deactivated_account(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = make_user_row(is_active=0)

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/login", json={
                "email": "john@example.com",
                "password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is False
        assert "deactivated" in data["message"].lower()

    def test_login_admin_redirect(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = make_user_row(role="admin")

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/login", json={
                "email": "john@example.com",
                "password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is True
        assert "admin" in data["redirect"]

    def test_login_db_connection_error(self, client, mock_mail_send):
        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=None):
            resp = client.post("/login", json={
                "email": "john@example.com",
                "password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is False


# ===========================================================================
# 3.  REGISTRATION TESTS
# ===========================================================================
class TestHandleSignup:
    """Tests for the handle_signup handler via POST /register (JSON)."""

    def test_register_success(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        # No existing user → fetchone returns None
        cursor.fetchone.return_value = None
        cursor.lastrowid = 42

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/register", json={
                "firstname": "Jane",
                "lastname": "Smith",
                "email": "jane@example.com",
                "contact_number": "09171234567",
                "password": "Password1",
                "confirm_password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is True
        assert data.get("needs_verification") is True

    def test_register_missing_fields(self, client, mock_db, mock_mail_send):
        resp = client.post("/register", json={
            "firstname": "",
            "lastname": "",
            "email": "",
            "contact_number": "",
            "password": "",
        })
        data = resp.get_json()
        assert data["success"] is False
        assert "required" in data["message"].lower()

    def test_register_password_mismatch(self, client, mock_db, mock_mail_send):
        resp = client.post("/register", json={
            "firstname": "Jane",
            "lastname": "Smith",
            "email": "jane@example.com",
            "contact_number": "09171234567",
            "password": "Password1",
            "confirm_password": "Different1",
        })
        data = resp.get_json()
        assert data["success"] is False
        assert "match" in data["message"].lower()

    def test_register_invalid_email(self, client, mock_db, mock_mail_send):
        resp = client.post("/register", json={
            "firstname": "Jane",
            "lastname": "Smith",
            "email": "not-an-email",
            "contact_number": "09171234567",
            "password": "Password1",
            "confirm_password": "Password1",
        })
        data = resp.get_json()
        assert data["success"] is False
        assert "email" in data["message"].lower()

    def test_register_short_password(self, client, mock_db, mock_mail_send):
        resp = client.post("/register", json={
            "firstname": "Jane",
            "lastname": "Smith",
            "email": "jane@example.com",
            "contact_number": "09171234567",
            "password": "Ab1",
            "confirm_password": "Ab1",
        })
        data = resp.get_json()
        assert data["success"] is False
        assert "8 characters" in data["message"]

    def test_register_weak_password(self, client, mock_db, mock_mail_send):
        resp = client.post("/register", json={
            "firstname": "Jane",
            "lastname": "Smith",
            "email": "jane@example.com",
            "contact_number": "09171234567",
            "password": "abcdefgh",
            "confirm_password": "abcdefgh",
        })
        data = resp.get_json()
        assert data["success"] is False
        assert "uppercase" in data["message"].lower()

    def test_register_existing_verified_email(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = {"id": 1, "first_name": "Jane", "is_email_verified": 1}

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/register", json={
                "firstname": "Jane",
                "lastname": "Smith",
                "email": "jane@example.com",
                "contact_number": "09171234567",
                "password": "Password1",
                "confirm_password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is False
        assert "already registered" in data["message"].lower()

    def test_register_existing_unverified_email(self, client, mock_db, mock_mail_send):
        """Re-registering with an unverified email should resend OTP."""
        conn, cursor = mock_db
        cursor.fetchone.return_value = {"id": 5, "first_name": "Jane", "is_email_verified": 0}

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/register", json={
                "firstname": "Jane",
                "lastname": "Smith",
                "email": "jane@example.com",
                "contact_number": "09171234567",
                "password": "Password1",
                "confirm_password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is True
        assert data.get("needs_verification") is True
        assert data.get("existing_unverified") is True

    def test_register_email_send_failure_rolls_back(self, client, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        cursor.lastrowid = 42

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn), \
             patch("MyFlaskApp.authentication.auth.send_otp_email", return_value=False):
            resp = client.post("/register", json={
                "firstname": "Jane",
                "lastname": "Smith",
                "email": "jane@example.com",
                "contact_number": "09171234567",
                "password": "Password1",
                "confirm_password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is False
        conn.rollback.assert_called_once()

    def test_register_db_connection_error(self, client, mock_mail_send):
        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=None):
            resp = client.post("/register", json={
                "firstname": "Jane",
                "lastname": "Smith",
                "email": "jane@example.com",
                "contact_number": "09171234567",
                "password": "Password1",
                "confirm_password": "Password1",
            })

        data = resp.get_json()
        assert data["success"] is False


# ===========================================================================
# 4.  OTP VERIFICATION TESTS
# ===========================================================================
class TestVerifyOtp:
    def test_verify_otp_success(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        now = datetime.now()
        otp_record = {
            "id": 1,
            "otp_code": "123456",
            "expires_at": now + timedelta(minutes=5),
            "is_verified": False,
        }
        user_row = {
            "id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "role": "user",
            "is_active": 1,
        }
        # fetchone called twice: first for OTP, then for user
        cursor.fetchone.side_effect = [otp_record, user_row]

        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/verify-otp", json={"otp_code": "123456"})

        data = resp.get_json()
        assert data["success"] is True
        assert "verified" in data["message"].lower()

    def test_verify_otp_expired(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        otp_record = {
            "id": 1,
            "otp_code": "123456",
            "expires_at": datetime.now() - timedelta(minutes=1),
            "is_verified": False,
        }
        cursor.fetchone.return_value = otp_record

        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/verify-otp", json={"otp_code": "123456"})

        data = resp.get_json()
        assert data["success"] is False
        assert "expired" in data["message"].lower()

    def test_verify_otp_wrong_code(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        otp_record = {
            "id": 1,
            "otp_code": "123456",
            "expires_at": datetime.now() + timedelta(minutes=5),
            "is_verified": False,
        }
        cursor.fetchone.return_value = otp_record

        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/verify-otp", json={"otp_code": "000000"})

        data = resp.get_json()
        assert data["success"] is False
        assert "invalid" in data["message"].lower()

    def test_verify_otp_no_pending(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None

        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/verify-otp", json={"otp_code": "123456"})

        data = resp.get_json()
        assert data["success"] is False
        assert "no pending" in data["message"].lower()

    def test_verify_otp_missing_session(self, client, mock_db, mock_mail_send):
        resp = client.post("/verify-otp", json={"otp_code": "123456"})
        data = resp.get_json()
        assert data["success"] is False

    def test_verify_otp_empty_code(self, client, mock_mail_send):
        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        resp = client.post("/verify-otp", json={"otp_code": ""})
        data = resp.get_json()
        assert data["success"] is False

    def test_verify_otp_db_error(self, client, mock_mail_send):
        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=None):
            resp = client.post("/verify-otp", json={"otp_code": "123456"})

        data = resp.get_json()
        assert data["success"] is False


# ===========================================================================
# 5.  RESEND OTP TESTS
# ===========================================================================
class TestResendOtp:
    def test_resend_otp_success(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        # No rate-limit record, user exists
        cursor.fetchone.side_effect = [
            None,                           # rate limit check
            {"first_name": "John", "email": "john@example.com"},  # user lookup
        ]

        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn), \
             patch("MyFlaskApp.authentication.auth.send_otp_email", return_value=True):
            resp = client.post("/resend-otp", json={"email": "john@example.com"})

        data = resp.get_json()
        assert data["success"] is True

    def test_resend_otp_rate_limited_too_many(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = {
            "last_sent": datetime.now(),
            "attempts": 3,
        }

        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/resend-otp", json={"email": "john@example.com"})

        data = resp.get_json()
        assert data["success"] is False
        assert "too many" in data["message"].lower()

    def test_resend_otp_rate_limited_cooldown(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = {
            "last_sent": datetime.now(),
            "attempts": 1,
        }

        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.post("/resend-otp", json={"email": "john@example.com"})

        data = resp.get_json()
        assert data["success"] is False
        assert "60 seconds" in data["message"]

    def test_resend_otp_missing_session(self, client, mock_db, mock_mail_send):
        resp = client.post("/resend-otp", json={"email": "john@example.com"})
        data = resp.get_json()
        assert data["success"] is False

    def test_resend_otp_email_send_failure(self, client, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.side_effect = [
            None,
            {"first_name": "John", "email": "john@example.com"},
        ]

        with client.session_transaction() as sess:
            sess["temp_user_id"] = 1

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn), \
             patch("MyFlaskApp.authentication.auth.send_otp_email", return_value=False):
            resp = client.post("/resend-otp", json={"email": "john@example.com"})

        data = resp.get_json()
        assert data["success"] is False


# ===========================================================================
# 6.  LOGOUT TESTS
# ===========================================================================
class TestLogout:
    def test_logout_post(self, client, mock_mail_send):
        with client.session_transaction() as sess:
            sess["loggedin"] = True
            sess["user_id"] = 1

        resp = client.post("/logout")
        data = resp.get_json()
        assert data["success"] is True

    def test_logout_get_redirects(self, client, mock_mail_send):
        resp = client.get("/logout")
        assert resp.status_code == 302


# ===========================================================================
# 7.  CHECK EMAIL AVAILABILITY
# ===========================================================================
class TestCheckEmail:
    def test_email_available(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.get("/check-email/jane@example.com")

        data = resp.get_json()
        assert data["available"] is True

    def test_email_already_registered(self, client, mock_db, mock_mail_send):
        conn, cursor = mock_db
        cursor.fetchone.return_value = {"id": 1}

        with patch("MyFlaskApp.authentication.auth.get_db_connection", return_value=conn):
            resp = client.get("/check-email/jane@example.com")

        data = resp.get_json()
        assert data["available"] is False

    def test_email_invalid_format(self, client, mock_db, mock_mail_send):
        resp = client.get("/check-email/not-an-email")
        data = resp.get_json()
        assert data["available"] is False


# ===========================================================================
# 8.  SEND OTP EMAIL (unit test with mocked Flask-Mail)
# ===========================================================================
class TestSendOtpEmail:
    def test_send_success(self, app, mock_mail_send):
        with app.app_context():
            from MyFlaskApp.authentication.auth import send_otp_email
            result = send_otp_email("user@example.com", "123456", "TestUser")
            assert result is True
            mock_mail_send.assert_called_once()

    def test_send_fails_without_mail_config(self, app, mock_mail_send):
        with app.app_context():
            app.config["MAIL_USERNAME"] = None
            app.config["MAIL_PASSWORD"] = None
            from MyFlaskApp.authentication.auth import send_otp_email
            result = send_otp_email("user@example.com", "123456", "TestUser")
            assert result is False
            mock_mail_send.assert_not_called()

    def test_send_fails_on_exception(self, app, mock_mail_send):
        mock_mail_send.side_effect = Exception("SMTP error")
        with app.app_context():
            from MyFlaskApp.authentication.auth import send_otp_email
            result = send_otp_email("user@example.com", "123456", "TestUser")
            assert result is False