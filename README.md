# YNAB-PayPal Transaction Matcher

Automatically match PayPal transactions with YNAB bank transactions to identify the original merchants and retailers.

## Problem Statement

When you use PayPal for online purchases:
- Transactions appear in your bank account labeled as "PayPal"
- These transactions are imported into YNAB without merchant details
- You have to manually cross-reference PayPal to identify the actual retailer
- Currency conversions make amount matching difficult

This tool solves that problem by:
- Fetching transactions from both YNAB and PayPal
- Intelligently matching them based on amount and date (with tolerance for delays and currency conversion)
- Displaying the matched merchant information
- Optionally updating YNAB transactions with merchant details

## Features

- **Flexible PayPal Integration**: Works with PayPal CSV exports (Personal accounts) or PayPal API (Business accounts)
- **Smart Matching Algorithm**:
  - Handles multi-day clearing delays (configurable)
  - Tolerates currency conversion fluctuations (configurable percentage)
  - Confidence scoring (high/medium/low)
- **Multiple Currencies**: Handles transactions in GBP, EUR, USD, AUD, etc.
- **Safe Operation**: View matches before applying any updates to YNAB
- **Detailed Output**: Shows matched transactions with confidence levels

## Requirements

- Python 3.7 or higher
- YNAB account with Personal Access Token
- PayPal account (Personal or Business)

## Installation

1. **Clone or download this repository**

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up configuration**
   ```bash
   cp .env.example .env
   ```

4. **Configure your credentials** (see Configuration section below)

## Configuration

### YNAB Setup

1. Go to [YNAB Account Settings](https://app.ynab.com/settings/developer)
2. Click "New Token" under Personal Access Tokens
3. Copy the token and add it to your `.env` file:
   ```
   YNAB_API_TOKEN=your_token_here
   ```

4. Find your Budget ID:
   - Go to YNAB in your browser
   - The URL will look like: `https://app.ynab.com/<BUDGET_ID>/budget`
   - Copy the Budget ID and add it to `.env`:
   ```
   YNAB_BUDGET_ID=your_budget_id_here
   ```

### PayPal Setup (Option 1: CSV Export - Recommended for Personal Accounts)

1. Log into PayPal
2. Go to **Activity** > **Download**
3. Select:
   - **Transaction type**: All transactions
   - **Date range**: Choose your range (e.g., last 3 months)
   - **Format**: CSV (Comma Delimited)
4. Click **Create Report** and then **Download**
5. Save the file as `paypal_transactions.csv` in the project directory

Or update `.env` with your CSV path:
```
PAYPAL_CSV_PATH=path/to/your/paypal_export.csv
```

### PayPal Setup (Option 2: API - For Business Accounts)

1. Go to [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/applications)
2. Create a new REST API app
3. Enable "Transaction Search" permission in app settings
4. Copy your Client ID and Secret to `.env`:
   ```
   PAYPAL_CLIENT_ID=your_client_id_here
   PAYPAL_CLIENT_SECRET=your_client_secret_here
   PAYPAL_MODE=live
   ```

**Note**: After enabling Transaction Search permission, it may take up to 9 hours for a new access token to have this permission.

### Matching Configuration

Adjust these settings in `.env` to tune the matching algorithm:

```bash
# Number of days before YNAB transaction date to search for PayPal transactions
DATE_TOLERANCE_DAYS=7

# Percentage tolerance for amount matching (handles currency conversion)
AMOUNT_TOLERANCE_PERCENT=3.0

# Keywords to identify PayPal transactions in YNAB (comma-separated)
PAYPAL_KEYWORDS=PayPal,PAYPAL,Pp *
```

## Usage

### Test Your Connection

```bash
python main.py --test
```

### View Matches (Last 30 Days)

```bash
python main.py --days 30
```

### Save Matches to File

```bash
python main.py --days 30 --output matches.txt
```

### Use PayPal API Instead of CSV

```bash
python main.py --days 30 --use-api
```

### Update YNAB Transactions

**High confidence matches only (recommended):**
```bash
python main.py --days 30 --update --confidence high
```

**Include medium confidence matches:**
```bash
python main.py --days 30 --update --confidence medium
```

The tool will show you a preview and ask for confirmation before making any changes to YNAB.

## How It Works

### 1. Transaction Identification

The tool searches YNAB for transactions containing PayPal keywords (configurable in `.env`):
- Checks payee name and memo fields
- Only considers outgoing transactions (negative amounts)

### 2. Matching Algorithm

For each YNAB PayPal transaction, the tool:

1. **Date Matching**: Looks for PayPal transactions that occurred 0-7 days BEFORE the YNAB transaction date
   - Accounts for bank clearing delays
   - Especially important for weekends and holidays

2. **Amount Matching**: Compares transaction amounts with tolerance
   - Handles currency conversion fluctuations (default ±3%)
   - YNAB amounts are in GBP (from your bank)
   - PayPal amounts may be in different currencies

3. **Scoring**: Calculates match score based on:
   - Date proximity (closer = better)
   - Amount accuracy (closer = better)
   - Currency bonus (GBP transactions get higher confidence)

4. **Confidence Levels**:
   - **High** (score ≥ 0.9): Very likely correct match
   - **Medium** (score ≥ 0.7): Probably correct, review recommended
   - **Low** (score ≥ 0.5): Uncertain, manual review required

### 3. Output

The tool displays:
```
YNAB:   2025-11-08 | £42.99 | PayPal
PayPal: 2025-11-05 | £42.99 | Amazon UK
        Item: Wireless Mouse
Match:  Score: 0.95 | Confidence: HIGH | Days diff: 3
```

### 4. Updating YNAB (Optional)

When using `--update`, the tool:
- Updates the memo field with merchant name and details
- Example: "Amazon UK (Wireless Mouse) [EUR 49.99]"
- Only updates transactions meeting your confidence threshold
- Preserves original transaction data

## Example Workflow

1. **Export PayPal transactions** for the last 90 days
2. **Run the matcher** to see matches:
   ```bash
   python main.py --days 90 --output my_matches.txt
   ```
3. **Review the output** file to check accuracy
4. **Apply high-confidence updates**:
   ```bash
   python main.py --days 90 --update --confidence high
   ```
5. **Manually review** any unmatched or low-confidence transactions in YNAB

## Troubleshooting

### "No PayPal transactions found in YNAB"

- Check your `PAYPAL_KEYWORDS` setting in `.env`
- Verify how PayPal transactions appear in YNAB
- Try adding more variations (e.g., "PP*", "PAYPAL*")

### "PayPal CSV file not found"

- Make sure you've exported the CSV from PayPal
- Check the path in `PAYPAL_CSV_PATH` setting
- Verify the file is in the correct location

### "YNAB API connection failed"

- Verify your `YNAB_API_TOKEN` is correct
- Check your `YNAB_BUDGET_ID` is correct
- Ensure your token hasn't expired

### "PayPal API connection failed"

- Verify Transaction Search permission is enabled
- Wait up to 9 hours after enabling permission
- Check your Client ID and Secret are correct
- Verify `PAYPAL_MODE` is set correctly (live/sandbox)

### Poor Match Quality

Adjust matching parameters in `.env`:
- Increase `DATE_TOLERANCE_DAYS` if transactions take longer to clear
- Increase `AMOUNT_TOLERANCE_PERCENT` if currency conversions vary more
- Check your bank statement timing vs PayPal transaction dates

### CSV Parsing Errors

PayPal CSV formats can vary by region:
- The tool attempts to detect column names automatically
- If parsing fails, check the CSV file structure
- Ensure you selected "Comma Delimited" format when exporting

## Future Enhancements

Potential improvements for future versions:
- Automatic scheduled matching
- Web interface
- Support for other payment providers (Stripe, Revolut, etc.)
- Machine learning for improved matching
- Direct payee name updates (requires YNAB API enhancement)

## Security Notes

- Never commit your `.env` file to version control
- Keep your API tokens secure
- The tool only reads your transactions and optionally updates memo fields
- No financial transactions are initiated
- Review matches before applying updates

## License

MIT License - Feel free to modify and distribute

## Support

If you encounter issues:
1. Check the Troubleshooting section above
2. Verify your `.env` configuration
3. Run with `--test` flag to check connections
4. Review the error messages carefully

## Contributing

Contributions welcome! Areas for improvement:
- Support for additional payment providers
- Enhanced matching algorithms
- Better CSV format detection
- UI/web interface
- Additional output formats (JSON, Excel)

## Acknowledgments

- [YNAB API Documentation](https://api.ynab.com/)
- [PayPal REST API Documentation](https://developer.paypal.com/api/rest/)