#!/usr/bin/env python3
"""Quick Atmos prod/sandbox check: token + merchant/pay/create."""
import json
import base64
import os
import subprocess
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv("/var/www/deenify/.env")

base = os.environ["ATMOS_BASE_URL"].rstrip("/")
key, secret = os.environ["ATMOS_CONSUMER_KEY"], os.environ["ATMOS_CONSUMER_SECRET"]
store = os.environ["ATMOS_STORE_ID"].strip()
terminal = os.environ.get("ATMOS_TERMINAL_ID", "").strip()
test_mode = os.environ.get("ATMOS_TEST_MODE", "False") == "True"

print("mode:", "TEST" if test_mode else "PROD")
print("store_id:", store)
print("terminal_id:", terminal or "(not set — optional)")

creds = base64.b64encode(f"{key}:{secret}".encode()).decode()

try:
    with urlopen(
        Request(
            f"{base}/token?grant_type=client_credentials",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        ),
        timeout=20,
    ) as r:
        token = json.loads(r.read())["access_token"]
    print("token: OK")
except HTTPError as e:
    print("token: FAIL", e.code, e.read().decode()[:300])
    raise SystemExit(1)

acc = f"m-{uuid.uuid4().hex[:10]}"
payload = {
    "amount": 40000000,
    "account": acc,
    "store_id": store,
    "redirect_link": os.environ.get("ATMOS_RETURN_URL", ""),
    "lang": "uz",
}
if terminal:
    payload["terminal_id"] = terminal

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

req = Request(
    f"{base}/merchant/pay/create",
    data=json.dumps(payload).encode(),
    headers=headers,
    method="POST",
)
try:
    with urlopen(req, timeout=30) as r:
        raw = json.loads(r.read())
    print("merchant/pay/create:", json.dumps(raw, ensure_ascii=False)[:800])
    tid = raw.get("transaction_id") or raw.get("payment_id")
    st = raw.get("store_transaction") or {}
    tid = tid or st.get("trans_id") or st.get("success_trans_id")
    print("transaction_id:", tid)
    if tid and test_mode:
        qs = f"storeId={store}&transactionId={tid}"
        for host in ["test-checkout.pays.uz", "api.frienfinity.uz"]:
            code = subprocess.check_output(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    "10",
                    f"https://{host}/invoice/get?{qs}",
                ],
                text=True,
            )
            print(f"GET https://{host}/invoice/get -> HTTP {code}")
except HTTPError as e:
    body = e.read().decode()[:500]
    print("merchant/pay/create HTTP", e.code, body or "(empty — usually IP whitelist / Store access)")
    if e.code == 403:
        print("hint: register IP at Atmos and enable Merchant API for store", store)
    raise SystemExit(1)
