"""Export service for converting Statement objects to various formats.

Provides multiple export strategies:
- Pandas DataFrame (for data analysis)
- CSV (for spreadsheet import)
- OFX (Open Financial Exchange - for QuickBooks, Xero, etc.)
- QBO (QuickBooks Online format)
"""

import csv
from datetime import datetime
from io import StringIO
from typing import Optional

import pandas as pd

from ..models import Statement


class ExportService:
    """Application-layer service for exporting Statement domain objects.
    
    This service is format-agnostic and contains no parsing logic.
    It transforms validated Statement aggregates into various output formats.
    """
    
    @staticmethod
    def to_dataframe(statement: Statement) -> pd.DataFrame:
        """Export statement transactions to a Pandas DataFrame.
        
        Args:
            statement: Validated Statement aggregate
            
        Returns:
            DataFrame with columns: activity_date, post_date, reference_number,
            description, amount. Date columns are datetime64[ns].
        """
        rows = [
            {
                "activity_date":    t.activity_date,
                "post_date":        t.post_date,
                "reference_number": t.reference_number,
                "description":      t.description,
                "amount":           float(t.amount),
            }
            for t in statement.transactions
        ]
        df = pd.DataFrame(rows)
        if not df.empty:
            df["activity_date"] = pd.to_datetime(df["activity_date"])
            df["post_date"]     = pd.to_datetime(df["post_date"])
        return df
    
    @staticmethod
    def to_csv(statement: Statement, include_header: bool = True) -> str:
        """Export statement transactions to CSV format.
        
        Args:
            statement: Validated Statement aggregate
            include_header: Whether to include column headers
            
        Returns:
            CSV string with columns: activity_date, post_date, reference_number,
            description, amount
        """
        output = StringIO()
        writer = csv.writer(output)
        
        if include_header:
            writer.writerow([
                "activity_date",
                "post_date",
                "reference_number",
                "description",
                "amount"
            ])
        
        for t in statement.transactions:
            writer.writerow([
                t.activity_date.isoformat(),
                t.post_date.isoformat(),
                t.reference_number,
                t.description,
                str(t.amount)
            ])
        
        return output.getvalue()
    
    @staticmethod
    def to_ofx(statement: Statement, account_id: Optional[str] = None) -> str:
        """Export statement transactions to OFX (Open Financial Exchange) format.
        
        OFX is an XML-based format supported by QuickBooks, Xero, and most
        accounting software. The <FITID> tag maps to reference_number to
        prevent duplicate imports.
        
        Args:
            statement: Validated Statement aggregate
            account_id: Optional account identifier (defaults to account_suffix)
            
        Returns:
            OFX XML string
        """
        account_id = account_id or statement.account_suffix
        
        # OFX header (required by spec)
        ofx_lines = [
            "OFXHEADER:100",
            "DATA:OFXSGML",
            "VERSION:102",
            "SECURITY:NONE",
            "ENCODING:USASCII",
            "CHARSET:1252",
            "COMPRESSION:NONE",
            "OLDFILEUID:NONE",
            "NEWFILEUID:NONE",
            "",
            "<OFX>",
            "<SIGNONMSGSRSV1>",
            "<SONRS>",
            "<STATUS>",
            "<CODE>0",
            "<SEVERITY>INFO",
            "</STATUS>",
            f"<DTSERVER>{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "<LANGUAGE>ENG",
            "</SONRS>",
            "</SIGNONMSGSRSV1>",
            "<CREDITCARDMSGSRSV1>",
            "<CCSTMTTRNRS>",
            "<TRNUID>1",
            "<STATUS>",
            "<CODE>0",
            "<SEVERITY>INFO",
            "</STATUS>",
            "<CCSTMTRS>",
            "<CURDEF>USD",
            "<CCACCTFROM>",
            f"<ACCTID>{account_id}",
            "</CCACCTFROM>",
            "<BANKTRANLIST>",
            f"<DTSTART>{statement.billing_period_start.strftime('%Y%m%d')}",
            f"<DTEND>{statement.billing_period_end.strftime('%Y%m%d')}",
        ]
        
        # Transaction entries
        for t in statement.transactions:
            # OFX uses negative for credits, positive for debits (opposite of our model)
            ofx_amount = -float(t.amount)
            trntype = "CREDIT" if ofx_amount > 0 else "DEBIT"
            
            ofx_lines.extend([
                "<STMTTRN>",
                f"<TRNTYPE>{trntype}",
                f"<DTPOSTED>{t.post_date.strftime('%Y%m%d')}",
                f"<TRNAMT>{ofx_amount:.2f}",
                f"<FITID>{t.reference_number}",  # Critical: prevents duplicate imports
                f"<MEMO>{t.description}",
                "</STMTTRN>",
            ])
        
        # OFX footer
        ofx_lines.extend([
            "</BANKTRANLIST>",
            "<LEDGERBAL>",
            f"<BALAMT>{float(statement.balance_summary.new_balance):.2f}",
            f"<DTASOF>{statement.billing_period_end.strftime('%Y%m%d')}",
            "</LEDGERBAL>",
            "</CCSTMTRS>",
            "</CCSTMTTRNRS>",
            "</CREDITCARDMSGSRSV1>",
            "</OFX>",
        ])
        
        return "\n".join(ofx_lines)
    
    @staticmethod
    def to_qbo(statement: Statement, account_id: Optional[str] = None) -> str:
        """Export statement transactions to QBO (QuickBooks Online) format.
        
        QBO is essentially OFX with minor variations. This method is an alias
        for to_ofx() as QuickBooks accepts standard OFX format.
        
        Args:
            statement: Validated Statement aggregate
            account_id: Optional account identifier (defaults to account_suffix)
            
        Returns:
            QBO/OFX XML string
        """
        return ExportService.to_ofx(statement, account_id)


# Convenience functions for backward compatibility and simpler API
def to_df(statement: Statement) -> pd.DataFrame:
    """Export statement transactions to a Pandas DataFrame.
    
    Convenience function that delegates to ExportService.to_dataframe().
    """
    return ExportService.to_dataframe(statement)


def to_csv(statement: Statement, include_header: bool = True) -> str:
    """Export statement transactions to CSV format.
    
    Convenience function that delegates to ExportService.to_csv().
    """
    return ExportService.to_csv(statement, include_header)


def to_ofx(statement: Statement, account_id: Optional[str] = None) -> str:
    """Export statement transactions to OFX format.
    
    Convenience function that delegates to ExportService.to_ofx().
    """
    return ExportService.to_ofx(statement, account_id)


def to_qbo(statement: Statement, account_id: Optional[str] = None) -> str:
    """Export statement transactions to QBO format.
    
    Convenience function that delegates to ExportService.to_qbo().
    """
    return ExportService.to_qbo(statement, account_id)
