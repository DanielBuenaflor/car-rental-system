from flask import render_template, current_app
from flask_mail import Message
from MyFlaskApp import mail

class EmailService:

    @staticmethod
    def send_email(to, subject, template, **kwargs):
        """Send email using template from email/templates/ folder"""
        try:
            msg = Message(
                subject=subject,
                recipients=[to],
                html=render_template(f'email/templates/{template}.html', **kwargs),
                sender=current_app.config['MAIL_DEFAULT_SENDER']
            )
            mail.send(msg)
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to}: {str(e)}")
            return False

    @staticmethod
    def send_verification_approved(user):
        """Send email when verification is approved"""
        return EmailService.send_email(
            to=user['email'],
            subject="Identity Verification Approved - CarRental Pro",
            template="verification_approved",
            username=user['first_name']
        )

    @staticmethod
    def send_verification_rejected(user, reason):
        """Send email when verification is rejected"""
        return EmailService.send_email(
            to=user['email'],
            subject="Identity Verification Update - CarRental Pro",
            template="verification_rejected",
            username=user['first_name'],
            reason=reason
        )

    @staticmethod
    def send_booking_confirmation(user, booking, vehicle):
        """Send booking confirmation email"""
        return EmailService.send_email(
            to=user['email'],
            subject=f"Booking Confirmed - #{booking['booking_reference']}",
            template="booking_confirmation",
            username=user['first_name'],
            booking=booking,
            vehicle=vehicle
        )

    @staticmethod
    def send_payment_receipt(user, payment, booking, vehicle):
        """Send payment receipt email"""
        return EmailService.send_email(
            to=user['email'],
            subject=f"Payment Receipt - #{payment['payment_reference']}",
            template="payment_receipt",
            username=user['first_name'],
            payment=payment,
            booking=booking,
            vehicle=vehicle
        )

    @staticmethod
    def send_invoice(user, invoice, booking, vehicle):
        """Send invoice email"""
        return EmailService.send_email(
            to=user['email'],
            subject=f"Invoice - #{invoice['invoice_number']}",
            template="invoice",
            username=user['first_name'],
            invoice=invoice,
            booking=booking,
            vehicle=vehicle
        )

    @staticmethod
    def send_fine_notice(user, fine, booking, vehicle):
        """Send late return fine notice"""
        return EmailService.send_email(
            to=user['email'],
            subject=f"Late Return Fee Notice - #{booking['booking_reference']}",
            template="fine_notice",
            username=user['first_name'],
            fine=fine,
            booking=booking,
            vehicle=vehicle
        )

    @staticmethod
    def send_rental_reminder(user, booking, vehicle):
        """Send rental reminder (24 hours before pickup)"""
        return EmailService.send_email(
            to=user['email'],
            subject=f"Reminder: Your Rental Starts Tomorrow - #{booking['booking_reference']}",
            template="rental_reminder",
            username=user['first_name'],
            booking=booking,
            vehicle=vehicle
        )

    @staticmethod
    def send_newsletter(subscriber, subject, content):
        """Send newsletter to subscriber"""
        return EmailService.send_email(
            to=subscriber['email'],
            subject=subject,
            template="newsletter",
            username=subscriber.get('name', 'Valued Customer'),
            newsletter_subject=subject,
            content=content,
            unsubscribe_link=f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/unsubscribe?email={subscriber['email']}"
        )
