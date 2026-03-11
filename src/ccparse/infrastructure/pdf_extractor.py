import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from itertools import groupby

import pdfplumber

from ..exceptions import DataIntegrityError

# ---------------------------------------------------------------------------
# Column x-coordinate anchors from statement_extracted.txt (page 3 WORDS)
# Activity Date:  x0 ≈ 82.5   → (70,  115)
# Post Date:      x0 ≈ 138.4  → (125, 165)
# Reference #:    x0 ≈ 197.7  → (185, 230)
# Description:    x0 ≈ 265.1  → (255, 510)
# Amount:         x0 > 520    → (515, 580)
# ---------------------------------------------------------------------------
COL_ACTIVITY = (70,  115)
COL_POST     = (125, 165)
COL_REF      = (185, 230)
COL_DESC     = (255, 510)
COL_AMOUNT   = (515, 580)

MONTH_ABBR   = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
RE_TXN_DATE  = re.compile(rf"^{MONTH_ABBR}\d{{2}}$")
RE_CURRENCY  = re.compile(r"\$[\d,]+\.\d{2}(?:CR)?")


def words_by_row(page) -> list[list[dict]]:
    """Extract words from a PDF page and group them into rows by y-coordinate."""
    words = page.extract_words(x_tolerance=3, y_tolerance=3)
    rows = []
    for _, grp in groupby(sorted(words, key=lambda w: round(w["top"])), key=lambda w: round(w["top"])):
        rows.append(sorted(grp, key=lambda w: w["x0"]))
    return rows


def in_col(word: dict, col: tuple) -> bool:
    """Check if a word's x-coordinate falls within a column boundary."""
    return col[0] <= word["x0"] <= col[1]


def parse_amount(raw: str) -> Decimal:
    """Parse a currency string into a Decimal, handling CR (credit) signage."""
    is_credit = "CR" in raw.upper()
    cleaned = re.sub(r"[+\-$,CR\s]", "", raw.upper())
    try:
        value = Decimal(cleaned)
    except InvalidOperation as e:
        raise DataIntegrityError(f"Cannot parse amount: {raw!r}") from e
    return -value if is_credit else value


def parse_date(raw: str, year: int) -> date:
    """Parse 'Jul07' (no space) or 'Jul 07' into a date."""
    if len(raw) > 3 and raw[3].isdigit():
        raw = f"{raw[:3]} {raw[3:]}"
    return datetime.strptime(f"{raw} {year}", "%b %d %Y").date()


def parse_billing_period(start_str: str, end_str: str) -> tuple[date, date]:
    """Parse billing period strings like 'July4,2024' into date objects."""
    start = datetime.strptime(start_str, "%B%d,%Y").date()
    end   = datetime.strptime(end_str,   "%B%d,%Y").date()
    return start, end


class PDFExtractor:
    """Infrastructure service for extracting text and structure from PDF files."""
    
    @staticmethod
    def open(pdf_path: str):
        """Open a PDF file and return a pdfplumber PDF object."""
        return pdfplumber.open(pdf_path)
    
    @staticmethod
    def extract_rows(page) -> list[list[dict]]:
        """Extract words from a page grouped into rows."""
        return words_by_row(page)
