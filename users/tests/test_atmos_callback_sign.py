import hashlib

from django.test import SimpleTestCase, override_settings

from users.services import calculate_atmos_sign, validate_atmos_callback_sign


class AtmosCallbackSignTests(SimpleTestCase):
    @override_settings(ATMOS_API_KEY="secret-key", ATMOS_SIGN_ALGORITHM="md5")
    def test_sign_uses_account_when_invoice_missing(self):
        payload = {
            "store_id": "100549",
            "transaction_id": "137059144",
            "amount": "100000",
            "account": "202606241320353628441442635843758185",
        }
        expected = hashlib.md5(
            b"100549137059144202606241320353628441442635843758185100000secret-key"
        ).hexdigest()
        payload["sign"] = expected
        self.assertEqual(calculate_atmos_sign(payload), expected)
        self.assertTrue(validate_atmos_callback_sign(payload))

    @override_settings(ATMOS_API_KEY="secret-key", ATMOS_SIGN_ALGORITHM="md5")
    def test_sign_fails_when_account_ignored(self):
        payload = {
            "store_id": "100549",
            "transaction_id": "137059144",
            "amount": "100000",
            "account": "202606241320353628441442635843758185",
            "sign": hashlib.md5(b"100549137059144100000secret-key").hexdigest(),
        }
        self.assertFalse(validate_atmos_callback_sign(payload))
