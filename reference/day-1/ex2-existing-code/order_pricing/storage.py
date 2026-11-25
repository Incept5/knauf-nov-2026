"""Reading the data files. Kept apart from the pricing rules so the rules can be tested without files."""
import json


def load_products(path):
    with open(path) as f:
        return {p["sku"]: p for p in json.load(f)}


def load_orders(path):
    with open(path) as f:
        return json.load(f)
