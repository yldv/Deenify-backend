#!/usr/bin/env python3
"""Diagnose Atmos checkout POST /invoice Server Action."""
import json
import base64
import os
import re
import subprocess
import uuid
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

account = f"diag-{uuid.uuid4().hex[:8]}"
amount = 40000000
body = {
    "request_id": account,
    "store_id": int(os.environ["ATMOS_STORE_ID"]),
    "account": account,
    "amount": amount,
    "success_url": os.environ.get("ATMOS_RETURN_URL"),
    "expiration_time": 3600,
    "payment_items": [
        {
            "items_id": "1",
            "code": "premium",
            "name": "Deenify Premium",
            "amount": amount,
            "quantity": 1,
            "details": [
                {"name": "package_code", "values": "1"},
                {"name": "mark_code", "values": "0"},
                {"name": "tin", "values": "0"},
                {"name": "discount", "values": "0"},
                {"name": "quantity", "values": "1"},
            ],
        }
    ],
}

with urlopen(
    Request(
        f"{base}/checkout/invoice/create",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    ),
    timeout=30,
) as r:
    created = json.loads(r.read())

inv = created["token"]
print("token", inv)

for host in ["dev-checkout.atmos.uz", "api.frienfinity.uz"]:
    cj = f"/tmp/{host.replace('.', '_')}.cj"
    html_path = f"/tmp/{host.replace('.', '_')}.html"
    subprocess.run(
        [
            "curl",
            "-s",
            "-c",
            cj,
            "-b",
            cj,
            f"https://{host}/invoice?id={inv}",
            "-o",
            html_path,
        ],
        check=True,
    )
    html = open(html_path).read()
    actions = re.findall(r'createServerReference\)\("([a-f0-9]{40})"', html)
    step_m = re.search(r'initialStepState\\":\{\\"id\\":(\d+)', html)
    if not step_m:
        step_m = re.search(r'"initialStepState":\{"id":(\d+)', html)
    if not step_m:
        step_m = re.search(r'initialStepState.*?"id":(\d+)', html)
    step_id = int(step_m.group(1)) if step_m else None
    print(f"\n=== {host} ===")
    print("html_len", len(html), "step_id", step_id)
    print("actions", list(set(actions)))
    if not step_id or not actions:
        print("SKIP - missing step or actions")
        continue
    for a in set(actions):
        payload = json.dumps(
            [
                {
                    "stepId": step_id,
                    "methodType": "VALIDATION",
                    "payload": "9860090101014364",
                    "serviceViewId": 2,
                    "windowId": str(uuid.uuid4()),
                }
            ]
        )
        out = subprocess.check_output(
            [
                "curl",
                "-s",
                "-w",
                "\nHTTP:%{http_code}",
                "--max-time",
                "15",
                "-X",
                "POST",
                f"https://{host}/invoice?id={inv}",
                "-b",
                cj,
                "-H",
                "Content-Type: text/plain;charset=UTF-8",
                "-H",
                "Accept: text/x-component",
                "-H",
                f"Next-Action: {a}",
                "-H",
                f"Origin: https://{host}",
                "-H",
                f"Referer: https://{host}/invoice?id={inv}",
                "--data-raw",
                payload,
            ],
            text=True,
        )
        code = out.split("HTTP:")[-1].strip()
        preview = out.split("HTTP:")[0][-200:]
        print(f"  {a[:16]}... -> HTTP {code}")
        print(f"    body tail: {preview[:150]}")
