sender = "thu900hockey@gmail.com"
receiver = "thu900hockey@gmail.com"
DAYS = 4 # number of days to look back for e-transfers

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import os

def read_etransfer_emails():
    """Read emails from the configured lookback period and extract e-transfer information"""
    
    password = os.environ.get('EMAIL_PASSWORD')
    
    # Connect to Gmail
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(sender, password)
    
    # Select inbox
    mail.select("inbox")
    
    # Calculate date to go back to DAYS 
    lookback_date = datetime.now() - timedelta(days=DAYS)
    date_string = lookback_date.strftime("%d-%b-%Y")
    
    # Search for emails
    status, messages = mail.search(None, f'(SINCE {date_string})')
    
    email_ids = messages[0].split()
    
    # List to store payment information
    payments = []
    
    for email_id in email_ids:
        # Fetch the email
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        # Parse email
        msg = email.message_from_bytes(msg_data[0][1])
        
        # Get subject
        subject_header = msg["Subject"]
        if subject_header:
            # Decode subject if it's encoded
            decoded_parts = decode_header(subject_header)
            subject = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    subject += part.decode(encoding or 'utf-8')
                else:
                    subject += part
            
            # Remove line breaks from subject (long subjects can have \r\n)
            # Replace any sequence of whitespace with a single space
            subject = re.sub(r'\s+', ' ', subject).strip()
            
            # Check if this is an Interac e-Transfer email
            # Pattern: "Interac e-Transfer: You've received $25.00 from EVAN MORGAN and it has been automatically deposited."
            pattern = r"Interac e-Transfer.*received \$([0-9]+\.[0-9]{2}) from (.+?) and it has been"
            match = re.search(pattern, subject, re.IGNORECASE)
            
            if match:
                amount = float(match.group(1))
                name = match.group(2).strip()
                
                # Get and parse email date
                date_header = msg.get("Date")
                try:
                    # Parse the RFC 2822 date format
                    email_date = parsedate_to_datetime(date_header)
                    # Convert to PST
                    pst_date = email_date.astimezone(ZoneInfo('America/Los_Angeles'))
                    date_formatted = pst_date.strftime('%b %d, %I:%M %p')
                    date_obj = pst_date  # Store datetime object for sorting
                except:
                    date_formatted = "Unknown date"
                    date_obj = datetime.min.replace(tzinfo=ZoneInfo('America/Los_Angeles'))  # Put errors at the beginning
                
                payments.append({
                    'name': name,
                    'amount': amount,
                    'date': date_formatted,
                    'date_obj': date_obj
                })
    
    mail.close()
    mail.logout()
    
    return payments

def format_payment_report(payments):
    """Format the payment data into a readable report"""
    
    if not payments:
        return f"No e-transfers received in the last {DAYS} days."
    
    # Sort by date (oldest first)
    payments.sort(key=lambda x: x['date_obj'])
    
    # Calculate totals
    total_amount = sum(p['amount'] for p in payments)
    total_people = len(payments)
    
    # Format report
    report = f"E-Transfer Payment Report\n"
    
    report += f"Total Received: ${total_amount:.2f}\n"
    report += f"Number of Payments: {total_people}\n\n"
    
    report += "Payment Details:\n"
    report += "-"*50 + "\n"
    
    for payment in payments:
        report += f"${payment['amount']:>7.2f} {payment['name']:<30} {payment['date']}\n"
    
    return report

def send_email(content, subject="Thu900 E-Transfer Report"):
    """Send the payment report via email"""
    
    # Get current time in PST
    pst_time = datetime.now(ZoneInfo('America/Los_Angeles'))
    
    password = os.environ.get('EMAIL_PASSWORD')
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = f"{subject} - {pst_time.strftime('%Y-%m-%d %I:%M %p PST')}"
    
    body = content
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

if __name__ == "__main__":
    print(f"Reading e-transfer emails from last {DAYS} days...")
    payments = read_etransfer_emails()
    
    print(f"Found {len(payments)} e-transfer(s)")
    
    report = format_payment_report(payments)
    print("\n" + report)
    
    print("\nSending email report...")
    send_email(report)
