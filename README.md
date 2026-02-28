# ccparse

A Python library for extracting high-fidelity financial data from TD Business Solutions Visa "born-digital" PDF statements.

Parses transactions, balance summaries, and rewards points into structured domain objects, validates the Golden Equation on every parse, and exports to Pandas DataFrames.

---

## Features

- Extracts all transactions with activity date, post date, reference number, description, and amount
- Correctly handles `CR` (credit balance) signage — stored as negative `Decimal` values
- Validates `Previous Balance + Purchases - Credits + Fees + Interest = New Balance` on every parse; raises `BalanceMismatchError` if it fails
- All monetary values use `decimal.Decimal` — floating-point arithmetic is never used
- Exports to a Pandas DataFrame with `datetime64` date columns
- All processing is local — no network calls, no data storage

---

## Installation

```bash
pip install ccparse
```

Requires Python 3.11+.

---

## Quick Start

```python
from ccparse import TDStatementParser

parser = TDStatementParser()
statement = parser.parse("path/to/statement.pdf")

# Metadata
print(statement.account_suffix)          # "5679"
print(statement.billing_period_start)    # datetime.date(2024, 7, 4)
print(statement.billing_period_end)      # datetime.date(2024, 8, 3)

# Balance summary
print(statement.balance_summary.new_balance)       # Decimal('-1151.02')
print(statement.balance_summary.previous_balance)  # Decimal('-1516.49')
print(statement.balance_summary.purchases)         # Decimal('365.47')

# Transactions
for t in statement.transactions:
    print(t.activity_date, t.reference_number, t.description, t.amount)

# Rewards
print(statement.current_points)  # 6050
```

### Pandas Export

```python
from ccparse import TDStatementParser
from ccparse.export import to_df

statement = TDStatementParser().parse("path/to/statement.pdf")
df = to_df(statement)

print(df.dtypes)
# activity_date    datetime64[ns]
# post_date        datetime64[ns]
# reference_number         object
# description              object
# amount                  float64
```

---

## Error Handling

```python
from ccparse import TDStatementParser, BalanceMismatchError, DataIntegrityError

try:
    statement = TDStatementParser().parse("path/to/statement.pdf")
except BalanceMismatchError as e:
    # Golden Equation failed — the PDF figures don't add up
    print(e)
except DataIntegrityError as e:
    # A required field could not be extracted
    print(e)
```

| Exception | Raised when |
|---|---|
| `BalanceMismatchError` | Golden Equation validation fails |
| `DataIntegrityError` | A required field is missing or unparseable |
| `TDParserError` | Base class for all library errors |

---

## Data Model

```python
@dataclass
class Statement:
    entity_name: str
    primary_cardholder: str
    account_suffix: str
    billing_period_start: date
    billing_period_end: date
    balance_summary: BalanceSummary
    current_points: int
    transactions: List[Transaction]

@dataclass(frozen=True)
class Transaction:
    activity_date: date
    post_date: date
    reference_number: str   # maps to <FITID> in OFX/QBO
    description: str
    amount: Decimal         # positive = spend, negative = payment/credit

@dataclass(frozen=True)
class BalanceSummary:
    previous_balance: Decimal
    purchases: Decimal
    credits: Decimal
    fees: Decimal
    interest: Decimal
    new_balance: Decimal
    available_credit: Decimal
    minimum_payment: Decimal
```

---

## Development

```bash
git clone https://github.com/rmuktader/ccparse
cd ccparse
uv sync
uv run pytest tests/ -v
```

---

## Roadmap

| Version | Features |
|---|---|
| 0.1 (MVP) | TD Business Visa parsing, Pandas export, balance validation |
| 1.1 | OFX / QBO / CSV export, rewards validation, optional dependency extras |
| 2.0 | Multi-bank strategy (Chase, Amex) |

---

## License

MIT
