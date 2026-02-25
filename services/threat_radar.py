"""
Threat Radar — Geospatial disease alert engine.

Uses the Haversine formula to find confirmed crop diseases within
a 15 km radius of a farm sector and automatically pushes CRITICAL
alerts into the Firebase Action Logs.
"""

from datetime import datetime, timezone

from sqlalchemy import select, text

from core.database import AsyncSessionLocal
from core.models import DiseaseThreat, FarmSector
from services.firebase_client import get_firestore_client


async def log_global_threat(disease_name: str, lat: float, lon: float) -> dict:
    """
    Save a new disease threat report to TiDB so it appears on
    the global geospatial radar for all nearby sectors.
    """
    async with AsyncSessionLocal() as db:
        threat = DiseaseThreat(
            disease_name=disease_name,
            latitude=lat,
            longitude=lon,
            reported_at=datetime.now(timezone.utc),
        )
        db.add(threat)
        await db.commit()
        await db.refresh(threat)
        print(f"[Radar] Logged threat: {disease_name} at ({lat}, {lon})")
        return {
            "status": "logged",
            "threat_id": threat.id,
            "disease": disease_name,
            "lat": lat,
            "lon": lon,
        }


_HAVERSINE_SQL = text("""
    SELECT disease_name,
           (6371 * acos(
               cos(radians(:lat)) * cos(radians(latitude))
               * cos(radians(longitude) - radians(:lon))
               + sin(radians(:lat)) * sin(radians(latitude))
           )) AS distance
    FROM disease_threats
    HAVING distance < 15
    ORDER BY distance ASC
    LIMIT 1
""")


async def scan_and_alert_sector(sector_id: int, lat: float, lon: float) -> None:
    """
    Run Haversine search for threats within 15 km of (lat, lon).
    If found, push a CRITICAL alert into the sector's Firebase action logs.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(_HAVERSINE_SQL, {"lat": lat, "lon": lon})
        row = result.first()

    if row is None:
        return  # No nearby threats — nothing to do

    disease_name = row[0]
    distance = row[1]

    # Write alert to Firebase Action Logs
    try:
        fs = get_firestore_client()
        fs.collection("farm_action_logs").add({
            "sector_id": sector_id,
            "title": "\u26a0\ufe0f COMMUNITY RADAR ALERT",
            "description": (
                f"Warning: {disease_name} detected {round(distance, 1)}km away. "
                "Suggested Action: Preventative measures required. "
                "Ask Terra to schedule a spray or actuate farm infrastructure."
            ),
            "urgency": "CRITICAL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        print(f"[Radar] CRITICAL alert for sector {sector_id}: {disease_name} @ {round(distance, 1)}km")
    except Exception as e:
        print(f"[Radar] Firebase write error: {e}")
