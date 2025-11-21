"""Transaction matching logic for YNAB and PayPal transactions."""
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional


class TransactionMatcher:
    """Match YNAB transactions with PayPal transactions."""

    def __init__(
        self,
        date_tolerance_days: int = 7,
        amount_tolerance_percent: float = 3.0
    ):
        """Initialize transaction matcher.

        Args:
            date_tolerance_days: Number of days before YNAB transaction to search
            amount_tolerance_percent: Percentage tolerance for amount matching
        """
        self.date_tolerance_days = date_tolerance_days
        self.amount_tolerance_percent = amount_tolerance_percent

    def match_transactions(
        self,
        ynab_transactions: List[Dict],
        paypal_transactions: List[Dict]
    ) -> List[Dict]:
        """Match YNAB transactions with PayPal transactions.

        Args:
            ynab_transactions: List of YNAB transactions (already filtered for PayPal)
            paypal_transactions: List of PayPal transactions

        Returns:
            List of match dictionaries containing YNAB and PayPal transaction info
        """
        matches = []
        matched_paypal_ids = set()

        for ynab_txn in ynab_transactions:
            # Find best match for this YNAB transaction
            best_match = self._find_best_match(
                ynab_txn,
                paypal_transactions,
                matched_paypal_ids
            )

            if best_match:
                paypal_txn, score = best_match
                matches.append({
                    'ynab': ynab_txn,
                    'paypal': paypal_txn,
                    'score': score,
                    'confidence': self._get_confidence_level(score)
                })
                # Mark this PayPal transaction as matched
                matched_paypal_ids.add(paypal_txn.get('transaction_id'))
            else:
                # No match found
                matches.append({
                    'ynab': ynab_txn,
                    'paypal': None,
                    'score': 0,
                    'confidence': 'no_match'
                })

        return matches

    def _find_best_match(
        self,
        ynab_txn: Dict,
        paypal_transactions: List[Dict],
        already_matched: set
    ) -> Optional[Tuple[Dict, float]]:
        """Find the best matching PayPal transaction for a YNAB transaction.

        Args:
            ynab_txn: YNAB transaction to match
            paypal_transactions: List of PayPal transactions
            already_matched: Set of already matched PayPal transaction IDs

        Returns:
            Tuple of (paypal_transaction, match_score) or None if no match
        """
        best_match = None
        best_score = 0.0
        min_score_threshold = 0.5

        ynab_date = datetime.strptime(ynab_txn['date'], "%Y-%m-%d")
        ynab_amount = abs(ynab_txn['amount'])

        for pp_txn in paypal_transactions:
            # Skip already matched transactions
            if pp_txn.get('transaction_id') in already_matched:
                continue

            # Calculate match score
            score = self._calculate_match_score(
                ynab_date,
                ynab_amount,
                pp_txn
            )

            # Update best match if this score is higher
            if score > best_score and score >= min_score_threshold:
                best_score = score
                best_match = pp_txn

        if best_match:
            return (best_match, best_score)
        return None

    def _calculate_match_score(
        self,
        ynab_date: datetime,
        ynab_amount: float,
        paypal_txn: Dict
    ) -> float:
        """Calculate match score between YNAB and PayPal transaction.

        Args:
            ynab_date: YNAB transaction date
            ynab_amount: YNAB transaction amount (positive)
            paypal_txn: PayPal transaction dictionary

        Returns:
            Match score between 0.0 and 1.0
        """
        try:
            pp_date = datetime.strptime(paypal_txn['date'], "%Y-%m-%d")
        except (ValueError, KeyError):
            return 0.0

        # Date score: PayPal transaction should be 0-N days BEFORE YNAB transaction
        date_diff = (ynab_date - pp_date).days

        if date_diff < 0 or date_diff > self.date_tolerance_days:
            # Outside acceptable date range
            return 0.0

        # Score based on date proximity (closer = higher score)
        # 0 days = 1.0, max days = 0.5
        date_score = 1.0 - (date_diff / self.date_tolerance_days) * 0.5

        # Amount score: Compare amounts with tolerance
        pp_amount = paypal_txn.get('gross_amount', 0)
        if pp_amount == 0:
            return 0.0

        # Calculate percentage difference
        amount_diff_percent = abs(ynab_amount - pp_amount) / pp_amount * 100

        if amount_diff_percent > self.amount_tolerance_percent:
            # Outside acceptable tolerance
            # But give partial score if close
            if amount_diff_percent <= self.amount_tolerance_percent * 2:
                amount_score = 0.3
            else:
                return 0.0
        else:
            # Within tolerance - score based on accuracy
            # Exact match = 1.0, at tolerance = 0.7
            amount_score = 1.0 - (amount_diff_percent / self.amount_tolerance_percent) * 0.3

        # Currency bonus: If PayPal is in GBP, higher confidence
        currency_bonus = 0.1 if paypal_txn.get('currency', '').upper() == 'GBP' else 0.0

        # Weighted total score
        # Date: 40%, Amount: 50%, Currency bonus: 10%
        total_score = (date_score * 0.4) + (amount_score * 0.5) + currency_bonus

        return min(total_score, 1.0)

    @staticmethod
    def _get_confidence_level(score: float) -> str:
        """Get confidence level from match score.

        Args:
            score: Match score (0.0-1.0)

        Returns:
            Confidence level string
        """
        if score >= 0.9:
            return 'high'
        elif score >= 0.7:
            return 'medium'
        elif score >= 0.5:
            return 'low'
        else:
            return 'very_low'

    @staticmethod
    def format_match_output(matches: List[Dict], show_unmatched: bool = True) -> str:
        """Format matches for display.

        Args:
            matches: List of match dictionaries
            show_unmatched: Whether to show unmatched transactions

        Returns:
            Formatted string for display
        """
        output_lines = []
        output_lines.append("=" * 100)
        output_lines.append("YNAB-PayPal Transaction Matches")
        output_lines.append("=" * 100)
        output_lines.append("")

        # Statistics
        total = len(matches)
        matched = sum(1 for m in matches if m['paypal'] is not None)
        output_lines.append(f"Total YNAB PayPal transactions: {total}")
        output_lines.append(f"Matched: {matched} ({matched/total*100:.1f}%)")
        output_lines.append(f"Unmatched: {total - matched}")
        output_lines.append("")
        output_lines.append("=" * 100)
        output_lines.append("")

        # Matched transactions
        high_conf = [m for m in matches if m['confidence'] == 'high']
        med_conf = [m for m in matches if m['confidence'] == 'medium']
        low_conf = [m for m in matches if m['confidence'] in ['low', 'very_low']]
        unmatched = [m for m in matches if m['paypal'] is None]

        if high_conf:
            output_lines.append(f"HIGH CONFIDENCE MATCHES ({len(high_conf)}):")
            output_lines.append("-" * 100)
            for match in high_conf:
                output_lines.extend(TransactionMatcher._format_single_match(match))
                output_lines.append("")

        if med_conf:
            output_lines.append(f"MEDIUM CONFIDENCE MATCHES ({len(med_conf)}):")
            output_lines.append("-" * 100)
            for match in med_conf:
                output_lines.extend(TransactionMatcher._format_single_match(match))
                output_lines.append("")

        if low_conf:
            output_lines.append(f"LOW CONFIDENCE MATCHES ({len(low_conf)}):")
            output_lines.append("-" * 100)
            for match in low_conf:
                output_lines.extend(TransactionMatcher._format_single_match(match))
                output_lines.append("")

        if show_unmatched and unmatched:
            output_lines.append(f"UNMATCHED YNAB TRANSACTIONS ({len(unmatched)}):")
            output_lines.append("-" * 100)
            for match in unmatched:
                ynab = match['ynab']
                output_lines.append(f"YNAB: {ynab['date']} | £{abs(ynab['amount']):.2f} | {ynab['payee_name']}")
                if ynab.get('memo'):
                    output_lines.append(f"      Memo: {ynab['memo']}")
                output_lines.append("")

        return "\n".join(output_lines)

    @staticmethod
    def _format_single_match(match: Dict) -> List[str]:
        """Format a single match for display.

        Args:
            match: Match dictionary

        Returns:
            List of formatted lines
        """
        lines = []
        ynab = match['ynab']
        paypal = match['paypal']

        if paypal:
            # YNAB transaction
            lines.append(f"YNAB:   {ynab['date']} | £{abs(ynab['amount']):.2f} | {ynab['payee_name']}")
            if ynab.get('memo'):
                lines.append(f"        Memo: {ynab['memo']}")

            # PayPal transaction
            currency_display = f"{paypal['currency']} " if paypal['currency'] != 'GBP' else '£'
            lines.append(f"PayPal: {paypal['date']} | {currency_display}{paypal['gross_amount']:.2f} | {paypal['merchant_name']}")
            if paypal.get('item_title'):
                lines.append(f"        Item: {paypal['item_title']}")

            # Match info
            days_diff = (datetime.strptime(ynab['date'], "%Y-%m-%d") -
                        datetime.strptime(paypal['date'], "%Y-%m-%d")).days
            lines.append(f"Match:  Score: {match['score']:.2f} | Confidence: {match['confidence'].upper()} | Days diff: {days_diff}")

        return lines

    @staticmethod
    def generate_update_script(matches: List[Dict], min_confidence: str = 'medium') -> List[Dict]:
        """Generate list of YNAB updates for matched transactions.

        Args:
            matches: List of match dictionaries
            min_confidence: Minimum confidence level to include (high, medium, low)

        Returns:
            List of update dictionaries for YNAB API
        """
        confidence_levels = {
            'high': ['high'],
            'medium': ['high', 'medium'],
            'low': ['high', 'medium', 'low']
        }
        allowed_confidence = confidence_levels.get(min_confidence, ['high'])

        updates = []
        for match in matches:
            if match['paypal'] and match['confidence'] in allowed_confidence:
                ynab = match['ynab']
                paypal = match['paypal']

                # Create new memo with PayPal merchant info
                merchant = paypal['merchant_name']
                item = paypal.get('item_title', '')
                currency = paypal['currency']
                amount = paypal['gross_amount']

                new_memo_parts = [merchant]
                if item:
                    new_memo_parts.append(f"({item})")
                if currency != 'GBP':
                    new_memo_parts.append(f"[{currency} {amount:.2f}]")

                new_memo = " ".join(new_memo_parts)

                updates.append({
                    'transaction_id': ynab['id'],
                    'new_memo': new_memo,
                    'merchant_name': merchant,
                    'confidence': match['confidence']
                })

        return updates
