# Changelog

All notable changes to ccparse will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2025-01-10

### Added
- **CSV Export**: Export transactions to CSV format with `to_csv()`
- **OFX Export**: Export to Open Financial Exchange format with `to_ofx()`
- **QBO Export**: Export to QuickBooks Online format with `to_qbo()`
- **ExportService**: Application-layer service with multiple export strategies
- **Strategy Pattern**: `StatementParser` ABC for multi-bank extensibility
- **Infrastructure Layer**: `PDFExtractor` isolates pdfplumber dependency
- **Parser Layer**: `TDBusinessVisaParser` implements concrete parsing strategy
- 38 new tests for export functionality (66 total tests)
- Comprehensive architecture documentation

### Changed
- Refactored monolithic `parser.py` into layered architecture
- Split parsing logic into `infrastructure/` and `parsers/` layers
- Reorganized export functionality into `export/` application layer
- Updated README with new export examples and architecture diagram

### Fixed
- Improved code organization and separation of concerns
- Enhanced testability through layer isolation

### Maintained
- 100% backward compatibility with v0.5.0 API
- All original 28 tests continue to pass
- Public API unchanged (`TDStatementParser`, `to_df()`)

## [0.5.0] - Previous Release

### Added
- TD Business Solutions Visa PDF parsing
- Transaction extraction with activity date, post date, reference number, description, amount
- CR (credit balance) signage handling
- Golden Equation balance validation
- Pandas DataFrame export with `to_df()`
- Rewards points extraction
- Domain models: `Statement`, `Transaction`, `BalanceSummary`
- Exception hierarchy: `TDParserError`, `BalanceMismatchError`, `DataIntegrityError`

---

## Upgrade Guide

### From 0.5.0 to 0.6.0

No code changes required! The API is fully backward compatible.

**Optional: Use new export formats**

```python
from ccparse import TDStatementParser
from ccparse.export import to_csv, to_ofx, to_qbo

statement = TDStatementParser().parse("statement.pdf")

# New in 0.6.0
csv_output = to_csv(statement)
ofx_output = to_ofx(statement)
qbo_output = to_qbo(statement)

# Original API still works
from ccparse.export import to_df
df = to_df(statement)
```

---

## Migration Notes

### Internal Changes (Transparent to Users)

The following internal changes do not affect the public API:

- `parser.py` logic moved to `parsers/td_business_visa.py`
- PDF utilities moved to `infrastructure/pdf_extractor.py`
- Export logic moved to `export/export_service.py`

Users can continue using:
```python
from ccparse import TDStatementParser
from ccparse.export import to_df
```

---

## Future Releases

### [1.0.0] - Planned
- Rewards validation
- Optional dependency extras (`[pandas]`, `[ofx]`)
- `StatementMetadata` and `RewardsSummary` value objects
- `BalanceValidator` and `RewardsValidator` classes

### [2.0.0] - Planned
- Multi-bank support (Chase, Amex)
- Parser factory/registry pattern
- Additional export formats (JSON, Excel)

---

## Links

- [PyPI Package](https://pypi.org/project/ccparse/)
- [GitHub Repository](https://github.com/rmuktader/ccparse)
- [Documentation](https://github.com/rmuktader/ccparse/tree/main/docs)
