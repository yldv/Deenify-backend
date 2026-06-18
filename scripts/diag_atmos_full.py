#!/usr/bin/env python3
"""Full Atmos server-to-server flow: create -> pre-apply -> apply."""
import base64
import json
import os
import sys
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv("/var/www/deenify/.env")

BASE = os.environ["ATMOS_BASE_URL"].rstrip("/")
STORE = int(os.environ["ATMOS_STORE_ID"])
KEY = os.environ["ATMOS_CONSUMER_KEY"]
SECRET = os.environ["ATMOS_CONSUMER_SECRET"]
API_KEY = os.environ.get("ATMOS_API_KEY", "").strip()

CARD = sys.argv[1] if len(sys.argv) > 1 else "8600490744313347"
EXPIRY = sys.argv[2] if len(sys.argv) > 2 else "2410"
OTP = sys.argv[3] if len(sys.argv) > 3 else "111111"


def token():
    creds = base64.b64encode(f"{KEY}:{SECRET}".encode()).decode()
    req = Request(
        f"{BASE}/token?grant_type=client_credentials",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read())["access_token"]


def call(path, body, tok):
    headers = {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
    }
    if API_KEY:
        headers["X-Api-Key"] = API_KEY
    req = Request(f"{BASE}{path}", data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:400]}


tok = token()

print("=== 1) merchant/pay/create ===")
acc = f"d-{uuid.uuid4().hex[:8]}"
created = call(
    "/merchant/pay/create",
    {"amount": 40000000, "account": acc, "store_id": str(STORE), "lang": "uz",
     "redirect_link": os.environ.get("ATMOS_RETURN_URL", "")},
    tok,
)
print(json.dumps(created, ensure_ascii=False)[:300])
tid = created.get("transaction_id")
if not tid:
    sys.exit("no transaction_id")

print(f"\n=== 2) merchant/pay/pre-apply (card {CARD}, expiry {EXPIRY}) ===")
pre = call(
    "/merchant/pay/pre-apply",
    {"card_number": CARD, "expiry": EXPIRY, "store_id": STORE, "transaction_id": tid},
    tok,
)
print(json.dumps(pre, ensure_ascii=False)[:400])

print(f"\n=== 3) merchant/pay/apply (otp {OTP}) ===")
applied = call(
    "/merchant/pay/apply",
    {"otp": int(OTP) if OTP.isdigit() else OTP, "store_id": STORE, "transaction_id": tid},
    tok,
)
print(json.dumps(applied, ensure_ascii=False)[:500])
