import json
import sys
from pricing import load_products, price_order


def main(path):
    products = load_products("data/products.json")
    with open(path) as f:
        orders = json.load(f)
    for order in orders:
        result = price_order(order, products)
        print(f"Order {result['order']}: net {result['net']:.2f}  delivery {result['delivery']:.2f}  "
              f"VAT {result['vat']:.2f}  total {result['gross']:.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/orders.json")
