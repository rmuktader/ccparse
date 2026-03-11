"""Backward compatibility layer for the original TDStatementParser API.

This module maintains the public API while delegating to the new layered architecture.
"""

from .parsers.td_business_visa import TDBusinessVisaParser


class TDStatementParser(TDBusinessVisaParser):
    """TD Business Solutions Visa statement parser.
    
    This class maintains backward compatibility with the original API.
    It delegates to TDBusinessVisaParser which implements the Strategy Pattern.
    """
    pass
