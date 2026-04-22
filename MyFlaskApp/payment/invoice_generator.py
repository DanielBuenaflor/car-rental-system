from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime


class InvoiceGenerator:

    @staticmethod
    def generate_invoice(booking, user, vehicle, payment=None):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0f3b6f'),
            spaceAfter=6,
            alignment=TA_CENTER
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#0f3b6f'),
            spaceBefore=20,
            spaceAfter=10
        )
        
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        
        elements.append(Paragraph("CarRental Pro", title_style))
        elements.append(Paragraph("123 Rental Street, Manila, Philippines 1000", header_style))
        elements.append(Paragraph("Email: info@carrentalpro.com | Tel: +63 912 345 6789", header_style))
        elements.append(Spacer(1, 20))
        
        invoice_title = ParagraphStyle(
            'InvoiceTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#0f3b6f'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        elements.append(Paragraph("INVOICE", invoice_title))
        
        invoice_date = datetime.now().strftime("%B %d, %Y")
        invoice_data = [
            ["Invoice Number:", f"INV-{booking.get('booking_reference', 'N/A')}", "Date:", invoice_date],
            ["Booking Reference:", booking.get('booking_reference', 'N/A'), "Status:", "PAID"],
        ]
        
        invoice_table = Table(invoice_data, colWidths=[1.5*inch, 2*inch, 1*inch, 2*inch])
        invoice_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('ALIGN', (3, 0), (3, -1), 'LEFT'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(invoice_table)
        elements.append(Spacer(1, 30))
        
        elements.append(Paragraph("Bill To:", section_style))
        user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        bill_to_data = [
            ["Name:", user_name or "N/A"],
            ["Email:", user.get('email', 'N/A')],
        ]
        bill_to_table = Table(bill_to_data, colWidths=[1.5*inch, 4.5*inch])
        bill_to_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(bill_to_table)
        elements.append(Spacer(1, 20))
        
        elements.append(Paragraph("Vehicle Details:", section_style))
        vehicle_name = f"{vehicle.get('brand_name', '')} {vehicle.get('model', '')}".strip()
        vehicle_data = [
            ["Vehicle:", vehicle_name or "N/A"],
            ["License Plate:", vehicle.get('license_plate', 'N/A')],
        ]
        vehicle_table = Table(vehicle_data, colWidths=[1.5*inch, 4.5*inch])
        vehicle_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(vehicle_table)
        elements.append(Spacer(1, 20))
        
        elements.append(Paragraph("Booking Details:", section_style))
        
        start_date = booking.get('start_date')
        end_date = booking.get('end_date')
        
        if hasattr(start_date, 'strftime'):
            start_str = start_date.strftime("%B %d, %Y")
        else:
            start_str = str(start_date) if start_date else "N/A"
            
        if hasattr(end_date, 'strftime'):
            end_str = end_date.strftime("%B %d, %Y")
        else:
            end_str = str(end_date) if end_date else "N/A"
        
        booking_data = [
            ["Pickup Date:", start_str, "Return Date:", end_str],
            ["Pickup Location:", booking.get('pickup_location', 'N/A')],
            ["Return Location:", booking.get('return_location', 'N/A')],
            ["Rental Days:", f"{booking.get('rental_days', 0)} days"],
        ]
        booking_table = Table(booking_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
        booking_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('SPAN', (1, 1), (3, 1)),
            ('SPAN', (1, 2), (3, 2)),
        ]))
        elements.append(booking_table)
        elements.append(Spacer(1, 30))
        
        elements.append(Paragraph("Payment Summary:", section_style))
        
        subtotal = float(booking.get('subtotal', 0))
        tax_amount = float(booking.get('tax_amount', 0))
        security_deposit = float(booking.get('security_deposit', 0))
        total_amount = float(booking.get('total_amount', 0))
        
        payment_data = [
            ["Description", "Amount"],
            ["Subtotal (Rental)", f"₱{subtotal:,.2f}"],
            ["Tax (10%)", f"₱{tax_amount:,.2f}"],
            ["Security Deposit (Refundable)", f"₱{security_deposit:,.2f}"],
        ]
        
        payment_table = Table(payment_data, colWidths=[4*inch, 2*inch])
        payment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f3b6f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(payment_table)
        elements.append(Spacer(1, 10))
        
        total_data = [["Total Amount Paid:", f"₱{total_amount:,.2f}"]]
        total_table = Table(total_data, colWidths=[4*inch, 2*inch])
        total_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0f3b6f')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(total_table)
        elements.append(Spacer(1, 50))
        
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#0f3b6f'),
            alignment=TA_CENTER,
            spaceBefore=30
        )
        elements.append(Paragraph("Thank you for choosing CarRental Pro!", footer_style))
        elements.append(Spacer(1, 10))
        
        thank_you_style = ParagraphStyle(
            'ThankYou',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("We hope to serve you again soon!", thank_you_style))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer