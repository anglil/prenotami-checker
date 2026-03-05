# PrenotaMi Schengen Visa Slot Checker

Automatically monitors the Italian consulate's [PrenotaMi](https://prenotami.esteri.it/) appointment system for available **Schengen visa** slots and sends you an email when one opens up.

PrenotaMi is notoriously difficult to get appointments on — slots are released unpredictably and get snatched within minutes. This tool checks every 15 minutes so you don't have to.

## How It Works

1. Logs into your PrenotaMi account using headless Chromium (via [Playwright](https://playwright.dev/python/))
2. Navigates to the services page and clicks **PRENOTA** on the Schengen visa row
3. Detects whether the "all booked" popup appears (in English or Italian)
4. If slots are available → sends you an email notification via macOS Mail.app

## Prerequisites

- **Python 3.10+**
- **macOS** (for Mail.app email notifications — or modify for SMTP)
- A **PrenotaMi account** — register at [prenotami.esteri.it](https://prenotami.esteri.it/)
- **Mail.app** configured with your email account

## Setup

```bash
# Clone the repo
git clone https://github.com/anglil/prenotami-checker.git
cd prenotami-checker

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install playwright
playwright install chromium

# Configure your credentials
cp .env.example .env
# Edit .env with your PrenotaMi login and notification email
```

## Configuration

Copy `.env.example` to `.env` and fill in your details:

```bash
PRENOTAMI_EMAIL=your-email@example.com
PRENOTAMI_PASSWORD=your-password
NOTIFY_EMAIL=your-email@example.com
CHECK_INTERVAL=900        # seconds (default: 15 minutes)
NOTIFY_COOLDOWN=1800      # seconds between repeat notifications
NOTIFY_METHOD=macos_mail  # currently only macos_mail supported
```

## Usage

### Single check
```bash
source venv/bin/activate
python3 checker.py
```

### Continuous monitoring (recommended)
```bash
source venv/bin/activate
python3 checker.py --loop
```

### Background mode
```bash
# Start in background
nohup bash run_loop.sh > logs/loop.log 2>&1 & disown

# View logs
tail -f logs/checker.log

# Stop
kill $(cat .runner.pid)
```

## Tips for Getting Slots

- **Check at 3:00 PM PST** (midnight Italy time) — this is when new slots are typically released
- Slots get taken within minutes, so the 15-minute check interval is a good balance
- You can reduce `CHECK_INTERVAL` to `300` (5 minutes) for more aggressive checking
- Keep your Mac awake / plugged in so the checker keeps running

## Logs & Debugging

Screenshots are saved to `logs/` at each step:
- `step1_homepage.png` — PrenotaMi landing page
- `step2_login_page.png` — IAM login form
- `step3_after_login.png` — Post-login state
- `step4_services.png` — Services/booking page
- `step5_after_book.png` — Result after clicking PRENOTA
- `slots_available.png` — Captured when slots are detected
- `error.png` — Captured on errors

## Adapting for Other Consulates

The script currently targets the **San Francisco** consulate. To use it with a different consulate:

1. Register a new PrenotaMi account and select your consulate during registration
2. The script automatically finds the Schengen visa row on whatever consulate your account is linked to
3. No code changes needed — just update `.env` with your new account credentials

## License

MIT
