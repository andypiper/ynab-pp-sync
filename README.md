# YNAB-PayPal Transaction Matcher

> Automatically match PayPal transactions with YNAB bank transactions to identify original merchants

This tool solves a common problem for YNAB users who make online purchases through PayPal: transactions appear in your bank account labeled only as "PayPal", making it difficult to track which retailer you actually paid. This matcher intelligently connects your YNAB transactions with PayPal transaction details using smart date and amount matching with tolerance for currency conversion and banking delays.

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
  - [Configuration](#configuration)
  - [Commands](#commands)
  - [Examples](#examples)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Background

### The Problem

When you use PayPal for online purchases:
- Bank transactions appear labeled as "PayPal" without merchant details
- Transactions are imported into YNAB without the original retailer information
- You must manually cross-reference PayPal to identify each purchase
- Currency conversions make amount matching difficult

### The Solution

This tool:
- Fetches transactions from both YNAB and PayPal
- Intelligently matches them based on amount and date (with tolerance for delays and currency conversion)
- Displays matched merchant information with confidence scoring
- Optionally updates YNAB transactions with merchant details

### Features

- **Flexible PayPal Integration**: CSV exports (Personal accounts) or REST API (Business accounts)
- **Smart Matching Algorithm**:
  - Multi-day clearing delay tolerance (configurable)
  - Currency conversion fluctuation tolerance (±3% default)
  - Confidence scoring (high/medium/low)
- **Multiple Currencies**: Handles GBP, EUR, USD, AUD, and more
- **Safe Operation**: Preview matches before applying updates to YNAB
- **Beautiful CLI**: Rich formatted output with tables, progress bars, and color coding

## Install

### Requirements

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- YNAB account with Personal Access Token
- PayPal account (Personal or Business)

### With uv (recommended)

```bash
# Clone repository
git clone https://github.com/yourusername/ynab-pp-sync.git
cd ynab-pp-sync

# Run directly (uv handles dependencies automatically)
uv run main.py --help
```

### With pip

```bash
# Clone repository
git clone https://github.com/yourusername/ynab-pp-sync.git
cd ynab-pp-sync

# Install dependencies
pip install -r requirements.txt

# Run tool
python main.py --help
```

## Usage

### Configuration

1. **Set up configuration file**

```bash
cp .env.example .env
```

2. **Configure YNAB credentials**

Get your Personal Access Token from [YNAB Account Settings](https://app.ynab.com/settings/developer):

```bash
YNAB_API_TOKEN=your_token_here
```

Find your Budget ID in your YNAB URL (`https://app.ynab.com/<BUDGET_ID>/budget`):

```bash
YNAB_BUDGET_ID=your_budget_id_here
```

3. **Configure PayPal source**

**Option A: CSV Export** (Recommended for Personal accounts)

Export transactions from PayPal:
- Go to PayPal → Activity → Download
- Select: All transactions, date range, CSV format
- Save as `paypal_transactions.csv`

```bash
PAYPAL_CSV_PATH=paypal_transactions.csv
```

**Option B: API** (Business accounts only)

Create app at [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/applications):

```bash
PAYPAL_CLIENT_ID=your_client_id_here
PAYPAL_CLIENT_SECRET=your_client_secret_here
PAYPAL_MODE=live
```

4. **Customize matching parameters** (optional)

```bash
DATE_TOLERANCE_DAYS=7
AMOUNT_TOLERANCE_PERCENT=3.0
PAYPAL_KEYWORDS=PayPal,PAYPAL,Pp *
```

### Commands

#### Test Connections

```bash
uv run main.py test
```

Verifies YNAB and PayPal API credentials.

#### Match Transactions

```bash
uv run main.py [OPTIONS]
```

**Options:**

- `--days INTEGER` - Days to look back (default: 90)
- `--use-api` - Use PayPal API instead of CSV
- `--csv PATH` - Path to PayPal CSV file
- `--output PATH` - Save results to file
- `--update` - Update YNAB with matches
- `--confidence [high|medium|low]` - Minimum confidence for updates (default: high)
- `--env PATH` - Path to .env file (default: .env)
- `--help` - Show help message

### Examples

**View matches from last 30 days:**
```bash
uv run main.py --days 30
```

**Use PayPal API (Business accounts):**
```bash
uv run main.py --use-api --days 30
```

**Save results to file:**
```bash
uv run main.py --days 30 --output matches.txt
```

**Update YNAB with high-confidence matches:**
```bash
uv run main.py --days 30 --update --confidence high
```

**Include medium-confidence matches:**
```bash
uv run main.py --days 30 --update --confidence medium
```

### Example Output

```
Match Statistics
┌────────────────────────────────────┬─────────┐
│ Total YNAB PayPal transactions:    │ 45      │
│ Matched:                           │ 42 (93%)│
│ Unmatched:                         │ 3       │
└────────────────────────────────────┴─────────┘

HIGH CONFIDENCE MATCHES (38)
┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━┓
┃ YNAB Date  ┃ Amount ┃ PayPal Date┃ Merchant          ┃ Score ┃ Days ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━┩
│ 2025-11-08 │ £42.99 │ 2025-11-05 │ Amazon UK         │ 0.95  │ 3    │
│ 2025-11-07 │ £15.50 │ 2025-11-06 │ Spotify (Premium) │ 0.92  │ 1    │
└────────────┴────────┴────────────┴───────────────────┴───────┴──────┘
```

## How It Works

### 1. Transaction Identification

The tool searches YNAB for transactions containing PayPal keywords (configurable in `.env`):
- Checks payee name and memo fields
- Only considers outgoing transactions (negative amounts)

### 2. Matching Algorithm

For each YNAB PayPal transaction:

**Date Matching:**
- Looks for PayPal transactions 0-7 days BEFORE the YNAB date
- Accounts for bank clearing delays (weekends, holidays)

**Amount Matching:**
- Compares amounts with ±3% tolerance (default)
- Handles currency conversion fluctuations
- YNAB amounts in GBP; PayPal may be EUR, USD, AUD, etc.

**Scoring:**
- Date proximity (closer = better)
- Amount accuracy (closer = better)
- Currency bonus (GBP transactions get higher confidence)

**Confidence Levels:**
- **High** (score ≥ 0.9): Very likely correct - safe for auto-update
- **Medium** (score ≥ 0.7): Probably correct - review recommended
- **Low** (score ≥ 0.5): Uncertain - manual verification needed

### 3. Output

Displays matches categorized by confidence level with detailed information.

### 4. Updating YNAB (Optional)

When using `--update`:
- Updates memo field with merchant name and details
- Example: "Amazon UK (Wireless Mouse) [EUR 49.99]"
- Only updates transactions meeting confidence threshold
- Requires confirmation before proceeding

## Troubleshooting

### "No PayPal transactions found in YNAB"

- Check `PAYPAL_KEYWORDS` setting in `.env`
- Verify how PayPal transactions appear in YNAB
- Try adding variations: "PP*", "PAYPAL*"

### "PayPal CSV file not found"

- Ensure CSV is exported from PayPal
- Check `PAYPAL_CSV_PATH` in `.env`
- Verify file location

### "YNAB API connection failed"

- Verify `YNAB_API_TOKEN` is correct
- Check `YNAB_BUDGET_ID` is correct
- Ensure token hasn't expired

### "PayPal API connection failed"

- Verify Transaction Search permission is enabled
- Wait up to 9 hours after enabling permission
- Check Client ID and Secret
- Verify `PAYPAL_MODE` setting (live/sandbox)

### Poor Match Quality

Adjust parameters in `.env`:
- Increase `DATE_TOLERANCE_DAYS` if transactions take longer to clear
- Increase `AMOUNT_TOLERANCE_PERCENT` for more currency variation
- Check bank statement timing vs PayPal dates

### CSV Parsing Errors

- PayPal CSV formats vary by region
- Tool auto-detects column names
- Ensure "Comma Delimited" format was selected

## Maintainers

[@andypiper](https://github.com/andypiper)

## Contributing

Contributions welcome! Areas for improvement:

- Support for additional payment providers (Stripe, Revolut, etc.)
- Enhanced matching algorithms
- Better CSV format detection
- Web interface
- Additional output formats (JSON, Excel)

Please feel free to open an issue or submit a pull request.

## License

[MIT](LICENSE) © 2025
