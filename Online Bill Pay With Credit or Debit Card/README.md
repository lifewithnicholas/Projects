# Online Bill Pay (Flask + optional Stripe Checkout)

A minimal Python project to accept online bill payments by credit/debit card and calculate totals after tax and shipping.

## Features
- Enter a bill amount and description.
- Calculates tax and shipping (configurable).
- Shows an itemized summary.
- Optional Stripe Checkout integration for real card payments (test or live).
  - If `STRIPE_SECRET_KEY` is not set, the app runs in **Demo Mode** and simulates a successful payment without charging.

## Quick Start

### 1) Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Configure (optional but recommended)
Copy `.env.example` to `.env` and set:
- `STRIPE_SECRET_KEY` – your Stripe secret key (starts with `sk_test_...` for test).
- `STRIPE_PUBLISHABLE_KEY` – your Stripe publishable key (starts with `pk_test_...` for test).
If you skip this, app runs in Demo Mode.

You can also adjust tax and shipping in `app.py` (search for `TAX_RATE` and `SHIPPING_FLAT`).

### 3) Run the app
```bash
flask --app app run --debug
```
Open http://127.0.0.1:5000

### Stripe Test Cards
When in test mode, you can use Stripe’s test cards such as:
- Number: 4242 4242 4242 4242
- Any future expiry, any CVC, any postal code.

### Notes
- Amounts are handled using `Decimal` to avoid floating-point issues.
- Stripe amounts are sent in the smallest currency unit (cents).
- This sample is for educational purposes; add proper auth, logging, and validation for production.
