from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from td_parser import TDStatementParser, BalanceMismatchError, DataIntegrityError
from td_parser.models import BalanceSummary
from td_parser.parser import _parse_amount, _parse_date, _validate_balance

PDF_PATH = Path(__file__).parent.parent / "docs" / "View PDF Statement_2024-08-03.pdf"


# ---------------------------------------------------------------------------
# Unit tests — pure functions, no PDF required
# ---------------------------------------------------------------------------

class TestParseAmount:
    def test_cr_returns_negative(self):
        assert _parse_amount("$1,516.49CR") == Decimal("-1516.49")

    def test_cr_with_space(self):
        assert _parse_amount("$1,151.02 CR") == Decimal("-1151.02")

    def test_positive_amount(self):
        assert _parse_amount("$365.47") == Decimal("365.47")

    def test_plus_prefix(self):
        assert _parse_amount("+$365.47") == Decimal("365.47")

    def test_zero(self):
        assert _parse_amount("$0.00") == Decimal("0.00")

    def test_invalid_raises(self):
        with pytest.raises(DataIntegrityError):
            _parse_amount("not-a-number")


class TestParseDate:
    def test_no_space(self):
        assert _parse_date("Jul07", 2024) == date(2024, 7, 7)

    def test_with_space(self):
        assert _parse_date("Jul 07", 2024) == date(2024, 7, 7)

    def test_year_boundary(self):
        assert _parse_date("Jan03", 2025) == date(2025, 1, 3)


class TestValidateBalance:
    def _summary(self, **overrides):
        defaults = dict(
            previous_balance=Decimal("-1516.49"),
            purchases=Decimal("365.47"),
            credits=Decimal("0.00"),
            fees=Decimal("0.00"),
            interest=Decimal("0.00"),
            new_balance=Decimal("-1151.02"),
            available_credit=Decimal("20000.00"),
            minimum_payment=Decimal("0.00"),
        )
        defaults.update(overrides)
        return BalanceSummary(**defaults)

    def test_valid_passes(self):
        _validate_balance(self._summary())  # no exception

    def test_mismatch_raises(self):
        with pytest.raises(BalanceMismatchError):
            _validate_balance(self._summary(new_balance=Decimal("-9999.99")))


# ---------------------------------------------------------------------------
# Integration tests — require the real PDF
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def statement():
    return TDStatementParser().parse(str(PDF_PATH))


class TestStatementMetadata:
    def test_account_suffix(self, statement):
        assert statement.account_suffix == "5679"

    def test_billing_period_start(self, statement):
        assert statement.billing_period_start == date(2024, 7, 4)

    def test_billing_period_end(self, statement):
        assert statement.billing_period_end == date(2024, 8, 3)


class TestBalanceSummary:
    def test_new_balance(self, statement):
        assert statement.balance_summary.new_balance == Decimal("-1151.02")

    def test_previous_balance(self, statement):
        assert statement.balance_summary.previous_balance == Decimal("-1516.49")

    def test_purchases(self, statement):
        assert statement.balance_summary.purchases == Decimal("365.47")

    def test_minimum_payment(self, statement):
        assert statement.balance_summary.minimum_payment == Decimal("0.00")

    def test_golden_equation(self, statement):
        s = statement.balance_summary
        assert s.previous_balance + s.purchases - s.credits + s.fees + s.interest == s.new_balance


class TestTransactions:
    def test_transaction_count(self, statement):
        assert len(statement.transactions) == 2

    def test_first_transaction(self, statement):
        t = statement.transactions[0]
        assert t.activity_date == date(2024, 7, 7)
        assert t.post_date == date(2024, 7, 8)
        assert t.reference_number == "39053938"
        assert t.amount == Decimal("32.53")

    def test_second_transaction(self, statement):
        t = statement.transactions[1]
        assert t.activity_date == date(2024, 7, 20)
        assert t.reference_number == "85474265"
        assert t.amount == Decimal("332.94")

    def test_purchase_total_matches_balance(self, statement):
        total = sum(t.amount for t in statement.transactions)
        assert total == statement.balance_summary.purchases


class TestRewards:
    def test_current_points(self, statement):
        assert statement.current_points == 6050


class TestDataFrameExport:
    def test_returns_dataframe(self, statement):
        from td_parser.export import to_df
        df = to_df(statement)
        assert isinstance(df, pd.DataFrame)

    def test_row_count(self, statement):
        from td_parser.export import to_df
        df = to_df(statement)
        assert len(df) == 2

    def test_activity_date_dtype(self, statement):
        from td_parser.export import to_df
        df = to_df(statement)
        assert pd.api.types.is_datetime64_any_dtype(df["activity_date"])

    def test_post_date_dtype(self, statement):
        from td_parser.export import to_df
        df = to_df(statement)
        assert pd.api.types.is_datetime64_any_dtype(df["post_date"])
