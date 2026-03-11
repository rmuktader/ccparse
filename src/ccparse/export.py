"""Backward compatibility layer for export functions.

This module maintains the original API while delegating to the new export service.
"""

from .export import to_df, to_csv, to_ofx, to_qbo, ExportService

__all__ = ["to_df", "to_csv", "to_ofx", "to_qbo", "ExportService"]
