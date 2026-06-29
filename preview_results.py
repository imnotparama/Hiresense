#!/usr/bin/env python3
"""
Preview the candidate ranking results.
Prints summary stats and formats the top 10 candidates in a clean terminal table.
"""

import os
import sys
import textwrap
import pandas as pd


def get_file_size_display(file_path):
    """Return a human-readable file size string."""
    try:
        size_bytes = os.path.getsize(file_path)
        for unit in ["B", "KB", "MB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} GB"
    except Exception:
        return "Unknown"


def print_table(df_top_10):
    """Prints a beautiful, professional, and well-aligned terminal table."""
    col_widths = {
        "rank": 6,
        "candidate_id": 14,
        "score": 8,
        "reasoning": 60
    }

    # Header Border
    border = (
        f"+{'-' * (col_widths['rank'] + 2)}"
        f"+{'-' * (col_widths['candidate_id'] + 2)}"
        f"+{'-' * (col_widths['score'] + 2)}"
        f"+{'-' * (col_widths['reasoning'] + 2)}+"
    )

    print(border)
    print(
        f"| {'Rank':^{col_widths['rank']}} "
        f"| {'Candidate ID':^{col_widths['candidate_id']}} "
        f"| {'Score':^{col_widths['score']}} "
        f"| {'Reasoning':^{col_widths['reasoning']}} |"
    )
    print(border)

    for _, row in df_top_10.iterrows():
        rank_str = str(int(row["rank"]))
        cid_str = str(row["candidate_id"])
        
        try:
            score_val = float(row["score"])
            score_str = f"{score_val:.4f}"
        except ValueError:
            score_str = str(row["score"])
            
        reasoning_str = str(row["reasoning"])

        # Wrap reasoning text to fit the designated column width
        wrapped_reasoning = textwrap.wrap(reasoning_str, width=col_widths["reasoning"])
        if not wrapped_reasoning:
            wrapped_reasoning = [""]

        # Print the first line with all columns filled
        print(
            f"| {rank_str:>{col_widths['rank']}} "
            f"| {cid_str:<{col_widths['candidate_id']}} "
            f"| {score_str:>{col_widths['score']}} "
            f"| {wrapped_reasoning[0]:<{col_widths['reasoning']}} |"
        )

        # Print subsequent wrapped lines for reasoning
        for extra_line in wrapped_reasoning[1:]:
            print(
                f"| {'':<{col_widths['rank']}} "
                f"| {'':<{col_widths['candidate_id']}} "
                f"| {'':<{col_widths['score']}} "
                f"| {extra_line:<{col_widths['reasoning']}} |"
            )
        print(border)


def main():
    csv_path = os.path.join("output", "submission.csv")

    if not os.path.exists(csv_path):
        print(f"Error: Submission file '{csv_path}' not found. Please run rank.py first.")
        sys.exit(1)

    # Gather file and row stats
    file_size_str = get_file_size_display(csv_path)

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading '{csv_path}': {e}")
        sys.exit(1)

    total_rows = len(df)

    # Print summary statistics
    print("\n" + "=" * 98)
    print("                     HIRESENSE CANDIDATE RANKINGS PREVIEW")
    print("=" * 98)
    print(f"Total Candidates Ranked : {total_rows}")
    print(f"CSV File Path           : {csv_path}")
    print(f"CSV File Size           : {file_size_str}")
    print(f"Total Data Rows         : {total_rows}")
    print("=" * 98)
    print("\nTOP 10 CANDIDATES:")

    # Select top 10
    top_10 = df.head(10)
    print_table(top_10)
    print()


if __name__ == "__main__":
    main()
