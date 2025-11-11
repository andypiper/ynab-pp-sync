#!/usr/bin/env python3
"""
YNAB-PayPal Transaction Matcher

Matches PayPal transactions with YNAB bank transactions to identify original merchants.
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.config import Config
from src.ynab_client import YNABClient
from src.paypal_csv import PayPalCSVParser
from src.paypal_api import PayPalAPIClient
from src.matcher import TransactionMatcher


def main():
    """Main entry point for the YNAB-PayPal matcher."""
    parser = argparse.ArgumentParser(
        description='Match YNAB PayPal transactions with PayPal merchant details',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Match transactions from last 30 days using CSV
  python main.py --days 30

  # Match using PayPal API (requires Business account)
  python main.py --use-api --days 30

  # Save output to file
  python main.py --days 30 --output matches.txt

  # Apply updates to YNAB (high confidence only)
  python main.py --days 30 --update --confidence high
        """
    )

    parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='Number of days to look back for transactions (default: 90)'
    )

    parser.add_argument(
        '--use-api',
        action='store_true',
        help='Use PayPal API instead of CSV (requires Business account)'
    )

    parser.add_argument(
        '--csv',
        type=str,
        help='Path to PayPal CSV file (overrides .env setting)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Save output to file instead of printing to console'
    )

    parser.add_argument(
        '--update',
        action='store_true',
        help='Update YNAB transaction memos with matched merchant names'
    )

    parser.add_argument(
        '--confidence',
        choices=['high', 'medium', 'low'],
        default='high',
        help='Minimum confidence level for updates (default: high)'
    )

    parser.add_argument(
        '--env',
        type=str,
        default='.env',
        help='Path to .env file (default: .env)'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Test API connections and exit'
    )

    args = parser.parse_args()

    # Load configuration
    print("Loading configuration...")
    config = Config(args.env)

    # Validate YNAB configuration
    if not config.validate_ynab():
        print("\nPlease set up your YNAB credentials in .env file")
        print("See .env.example for reference")
        sys.exit(1)

    # Initialize YNAB client
    print("Connecting to YNAB...")
    ynab_client = YNABClient(config.ynab_token, config.ynab_budget_id)

    if args.test:
        print("\nTesting YNAB API connection...")
        if ynab_client.test_connection():
            print("✓ YNAB API connection successful")
        else:
            print("✗ YNAB API connection failed")
            sys.exit(1)

        # Test PayPal connection
        if args.use_api or config.validate_paypal_api():
            print("\nTesting PayPal API connection...")
            paypal_client = PayPalAPIClient(
                config.paypal_client_id,
                config.paypal_client_secret,
                config.paypal_mode
            )
            if paypal_client.test_connection():
                print("✓ PayPal API connection successful")
            else:
                print("✗ PayPal API connection failed")
                sys.exit(1)
        else:
            print("\nPayPal API credentials not configured (using CSV mode)")

        print("\n✓ All configured connections successful!")
        sys.exit(0)

    # Determine date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)

    print(f"\nFetching transactions from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Fetch YNAB transactions
    print("\nFetching YNAB transactions...")
    try:
        ynab_paypal_transactions = ynab_client.find_paypal_transactions(
            paypal_keywords=config.paypal_keywords,
            since_date=start_date
        )
        print(f"Found {len(ynab_paypal_transactions)} PayPal transactions in YNAB")
    except Exception as e:
        print(f"Error fetching YNAB transactions: {e}")
        sys.exit(1)

    if not ynab_paypal_transactions:
        print("\nNo PayPal transactions found in YNAB for the specified date range.")
        print(f"Keywords used: {', '.join(config.paypal_keywords)}")
        sys.exit(0)

    # Fetch PayPal transactions
    paypal_transactions = []

    if args.use_api:
        print("\nFetching PayPal transactions via API...")
        if not config.validate_paypal_api():
            print("Error: PayPal API credentials not configured")
            print("Please set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env")
            sys.exit(1)

        try:
            paypal_client = PayPalAPIClient(
                config.paypal_client_id,
                config.paypal_client_secret,
                config.paypal_mode
            )
            paypal_transactions = paypal_client.get_transactions_for_range(
                start_date,
                end_date
            )
        except Exception as e:
            print(f"Error fetching PayPal transactions: {e}")
            sys.exit(1)
    else:
        # Use CSV
        csv_path = args.csv or config.paypal_csv_path
        print(f"\nParsing PayPal CSV: {csv_path}")

        if not Path(csv_path).exists():
            print(f"Error: PayPal CSV file not found: {csv_path}")
            print("\nTo export PayPal transactions:")
            print("1. Log into PayPal")
            print("2. Go to Activity > Download")
            print("3. Select date range and CSV format")
            print(f"4. Save as: {csv_path}")
            sys.exit(1)

        try:
            parser = PayPalCSVParser(csv_path)
            all_paypal = parser.parse_transactions()

            # Filter by date range
            paypal_transactions = parser.filter_by_date_range(
                all_paypal,
                start_date,
                end_date
            )
            print(f"Found {len(paypal_transactions)} PayPal transactions in CSV")
        except Exception as e:
            print(f"Error parsing PayPal CSV: {e}")
            sys.exit(1)

    if not paypal_transactions:
        print("\nNo PayPal transactions found for the specified date range.")
        sys.exit(0)

    # Match transactions
    print("\nMatching transactions...")
    matcher = TransactionMatcher(
        date_tolerance_days=config.date_tolerance_days,
        amount_tolerance_percent=config.amount_tolerance_percent
    )

    matches = matcher.match_transactions(ynab_paypal_transactions, paypal_transactions)

    # Format output
    output = matcher.format_match_output(matches, show_unmatched=True)

    # Display or save output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output)
        print(f"\nResults saved to: {args.output}")
    else:
        print("\n")
        print(output)

    # Apply updates if requested
    if args.update:
        print(f"\nGenerating updates for {args.confidence} confidence matches...")
        updates = matcher.generate_update_script(matches, min_confidence=args.confidence)

        if not updates:
            print("No transactions to update")
            sys.exit(0)

        print(f"Found {len(updates)} transactions to update")
        print("\nPreview of updates:")
        for i, update in enumerate(updates[:5], 1):
            print(f"{i}. {update['merchant_name']} - {update['new_memo']}")
        if len(updates) > 5:
            print(f"... and {len(updates) - 5} more")

        # Confirm before applying
        response = input("\nApply these updates to YNAB? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Updates cancelled")
            sys.exit(0)

        # Apply updates
        print("\nApplying updates...")
        success_count = 0
        for update in updates:
            if ynab_client.update_transaction_memo(
                update['transaction_id'],
                update['new_memo']
            ):
                success_count += 1
                print(f"✓ Updated: {update['merchant_name']}")
            else:
                print(f"✗ Failed: {update['merchant_name']}")

        print(f"\nSuccessfully updated {success_count}/{len(updates)} transactions")


if __name__ == '__main__':
    main()
