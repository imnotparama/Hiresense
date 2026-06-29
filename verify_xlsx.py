#!/usr/bin/env python3
"""
Verify that the output/submission.xlsx has exactly 100 rows and the correct columns.
"""

import sys
import pandas as pd


def main():
    try:
        df = pd.read_excel("output/submission.xlsx")
        print("XLSX rows:", len(df))
        print("Columns:", list(df.columns))
        assert len(df) == 100, "ERROR: Should have exactly 100 rows"
        assert list(df.columns) == [
            "candidate_id",
            "rank",
            "score",
            "reasoning",
        ], "ERROR: Wrong columns"
        print("XLSX is valid and ready for submission!")
    except AssertionError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error checking Excel file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
