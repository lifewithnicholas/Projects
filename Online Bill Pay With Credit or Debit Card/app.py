import os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Optional Stripe integration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()

try:
    import stripe
except Exception:
    stripe = None

if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# --- Configuration ---
CURRENCY = "usd"
# Adjust these for your locale:
TAX_RATE = Decimal("0.0825")  # 8.25% sales tax
SHIPPING_FLAT = Decimal("4.99")  # flat shipping fee

def to_decimal(value: str) -> Decimal:
    """Safe conversion to Decimal with 2dp, rejecting negatives."""
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid number.")
    if d < 0:
        raise ValueError("Amount cannot be negative.")
    # Normalize to 2 decimal places for currency
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def calc_totals(subtotal: Decimal):
    """Return a dict with detailed totals."""
    tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    shipping = SHIPPING_FLAT
    total = (subtotal + tax + shipping).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "subtotal": subtotal,
        "tax": tax,
        "shipping": shipping,
        "total": total,
    }

def dollars_to_cents(dec_amount: Decimal) -> int:
    return int((dec_amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", publishable_key=STRIPE_PUBLISHABLE_KEY, currency=CURRENCY.upper())

@app.route("/calculate", methods=["POST"])
def calculate():
    description = request.form.get("description", "Online Bill")
    amount_str = request.form.get("amount", "0")
    email = request.form.get("email", "").strip()

    try:
        subtotal = to_decimal(amount_str)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("index"))

    breakdown = calc_totals(subtotal)

    # Store in session-like temp via Flask flash? For simplicity, pass via query (not ideal).
    # In production, use a proper session or database.
    return render_template(
        "summary.html",
        description=description,
        email=email,
        subtotal=breakdown["subtotal"],
        tax=breakdown["tax"],
        shipping=breakdown["shipping"],
        total=breakdown["total"],
        currency=CURRENCY.upper(),
        stripe_enabled=bool(stripe and STRIPE_SECRET_KEY),
    )

@app.route("/pay", methods=["POST"])
def pay():
    description = request.form.get("description", "Online Bill")
    email = request.form.get("email", "").strip()
    subtotal = to_decimal(request.form.get("subtotal"))
    tax = to_decimal(request.form.get("tax"))
    shipping = to_decimal(request.form.get("shipping"))
    total = to_decimal(request.form.get("total"))

    # Safety: recompute totals server-side
    recomputed = calc_totals(subtotal)
    if recomputed["tax"] != tax or recomputed["shipping"] != shipping or recomputed["total"] != total:
        flash("Total mismatch; please try again.", "error")
        return redirect(url_for("index"))

    # If Stripe is configured, use Checkout
    if stripe and STRIPE_SECRET_KEY:
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                customer_email=email if email else None,
                line_items=[
                    {
                        "price_data": {
                            "currency": CURRENCY,
                            "product_data": {"name": description},
                            "unit_amount": dollars_to_cents(total),
                        },
                        "quantity": 1,
                    }
                ],
                success_url=url_for("success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=url_for("cancel", _external=True),
                allow_promotion_codes=True,
            )
            return redirect(session.url, code=303)
        except Exception as e:
            flash(f"Payment error: {e}", "error")
            return redirect(url_for("index"))

    # Demo mode: simulate a success without charging
    return redirect(url_for("success"))

@app.route("/success", methods=["GET"])
def success():
    return render_template("success.html")

@app.route("/cancel", methods=["GET"])
def cancel():
    return render_template("cancel.html")

if __name__ == "__main__":
    app.run(debug=True)
