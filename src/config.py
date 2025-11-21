"""Configuration management for YNAB-PayPal matcher."""
import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Configuration loader and validator."""

    def __init__(self, env_file: str = '.env'):
        """Load configuration from environment file.

        Args:
            env_file: Path to .env file (default: '.env')
        """
        # Load environment variables
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
        else:
            print(f"Warning: {env_file} not found. Using environment variables or defaults.")

        # YNAB Configuration
        self.ynab_token = os.getenv('YNAB_API_TOKEN')
        self.ynab_budget_id = os.getenv('YNAB_BUDGET_ID')

        # PayPal API Configuration (optional)
        self.paypal_client_id = os.getenv('PAYPAL_CLIENT_ID')
        self.paypal_client_secret = os.getenv('PAYPAL_CLIENT_SECRET')
        self.paypal_mode = os.getenv('PAYPAL_MODE', 'live')

        # PayPal CSV Configuration
        self.paypal_csv_path = os.getenv('PAYPAL_CSV_PATH', 'paypal_transactions.csv')
        self.paypal_date_format = os.getenv('PAYPAL_DATE_FORMAT', 'auto')

        # Matching Configuration
        self.date_tolerance_days = int(os.getenv('DATE_TOLERANCE_DAYS', '7'))
        self.amount_tolerance_percent = float(os.getenv('AMOUNT_TOLERANCE_PERCENT', '3.0'))

        # YNAB Filtering Configuration
        self.only_uncleared = os.getenv('YNAB_ONLY_UNCLEARED', 'false').lower() == 'true'
        self.only_unapproved = os.getenv('YNAB_ONLY_UNAPPROVED', 'true').lower() == 'true'

        # Parse PayPal keywords
        keywords_str = os.getenv('PAYPAL_KEYWORDS', 'PayPal,PAYPAL,Pp *')
        self.paypal_keywords = [k.strip() for k in keywords_str.split(',')]

    def validate_ynab(self) -> bool:
        """Validate YNAB configuration.

        Returns:
            True if valid, False otherwise
        """
        if not self.ynab_token:
            print("Error: YNAB_API_TOKEN not set")
            return False
        if not self.ynab_budget_id:
            print("Error: YNAB_BUDGET_ID not set")
            return False
        return True

    def validate_paypal_api(self) -> bool:
        """Validate PayPal API configuration.

        Returns:
            True if valid, False otherwise
        """
        return bool(self.paypal_client_id and self.paypal_client_secret)
