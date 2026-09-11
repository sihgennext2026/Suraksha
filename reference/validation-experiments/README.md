# Validation Final

Python toolkit for extracting and validating data from identity documents (Passport, Visa, Aadhaar / National ID, Driving License) using OCR, MRZ parsing, and barcode/QR reading.

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

**Notes**
- On Windows you may need the ZBar DLLs for `pyzbar`.
- On Linux install system package `libzbar0` (or equivalent).

## Structure

```
validation/
├── driving_license/   # Driving license processing
├── index/             # Main conversion / orchestration
├── nationalid/        # Aadhaar / National ID
├── pass/              # Passport + MRZ
└── visaprocess/       # Visa + MRZ
```

Do **not** commit the `.venv` folder.
