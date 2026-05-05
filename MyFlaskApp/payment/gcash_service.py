import requests
import json
from datetime import datetime
import base64
import os

from MyFlaskApp.payment.config import PAYMONGO_SECRET_KEY, PAYMONGO_MODE

class GCashService:

    def __init__(self):
        self.secret_key = PAYMONGO_SECRET_KEY
        self.mode = PAYMONGO_MODE
        # PayMongo uses same endpoint for both sandbox and live - determined by API keys
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
                        # Removed {CHECKOUT_SESSION_ID} placeholder - PayMongo doesn't auto-replace it
                        # Instead, we verify payment by checking the checkout_session_id we store in payments table
                        "success_url": f"{base_url}/payment/success?booking_id={booking_id}",
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
                    'raw_response': data,
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
    
    def get_payment_intent_status(self, checkout_session_id):
        """Get payment intent status from checkout session - more reliable than checkout status"""
        try:
            # First get the checkout session to find the payment intent ID
            response = requests.get(
                f"{self.base_url}/checkout_sessions/{checkout_session_id}",
                headers=self.get_auth_header()
            )
            
            if response.status_code != 200:
                print(f"[PayMongo] Error getting checkout session: {response.status_code}")
                return {'success': False, 'message': 'Failed to get checkout session'}
            
            data = response.json()
            checkout_attrs = data['data']['attributes']
            
            # Get payment_intent from checkout session
            payment_intent = checkout_attrs.get('payment_intent', {})
            if not payment_intent:
                print(f"[PayMongo] No payment_intent in checkout session")
                return {'success': False, 'message': 'No payment intent found'}
            
            payment_intent_id = payment_intent.get('id')
            print(f"[PayMongo] Found payment_intent: {payment_intent_id}")
            
            # Now get the payment intent status
            pi_response = requests.get(
                f"{self.base_url}/payment_intents/{payment_intent_id}",
                headers=self.get_auth_header()
            )
            
            if pi_response.status_code == 200:
                pi_data = pi_response.json()
                pi_attrs = pi_data['data']['attributes']
                status = pi_attrs.get('status')
                print(f"[PayMongo] Payment intent status: {status}")
                
                # Status can be: 'succeeded', 'processing', 'awaiting_payment_method', 'canceled'
                paid = status == 'succeeded'
                
                return {
                    'success': True,
                    'payment_intent_id': payment_intent_id,
                    'status': status,
                    'paid': paid,
                    'raw_status': pi_attrs
                }
            else:
                print(f"[PayMongo] Error getting payment intent: {pi_response.status_code}")
                return {'success': False, 'message': 'Failed to get payment intent'}
                
        except Exception as e:
            print(f"[PayMongo] Exception in get_payment_intent_status: {e}")
            return {'success': False, 'message': str(e)}