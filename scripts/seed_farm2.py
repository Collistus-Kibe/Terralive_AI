"""Seed a 2nd demo farm: Kericho Tea Highlands"""
import ssl
from datetime import datetime, timedelta
import random
from sqlalchemy import create_engine, text
import sys
sys.path.insert(0, ".")
from core.config import settings

UID = "U6WuOukAAxbkzfvIUN5KrS4tQhm1"
url = settings.TIDB_URL.replace("+aiomysql", "+pymysql")
ctx = ssl.create_default_context()
eng = create_engine(url, connect_args={"ssl": ctx})
conn = eng.connect()

# Check if 2nd farm already exists
count = conn.execute(text("SELECT COUNT(*) FROM farm_sectors WHERE user_id = :uid AND name = :n"),
                     {"uid": UID, "n": "Kericho Tea Highlands"}).scalar()
if count > 0:
    print("2nd farm already exists. Skipping.")
    conn.close()
    exit(0)

now = datetime.utcnow()
plant_date = now - timedelta(days=120)

# Insert Kericho Tea Highlands  
conn.execute(text("""
    INSERT INTO farm_sectors (name, latitude, longitude, crop_type, area_hectares, plant_date, country, currency, user_id)
    VALUES (:name, :lat, :lon, :crop, :area, :pd, :country, :currency, :uid)
"""), {
    "name": "Kericho Tea Highlands",
    "lat": -0.3689,
    "lon": 35.2863,
    "crop": "Tea",
    "area": 5.2,
    "pd": plant_date,
    "country": "Kenya",
    "currency": "KES",
    "uid": UID,
})

farm_id = conn.execute(text("SELECT id FROM farm_sectors WHERE user_id = :uid ORDER BY id DESC LIMIT 1"),
                       {"uid": UID}).scalar()
print(f"Created farm #{farm_id}: Kericho Tea Highlands")

# 24 hours telemetry with more variation
for h in range(24):
    ts = now - timedelta(hours=23 - h)
    # Tea highlands: cooler, wetter
    conn.execute(text("""
        INSERT INTO telemetry (sector_id, timestamp, soil_moisture, temperature, nitrogen_level)
        VALUES (:sid, :ts, :sm, :temp, :n)
    """), {
        "sid": farm_id,
        "ts": ts,
        "sm": round(52.0 + 6.0 * (h / 24) + random.uniform(-2.5, 2.5), 1),
        "temp": round(18.0 + 3.0 * (h / 24) + random.uniform(-1.5, 1.5), 1),
        "n": round(42.0 + 4.0 * (h / 24) + random.uniform(-2.0, 2.0), 1),
    })
print("Inserted 24h telemetry for Kericho")

# IoT devices
conn.execute(text("""
    INSERT INTO iot_devices (sector_id, device_name, device_type, status)
    VALUES (:sid, :dn, :dt, :s)
"""), {"sid": farm_id, "dn": "Sprinkler System A", "dt": "PUMP", "s": "ON"})
conn.execute(text("""
    INSERT INTO iot_devices (sector_id, device_name, device_type, status)
    VALUES (:sid, :dn, :dt, :s)
"""), {"sid": farm_id, "dn": "Greenhouse Vent", "dt": "FAN", "s": "OFF"})
conn.execute(text("""
    INSERT INTO iot_devices (sector_id, device_name, device_type, status)
    VALUES (:sid, :dn, :dt, :s)
"""), {"sid": farm_id, "dn": "Soil Sensor Node B", "dt": "VALVE", "s": "OFF"})
print("Inserted 3 IoT devices")

conn.commit()
conn.close()
print("Done! 2nd farm seeded.")
