import random
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, AsyncSessionLocal
from core.models import FarmSector, Telemetry, IoTDevice, DiseaseThreat
from services.earth_engine import get_real_ndvi
from services.weather import get_real_weather
from services.firebase_client import get_firestore_client
from services.economics import calculate_global_economics
from services.threat_radar import scan_and_alert_sector
from api.deps import get_current_user

router = APIRouter()


# ── Request / Response schemas ───────────────────────────
class SectorIn(BaseModel):
    """Schema for creating a new farm sector."""

    name: str
    latitude: float
    longitude: float
    crop_type: Optional[str] = None
    area_hectares: float = 1.0
    country: str = "Unknown"
    currency: str = "USD"


class SectorUpdate(BaseModel):
    """Schema for patching sector fields."""

    crop_type: Optional[str] = None
    plant_date: Optional[datetime] = None
    area_hectares: Optional[float] = None
    country: Optional[str] = None
    currency: Optional[str] = None


class SectorOut(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    crop_type: Optional[str] = None
    plant_date: Optional[datetime] = None
    area_hectares: float = 1.0
    country: str = "Unknown"
    currency: str = "USD"

    class Config:
        from_attributes = True


class TelemetryIn(BaseModel):
    """Schema for ingesting a telemetry reading from an IoT device."""

    sector_id: int
    soil_moisture: float
    temperature: float
    nitrogen_level: float
    timestamp: datetime | None = None


class TelemetryOut(BaseModel):
    id: int
    sector_id: int
    timestamp: datetime
    soil_moisture: float
    temperature: float
    nitrogen_level: float

    class Config:
        from_attributes = True


class SectorHealthOut(BaseModel):
    sector_id: int
    sector_name: str
    latitude: float
    longitude: float
    latest_telemetry: TelemetryOut | None
    telemetry_history: List[TelemetryOut]
    ndvi: float | None


# ── Sector Endpoints ────────────────────────────────────
@router.get("/sectors", response_model=List[SectorOut])
async def list_sectors(
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(get_current_user),
):
    """Return every registered farm for the logged-in user.
    For the demo account, auto-seed realistic data on first login."""
    user_id = user_data["uid"]

    result = await db.execute(
        select(FarmSector)
        .where(FarmSector.user_id == user_id)
        .order_by(FarmSector.id)
    )
    farms = result.scalars().all()

    # ── Auto-seed for the demo account ────────────────────
    if not farms and user_data.get("email") == "collistuskibe254@gmail.com":
        now = datetime.utcnow()

        # 1. Create demo farm
        farm = FarmSector(
            name="Ruiru Coffee Estate",
            latitude=-1.148,
            longitude=36.960,
            crop_type="Coffee",
            area_hectares=3.5,
            plant_date=now - timedelta(days=180),
            country="Kenya",
            currency="KES",
            user_id=user_id,
        )
        db.add(farm)
        await db.flush()

        # 2. 24 hours of telemetry
        for h in range(24):
            ts = now - timedelta(hours=23 - h)
            db.add(Telemetry(
                sector_id=farm.id,
                timestamp=ts,
                soil_moisture=round(random.uniform(42.0, 48.0), 1),
                temperature=round(random.uniform(22.0, 26.0), 1),
                nitrogen_level=round(random.uniform(35.0, 40.0), 1),
            ))

        # 3. IoT devices
        db.add(IoTDevice(
            sector_id=farm.id,
            device_name="Main Irrigation Pump",
            device_type="PUMP",
            status="OFF",
        ))
        db.add(IoTDevice(
            sector_id=farm.id,
            device_name="Sector A Valve",
            device_type="VALVE",
            status="OFF",
        ))

        # 4. Disease threat (nearby)
        db.add(DiseaseThreat(
            disease_name="Coffee Berry Disease",
            latitude=-1.120,
            longitude=36.950,
            reported_at=now,
        ))

        await db.commit()
        print(f"[AutoSeed] Seeded demo data for {user_data['email']}")

        # Re-query
        result = await db.execute(
            select(FarmSector)
            .where(FarmSector.user_id == user_id)
            .order_by(FarmSector.id)
        )
        farms = result.scalars().all()

    return farms


@router.post("/sectors", response_model=SectorOut, status_code=201)
async def create_sector(
    payload: SectorIn,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(get_current_user),
):
    """Register a new farm in TiDB for the logged-in user."""
    user_id = user_data["uid"]
    sector = FarmSector(
        name=payload.name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        crop_type=payload.crop_type,
        area_hectares=payload.area_hectares,
        country=payload.country,
        currency=payload.currency,
        user_id=user_id,
    )
    db.add(sector)
    await db.commit()
    await db.refresh(sector)
    return sector


@router.patch("/sector/{sector_id}", response_model=SectorOut)
async def update_sector(
    sector_id: int,
    payload: SectorUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Manually update crop lifecycle or area fields for a sector."""
    result = await db.execute(
        select(FarmSector).where(FarmSector.id == sector_id)
    )
    sector = result.scalar_one_or_none()
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector not found")

    if payload.crop_type is not None:
        sector.crop_type = payload.crop_type
    if payload.plant_date is not None:
        sector.plant_date = payload.plant_date
    if payload.area_hectares is not None:
        sector.area_hectares = payload.area_hectares
    if payload.country is not None:
        sector.country = payload.country
    if payload.currency is not None:
        sector.currency = payload.currency

    await db.commit()
    await db.refresh(sector)
    return sector


# ── Telemetry Endpoints ─────────────────────────────────
@router.post("/telemetry", response_model=TelemetryOut, status_code=201)
async def ingest_telemetry(
    payload: TelemetryIn,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a real IoT telemetry reading and persist it to TiDB."""

    result = await db.execute(
        select(FarmSector).where(FarmSector.id == payload.sector_id)
    )
    sector = result.scalar_one_or_none()
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector not found")

    record = Telemetry(
        sector_id=payload.sector_id,
        soil_moisture=payload.soil_moisture,
        temperature=payload.temperature,
        nitrogen_level=payload.nitrogen_level,
        timestamp=payload.timestamp or datetime.utcnow(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ── Health Endpoint ──────────────────────────────────────
@router.get("/sector/{sector_id}/health", response_model=SectorHealthOut)
async def get_sector_health(
    sector_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Combined real-time health snapshot for a sector:
    - Recent telemetry history from TiDB (last 20 readings)
    - Live NDVI from Google Earth Engine (Sentinel-2)
    """

    result = await db.execute(
        select(FarmSector).where(FarmSector.id == sector_id)
    )
    sector = result.scalar_one_or_none()
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector not found")

    # Recent telemetry (newest first, limited to 20 for charting)
    tel_result = await db.execute(
        select(Telemetry)
        .where(Telemetry.sector_id == sector_id)
        .order_by(Telemetry.timestamp.desc())
        .limit(20)
    )
    rows = list(tel_result.scalars().all())
    latest = rows[0] if rows else None

    # Real satellite NDVI
    ndvi = await get_real_ndvi(sector.latitude, sector.longitude)

    return SectorHealthOut(
        sector_id=sector.id,
        sector_name=sector.name,
        latitude=sector.latitude,
        longitude=sector.longitude,
        latest_telemetry=latest,
        telemetry_history=rows,
        ndvi=ndvi,
    )


# ── Weather Endpoint ────────────────────────────────────
@router.get("/sector/{sector_id}/weather")
async def get_sector_weather(
    sector_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch the current weather and 7-day forecast for a sector's
    coordinates from the Open-Meteo API.
    """
    result = await db.execute(
        select(FarmSector).where(FarmSector.id == sector_id)
    )
    sector = result.scalar_one_or_none()
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector not found")

    weather = await get_real_weather(sector.latitude, sector.longitude)
    return weather


# ── Economics Endpoint ────────────────────────────────────────
@router.get("/sector/{sector_id}/economics")
async def get_sector_economics(
    sector_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate projected yield and revenue for a sector
    based on live NDVI and the sector's local currency.
    """
    result = await db.execute(
        select(FarmSector).where(FarmSector.id == sector_id)
    )
    sector = result.scalar_one_or_none()
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector not found")

    if not sector.crop_type:
        return {"error": "No crop planted in this sector"}

    ndvi = await get_real_ndvi(sector.latitude, sector.longitude)
    if ndvi is None:
        ndvi = 0.5

    economics = await calculate_global_economics(
        crop_type=sector.crop_type,
        area_hectares=sector.area_hectares or 1.0,
        ndvi_score=ndvi,
        currency=sector.currency or "USD",
    )
    return economics


# ── Action Logs Endpoint ────────────────────────────────
@router.get("/sector/{sector_id}/logs")
async def get_sector_logs(
    sector_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch the most recent Farm Action Logs from Firestore for the
    given sector, ordered by timestamp descending, limited to 10.

    Before returning, runs the Community Threat Radar scan to
    auto-generate CRITICAL alerts for any nearby diseases.
    Falls back to intelligent demo logs if Firestore is unavailable.
    """
    import asyncio

    # Look up sector coords for the radar scan
    result = await db.execute(
        select(FarmSector).where(FarmSector.id == sector_id)
    )
    sector = result.scalar_one_or_none()
    if sector:
        try:
            await scan_and_alert_sector(sector_id, sector.latitude, sector.longitude)
        except Exception as e:
            print(f"[Radar] scan error: {e}")

    # Try Firestore first
    logs = []
    try:
        def _query():
            fs = get_firestore_client()
            docs = (
                fs.collection("farm_action_logs")
                .where("sector_id", "==", sector_id)
                .order_by("timestamp", direction="DESCENDING")
                .limit(10)
                .stream()
            )
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]

        logs = await asyncio.to_thread(_query)
    except Exception as e:
        print(f"[Logs] Firestore query failed: {e}")

    # Fallback: generate demo logs if Firestore returned nothing
    if not logs:
        now = datetime.utcnow()
        crop = sector.crop_type if sector else "Crop"
        logs = [
            {
                "id": "auto-1",
                "sector_id": sector_id,
                "title": "⚠️ COMMUNITY RADAR ALERT",
                "description": f"Coffee Berry Disease detected 3.4km away. AI recommends Copper Fungicide protocol via IoT irrigation.",
                "urgency": "CRITICAL",
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
            },
            {
                "id": "auto-2",
                "sector_id": sector_id,
                "title": "🛰️ Satellite NDVI Assessment",
                "description": f"Sentinel-2 analysis complete. {crop} canopy health scored 0.72 — Excellent vegetation detected across 3.5 ha.",
                "urgency": "LOW",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
            },
            {
                "id": "auto-3",
                "sector_id": sector_id,
                "title": "💧 Automated Irrigation Triggered",
                "description": "Soil moisture dropped below 44%. Main Pump activated for Zone A — estimated 25 min cycle.",
                "urgency": "MEDIUM",
                "timestamp": (now - timedelta(hours=2)).isoformat(),
            },
            {
                "id": "auto-4",
                "sector_id": sector_id,
                "title": "🧪 Soil Analysis Complete",
                "description": f"Nitrogen level at 37.2 mg/kg — within optimal range for {crop}. No fertiliser adjustment needed.",
                "urgency": "LOW",
                "timestamp": (now - timedelta(hours=6)).isoformat(),
            },
            {
                "id": "auto-5",
                "sector_id": sector_id,
                "title": "🛡️ Disease Prevention Protocol",
                "description": "Preventative fungicide spray scheduled for dawn. Sector A Valve will open at 05:30 EAT.",
                "urgency": "HIGH",
                "timestamp": (now - timedelta(hours=12)).isoformat(),
            },
        ]

    return logs


# ── IoT Devices Endpoint ──────────────────────────────
@router.get("/sector/{sector_id}/iot")
async def get_sector_iot(
    sector_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Return all IoT devices attached to a given sector.
    """
    result = await db.execute(
        select(IoTDevice).where(IoTDevice.sector_id == sector_id)
        .order_by(IoTDevice.id)
    )
    devices = result.scalars().all()
    return [
        {
            "id": d.id,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "status": d.status,
        }
        for d in devices
    ]
