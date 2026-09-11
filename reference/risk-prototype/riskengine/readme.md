# Hybrid Risk Scoring Engine

A deterministic hybrid risk scoring engine that combines:

- Document Validation
- Document Tampering Detection
- Face Verification

to generate a final risk score and fraud category.

## Input Files

The engine requires three JSON files:

- `validateout.json`
- `tampering.json`
- `faceout.json`

## Output

The engine generates:

- `riskout.json`

## Risk Weights

| Module | Weight |
|---|---:|
| Validation | 25% |
| Tampering | 45% |
| Face Verification | 30% |

## Risk Categories

| Risk Score | Category |
|---:|---|
| 0–24 | Genuine |
| 25–49 | Suspicious |
| 50–74 | High-Risk Fake |
| 75–100 | Critical Fraud |

## How to Run

Make sure Python 3.9+ is installed.

Run:

```bash
python risk.pyS