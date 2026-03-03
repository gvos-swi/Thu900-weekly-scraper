sender = "thu900hockey@gmail.com"
receiver = "thu900hockey@gmail.com"
url = "https://gamelogin.com/thu900"

from playwright.sync_api import sync_playwright
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

password = os.environ.get('EMAIL_PASSWORD')

def scrape_player_list(url):
    try:
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Navigate to the page
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait a bit for dynamic content to load
            page.wait_for_timeout(3000)
            
            # Get the page content
            player_data = page.inner_text('body')
            
            # Extract content between "Home / Away" and "Future Games"
            start_marker1 = "Home\tAway"  # Tab character between Home and Away
            start_marker2 = "Players Logged In"  # Alternative marker if the first one is not found"
            end_marker = "Future Games"
            
            start_idx1 = player_data.find(start_marker1)
            start_idx2 = player_data.find(start_marker2)    
            end_idx = player_data.find(end_marker)
            
            if start_idx1 != -1 and end_idx != -1:
                player_data = player_data[start_idx1 + len(start_marker1):end_idx]
            elif start_idx2 != -1 and end_idx != -1:
                player_data = player_data[start_idx2 + 9 + len(start_marker2):end_idx]
            else:
                player_data = "Could not find text indicators to extract player names" 
            
            # Split into lines and clean
            lines = player_data.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.isdigit():
                    cleaned_lines.append(stripped)
            
            # Separate home and away players (alternating)
            home_players = []
            away_players = []
            
            is_home = True
            for line in cleaned_lines:
                if is_home:
                    home_players.append(line)
                else:
                    away_players.append(line)
                is_home = not is_home
            
            # Format the output
            result = "AWAY TEAM:\n"
            for player in away_players:
                result += player + "\n"
            result += "\n"
            result += "HOME TEAM:\n"
            for player in home_players:
                result += player + "\n"
            
            browser.close()
            return result
            
    except Exception as e:
        return f"Error scraping: {str(e)}"

def send_email(content, subject="Thu900 Player List"):
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = f"{subject} - {pst_time.strftime('%Y-%m-%d %I:%M %p PST')}"
    
    body = f"Player List for Thu900\n"
    body += f"Scraped on: {pst_time.strftime('%Y-%m-%d %I:%M:%S %p PST')}\n"
    body += "="*50 + "\n\n"
    body += content
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

if __name__ == "__main__":
    print(f"Scraping {url}...")
    player_list = scrape_player_list(url)
    print(f"Sending email with player list...")
    send_email(player_list)