"""
Shareify Payment Service
- Mock payment processing
- Return success/failure
"""

import os
import uuid
import sqlite3
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Shareify Payment Service", version="1.0.0")

# ── Config ──────────────────────────────────────────────────────────────────
DATABASE = os.getenv("DATABASE_PATH", "./data/payments.db")


# ── Database ────────────────────────────────────────────────────────────────
def get_db():
    os.makedirs(os.path.dirname(DATABASE) or ".", exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            booking_id TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


# ── Schemas ─────────────────────────────────────────────────────────────────
class PaymentRequest(BaseModel):
    booking_id: str
    amount: float


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.post("/payments")
def process_payment(req: PaymentRequest):
    """Mock payment – always succeeds if amount > 0."""
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    payment_id = str(uuid.uuid4())
    status = "success"  # Mock: always succeeds

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO payments (payment_id, booking_id, amount, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (payment_id, req.booking_id, req.amount, status,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return {
            "payment_id": payment_id,
            "booking_id": req.booking_id,
            "amount": req.amount,
            "status": status,
        }
    finally:
        conn.close()


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM payments WHERE payment_id = ?", (payment_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Payment not found")
        return dict(row)
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "shareify-payment-service"}
