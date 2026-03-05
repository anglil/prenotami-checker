#!/usr/bin/env python3
"""
PrenotaMi Schengen Visa Slot Checker

Monitors the Italian consulate's PrenotaMi appointment system for available
Schengen visa slots and sends an email notification when one opens up.

Configuration is done via environment variables or a .env file.
"""

import os
import sys
import subprocess
import logging
import time
from datetime import datetime
from pathlib import Path

# --- Configuration (from environment variables or .env file) ---
def load_env():
    """Load .env file if it exists."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env()

EMAIL = os.environ.get("PRENOTAMI_EMAIL", "")
PASSWORD = os.environ.get("PRENOTAMI_PASSWORD", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", EMAIL)
# Check interval in seconds (default: 900 = 15 minutes)
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "900"))
# Notification cooldown in seconds (default: 1800 = 30 minutes)
NOTIFY_COOLDOWN_SECONDS = int(os.environ.get("NOTIFY_COOLDOWN", "1800"))
# Notification method: "macos_mail" or "smtp"
NOTIFY_METHOD = os.environ.get("NOTIFY_METHOD", "macos_mail")

LOG_DIR = Path(__file__).parent / "logs"
COOLDOWN_FILE = Path(__file__).parent / ".last_notified"

# Set up logging
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "checker.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("prenotami")


def send_email_notification(subject: str, body: str):
    """Send an email notification. Uses macOS Mail.app by default."""
    if NOTIFY_METHOD == "macos_mail":
        _send_via_macos_mail(subject, body)
    else:
        log.warning(f"Unknown notification method: {NOTIFY_METHOD}. Email not sent.")


def _send_via_macos_mail(subject: str, body: str):
    """Send email via macOS Mail.app using osascript."""
    # Escape quotes for AppleScript
    subject_escaped = subject.replace('"', '\\"')
    body_escaped = body.replace('"', '\\"')
    script = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{subject_escaped}", content:"{body_escaped}", visible:false}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{NOTIFY_EMAIL}"}}
        end tell
        send newMessage
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            log.info(f"Email notification sent to {NOTIFY_EMAIL}")
        else:
            log.error(f"Failed to send email: {result.stderr}")
    except Exception as e:
        log.error(f"Email notification error: {e}")


def should_notify() -> bool:
    """Check if we should send a notification (respecting cooldown)."""
    if not COOLDOWN_FILE.exists():
        return True
    try:
        last_notified = float(COOLDOWN_FILE.read_text().strip())
        return (time.time() - last_notified) > NOTIFY_COOLDOWN_SECONDS
    except (ValueError, OSError):
        return True


def mark_notified():
    """Record that we just sent a notification."""
    COOLDOWN_FILE.write_text(str(time.time()))


def check_slots():
    """Log into PrenotaMi and check for available Schengen visa slots."""
    from playwright.sync_api import sync_playwright

    if not EMAIL or not PASSWORD:
        log.error("PRENOTAMI_EMAIL and PRENOTAMI_PASSWORD must be set. "
                  "Use environment variables or create a .env file.")
        sys.exit(1)

    log.info("Starting slot check...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            # Step 1: Navigate to PrenotaMi
            log.info("Navigating to PrenotaMi...")
            page.goto("https://prenotami.esteri.it/", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)
            page.screenshot(path=str(LOG_DIR / "step1_homepage.png"))

            # Step 2: Click the login button
            log.info("Looking for login link...")
            login_selectors = [
                "a:has-text('EFFETTUARE IL LOGIN')",
                "a:has-text('LOGIN')",
                "a:has-text('Log in')",
                "a:has-text('Accedi')",
                "a[href*='Login']",
                "a[href*='login']",
                "button:has-text('LOGIN')",
            ]
            clicked = False
            for sel in login_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        clicked = True
                        log.info(f"Clicked login via: {sel}")
                        break
                except:
                    continue

            if not clicked:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                for sel in login_selectors:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=2000):
                            el.click()
                            clicked = True
                            log.info(f"Clicked login (after scroll) via: {sel}")
                            break
                    except:
                        continue

            if not clicked:
                log.error("Could not find login link!")
                page.screenshot(path=str(LOG_DIR / "no_login_link.png"))
                return

            # Wait for redirect to iam.esteri.it
            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(3)
            page.screenshot(path=str(LOG_DIR / "step2_login_page.png"))
            log.info(f"Login page URL: {page.url}")

            # Step 3: Fill in credentials
            log.info("Filling login credentials...")
            for sel in ["input#UserName", "input[name='UserName']", "input[type='text']", "input[type='email']"]:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=3000):
                        el.fill(EMAIL)
                        log.info(f"Filled username via: {sel}")
                        break
                except:
                    continue

            for sel in ["input#Password", "input[name='Password']", "input[type='password']"]:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=3000):
                        el.fill(PASSWORD)
                        log.info(f"Filled password via: {sel}")
                        break
                except:
                    continue

            for sel in ["button:has-text('Next')", "button:has-text('Sign in')", "button:has-text('Login')", "button[type='submit']"]:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        log.info(f"Clicked submit via: {sel}")
                        break
                except:
                    continue

            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(5)
            page.screenshot(path=str(LOG_DIR / "step3_after_login.png"))

            # Check for login failure
            page_text = page.content().lower()
            if "login failure" in page_text or "login failed" in page_text:
                log.error("Login failed! Check credentials.")
                page.screenshot(path=str(LOG_DIR / "login_failed.png"))
                return

            log.info("Login successful!")

            # Step 4: Navigate to services page
            log.info("Navigating to booking page...")
            page.goto("https://prenotami.esteri.it/Services", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(3)
            page.screenshot(path=str(LOG_DIR / "step4_services.png"))

            # Step 5: Find the Schengen Visa row and click PRENOTA/BOOK
            log.info("Looking for Schengen visa booking...")
            schengen_clicked = page.evaluate("""() => {
                const rows = document.querySelectorAll('tr');
                for (const row of rows) {
                    const text = row.textContent.toLowerCase();
                    if (text.includes('schengen')) {
                        const allLinks = row.querySelectorAll('a, button');
                        for (const l of allLinks) {
                            const t = l.textContent.trim().toUpperCase();
                            if (t.includes('PRENOTA') || t.includes('BOOK')) {
                                l.click();
                                return true;
                            }
                        }
                    }
                }
                return false;
            }""")

            if not schengen_clicked:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                schengen_clicked = page.evaluate("""() => {
                    const rows = document.querySelectorAll('tr');
                    for (const row of rows) {
                        const text = row.textContent.toLowerCase();
                        if (text.includes('schengen')) {
                            const allLinks = row.querySelectorAll('a, button');
                            for (const l of allLinks) {
                                const t = l.textContent.trim().toUpperCase();
                                if (t.includes('PRENOTA') || t.includes('BOOK')) {
                                    l.click();
                                    return true;
                                }
                            }
                        }
                    }
                    return false;
                }""")

            if not schengen_clicked:
                log.warning("No Schengen visa PRENOTA button found")
                page.screenshot(path=str(LOG_DIR / "no_schengen_button.png"))
                return

            log.info("Clicked PRENOTA for Schengen visa")
            time.sleep(3)

            # Step 6: Check if all booked or slots available
            page_content = page.content()
            page.screenshot(path=str(LOG_DIR / "step5_after_book.png"))

            all_booked_indicators = [
                "All appointments for this service are currently booked",
                "tutti gli appuntamenti",
                "currently booked",
                "attualmente esauriti",
                "posti disponibili per il servizio scelto sono esauriti",
                "elevata richiesta",
                "sono esauriti",
            ]

            is_all_booked = any(ind in page_content for ind in all_booked_indicators)

            if is_all_booked:
                log.info("❌ No slots available - all appointments are currently booked.")
                try:
                    ok_btn = page.locator("button:has-text('OK'), a:has-text('OK')").first
                    if ok_btn.is_visible(timeout=2000):
                        ok_btn.click()
                except:
                    pass
            else:
                log.info("🎉 SLOTS MAY BE AVAILABLE!")
                page.screenshot(path=str(LOG_DIR / "slots_available.png"))

                if should_notify():
                    send_email_notification(
                        "PrenotaMi Schengen Visa Slot Available!",
                        "A Schengen visa appointment slot appears to be available!\\n\\n"
                        "Go book it NOW: https://prenotami.esteri.it/\\n\\n"
                        f"Detected at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n"
                        "-- PrenotaMi Slot Checker"
                    )
                    mark_notified()
                else:
                    log.info("Notification cooldown active, skipping email.")

        except Exception as e:
            log.error(f"Error during slot check: {e}")
            try:
                page.screenshot(path=str(LOG_DIR / "error.png"))
            except:
                pass
        finally:
            browser.close()

    log.info("Slot check complete.")


def run_loop():
    """Run the checker in a loop."""
    log.info(f"Starting checker loop (interval: {CHECK_INTERVAL}s)...")
    while True:
        check_slots()
        log.info(f"Next check in {CHECK_INTERVAL // 60} minutes...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PrenotaMi Schengen Visa Slot Checker")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode")
    parser.add_argument("--once", action="store_true", help="Run a single check (default)")
    args = parser.parse_args()

    if args.loop:
        run_loop()
    else:
        check_slots()
