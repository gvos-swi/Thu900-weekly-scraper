sender = "thu900hockey@gmail.com"
receiver = "thu900hockey@gmail.com"
url = "https://gamelogin.com/thu900"

from playwright.sync_api import sync_playwright
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import re

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
            
            # Extract content between "Home / Away" or "Players Logged In" and "Future Games"
            start_marker_teams = "Home\tAway"  # Tab character between Home and Away
            start_marker_noteams = "Players Logged In"  # when teams are not set
            end_marker = "Future Games"
            
            end_idx = player_data.find(end_marker)
            start_idx_teams = player_data.find(start_marker_teams)
            start_idx_noteams = player_data.find(start_marker_noteams)

            teams_set = False
            if end_idx == -1:
                player_data = "Couldn't find text indicators to extract player names" 
            elif start_idx_teams != -1:  # teams set
                teams_set = True
                player_data = player_data[start_idx_teams + len(start_marker_teams):end_idx]
            elif start_idx_noteams != -1:  # teams not set
                player_data = player_data[start_idx_noteams + len(start_marker_noteams):end_idx]
            else:
                player_data = "Could not find text indicators to extract player names" 
            
            # Split into lines and clean
            lines = player_data.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                # Skip blank lines, digit-only lines, and "Max 22" style lines
                if stripped and not stripped.isdigit() and not re.match(r'^Max\s+\d+$', stripped):
                    cleaned_lines.append(stripped)
            
            if teams_set:
                # Separate home and away players (alternating)
                home_players = []
                away_players = []
                goalies = []
                
                is_home = True
                for line in cleaned_lines:
                    # Check if player is a goalie
                    if line.startswith('[G]'):
                        # Remove [G] prefix and strip whitespace
                        goalie_name = line.replace('[G]', '').strip()
                        goalies.append(goalie_name)
                    elif is_home:
                        home_players.append(line)
                    else:
                        away_players.append(line)
                    is_home = not is_home
                
                # Calculate total players
                total_players = len(goalies) + len(home_players) + len(away_players)
                
                # Format the output - Goalies, Away, Home
                result = f"Number of players: {total_players}\n\n"
                
                # Goalies section - always 2 lines
                result += "Goalies:\n"
                for player in goalies:
                    result += player + "\n"
                # Pad with blank lines to reach 2 goalies
                for i in range(2 - len(goalies)):
                    result += "\n"
                result += "\n"
                
                # Away team section - always 10 lines
                result += "Away:\n"
                for player in away_players:
                    result += player + "\n"
                # Pad with blank lines to reach 10 players
                for i in range(10 - len(away_players)):
                    result += "\n"
                result += "\n"
                
                # Home team section - always 10 lines
                result += "Home:\n"
                for player in home_players:
                    result += player + "\n"
                # Pad with blank lines to reach 10 players
                for i in range(10 - len(home_players)):
                    result += "\n"
            else:
                # Just list all players without team separation
                # Remove [G] prefix from goalie names
                all_players = []
                for player in cleaned_lines:
                    if player.startswith('[G]'):
                        all_players.append(player.replace('[G]', '').strip())
                    else:
                        all_players.append(player)
                
                total_players = len(all_players)
                result = f"Number of players: {total_players}\nNo Teams Set\nPLAYERS LOGGED IN:\n"
                for player in all_players:
                    result += player + "\n"
            
            browser.close()
            return result
            
    except Exception as e:
        return f"Error scraping: {str(e)}"

def send_email(content, subject="Thu900 Player List"):
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
    print(f"Scraping {url}...")
    player_list = scrape_player_list(url)
    
    # Print email content to command line
    print("\n" + "="*60)
    print("EMAIL CONTENT:")
    print("="*60)
    print(player_list)
    print("="*60 + "\n")
    
    print(f"Sending email with player list...")
    send_email(player_list)
