import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PayMongo API Keys (Primary Payment Method)
PAYMONGO_SECRET_KEY = os.environ.get('PAYMONGO_SECRET_KEY', '')
PAYMONGO_PUBLIC_KEY = os.environ.get('PAYMONGO_PUBLIC_KEY', '')
PAYMONGO_MODE = os.environ.get('PAYMONGO_MODE', 'sandbox')

# PayPal API Keys
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET', '')
PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'sandbox')

# Payment Settings
CURRENCY = 'php'  # Philippine Peso
TAX_RATE = 0.12  # 12% VAT in PH
ADVANCE_PAYMENT_PERCENTAGE = 30
