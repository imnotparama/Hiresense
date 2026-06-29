#!/usr/bin/env python3
"""
Convert submission CSV to XLSX format.
Verifies columns conform to the challenge specifications.
"""

import os
import sys
import pandas as pd


def main():
    csv_path = os.path.join("output", "submission.csv")
    xlsx_path = os.path.join("output", "submission.xlsx")

    # Verify input file exists
    if not os.path.exists(csv_path):
        print(f"Error: Submission file '{csv_path}' not found. Please run rank.py first.")
        sys.exit(1)

    try:
        # Load the CSV file
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading '{csv_path}': {e}")
        sys.exit(1)

    # Verify columns are correct
    expected_columns = ["candidate_id", "rank", "score", "reasoning"]
    actual_columns = list(df.columns)
    if actual_columns != expected_columns:
        print("Error: Columns in CSV do not match the expected schema.")
        print(f"Expected: {expected_columns}")
        print(f"Found:    {actual_columns}")
        sys.exit(1)

    # Convert to Excel
    try:
        df.to_excel(xlsx_path, index=False)
    except ImportError:
        print("Error: The 'openpyxl' package is required to write to Excel.")
        print("Please install it using: pip install openpyxl")
        sys.exit(1)
    except Exception as e:
        print(f"Error writing to '{xlsx_path}': {e}")
        sys.exit(1)

    # Success outputs
    print(f"Conversion complete. Rows: {len(df)}")
    print("submission.xlsx is ready for upload")


if __name__ == "__main__":
    main()
