import re
from decimal import Decimal
from typing import List

from .base import StatementParser
from ..exceptions import BalanceMismatchError, DataIntegrityError, UnsupportedFormatError
from ..models import BalanceSummary, Statement, Transaction
from ..infrastructure.pdf_extractor import (
    PDFExtractor,
    parse_amount,
    parse_date,
    parse_billing_period,
    in_col,
    COL_ACTIVITY,
    COL_POST,
    COL_REF,
    COL_DESC,
    COL_AMOUNT,
    RE_TXN_DATE,
    RE_CURRENCY,
)


# Fingerprint tokens that uniquely identify a TD Business Visa statement.
_VISA_FINGERPRINTS = {"TDBUSINESSSOLUTIONS", "SummaryOfAccountActivity", "PreviousBalance"}


class TDBusinessVisaParser(StatementParser):
    """Concrete parser for TD Business Solutions Visa statements."""
    
    def parse(self, pdf_path: str) -> Statement:
        """Parse a TD Business Visa PDF statement with balance validation."""
        stmt = self._extract(pdf_path)
        self._validate_balance(stmt.balance_summary)
        return stmt
    
    def parse_unvalidated(self, pdf_path: str) -> Statement:
        """Parse without raising on balance mismatch. Use for diagnostics only."""
        return self._extract(pdf_path)
    
    def _extract(self, pdf_path: str) -> Statement:
        """Extract all fields without balance validation."""
        with PDFExtractor.open(pdf_path) as pdf:
            page1_rows = PDFExtractor.extract_rows(pdf.pages[0])
            self._assert_visa_statement(page1_rows, pdf_path)

            header  = self._extract_header(page1_rows)
            balance = self._extract_balance_summary(page1_rows)
            points  = self._extract_points(page1_rows)

            billing_start, billing_end = parse_billing_period(
                header["billing"][0], header["billing"][1]
            )
            transactions = self._extract_transactions(
                pdf.pages, billing_end.year, billing_end.month
            )

        return Statement(
            entity_name=header.get("entity", ""),
            primary_cardholder=header.get("cardholder", ""),
            account_suffix=header.get("suffix", ""),
            billing_period_start=billing_start,
            billing_period_end=billing_end,
            balance_summary=balance,
            current_points=points,
            transactions=transactions,
        )
    
    def _assert_visa_statement(self, rows: list[list[dict]], pdf_path: str) -> None:
        """Verify the PDF is a TD Business Visa statement by checking fingerprints."""
        all_text = "".join(w["text"] for row in rows for w in row)
        missing = [f for f in _VISA_FINGERPRINTS if f not in all_text]
        if missing:
            raise UnsupportedFormatError(
                f"{pdf_path!r} is not a TD Business Solutions Visa statement. "
                f"Missing expected markers: {missing}"
            )
    
    def _extract_header(self, rows: list[list[dict]]) -> dict:
        """Extract statement metadata from page 1 header."""
        result = {}
        for row in rows:
            joined = "".join(w["text"] for w in row)
            top = row[0]["top"]
            x0  = row[0]["x0"]

            if not result.get("cardholder") and x0 > 400 and top < 35:
                result["cardholder"] = row[0]["text"]

            if not result.get("entity") and x0 > 400 and 35 < top < 50:
                result["entity"] = row[0]["text"]

            if not result.get("suffix") and "AccountNumberEndingin:" in joined:
                if m := re.search(r"(\d{4})$", joined):
                    result["suffix"] = m[1]

            if  m := re.search(
                r"(\w+\d+,\d{4})-(\w+\d+,\d{4})", joined.replace(" ", "")
            ):
                result["billing"] = m[1], m[2]

        return result
    
    def _extract_balance_summary(self, rows: list[list[dict]]) -> BalanceSummary:
        """Extract balance summary from page 1."""
        # Map label text → field key. We find the currency token to the RIGHT
        # of the label word on the same row — handles the two-column page layout.
        label_map = {
            "PreviousBalance":   "previous_balance",
            "Payments":          "payments",
            "Purchases":         "purchases",
            "OtherCredits":      "credits",
            "FeesCharged":       "fees",
            "InterestCharged":   "interest",
            "NewBalance":        "new_balance",
            "Available":         "available_credit",
            "MinimumPaymentDue": "minimum_payment",
        }
        values = {}

        for row in rows:
            joined = "".join(w["text"] for w in row)
            for label, key in label_map.items():
                if key in values:
                    continue
                if label not in joined:
                    continue
                # Find x0 of the label word itself
                label_x = next(
                    (w["x0"] for w in row if label in w["text"]), 0
                )
                # Take the leftmost currency token that appears after the label
                candidates = [
                    w for w in row
                    if w["x0"] > label_x and RE_CURRENCY.search(w["text"])
                ]
                if not candidates:
                    continue
                best = min(candidates, key=lambda w: w["x0"])
                raw = best["text"]
                amount = parse_amount(raw)
                if raw.startswith("-"):
                    amount = -abs(amount)
                values[key] = amount

        if missing := [k for k in label_map.values() if k not in values]:
            raise DataIntegrityError(f"Missing balance fields: {missing}")

        return BalanceSummary(**values)
    
    def _extract_points(self, rows: list[list[dict]]) -> int | None:
        """Extract current rewards points from page 1."""
        for row in rows:
            if "NewPointsBalance" in "".join(w["text"] for w in row):
                for w in reversed(row):
                    try:
                        return int(w["text"].replace(",", ""))
                    except ValueError:
                        continue
        return None
    
    def _extract_transactions(self, pages, year: int, billing_end_month: int) -> List[Transaction]:
        """Extract all transactions from the statement pages."""
        transactions: List[Transaction] = []
        in_transactions = False
        stop_labels = {"Fees", "TOTALFEESFORTHISPERIOD", "TotalFees"}

        for page in pages:
            rows = PDFExtractor.extract_rows(page)
            for row in rows:
                joined = "".join(w["text"] for w in row)

                # Enter transaction section
                if not in_transactions:
                    if joined.strip() == "Transactions":
                        in_transactions = True
                    continue

                # Exit transaction section at Fees header
                if any(s in joined for s in stop_labels):
                    return transactions

                # Skip column header and card-number rows
                if "ActivityDate" in joined or "CardNumberEnding" in joined:
                    continue

                date_words = [w for w in row if in_col(w, COL_ACTIVITY) and RE_TXN_DATE.match(w["text"])]

                if not date_words:
                    # Description continuation line — append to last transaction
                    desc_words = [w for w in row if in_col(w, COL_DESC)]
                    if desc_words and transactions:
                        extra = " ".join(w["text"] for w in desc_words)
                        last = transactions[-1]
                        transactions[-1] = Transaction(
                            activity_date=last.activity_date,
                            post_date=last.post_date,
                            reference_number=last.reference_number,
                            description=f"{last.description} {extra}",
                            amount=last.amount,
                        )
                    continue

                post_words = [w for w in row if in_col(w, COL_POST)]
                ref_words  = [w for w in row if in_col(w, COL_REF)]
                desc_words = [w for w in row if in_col(w, COL_DESC)]
                amt_words  = [w for w in row if in_col(w, COL_AMOUNT)]

                if not (post_words and ref_words and amt_words):
                    continue

                # Year-boundary: Jan transaction in a Dec-ending billing period
                act_raw = date_words[0]["text"]
                txn_year = year + 1 if (act_raw[:3] == "Jan" and billing_end_month == 12) else year

                transactions.append(Transaction(
                    activity_date=parse_date(act_raw, txn_year),
                    post_date=parse_date(post_words[0]["text"], txn_year),
                    reference_number=ref_words[0]["text"],
                    description=" ".join(w["text"] for w in desc_words),
                    amount=parse_amount(amt_words[0]["text"]),
                ))

        return transactions
    
    def _validate_balance(self, summary: BalanceSummary) -> None:
        """Validate the Golden Equation: Previous + Purchases - Credits + Fees + Interest = New."""
        calculated = self._calculate_balance(summary)
        if calculated != summary.new_balance:
            raise BalanceMismatchError(
                f"Balance mismatch: calculated={calculated}, stated={summary.new_balance}"
            )
    
    def _calculate_balance(self, summary: BalanceSummary) -> Decimal:
        """Calculate expected new balance from summary components."""
        return (
            summary.previous_balance
            + summary.payments
            + summary.purchases
            - summary.credits
            + summary.fees
            + summary.interest
        )
