"""Test Atmos callback signature and simulate validation response."""

import hashlib
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from users.services import (
    calculate_atmos_sign,
    process_atmos_callback,
    validate_atmos_callback_sign,
)


class Command(BaseCommand):
    help = "Verify Atmos callback sign (MD5) and optionally dry-run process_atmos_callback."

    def add_arguments(self, parser):
        parser.add_argument(
            "--payload",
            help='Callback JSON, e.g. \'{"store_id":"100549",...}\'',
        )
        parser.add_argument(
            "--payload-file",
            dest="payload_file",
            help="Path to JSON file with callback body.",
        )
        parser.add_argument(
            "--process",
            action="store_true",
            help="Run process_atmos_callback (needs matching order in DB).",
        )

    def handle(self, *args, **options):
        raw = options.get("payload")
        if options.get("payload_file"):
            with open(options["payload_file"], encoding="utf-8") as fh:
                raw = fh.read()
        if not raw:
            raw = (
                '{"store_id":"100549","transaction_id":"137059144","amount":"100000",'
                '"account":"202606241320353628441442635843758185",'
                '"sign":"aa20d8d447edc30932df41b4dcd4603a"}'
            )
            self.stdout.write(self.style.WARNING("Using example payload from Atmos ticket."))

        payload = json.loads(raw)
        api_key_set = bool((settings.ATMOS_API_KEY or "").strip())
        self.stdout.write(f"ATMOS_SIGN_ALGORITHM: {settings.ATMOS_SIGN_ALGORITHM}")
        self.stdout.write(f"ATMOS_API_KEY set: {api_key_set}")
        if not api_key_set:
            self.stderr.write(self.style.ERROR("ATMOS_API_KEY is empty in .env"))
            return

        received = str(payload.get("sign", ""))
        calculated = calculate_atmos_sign(payload)
        self.stdout.write(f"received sign:   {received}")
        self.stdout.write(f"calculated sign: {calculated}")

        source = "".join(
            [
                str(payload.get("store_id", "")),
                str(payload.get("transaction_id", "")),
                str(payload.get("account") or payload.get("invoice") or ""),
                str(payload.get("amount", "")),
                settings.ATMOS_API_KEY,
            ]
        )
        self.stdout.write(f"sign source (no key): {source[:-len(settings.ATMOS_API_KEY)]}<API_KEY>")
        self.stdout.write(
            f"md5 check: {hashlib.md5(source.encode()).hexdigest()}"
        )

        if validate_atmos_callback_sign(payload):
            self.stdout.write(self.style.SUCCESS("Signature OK"))
        else:
            self.stderr.write(self.style.ERROR("Signature MISMATCH — fix ATMOS_API_KEY or algorithm"))
            return

        if options.get("process"):
            result = process_atmos_callback(payload)
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
