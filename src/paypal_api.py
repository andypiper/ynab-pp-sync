"""PayPal API client for fetching transactions (Business accounts only)."""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class PayPalAPIClient:
    """Client for interacting with PayPal REST API.

    Note: Requires Business account with Transaction Search permission enabled.
    """

    SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
    LIVE_BASE_URL = "https://api-m.paypal.com"

    def __init__(self, client_id: str, client_secret: str, mode: str = 'live'):
        """Initialize PayPal API client.

        Args:
            client_id: PayPal REST API client ID
            client_secret: PayPal REST API client secret
            mode: 'sandbox' or 'live' (default: 'live')
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.mode = mode.lower()
        self.base_url = self.SANDBOX_BASE_URL if self.mode == 'sandbox' else self.LIVE_BASE_URL
        self.access_token = None
        self.token_expiry = None

    def _get_access_token(self) -> str:
        """Get OAuth access token.

        Returns:
            Access token string

        Raises:
            requests.HTTPError: If authentication fails
        """
        # Check if we have a valid cached token
        if self.access_token and self.token_expiry:
            if datetime.now() < self.token_expiry:
                return self.access_token

        # Request new token
        url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US"
        }
        data = {
            "grant_type": "client_credentials",
            "scope": "https://uri.paypal.com/services/reporting/search/read"
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                data=data,
                auth=(self.client_id, self.client_secret)
            )
            response.raise_for_status()

            result = response.json()
            self.access_token = result['access_token']

            # Set expiry time (subtract 60 seconds as buffer)
            expires_in = result.get('expires_in', 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)

            return self.access_token

        except requests.exceptions.RequestException as e:
            print(f"Error authenticating with PayPal API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise

    def get_transactions(
        self,
        start_date: datetime,
        end_date: datetime,
        transaction_status: str = 'S'
    ) -> List[Dict]:
        """Fetch transactions from PayPal Transaction Search API.

        Args:
            start_date: Start date for transaction search
            end_date: End date for transaction search (max 31 days from start_date)
            transaction_status: Transaction status filter (S=Success, default)

        Returns:
            List of transaction dictionaries

        Raises:
            requests.HTTPError: If API request fails
            ValueError: If date range exceeds 31 days
        """
        # Validate date range (PayPal API limitation)
        if (end_date - start_date).days > 31:
            raise ValueError("Date range cannot exceed 31 days for PayPal Transaction Search API")

        token = self._get_access_token()
        url = f"{self.base_url}/v1/reporting/transactions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        params = {
            "start_date": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "end_date": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "transaction_status": transaction_status,
            "fields": "all",
            "page_size": 500
        }

        all_transactions = []
        page = 1

        try:
            while True:
                params['page'] = page
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()

                data = response.json()
                transaction_details = data.get('transaction_details', [])

                if not transaction_details:
                    break

                all_transactions.extend(transaction_details)

                # Check if there are more pages
                total_pages = data.get('total_pages', 1)
                if page >= total_pages:
                    break

                page += 1

        except requests.exceptions.RequestException as e:
            print(f"Error fetching PayPal transactions: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise

        print(f"Fetched {len(all_transactions)} transactions from PayPal API")
        return all_transactions

    @staticmethod
    def parse_transaction(transaction: Dict) -> Dict:
        """Parse PayPal API transaction into standardized format.

        Args:
            transaction: Raw PayPal API transaction dictionary

        Returns:
            Parsed transaction dictionary
        """
        txn_info = transaction.get('transaction_info', {})
        payer_info = transaction.get('payer_info', {})

        # Extract transaction amount
        amount_info = txn_info.get('transaction_amount', {})
        currency = amount_info.get('currency_code', 'GBP')
        amount = float(amount_info.get('value', 0))

        # Parse date
        date_str = txn_info.get('transaction_initiation_date', '')
        try:
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            date = date_str[:10] if date_str else ''

        # Get payer/merchant name
        payer_name = payer_info.get('payer_name', {})
        merchant_name = f"{payer_name.get('given_name', '')} {payer_name.get('surname', '')}".strip()
        if not merchant_name:
            merchant_name = payer_info.get('email_address', 'Unknown')

        return {
            'date': date,
            'merchant_name': merchant_name,
            'type': txn_info.get('transaction_event_code', ''),
            'status': txn_info.get('transaction_status', ''),
            'currency': currency,
            'gross_amount': abs(amount),
            'net_amount': abs(amount),
            'item_title': '',
            'transaction_id': txn_info.get('transaction_id', ''),
            'raw': transaction
        }

    def get_transactions_for_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Fetch and parse transactions for a date range, handling 31-day limitation.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of parsed transactions
        """
        all_transactions = []
        current_start = start_date

        # Split into 31-day chunks if necessary
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=31), end_date)

            raw_transactions = self.get_transactions(current_start, current_end)
            parsed_transactions = [self.parse_transaction(txn) for txn in raw_transactions]

            # Filter for outgoing payments only
            outgoing = [txn for txn in parsed_transactions if txn['gross_amount'] > 0]
            all_transactions.extend(outgoing)

            current_start = current_end + timedelta(days=1)

        return all_transactions

    def test_connection(self) -> bool:
        """Test connection to PayPal API.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            self._get_access_token()
            return True
        except Exception as e:
            print(f"PayPal API connection failed: {e}")
            return False
