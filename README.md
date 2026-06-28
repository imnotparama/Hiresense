# HireSense Candidate Ranking System

HireSense is an intelligent, memory-efficient candidate ranking system built for the Redrob x Hack2Skill Hackathon. It evaluates and ranks 100,000 candidates against a Senior AI Engineer (Founding Team) job description, selecting the top 100 candidates.

## 🚀 Key Features
- **CPU Optimized**: Processes 100,000 profiles in under 30 seconds on CPU.
- **Memory Efficient**: Streams JSONL data line-by-line with a peak RAM footprint under 50MB.
- **6-Stage Scoring Architecture**: Evaluates candidates based on Honeypot detection, Hard Disqualifiers, Skill weights & endorsements, Career relevance, Behavioral signals, Education, and Location.
- **Automated Validation**: Fully compliant with the hackathon's submission formats and tie-breaking rules.

## 🛠️ Installation & Setup

1. Ensure you have Python 3.11+ installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   pip install openpyxl
   ```

## 💻 Running the Ranker

To process the candidate dataset and generate the submission file, run:
```bash
python rank.py --candidates ../candidates.jsonl --out output/submission.csv
```

## 🔄 Convert and Verify CSV to Excel (XLSX)

Convert the output CSV to the submission-ready Excel format:
```bash
python -c "
import pandas as pd
df = pd.read_csv('output/submission.csv')
df.to_excel('output/submission.xlsx', index=False)
print('Conversion Complete. Rows:', len(df))
"
```

Verify that the XLSX format is fully valid:
```bash
python -c "
import pandas as pd
df = pd.read_excel('output/submission.xlsx')
print('XLSX rows:', len(df))
print('Columns:', list(df.columns))
assert len(df) == 100, 'ERROR: Should have exactly 100 rows'
assert list(df.columns) == ['candidate_id', 'rank', 'score', 'reasoning'], 'ERROR: Wrong columns'
print('XLSX is valid and ready for submission!')
"
```

## 🧪 Validation Checks

Run the local validator script to confirm correctness:
```bash
python validate_submission.py output/submission.csv
```
Expected output:
```text
Submission is valid.
```
