"""
Shareify Payment Service
- Mock payment processing
- Return success/failure
"""

import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Shareify Payment Service", version="1.0.0")
# -- POSTGRESQL HOTFIX: SQLite Polyfill --------------------------------------
# Automatically translates SQLite conn.execute() and '?' to PostgreSQL syntax
import psycopg2
from psycopg2.extensions import connection

def _sqlite_to_psycopg2_execute(self, query, vars=None):
    if '?' in query:
        query = query.replace('?', '%s')
    cursor = self.cursor()
    cursor.execute(query, vars)
    return cursor

connection.execute = _sqlite_to_psycopg2_execute
# ----------------------------------------------------------------------------
import time
from fastapi import Request
from prometheus_client import make_asgi_app, Counter, Histogram

# -- Prometheus Metrics ------------------------------------------------------
REQUEST_COUNT = Counter("http_requests_total", "Total requests", ["method", "endpoint", "http_status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Latency", ["method", "endpoint"])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    method = request.method
    endpoint = request.url.path
    if endpoint == "/metrics":
        return await call_next(request)
        
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=response.status_code).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(process_time)
    
    return response


# ── Config ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:shareify-secure-db-pass@postgres-db:5432/payment_service")


# ── Database ────────────────────────────────────────────────────────────────
def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
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




