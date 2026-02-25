"""One-shot: seed the demo farm for collistuskibe254@gmail.com"""
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

# Check if already seeded
count = conn.execute(text("SELECT COUNT(*) FROM farm_sectors WHERE user_id = :uid"), {"uid": UID}).scalar()
if count > 0:
    print(f"✅ Demo account already has {count} farm(s). Skipping seed.")
    conn.close()
    exit(0)

now = datetime.utcnow()
plant_date = now - timedelta(days=180)

# 1. Insert demo farm
conn.execute(text("""
    INSERT INTO farm_sectors (name, latitude, longitude, crop_type, area_hectares, plant_date, country, currency, user_id)
    VALUES (:name, :lat, :lon, :crop, :area, :pd, :country, :currency, :uid)
"""), {
    "name": "Ruiru Coffee Estate",
    "lat": -1.148,
    "lon": 36.960,
    "crop": "Coffee",
    "area": 3.5,
    "pd": plant_date,
    "country": "Kenya",
    "currency": "KES",
    "uid": UID,
})

# Get farm id
farm_id = conn.execute(text("SELECT id FROM farm_sectors WHERE user_id = :uid ORDER BY id DESC LIMIT 1"), {"uid": UID}).scalar()
print(f"🌱 Created farm #{farm_id}: Ruiru Coffee Estate")

# 2. 24 hours of telemetry
for h in range(24):
    ts = now - timedelta(hours=23 - h)
    conn.execute(text("""
        INSERT INTO telemetry (sector_id, timestamp, soil_moisture, temperature, nitrogen_level)
        VALUES (:sid, :ts, :sm, :temp, :n)
    """), {
        "sid": farm_id,
        "ts": ts,
        "sm": round(random.uniform(42.0, 48.0), 1),
        "temp": round(random.uniform(22.0, 26.0), 1),
        "n": round(random.uniform(35.0, 40.0), 1),
    })
print("📊 Inserted 24h telemetry")

# 3. IoT devices
conn.execute(text("""
    INSERT INTO iot_devices (sector_id, device_name, device_type, status)
    VALUES (:sid, :dn, :dt, :s)
"""), {"sid": farm_id, "dn": "Main Irrigation Pump", "dt": "PUMP", "s": "OFF"})
conn.execute(text("""
    INSERT INTO iot_devices (sector_id, device_name, device_type, status)
    VALUES (:sid, :dn, :dt, :s)
"""), {"sid": farm_id, "dn": "Sector A Valve", "dt": "VALVE", "s": "OFF"})
print("🔌 Inserted 2 IoT devices")

# 4. Disease threat
conn.execute(text("""
    INSERT INTO disease_threats (disease_name, latitude, longitude, reported_at)
    VALUES (:dn, :lat, :lon, :ra)
"""), {"dn": "Coffee Berry Disease", "lat": -1.120, "lon": 36.950, "ra": now})
print("⚠️  Inserted disease threat")

conn.commit()
conn.close()
print("\n✅ Demo data seeded successfully!")
