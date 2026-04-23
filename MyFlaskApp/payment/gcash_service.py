import requests
import json
from datetime import datetime
import base64
import os

from MyFlaskApp.payment.config import PAYMONGO_SECRET_KEY

class GCashService:

    def __init__(self):
        self.secret_key = PAYMONGO_SECRET_KEY
        self.base_url = 'https://api.paymongo.com/v1'
        
    def get_auth_header(self):
        """Get authentication header for PayMongo"""
        auth_string = base64.b64encode(f"{self.secret_key}:".encode()).decode()
        return {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/json'
        }
    
    def create_gcash_payment(self, booking_id, amount, customer_name, customer_email, booking_reference):
        """Create GCash Checkout Session"""
        try:
            # Get base URL from config or environment
            base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
            
            amount_in_centavos = int(amount * 100)
            
            payload = {
                "data": {
                    "attributes": {
                        "send_email_receipt": False,
                        "show_description": True,
                        "show_line_items": True,
                        "description": f"Car Rental Booking #{booking_reference}",
                        "payment_method_types": ["gcash", "paymaya", "card"],
                        "line_items": [
                            {
                                "currency": "PHP",
                                "amount": amount_in_centavos,
                                "description": f"Car Rental: {booking_reference}",
                                "name": "Car Rental Payment",
                                "quantity": 1
                            }
                        ],
                        # FIXED: Include session_id in success URL
                        "success_url": f"{base_url}/payment/success?booking_id={booking_id}&session_id={{CHECKOUT_SESSION_ID}}",
                        "failed_url": f"{base_url}/payment/failed?booking_id={booking_id}",
                        "metadata": {
                            "booking_id": str(booking_id),
                            "customer_name": customer_name,
                            "customer_email": customer_email
                        }
                    }
                }
            }
        # ... rest of the function
            
            # Make API request to create checkout session
            response = requests.post(
                f"{self.base_url}/checkout_sessions",
                headers=self.get_auth_header(),
                json=payload
            )
            
            print(f"PayMongo Response Status: {response.status_code}")
            print(f"PayMongo Response Body: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                checkout_session_id = data['data']['id']
                checkout_url = data['data']['attributes']['checkout_url']
                
                return {
                    'success': True,
                    'checkout_session_id': checkout_session_id,
                    'checkout_url': checkout_url,
                    'message': 'Checkout session created successfully'
                }
            else:
                error_message = "Unknown error"
                try:
                    error_data = response.json()
                    if 'errors' in error_data and len(error_data['errors']) > 0:
                        error_message = error_data['errors'][0].get('detail', str(error_data))
                except:
                    error_message = response.text
                    
                return {
                    'success': False,
                    'message': f"PayMongo API Error: {error_message}"
                }
                
        except Exception as e:
            print(f"Exception in create_gcash_payment: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def retrieve_payment_status(self, checkout_session_id):
        """Retrieve checkout session payment status"""
        try:
            response = requests.get(
                f"{self.base_url}/checkout_sessions/{checkout_session_id}",
                headers=self.get_auth_header()
            )
            
            if response.status_code == 200:
                data = response.json()
                payment_status = data['data']['attributes'].get('payment_status')
                checkout_status = data['data']['attributes'].get('status')
                print(f"[PayMongo] Session status: payment_status={payment_status}, checkout_status={checkout_status}")
                paid = payment_status == 'paid'
                return {
                    'success': True,
                    'payment_status': payment_status,
                    'checkout_status': checkout_status,
                    'paid': paid
                }
            else:
                print(f"[PayMongo] Error response: {response.status_code} - {response.text}")
                return {'success': False, 'message': 'Failed to retrieve payment status'}
                
        except Exception as e:
            return {'success': False, 'message': str(e)}