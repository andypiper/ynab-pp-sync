"""PayPal CSV parser for extracting transaction data."""
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class PayPalCSVParser:
    """Parser for PayPal CSV export files."""

    # Common column names in PayPal CSV exports
    # These may vary slightly by region/account type
    COLUMN_MAPPINGS = {
        'date': ['Date', 'date', 'Transaction Date'],
        'time': ['Time', 'time', 'Transaction Time'],
        'name': ['Name', 'name', 'To', 'From', 'Counterparty Name'],
        'type': ['Type', 'type', 'Transaction Type'],
        'status': ['Status', 'status', 'Transaction Status'],
        'currency': ['Currency', 'currency', 'Original Currency'],
        'gross': ['Gross', 'gross', 'Amount', 'Gross Amount'],
        'fee': ['Fee', 'fee', 'Fees', 'Transaction Fee'],
        'net': ['Net', 'net', 'Total', 'Net Amount'],
        'balance': ['Balance', 'balance', 'Balance'],
        'transaction_id': ['Transaction ID', 'transaction_id', 'Reference Txn ID'],
        'reference_id': ['Reference Txn ID', 'reference_id', 'Related Transaction'],
        'item_title': ['Item Title', 'item_title', 'Subject', 'Note'],
    }

    def __init__(self, csv_path: str, date_format: str = "auto"):
        """Initialize PayPal CSV parser.

        Args:
            csv_path: Path to PayPal CSV file
            date_format: Date format string (e.g., '%d/%m/%Y') or 'auto' for auto-detection
        """
        self.csv_path = Path(csv_path)
        self.date_format = date_format
        self.column_map = {}

    def _detect_columns(self, header_row: List[str]) -> None:
        """Detect which columns are present in the CSV.

        Args:
            header_row: List of column headers from CSV
        """
        for standard_name, possible_names in self.COLUMN_MAPPINGS.items():
            for header in header_row:
                if header in possible_names:
                    self.column_map[standard_name] = header
                    break

    def _parse_date(self, date_str: str, time_str: str = "") -> Optional[str]:
        """Parse PayPal date/time into ISO format.

        Args:
            date_str: Date string from CSV
            time_str: Optional time string from CSV

        Returns:
            ISO format date string (YYYY-MM-DD) or None if parsing fails
        """
        if not date_str:
            return None

        # If a specific format is configured, try it first
        if self.date_format and self.date_format.lower() != "auto":
            try:
                dt = datetime.strptime(date_str, self.date_format)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                print(
                    f"Warning: Could not parse date '{date_str}' with format '{self.date_format}', "
                    f"falling back to auto-detection"
                )

        # Fall back to trying various date formats PayPal might use
        date_formats = [
            "%d/%m/%Y",  # DD/MM/YYYY (UK format)
            "%m/%d/%Y",  # MM/DD/YYYY (US format)
            "%Y-%m-%d",  # ISO format
            "%d-%m-%Y",  # DD-MM-YYYY
            "%m-%d-%Y",  # MM-DD-YYYY
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        print(f"Warning: Could not parse date: {date_str}")
        return None

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float.

        Args:
            amount_str: Amount string from CSV (may include currency symbol)

        Returns:
            Float amount
        """
        if not amount_str:
            return 0.0

        # Remove currency symbols and commas
        cleaned = amount_str.replace(',', '').replace('£', '').replace('$', '').replace('€', '').strip()

        try:
            return float(cleaned)
        except ValueError:
            print(f"Warning: Could not parse amount: {amount_str}")
            return 0.0

    def parse_transactions(self) -> List[Dict]:
        """Parse PayPal CSV file and extract transactions.

        Returns:
            List of parsed transaction dictionaries

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV format is invalid
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(f"PayPal CSV file not found: {self.csv_path}")

        transactions = []

        try:
            with open(self.csv_path, 'r', encoding='utf-8-sig') as csvfile:
                # Try to detect if it's using comma or tab delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                delimiter = '\t' if '\t' in sample else ','

                reader = csv.DictReader(csvfile, delimiter=delimiter)

                # Clean column names (remove BOM, quotes, extra whitespace)
                if reader.fieldnames:
                    cleaned_fieldnames = [
                        name.strip().strip('"').strip("'") for name in reader.fieldnames
                    ]
                    # Manually set the fieldnames to cleaned versions
                    reader.fieldnames = cleaned_fieldnames

                    self._detect_columns(reader.fieldnames)

                # Parse each row
                total_rows = 0
                skipped_rows = 0
                for row in reader:
                    total_rows += 1
                    try:
                        txn = self._parse_row(row)
                        if txn:
                            transactions.append(txn)
                        else:
                            skipped_rows += 1
                    except Exception as e:
                        print(f"Warning: Error parsing row: {e}")
                        skipped_rows += 1
                        continue

                if skipped_rows > 0:
                    print(f"Skipped {skipped_rows} rows out of {total_rows} (likely incoming payments or currency conversions)")

        except Exception as e:
            raise ValueError(f"Error reading CSV file: {e}")

        if transactions:
            earliest = min(t['date'] for t in transactions)
            latest = max(t['date'] for t in transactions)
            print(f"Parsed {len(transactions)} transactions from PayPal CSV (dates: {earliest} to {latest})")
        else:
            print(f"Parsed {len(transactions)} transactions from PayPal CSV")
        return transactions

    def _parse_row(self, row: Dict[str, str]) -> Optional[Dict]:
        """Parse a single CSV row into a transaction dict.

        Args:
            row: Dictionary representing a CSV row

        Returns:
            Parsed transaction dictionary or None if invalid
        """
        # Get values using detected column names
        date_col = self.column_map.get('date', 'Date')
        time_col = self.column_map.get('time', 'Time')
        name_col = self.column_map.get('name', 'Name')
        type_col = self.column_map.get('type', 'Type')
        status_col = self.column_map.get('status', 'Status')
        currency_col = self.column_map.get('currency', 'Currency')
        gross_col = self.column_map.get('gross', 'Gross')
        net_col = self.column_map.get('net', 'Net')
        item_col = self.column_map.get('item_title', 'Item Title')
        txn_id_col = self.column_map.get('transaction_id', 'Transaction ID')

        # Parse date
        date_str = row.get(date_col, '')
        time_str = row.get(time_col, '')
        date = self._parse_date(date_str, time_str)

        if not date:
            return None

        # Parse amounts
        gross = self._parse_amount(row.get(gross_col, '0'))
        net = self._parse_amount(row.get(net_col, '0'))

        # Only include outgoing payments (negative amounts)
        # PayPal CSV typically has negative values for payments out
        if gross >= 0 and net >= 0:
            return None

        # Build transaction dict
        transaction = {
            'date': date,
            'merchant_name': row.get(name_col, '').strip(),
            'type': row.get(type_col, '').strip(),
            'status': row.get(status_col, '').strip(),
            'currency': row.get(currency_col, 'GBP').strip(),
            'gross_amount': abs(gross),  # Convert to positive for comparison
            'net_amount': abs(net),
            'item_title': row.get(item_col, '').strip(),
            'transaction_id': row.get(txn_id_col, '').strip(),
            'raw': row
        }

        return transaction

    def filter_by_date_range(
        self,
        transactions: List[Dict],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Filter transactions by date range.

        Args:
            transactions: List of transactions
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Filtered list of transactions
        """
        filtered = []
        for txn in transactions:
            try:
                txn_date = datetime.strptime(txn['date'], "%Y-%m-%d")
                if start_date <= txn_date <= end_date:
                    filtered.append(txn)
            except (ValueError, KeyError):
                continue

        return filtered
