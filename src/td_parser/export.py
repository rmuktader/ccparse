import pandas as pd

from .models import Statement


def to_df(statement: Statement) -> pd.DataFrame:
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
