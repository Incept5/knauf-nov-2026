"""Product list. Prices are net unit prices in EUR."""
from decimal import Decimal

PRODUCTS = {
    "PLB-0001": {"name": "Plasterboard 12.5 mm, 2500 x 1200", "unit_price": Decimal("8.90")},
    "PLB-0002": {"name": "Plasterboard moisture resistant, 2500 x 1200", "unit_price": Decimal("12.40")},
    "INS-0010": {"name": "Mineral wool roll 100 mm (per m2)", "unit_price": Decimal("6.35")},
    "CMT-0020": {"name": "Cement 25 kg bag", "unit_price": Decimal("5.15")},
    "SCR-0030": {"name": "Drywall screws 3.5 x 35, box of 1000", "unit_price": Decimal("14.95")},
}


def unit_price_for(sku: str) -> Decimal:
    """Net unit price in EUR. Raises KeyError for an unknown SKU."""
    return PRODUCTS[sku]["unit_price"]
