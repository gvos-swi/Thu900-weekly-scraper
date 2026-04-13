sender = "thu900hockey@gmail.com"
receiver = "thu900hockey@gmail.com"
DAYS = 5  # number of days to look back for e-transfers

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
import gspread
from google.oauth2.service_account import Credentials

# Google Sheet details
SHEET_ID = "1fC2SNekJdQjbv1jLd6bwOLhdFtvraDrAlH7e-WcfHxs"
TAB_NAME = "Player Name Mapping"
JSON_KEYFILE = "thu900-automation-66657e390dcb.json"

def get_player_credits():
    """Read player credits list from the first tab of Google Sheets"""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_file(JSON_KEYFILE, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(SHEET_ID)
        # Get the first worksheet (index 0)
        first_worksheet = sheet.get_worksheet(0)
        
        # Get all values from the sheet
        all_values = first_worksheet.get_all_values()
        
        # Search for "Player Credits:" in the sheet
        credits_row = None
        credits_col = None
        
        for row_idx, row in enumerate(all_values):
            for col_idx, cell in enumerate(row):
                if cell.strip() == "Player Credits:":
                    credits_row = row_idx
                    credits_col = col_idx
                    break
            if credits_row is not None:
                break
        
        if credits_row is None:
            print("Could not find 'Player Credits:' in first tab")
            return set()
        
        # Read players from cells below "Player Credits:" until blank cell
        credits_list = []
        row_idx = credits_row + 1
        
        while row_idx < len(all_values):
            cell_value = all_values[row_idx][credits_col].strip() if credits_col < len(all_values[row_idx]) else ""
            
            if not cell_value:  # Blank cell - end of list
                break
            
            credits_list.append(cell_value)
            row_idx += 1
        
        # Return as a set for fast lookup (case-insensitive)
        credits_set = set(name.upper().strip() for name in credits_list)
        print(f"Loaded {len(credits_set)} players with credits from Google Sheets")
        return credits_set
        
    except Exception as e:
        print(f"Error reading player credits: {e}")
        return set()

def get_name_mapping():
    """Read player name mapping from Google Sheets"""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_file(JSON_KEYFILE, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(SHEET_ID)
        worksheet = sheet.worksheet(TAB_NAME)
        
        # Get all values
        all_values = worksheet.get_all_values()
        
        # Create mapping dictionary (skip header row)
        mapping = {}
        for row in all_values[1:]:  # Skip header
            if len(row) >= 2 and row[0] and row[1]:
                etransfer_name = row[0].strip().upper()
                roster_name = row[1].strip()
                mapping[etransfer_name] = roster_name
        
        print(f"Loaded {len(mapping)} name mappings from Google Sheets")
        return mapping
        
    except Exception as e:
        print(f"Error reading name mapping: {e}")
        return {}

def get_latest_thursday_roster():
    """Get the player roster from the most recent Thursday's roster email"""
    password = os.environ.get('EMAIL_PASSWORD')
    
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(sender, password)
    mail.select("inbox")
    
    # Search for emails with subject containing "Thu900 Player List"
    status, messages = mail.search(None, '(SUBJECT "Thu900 Player List")')
    
    email_ids = messages[0].split()
    
    # Find the most recent Thursday email
    thursday_roster = None
    
    for email_id in reversed(email_ids):  # Start with most recent
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        
        # Get email date
        date_header = msg.get("Date")
        try:
            email_date = parsedate_to_datetime(date_header)
            pst_date = email_date.astimezone(ZoneInfo('America/Los_Angeles'))
            
            # Check if it's a Thursday
            if pst_date.weekday() == 3:  # Thursday is 3
                # Extract roster from email body
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            thursday_roster = parse_roster_from_email(body)
                            break
                else:
                    body = msg.get_payload(decode=True).decode()
                    thursday_roster = parse_roster_from_email(body)
                
                if thursday_roster:
                    print(f"Found Thursday roster from {pst_date.strftime('%b %d, %Y')}")
                    break
        except:
            continue
    
    mail.close()
    mail.logout()
    
    return thursday_roster if thursday_roster else []

def parse_roster_from_email(email_body):
    """Parse player names from the roster email (excluding goalies)"""
    players = []
    
    # Look for the sections: Goalies, Away, Home
    lines = email_body.split('\n')
    
    current_section = None
    for line in lines:
        line = line.strip()
        
        # Identify sections
        if line == "Goalies:":
            current_section = "goalies"
            continue
        elif line == "Away:":
            current_section = "away"
            continue
        elif line == "Home:":
            current_section = "home"
            continue
        elif line.startswith("Number of players:") or line.startswith("==="):
            continue
        
        # Collect player names (but skip goalies - they don't pay)
        if current_section and line and not line.startswith("Player List"):
            if current_section == "goalies":
                continue  # Skip goalies
            
            player_name = line.strip()
            if player_name:
                players.append(player_name)
    
    return players

def read_etransfer_emails():
    """Read emails from the configured lookback period and extract e-transfer information"""
    password = os.environ.get('EMAIL_PASSWORD')
    
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(sender, password)
    mail.select("inbox")
    
    # Calculate date to go back to DAYS 
    lookback_date = datetime.now() - timedelta(days=DAYS)
    date_string = lookback_date.strftime("%d-%b-%Y")
    
    # Search for emails since lookback date
    status, messages = mail.search(None, f'(SINCE {date_string})')
    
    email_ids = messages[0].split()
    
    payments = []
    
    for email_id in email_ids:
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        
        subject_header = msg["Subject"]
        if subject_header:
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
            pattern = r"Interac e-Transfer.*received \$([0-9]+\.[0-9]{2}) from (.+?) and it has been"
            match = re.search(pattern, subject, re.IGNORECASE)
            
            if match:
                amount = float(match.group(1))
                name = match.group(2).strip()
                
                # Get and parse email date
                date_header = msg.get("Date")
                try:
                    email_date = parsedate_to_datetime(date_header)
                    pst_date = email_date.astimezone(ZoneInfo('America/Los_Angeles'))
                    date_formatted = pst_date.strftime('%b %d, %I:%M %p')
                    date_obj = pst_date
                except:
                    date_formatted = "Unknown date"
                    date_obj = datetime.min.replace(tzinfo=ZoneInfo('America/Los_Angeles'))
                
                payments.append({
                    'name': name,
                    'amount': amount,
                    'date': date_formatted,
                    'date_obj': date_obj
                })
    
    mail.close()
    mail.logout()
    
    return payments

def match_payments_to_roster(payments, roster, name_mapping, credits_set):
    """Match e-transfer payments to roster players using the mapping (case-insensitive)"""
    
    # Normalize roster names (strip whitespace)
    roster_set = set(player.strip() for player in roster if player.strip())
    
    # Create case-insensitive lookup for roster
    roster_lookup = {player.upper().strip(): player for player in roster_set}
    
    # Track who paid
    paid_players = {}
    players_with_credits = []
    unmatched_payments = []
    
    for payment in payments:
        etransfer_name = payment['name'].strip().upper()
        matched = False
        
        # Try 1: Use mapping from Google Sheets
        if etransfer_name in name_mapping:
            mapped_name = name_mapping[etransfer_name]
            mapped_name_upper = mapped_name.strip().upper()
            
            # Check if this player is on the roster (case-insensitive)
            if mapped_name_upper in roster_lookup:
                actual_roster_name = roster_lookup[mapped_name_upper]
                paid_players[actual_roster_name] = payment
                matched = True
            else:
                # Mapped but not on this week's roster
                unmatched_payments.append({
                    'payment': payment,
                    'mapped_name': mapped_name,
                    'reason': 'Not on roster'
                })
                matched = True
        
        # Try 2: Fallback - direct case-insensitive match with roster
        if not matched and etransfer_name in roster_lookup:
            actual_roster_name = roster_lookup[etransfer_name]
            paid_players[actual_roster_name] = payment
            matched = True
        
        # No match found
        if not matched:
            unmatched_payments.append({
                'payment': payment,
                'mapped_name': None,
                'reason': 'No mapping'
            })
    
    # Find who didn't pay and separate those with credits
    unpaid_players = []
    for player in roster_set:
        if player not in paid_players:
            # Check if player has credits (case-insensitive)
            if player.upper().strip() in credits_set:
                players_with_credits.append(player)
            else:
                unpaid_players.append(player)
    
    return paid_players, unpaid_players, players_with_credits, unmatched_payments

def format_payment_report(payments, roster, paid_players, unpaid_players, players_with_credits, unmatched_payments):
    """Format the payment data into a readable report"""
    
    if not roster:
        return "Could not find Thursday roster email. Please check inbox."
    
    total_amount = sum(p['amount'] for p in payments)
    total_paid = len(paid_players)
    total_credits = len(players_with_credits)
    total_roster = len(roster)
    
    report = f"E-Transfer Payment Report\n"
    report += f"Last {DAYS} Days\n"
    report += "="*60 + "\n\n"
    
    report += f"Total Received: ${total_amount:.2f}\n"
    report += f"Players Paid: {total_paid}/{total_roster}\n"
    report += f"Has Credits: {total_credits}\n"
    report += f"Outstanding: {len(unpaid_players)}\n\n"
    
    # PAID section - combines actual payments and credits
    if paid_players or players_with_credits:
        report += "PAID:\n"
        report += "-"*60 + "\n"
        
        # Add actual payments (sorted by date)
        sorted_paid = sorted(paid_players.items(), key=lambda x: x[1]['date_obj'])
        for player_name, payment in sorted_paid:
            report += f"{player_name:<30} ${payment['amount']:>7.2f}  {payment['date']}\n"
        
        # Add players with credits (sorted alphabetically)
        for player in sorted(players_with_credits):
            report += f"{player:<30} Check and adjust credit\n"
        
        report += "\n"
    
    # Unpaid players section
    if unpaid_players:
        report += "NOT PAID:\n"
        report += "-"*60 + "\n"
        for player in sorted(unpaid_players):
            report += f"{player}\n"
        report += "\n"
    
    # Unmatched payments section
    if unmatched_payments:
        report += "UNMATCHED PAYMENTS (need to add to mapping):\n"
        report += "-"*60 + "\n"
        for item in unmatched_payments:
            payment = item['payment']
            reason = item['reason']
            report += f"${payment['amount']:>7.2f} from {payment['name']:<30} ({reason})\n"
        report += "\n"
    
    return report

def send_email(content, subject="Thu900 E-Transfer Report"):
    """Send the payment report via email"""
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
    print(f"Starting Thu900 Payment Tracker...")
    print("="*60)
    
    # Step 1: Get player credits from Google Sheets
    print("\n1. Loading player credits from Google Sheets...")
    credits_set = get_player_credits()
    
    # Step 2: Get name mapping from Google Sheets
    print("\n2. Loading player name mapping from Google Sheets...")
    name_mapping = get_name_mapping()
    
    # Step 3: Get latest Thursday roster
    print("\n3. Getting latest Thursday roster from email...")
    roster = get_latest_thursday_roster()
    print(f"   Found {len(roster)} players on roster")
    
    # Step 4: Get e-transfer payments
    print(f"\n4. Reading e-transfer emails from last {DAYS} days...")
    payments = read_etransfer_emails()
    print(f"   Found {len(payments)} e-transfer(s)")
    
    # Step 5: Match payments to roster
    print("\n5. Matching payments to roster...")
    paid_players, unpaid_players, players_with_credits, unmatched_payments = match_payments_to_roster(
        payments, roster, name_mapping, credits_set
    )
    
    # Step 6: Generate report
    print("\n6. Generating report...")
    report = format_payment_report(
        payments, roster, paid_players, unpaid_players, players_with_credits, unmatched_payments
    )
    
    print("\n" + "="*60)
    print(report)
    print("="*60)
    
    # Step 7: Send email
    print("\nSending email report...")
    send_email(report)
    
    print("\n✅ Done!")
