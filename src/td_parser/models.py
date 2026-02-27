from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List


@dataclass(frozen=True)
class Transaction:
    activity_date: date
    post_date: date
    reference_number: str
    description: str
    amount: Decimal  # Positive = spend, Negative = payment/credit


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


@dataclass
class Statement:
    entity_name: str
    primary_cardholder: str
    account_suffix: str
    billing_period_start: date
    billing_period_end: date
    balance_summary: BalanceSummary
    current_points: int
    transactions: List[Transaction] = field(default_factory=list)
