"""Tests for export service functionality."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from ccparse import TDStatementParser
from ccparse.export import ExportService, to_df, to_csv, to_ofx, to_qbo

PDF_PATH = Path(__file__).parent.parent / "docs" / "View PDF Statement_2024-08-03.pdf"


@pytest.fixture(scope="module")
def statement():
    return TDStatementParser().parse(str(PDF_PATH))


class TestPandasExport:
    """Tests for Pandas DataFrame export."""
    
    def test_to_df_returns_dataframe(self, statement):
        df = to_df(statement)
        assert isinstance(df, pd.DataFrame)
    
    def test_service_to_dataframe_returns_dataframe(self, statement):
        df = ExportService.to_dataframe(statement)
        assert isinstance(df, pd.DataFrame)
    
    def test_row_count(self, statement):
        df = to_df(statement)
        assert len(df) == 2
    
    def test_columns(self, statement):
        df = to_df(statement)
        expected_cols = ["activity_date", "post_date", "reference_number", "description", "amount"]
        assert list(df.columns) == expected_cols
    
    def test_activity_date_dtype(self, statement):
        df = to_df(statement)
        assert pd.api.types.is_datetime64_any_dtype(df["activity_date"])
    
    def test_post_date_dtype(self, statement):
        df = to_df(statement)
        assert pd.api.types.is_datetime64_any_dtype(df["post_date"])
    
    def test_amount_dtype(self, statement):
        df = to_df(statement)
        assert df["amount"].dtype == float
    
    def test_first_row_values(self, statement):
        df = to_df(statement)
        row = df.iloc[0]
        assert row["reference_number"] == "39053938"
        assert row["amount"] == 32.53
        assert row["description"] == statement.transactions[0].description


class TestCSVExport:
    """Tests for CSV export."""
    
    def test_to_csv_returns_string(self, statement):
        csv_output = to_csv(statement)
        assert isinstance(csv_output, str)
    
    def test_service_to_csv_returns_string(self, statement):
        csv_output = ExportService.to_csv(statement)
        assert isinstance(csv_output, str)
    
    def test_csv_has_header(self, statement):
        csv_output = to_csv(statement)
        lines = csv_output.strip().split("\n")
        # Strip any trailing \r from CSV output
        assert lines[0].strip() == "activity_date,post_date,reference_number,description,amount"
    
    def test_csv_without_header(self, statement):
        csv_output = to_csv(statement, include_header=False)
        lines = csv_output.strip().split("\n")
        assert not lines[0].startswith("activity_date")
    
    def test_csv_row_count(self, statement):
        csv_output = to_csv(statement)
        lines = csv_output.strip().split("\n")
        assert len(lines) == 3  # 1 header + 2 transactions
    
    def test_csv_first_transaction(self, statement):
        csv_output = to_csv(statement)
        lines = csv_output.strip().split("\n")
        # First transaction line (skip header)
        assert "2024-07-07" in lines[1]
        assert "39053938" in lines[1]
        assert "32.53" in lines[1]
    
    def test_csv_date_format(self, statement):
        csv_output = to_csv(statement)
        # Dates should be in ISO format (YYYY-MM-DD)
        assert "2024-07-07" in csv_output
        assert "2024-07-20" in csv_output


class TestOFXExport:
    """Tests for OFX export."""
    
    def test_to_ofx_returns_string(self, statement):
        ofx_output = to_ofx(statement)
        assert isinstance(ofx_output, str)
    
    def test_service_to_ofx_returns_string(self, statement):
        ofx_output = ExportService.to_ofx(statement)
        assert isinstance(ofx_output, str)
    
    def test_ofx_header(self, statement):
        ofx_output = to_ofx(statement)
        assert ofx_output.startswith("OFXHEADER:100")
        assert "DATA:OFXSGML" in ofx_output
        assert "VERSION:102" in ofx_output
    
    def test_ofx_contains_transactions(self, statement):
        ofx_output = to_ofx(statement)
        assert "<STMTTRN>" in ofx_output
        assert "</STMTTRN>" in ofx_output
    
    def test_ofx_fitid_mapping(self, statement):
        """FITID (Financial Institution Transaction ID) must map to reference_number."""
        ofx_output = to_ofx(statement)
        assert "<FITID>39053938" in ofx_output
        assert "<FITID>85474265" in ofx_output
    
    def test_ofx_transaction_dates(self, statement):
        ofx_output = to_ofx(statement)
        assert "<DTPOSTED>20240708" in ofx_output  # First transaction post date
        assert "<DTPOSTED>20240722" in ofx_output  # Second transaction post date
    
    def test_ofx_transaction_amounts(self, statement):
        ofx_output = to_ofx(statement)
        # OFX uses negative for credits, positive for debits (opposite of our model)
        # Our model: positive = spend, so OFX should be negative
        assert "<TRNAMT>-32.53" in ofx_output
        assert "<TRNAMT>-332.94" in ofx_output
    
    def test_ofx_account_id(self, statement):
        ofx_output = to_ofx(statement)
        assert f"<ACCTID>{statement.account_suffix}" in ofx_output
    
    def test_ofx_custom_account_id(self, statement):
        ofx_output = to_ofx(statement, account_id="CUSTOM123")
        assert "<ACCTID>CUSTOM123" in ofx_output
    
    def test_ofx_billing_period(self, statement):
        ofx_output = to_ofx(statement)
        assert "<DTSTART>20240704" in ofx_output
        assert "<DTEND>20240803" in ofx_output
    
    def test_ofx_balance(self, statement):
        ofx_output = to_ofx(statement)
        assert "<BALAMT>-1151.02" in ofx_output
    
    def test_ofx_transaction_descriptions(self, statement):
        ofx_output = to_ofx(statement)
        for t in statement.transactions:
            assert f"<MEMO>{t.description}" in ofx_output


class TestQBOExport:
    """Tests for QBO (QuickBooks Online) export."""
    
    def test_to_qbo_returns_string(self, statement):
        qbo_output = to_qbo(statement)
        assert isinstance(qbo_output, str)
    
    def test_service_to_qbo_returns_string(self, statement):
        qbo_output = ExportService.to_qbo(statement)
        assert isinstance(qbo_output, str)
    
    def test_qbo_is_ofx_format(self, statement):
        """QBO is essentially OFX format."""
        qbo_output = to_qbo(statement)
        ofx_output = to_ofx(statement)
        assert qbo_output == ofx_output
    
    def test_qbo_contains_fitid(self, statement):
        """QBO must have FITID for deduplication in QuickBooks."""
        qbo_output = to_qbo(statement)
        assert "<FITID>39053938" in qbo_output
        assert "<FITID>85474265" in qbo_output


class TestExportServiceAPI:
    """Tests for ExportService class API."""
    
    def test_service_has_all_methods(self):
        assert hasattr(ExportService, "to_dataframe")
        assert hasattr(ExportService, "to_csv")
        assert hasattr(ExportService, "to_ofx")
        assert hasattr(ExportService, "to_qbo")
    
    def test_all_methods_are_static(self):
        """All ExportService methods should be static (no instance required)."""
        import inspect
        for name in ["to_dataframe", "to_csv", "to_ofx", "to_qbo"]:
            method = getattr(ExportService, name)
            # Static methods don't have 'self' as first parameter
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())
            assert params[0] == "statement"  # First param should be statement, not self


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with original export.py API."""
    
    def test_can_import_to_df_from_export(self):
        from ccparse.export import to_df
        assert callable(to_df)
    
    def test_can_import_to_csv_from_export(self):
        from ccparse.export import to_csv
        assert callable(to_csv)
    
    def test_can_import_to_ofx_from_export(self):
        from ccparse.export import to_ofx
        assert callable(to_ofx)
    
    def test_can_import_to_qbo_from_export(self):
        from ccparse.export import to_qbo
        assert callable(to_qbo)
    
    def test_old_import_path_works(self, statement):
        """Original import path should still work."""
        from ccparse.export import to_df as old_to_df
        df = old_to_df(statement)
        assert isinstance(df, pd.DataFrame)
