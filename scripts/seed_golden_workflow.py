"""
Golden Workflow Seed Script — populates TiDB with realistic demo data
for a specific Firebase user, ready for a hackathon demo.

Usage:
    python -m scripts.seed_golden_workflow
    (will prompt for Firebase UID interactively)
"""

import asyncio
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.models import FarmSector, Telemetry, IoTDevice, DiseaseThreat


async def seed_data(uid: str):
    """Seed the database with a realistic Kenyan coffee farm."""

    async with AsyncSessionLocal() as db:
        # ── Guard: don't double-seed ──────────────────────────
        existing = await db.execute(
            select(FarmSector).where(FarmSector.user_id == uid)
        )
        if existing.scalar_one_or_none():
            print("⚠  Seed data already exists for this UID. Skipping.")
            return

        now = datetime.utcnow()

        # ── 1. Farm Sector ────────────────────────────────────
        farm = FarmSector(
            name="Ruiru Coffee Estate",
            latitude=-1.148,
            longitude=36.960,
            crop_type="Coffee",
            area_hectares=3.5,
            plant_date=now - timedelta(days=180),
            country="Kenya",
            currency="KES",
            user_id=uid,
        )
        db.add(farm)
        await db.flush()  # get farm.id
        print(f"✅ Created farm: {farm.name} (id={farm.id})")

        # ── 2. Telemetry — 24 hours of hourly readings ───────
        for h in range(24):
            ts = now - timedelta(hours=23 - h)
            reading = Telemetry(
                sector_id=farm.id,
                timestamp=ts,
                soil_moisture=round(random.uniform(42.0, 48.0), 1),
                temperature=round(random.uniform(18.0, 26.0), 1),
                nitrogen_level=round(random.uniform(33.0, 40.0), 1),
            )
            db.add(reading)
        print("✅ Created 24 telemetry readings")

        # ── 3. IoT Devices ────────────────────────────────────
        pump = IoTDevice(
            sector_id=farm.id,
            device_name="Main Pump",
            device_type="PUMP",
            status="OFF",
        )
        valve = IoTDevice(
            sector_id=farm.id,
            device_name="Zone A Valve",
            device_type="VALVE",
            status="OFF",
        )
        db.add_all([pump, valve])
        print("✅ Created 2 IoT devices")

        # ── 4. Disease Threat (nearby, ~3 km away) ────────────
        threat = DiseaseThreat(
            disease_name="Coffee Berry Disease",
            latitude=-1.120,
            longitude=36.950,
            reported_at=now,
        )
        db.add(threat)
        print("✅ Created disease threat: Coffee Berry Disease")

        # ── Commit everything ─────────────────────────────────
        await db.commit()
        print("\n🎉 Golden Workflow seed complete!")
        print(f"   Farm ID   : {farm.id}")
        print(f"   User UID  : {uid}")
        print(f"   Telemetry : 24 readings")
        print(f"   IoT       : 2 devices")
        print(f"   Threats   : 1 nearby disease")


if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  TerraLive — Golden Workflow Database Seeder         ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    uid_input = input("Enter the exact Firebase UID for collistuskibe254@gmail.com: ").strip()
    if not uid_input:
        print("❌ No UID provided. Exiting.")
    else:
        asyncio.run(seed_data(uid_input))
