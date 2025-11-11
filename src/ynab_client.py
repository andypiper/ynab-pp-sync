"""YNAB API client for fetching transactions."""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class YNABClient:
    """Client for interacting with YNAB API."""

    BASE_URL = "https://api.ynab.com/v1"

    def __init__(self, api_token: str, budget_id: str):
        """Initialize YNAB client.

        Args:
            api_token: YNAB Personal Access Token
            budget_id: YNAB Budget ID
        """
        self.api_token = api_token
        self.budget_id = budget_id
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    def get_transactions(
        self,
        since_date: Optional[datetime] = None,
        account_id: Optional[str] = None
    ) -> List[Dict]:
        """Fetch transactions from YNAB.

        Args:
            since_date: Optional date to fetch transactions from (defaults to 90 days ago)
            account_id: Optional account ID to filter transactions

        Returns:
            List of transaction dictionaries

        Raises:
            requests.HTTPError: If API request fails
        """
        # Default to last 90 days if not specified
        if since_date is None:
            since_date = datetime.now() - timedelta(days=90)

        url = f"{self.BASE_URL}/budgets/{self.budget_id}/transactions"
        params = {
            "since_date": since_date.strftime("%Y-%m-%d")
        }

        if account_id:
            url = f"{self.BASE_URL}/budgets/{self.budget_id}/accounts/{account_id}/transactions"

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("transactions", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching YNAB transactions: {e}")
            raise

    def get_accounts(self) -> List[Dict]:
        """Fetch all accounts from YNAB budget.

        Returns:
            List of account dictionaries

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.BASE_URL}/budgets/{self.budget_id}/accounts"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("accounts", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching YNAB accounts: {e}")
            raise

    def update_transaction_memo(self, transaction_id: str, memo: str) -> bool:
        """Update a transaction's memo field.

        Args:
            transaction_id: YNAB transaction ID
            memo: New memo text

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.BASE_URL}/budgets/{self.budget_id}/transactions/{transaction_id}"

        payload = {
            "transaction": {
                "memo": memo
            }
        }

        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error updating transaction {transaction_id}: {e}")
            return False

    @staticmethod
    def parse_transaction(transaction: Dict) -> Dict:
        """Parse YNAB transaction into standardized format.

        Args:
            transaction: Raw YNAB transaction dictionary

        Returns:
            Parsed transaction dictionary
        """
        # YNAB amounts are in milliunits (divide by 1000)
        amount = transaction.get("amount", 0) / 1000.0

        return {
            "id": transaction.get("id"),
            "date": transaction.get("date"),
            "amount": amount,
            "payee_name": transaction.get("payee_name"),
            "memo": transaction.get("memo", ""),
            "account_id": transaction.get("account_id"),
            "category_name": transaction.get("category_name"),
            "cleared": transaction.get("cleared"),
            "approved": transaction.get("approved"),
            "flag_color": transaction.get("flag_color"),
            "raw": transaction
        }

    def find_paypal_transactions(
        self,
        paypal_keywords: List[str],
        since_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Find transactions that appear to be PayPal payments.

        Args:
            paypal_keywords: List of keywords to identify PayPal transactions
            since_date: Optional date to search from

        Returns:
            List of parsed PayPal transactions from YNAB
        """
        transactions = self.get_transactions(since_date=since_date)
        paypal_transactions = []

        for txn in transactions:
            payee_name = txn.get("payee_name", "").lower()
            memo = txn.get("memo", "").lower()

            # Check if any PayPal keyword appears in payee name or memo
            is_paypal = any(
                keyword.lower() in payee_name or keyword.lower() in memo
                for keyword in paypal_keywords
            )

            # Only include outgoing transactions (negative amounts)
            if is_paypal and txn.get("amount", 0) < 0:
                paypal_transactions.append(self.parse_transaction(txn))

        return paypal_transactions

    def test_connection(self) -> bool:
        """Test connection to YNAB API.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            url = f"{self.BASE_URL}/user"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"YNAB API connection failed: {e}")
            return False
