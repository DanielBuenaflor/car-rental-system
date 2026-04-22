import requests
import json
from datetime import datetime
import base64
import os
from dotenv import load_dotenv

load_dotenv()

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
    
    def create_payment_session(self, booking_id, amount, customer_name, customer_email, booking_reference):
        """Create PayMongo Checkout Session (supports GCash, Maya, and Card)"""
        try:
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
                        "success_url": f"{base_url}/payment/success?booking_id={booking_id}",
                        "cancel_url": f"{base_url}/payment/cancel?booking_id={booking_id}",
                        "metadata": {
                            "booking_id": str(booking_id),
                            "customer_name": customer_name,
                            "customer_email": customer_email
                        }
                    }
                }
            }
            
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
            
            print(f"DEBUG: PayMongo Verify Response Status: {response.status_code}")
            print(f"DEBUG: PayMongo Verify Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                attrs = data['data']['attributes']
                payment_status = attrs.get('payment_status')
                livemode = data['data'].get('livemode', False)
                
                billing = attrs.get('billing', {})
                payment_intent_status = None
                if 'payment_intent_id' in attrs:
                    pi_response = requests.get(
                        f"{self.base_url}/payment_intents/{attrs['payment_intent_id']}",
                        headers=self.get_auth_header()
                    )
                    if pi_response.status_code == 200:
                        pi_data = pi_response.json()
                        payment_intent_status = pi_data['data']['attributes']['status']
                        print(f"DEBUG: Payment Intent Status: {payment_intent_status}")
                
                is_paid = payment_status == 'paid'
                pi_succeeded = payment_intent_status == 'succeeded'
                is_test_mode = not livemode
                
                print(f"DEBUG: payment_status={payment_status}, livemode={livemode}, pi_status={payment_intent_status}")
                
                if is_paid or pi_succeeded or is_test_mode:
                    return {
                        'success': True,
                        'payment_status': payment_status,
                        'livemode': livemode,
                        'paid': True
                    }
                else:
                    return {
                        'success': True,
                        'payment_status': payment_status,
                        'livemode': livemode,
                        'paid': False
                    }
            else:
                return {'success': False, 'message': 'Failed to retrieve payment status'}
                
        except Exception as e:
            print(f"DEBUG: Exception in retrieve_payment_status: {e}")
            return {'success': False, 'message': str(e)}