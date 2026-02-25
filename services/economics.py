"""
Global Agricultural Economics Engine — calculates crop revenue projections
in local currencies using NDVI-health-adjusted yield models.
"""

# ── Base prices per kilogram (USD) ───────────────────────────
_BASE_PRICES_USD = {
    "Maize": 0.20,
    "Coffee": 4.00,
    "Tea": 2.00,
    "Wheat": 0.25,
    "Rice": 0.40,
    "Tomato": 1.00,
    "Banana": 0.30,
}

# ── Standard yields (kg per hectare, healthy season) ────────
_STANDARD_YIELDS = {
    "Maize": 4000,
    "Coffee": 2200,
    "Tea": 3000,
    "Wheat": 3500,
    "Rice": 5000,
    "Tomato": 40000,
    "Banana": 25000,
}

# ── Exchange rates from USD (approximate, static fallback) ──
_EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "KES": 140.0,
    "INR": 83.0,
    "BRL": 5.0,
    "NGN": 1500.0,
    "ZAR": 19.0,
    "TZS": 2500.0,
    "UGX": 3700.0,
    "ETB": 56.0,
    "GHS": 12.5,
    "EGP": 31.0,
    "CNY": 7.2,
    "JPY": 150.0,
    "AUD": 1.55,
    "CAD": 1.36,
    "MXN": 17.0,
}

_DEFAULT_PRICE = 0.30  # USD/kg for unknown crops
_DEFAULT_YIELD = 3000  # kg/ha for unknown crops


def _health_multiplier(ndvi: float) -> float:
    """
    Map NDVI score to a yield multiplier.
    ≥ 0.6 → 1.0 (healthy)
    0.2–0.6 → linear 0.3–1.0
    < 0.2 → 0.3 (severely stressed)
    """
    if ndvi >= 0.6:
        return 1.0
    elif ndvi <= 0.2:
        return 0.3
    else:
        # linear interpolation between 0.3 and 1.0
        return 0.3 + (ndvi - 0.2) / (0.6 - 0.2) * 0.7


async def calculate_global_economics(
    crop_type: str,
    area_hectares: float,
    ndvi_score: float,
    currency: str,
) -> dict:
    """
    Project crop yield and revenue based on NDVI health, field size,
    and local currency.

    Returns
    -------
    dict with keys: currency, projected_yield_kg, projected_revenue,
    health_penalty, price_per_kg_local, exchange_rate
    """
    base_yield = _STANDARD_YIELDS.get(crop_type, _DEFAULT_YIELD)
    base_price = _BASE_PRICES_USD.get(crop_type, _DEFAULT_PRICE)
    rate = _EXCHANGE_RATES.get(currency, 1.0)

    multiplier = _health_multiplier(ndvi_score if ndvi_score is not None else 0.5)

    projected_yield_kg = base_yield * area_hectares * multiplier
    full_yield_kg = base_yield * area_hectares

    revenue_usd = projected_yield_kg * base_price
    full_revenue_usd = full_yield_kg * base_price

    local_revenue = revenue_usd * rate
    full_local_revenue = full_revenue_usd * rate
    penalty = full_local_revenue - local_revenue  # value at risk

    return {
        "crop_type": crop_type,
        "area_hectares": area_hectares,
        "currency": currency,
        "exchange_rate": rate,
        "price_per_kg_local": round(base_price * rate, 2),
        "projected_yield_kg": round(projected_yield_kg, 2),
        "projected_revenue": round(local_revenue, 2),
        "full_potential_revenue": round(full_local_revenue, 2),
        "health_penalty": round(penalty, 2),
        "ndvi_score": round(ndvi_score if ndvi_score is not None else 0, 3),
        "health_multiplier": round(multiplier, 2),
    }
