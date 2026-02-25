"""
Weather service — real-time forecast from Open-Meteo (free, no key required).
"""

import httpx

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def get_real_weather(lat: float, lon: float) -> dict:
    """
    Fetch current conditions and a 7-day forecast for the given coordinates
    from the Open-Meteo API.

    Returns a structured dict with ``current`` and ``daily`` keys — no mock data.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,relative_humidity_2m,precipitation,"
            "surface_pressure,cloud_cover,wind_speed_10m,wind_direction_10m"
        ),
        "daily": (
            "temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,precipitation_probability_max"
        ),
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    current_raw = data.get("current", {})
    daily_raw = data.get("daily", {})
    units = data.get("current_units", {})
    daily_units = data.get("daily_units", {})

    # ── Current conditions ────────────────────────────────────
    current = {
        "temperature_c": current_raw.get("temperature_2m"),
        "humidity_pct": current_raw.get("relative_humidity_2m"),
        "precipitation_mm": current_raw.get("precipitation"),
        "pressure_hpa": current_raw.get("surface_pressure"),
        "cloud_cover_pct": current_raw.get("cloud_cover"),
        "wind_speed_kmh": current_raw.get("wind_speed_10m"),
        "wind_direction_deg": current_raw.get("wind_direction_10m"),
    }

    # ── 7-day forecast ────────────────────────────────────────
    dates = daily_raw.get("time", [])
    daily = []
    for i, date in enumerate(dates):
        daily.append({
            "date": date,
            "temp_max_c": (daily_raw.get("temperature_2m_max") or [])[i] if i < len(daily_raw.get("temperature_2m_max", [])) else None,
            "temp_min_c": (daily_raw.get("temperature_2m_min") or [])[i] if i < len(daily_raw.get("temperature_2m_min", [])) else None,
            "precipitation_sum_mm": (daily_raw.get("precipitation_sum") or [])[i] if i < len(daily_raw.get("precipitation_sum", [])) else None,
            "precipitation_probability_pct": (daily_raw.get("precipitation_probability_max") or [])[i] if i < len(daily_raw.get("precipitation_probability_max", [])) else None,
        })

    return {
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timezone": data.get("timezone"),
        "current": current,
        "daily_forecast": daily,
    }
