import unittest
from decimal import Decimal

from orders.pricing import delivery_fee, line_total, price_order


class PricingTests(unittest.TestCase):
    def test_line_total_plain(self):
        self.assertEqual(line_total(Decimal("8.90"), 10, False), Decimal("89.00"))

    def test_line_total_contract_discount(self):
        self.assertEqual(line_total(Decimal("10.00"), 10, True), Decimal("92.00"))

    def test_delivery_boundary(self):
        self.assertEqual(delivery_fee(Decimal("500.00")), Decimal("45.00"))
        self.assertEqual(delivery_fee(Decimal("500.01")), Decimal("0.00"))

    def test_price_order(self):
        result = price_order([{"sku": "CMT-0020", "quantity": 10}])
        self.assertEqual(result["net"], Decimal("51.50"))
        self.assertEqual(result["gross"], Decimal("114.84"))


if __name__ == "__main__":
    unittest.main()
