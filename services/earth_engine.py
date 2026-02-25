import asyncio
from datetime import datetime, timedelta

import ee

from core.config import settings


async def init_ee() -> None:
    """Authenticate and initialize Google Earth Engine using a service account."""
    credentials = ee.ServiceAccountCredentials(
        email=None,  # inferred from the JSON key file
        key_file=settings.GOOGLE_APPLICATION_CREDENTIALS,
    )
    ee.Initialize(credentials=credentials)
    print("[EE] Google Earth Engine initialized successfully.")


async def get_real_ndvi(lat: float, lon: float) -> float | None:
    """
    Query Sentinel-2 Surface Reflectance (COPERNICUS/S2_SR) for the most
    recent NDVI value at the given coordinate over the last 30 days.

    NDVI = (B8 - B4) / (B8 + B4)

    Returns the raw float NDVI value, or None if no imagery is available.
    """

    def _query() -> float | None:
        point = ee.Geometry.Point([lon, lat])

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR")
            .filterBounds(point)
            .filterDate(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )
            .sort("system:time_start", opt_ascending=False)
        )

        count = collection.size().getInfo()
        if count == 0:
            return None

        latest = collection.first()

        ndvi = latest.normalizedDifference(["B8", "B4"]).rename("NDVI")

        value = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=10,
        ).getInfo()

        return value.get("NDVI")

    # Earth Engine client library is synchronous — run in a thread pool
    # so we don't block the async event loop.
    return await asyncio.to_thread(_query)
