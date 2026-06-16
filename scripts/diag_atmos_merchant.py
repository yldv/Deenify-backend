#!/usr/bin/env python3
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
creds = base64.b64encode(f"{key}:{secret}".encode()).decode()

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

acc = f"m-{uuid.uuid4().hex[:10]}"
amt = 40000000
payload = {
    "amount": amt,
    "account": acc,
    "store_id": int(os.environ["ATMOS_STORE_ID"]),
    "redirect_link": os.environ.get("ATMOS_RETURN_URL", ""),
    "lang": "uz",
}
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}
api_key = os.environ.get("ATMOS_API_KEY", "").strip()
if api_key:
    headers["X-Api-Key"] = api_key

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
    if tid:
        qs = f"storeId={os.environ['ATMOS_STORE_ID']}&transactionId={tid}"
        for host in ["test-checkout.pays.uz", "dev-checkout.atmos.uz", "api.frienfinity.uz"]:
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
    print("merchant/pay/create HTTP", e.code, e.read().decode()[:500])
except Exception as e:
    print("merchant/pay/create FAIL:", e)
