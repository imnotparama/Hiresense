# HireSense Ranking System

This project implements a rule-based candidate ranking system for the HireSense challenge.

## Setup

1. Ensure you have Python 3.11+ installed.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the ranking script on a dataset of candidates:

```bash
python rank.py --input_path path/to/candidates.json --output_path output/rankings.csv
```

The script will output a CSV file with ranked candidates.

## Progress

The script prints progress every 10,000 candidates.

## Requirements

- Python 3.11+
- pandas==2.2.0
- numpy==1.26.2
- python-dateutil==2.9.0.post0

No internet calls are made during ranking; all scoring is rule-based and uses keyword matching.

## Notes

- The system is designed to handle up to 100,000 candidates on CPU.
- Malformed or missing fields are handled gracefully with try/except.
- Tie-breaking: candidates with equal scores are sorted by candidate_id ascending.
- Honeypot detection: compares sum of duration_months in career_history vs years_of_experience * 12; flags if difference > 36 months.

## Validation

Run the provided validation script:

```bash
python validate_submission.py
```
```
