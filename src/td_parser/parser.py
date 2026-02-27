import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from itertools import groupby
from typing import List

import pdfplumber

from .exceptions import BalanceMismatchError, DataIntegrityError
from .models import BalanceSummary, Statement, Transaction

# ---------------------------------------------------------------------------
# Column x-coordinate anchors from statement_extracted.txt (page 3 WORDS)
# Activity Date:  x0 ≈ 82.5   → (70,  115)
# Post Date:      x0 ≈ 138.4  → (125, 165)
# Reference #:    x0 ≈ 197.7  → (185, 230)
# Description:    x0 ≈ 265.1  → (255, 510)
# Amount:         x0 > 520    → (515, 580)
# ---------------------------------------------------------------------------
_COL_ACTIVITY = (70,  115)
_COL_POST     = (125, 165)
_COL_REF      = (185, 230)
_COL_DESC     = (255, 510)
_COL_AMOUNT   = (515, 580)

_MONTH_ABBR   = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
_RE_TXN_DATE  = re.compile(rf"^{_MONTH_ABBR}\d{{2}}$")
_RE_CURRENCY  = re.compile(r"\$[\d,]+\.\d{2}(?:CR)?")


def _words_by_row(page) -> list[list[dict]]:
    words = page.extract_words(x_tolerance=3, y_tolerance=3)
    rows = []
    for _, grp in groupby(sorted(words, key=lambda w: round(w["top"])), key=lambda w: round(w["top"])):
        rows.append(sorted(grp, key=lambda w: w["x0"]))
    return rows


def _in_col(word: dict, col: tuple) -> bool:
    return col[0] <= word["x0"] <= col[1]


def _parse_amount(raw: str) -> Decimal:
    is_credit = "CR" in raw.upper()
    cleaned = re.sub(r"[+\-$,CR\s]", "", raw.upper())
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise DataIntegrityError(f"Cannot parse amount: {raw!r}")
    return -value if is_credit else value


def _parse_date(raw: str, year: int) -> date:
    """Parse 'Jul07' (no space) or 'Jul 07' into a date."""
    if len(raw) > 3 and raw[3].isdigit():
        raw = raw[:3] + " " + raw[3:]
    return datetime.strptime(f"{raw} {year}", "%b %d %Y").date()


def _extract_header(rows: list[list[dict]]) -> dict:
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
            m = re.search(r"(\d{4})$", joined)
            if m:
                result["suffix"] = m.group(1)

        if not result.get("billing") and top < 70:
            cleaned = joined.replace(" ", "")
            m = re.search(r"(\w+\d+,\d{4})-(\w+\d+,\d{4})", cleaned)
            if m:
                result["billing"] = (m.group(1), m.group(2))

    return result


def _parse_billing_period(start_str: str, end_str: str) -> tuple[date, date]:
    start = datetime.strptime(start_str, "%B%d,%Y").date()
    end   = datetime.strptime(end_str,   "%B%d,%Y").date()
    return start, end


def _extract_balance_summary(rows: list[list[dict]]) -> BalanceSummary:
    # Map label text → field key. We find the currency token to the RIGHT
    # of the label word on the same row — handles the two-column page layout.
    label_map = {
        "PreviousBalance":   "previous_balance",
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
                if w["x0"] > label_x and _RE_CURRENCY.search(w["text"])
            ]
            if not candidates:
                continue
            best = min(candidates, key=lambda w: w["x0"])
            raw = best["text"]
            amount = _parse_amount(raw)
            if raw.startswith("-"):
                amount = -abs(amount)
            values[key] = amount

    missing = [k for k in label_map.values() if k not in values]
    if missing:
        raise DataIntegrityError(f"Missing balance fields: {missing}")

    return BalanceSummary(**values)


def _extract_points(rows: list[list[dict]]) -> int:
    for row in rows:
        if "NewPointsBalance" in "".join(w["text"] for w in row):
            for w in reversed(row):
                try:
                    return int(w["text"].replace(",", ""))
                except ValueError:
                    continue
    raise DataIntegrityError("NewPointsBalance not found")


def _extract_transactions(pages, year: int, billing_end_month: int) -> List[Transaction]:
    transactions: List[Transaction] = []
    in_transactions = False
    stop_labels = {"Fees", "TOTALFEESFORTHISPERIOD", "TotalFees"}

    for page in pages:
        rows = _words_by_row(page)
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

            date_words = [w for w in row if _in_col(w, _COL_ACTIVITY) and _RE_TXN_DATE.match(w["text"])]

            if not date_words:
                # Description continuation line — append to last transaction
                desc_words = [w for w in row if _in_col(w, _COL_DESC)]
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

            post_words = [w for w in row if _in_col(w, _COL_POST)]
            ref_words  = [w for w in row if _in_col(w, _COL_REF)]
            desc_words = [w for w in row if _in_col(w, _COL_DESC)]
            amt_words  = [w for w in row if _in_col(w, _COL_AMOUNT)]

            if not (post_words and ref_words and amt_words):
                continue

            # Year-boundary: Jan transaction in a Dec-ending billing period
            act_raw = date_words[0]["text"]
            txn_year = year + 1 if (act_raw[:3] == "Jan" and billing_end_month == 12) else year

            transactions.append(Transaction(
                activity_date=_parse_date(act_raw, txn_year),
                post_date=_parse_date(post_words[0]["text"], txn_year),
                reference_number=ref_words[0]["text"],
                description=" ".join(w["text"] for w in desc_words),
                amount=_parse_amount(amt_words[0]["text"]),
            ))

    return transactions


def _validate_balance(summary: BalanceSummary) -> None:
    calculated = (
        summary.previous_balance
        + summary.purchases
        - summary.credits
        + summary.fees
        + summary.interest
    )
    if calculated != summary.new_balance:
        raise BalanceMismatchError(
            f"Balance mismatch: calculated={calculated}, stated={summary.new_balance}"
        )


class TDStatementParser:
    def parse(self, pdf_path: str) -> Statement:
        with pdfplumber.open(pdf_path) as pdf:
            page1_rows = _words_by_row(pdf.pages[0])

            header  = _extract_header(page1_rows)
            balance = _extract_balance_summary(page1_rows)
            points  = _extract_points(page1_rows)

            billing_start, billing_end = _parse_billing_period(
                header["billing"][0], header["billing"][1]
            )
            transactions = _extract_transactions(
                pdf.pages, billing_end.year, billing_end.month
            )

        _validate_balance(balance)

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
