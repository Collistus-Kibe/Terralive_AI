"""
Precision Agriculture Service — calculates exact water and fertiliser
needs based on crop type, field area, and live telemetry readings.
"""

# ── Crop-specific optimal parameters ─────────────────────────
_CROP_PROFILES = {
    "Maize": {"optimal_moisture": 60.0, "optimal_nitrogen": 40.0, "water_factor": 50_000, "npk_factor": 25},
    "Coffee": {"optimal_moisture": 55.0, "optimal_nitrogen": 35.0, "water_factor": 45_000, "npk_factor": 20},
    "Tea": {"optimal_moisture": 65.0, "optimal_nitrogen": 45.0, "water_factor": 55_000, "npk_factor": 30},
    "Wheat": {"optimal_moisture": 50.0, "optimal_nitrogen": 38.0, "water_factor": 40_000, "npk_factor": 22},
    "Rice": {"optimal_moisture": 80.0, "optimal_nitrogen": 42.0, "water_factor": 70_000, "npk_factor": 28},
    "Tomato": {"optimal_moisture": 65.0, "optimal_nitrogen": 50.0, "water_factor": 55_000, "npk_factor": 35},
    "Banana": {"optimal_moisture": 70.0, "optimal_nitrogen": 38.0, "water_factor": 60_000, "npk_factor": 25},
}

# Fallback for unknown crops
_DEFAULT_PROFILE = {"optimal_moisture": 60.0, "optimal_nitrogen": 40.0, "water_factor": 50_000, "npk_factor": 25}


async def calculate_treatment(
    crop_type: str,
    area_hectares: float,
    current_moisture: float,
    current_nitrogen: float,
) -> dict:
    """
    Calculate exact water and NPK fertiliser requirements for a field.

    Parameters
    ----------
    crop_type : str
        The crop currently planted (e.g. "Maize", "Coffee").
    area_hectares : float
        Total field area in hectares.
    current_moisture : float
        Current soil moisture percentage from telemetry.
    current_nitrogen : float
        Current nitrogen level (mg/kg) from telemetry.

    Returns
    -------
    dict with keys: water_liters_needed, npk_kg_needed, recommendation
    """
    profile = _CROP_PROFILES.get(crop_type, _DEFAULT_PROFILE)

    optimal_moisture = profile["optimal_moisture"]
    optimal_nitrogen = profile["optimal_nitrogen"]
    water_factor = profile["water_factor"]     # litres per hectare at 100 % deficit
    npk_factor = profile["npk_factor"]         # kg per hectare at 100 % deficit

    # ── Water deficit ────────────────────────────────────────
    moisture_gap = max(0, optimal_moisture - current_moisture)  # % points
    moisture_ratio = moisture_gap / optimal_moisture if optimal_moisture else 0
    water_liters = round(water_factor * area_hectares * moisture_ratio, 1)

    # ── Nitrogen / NPK deficit ───────────────────────────────
    nitrogen_gap = max(0, optimal_nitrogen - current_nitrogen)
    nitrogen_ratio = nitrogen_gap / optimal_nitrogen if optimal_nitrogen else 0
    npk_kg = round(npk_factor * area_hectares * nitrogen_ratio, 2)

    # ── Recommendation ───────────────────────────────────────
    parts = []
    if water_liters > 0:
        parts.append(
            f"Irrigate with {water_liters:,.0f} litres of water "
            f"({water_liters / area_hectares:,.0f} L/ha) to reach "
            f"{optimal_moisture}% soil moisture."
        )
    else:
        parts.append("Soil moisture is at or above optimal — no irrigation needed.")

    if npk_kg > 0:
        parts.append(
            f"Apply {npk_kg:,.1f} kg of NPK fertiliser "
            f"({npk_kg / area_hectares:,.1f} kg/ha) to reach "
            f"{optimal_nitrogen} mg/kg nitrogen."
        )
    else:
        parts.append("Nitrogen levels are sufficient — no fertiliser needed.")

    return {
        "crop_type": crop_type,
        "area_hectares": area_hectares,
        "current_moisture_pct": current_moisture,
        "current_nitrogen_mgkg": current_nitrogen,
        "water_liters_needed": water_liters,
        "npk_kg_needed": npk_kg,
        "recommendation": " ".join(parts),
    }
