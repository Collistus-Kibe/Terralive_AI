"""Update 1st farm telemetry with more visual variation for chart"""
import ssl
from datetime import datetime, timedelta
import random, math
from sqlalchemy import create_engine, text
import sys
sys.path.insert(0, ".")
from core.config import settings

UID = "U6WuOukAAxbkzfvIUN5KrS4tQhm1"
url = settings.TIDB_URL.replace("+aiomysql", "+pymysql")
ctx = ssl.create_default_context()
eng = create_engine(url, connect_args={"ssl": ctx})
conn = eng.connect()

# Get farm 1 ID
farm_id = conn.execute(text(
    "SELECT id FROM farm_sectors WHERE user_id = :uid AND name = :n"
), {"uid": UID, "n": "Ruiru Coffee Estate"}).scalar()

if not farm_id:
    print("Farm not found!")
    exit(1)

# Delete old telemetry
conn.execute(text("DELETE FROM telemetry WHERE sector_id = :sid"), {"sid": farm_id})

now = datetime.utcnow()
# More interesting data with sinusoidal variation (simulates day/night cycle)
for h in range(24):
    ts = now - timedelta(hours=23 - h)
    hour_frac = h / 24.0
    # Moisture dips during midday (evaporation), rises at night
    sm = 55.0 - 12.0 * math.sin(math.pi * hour_frac) + random.uniform(-1.5, 1.5)
    # Temp peaks at midday
    temp = 20.0 + 7.0 * math.sin(math.pi * hour_frac) + random.uniform(-0.8, 0.8)
    # Nitrogen slowly rises (fertilizer dissolving)
    n = 32.0 + 10.0 * hour_frac + random.uniform(-1.0, 1.0)

    conn.execute(text("""
        INSERT INTO telemetry (sector_id, timestamp, soil_moisture, temperature, nitrogen_level)
        VALUES (:sid, :ts, :sm, :temp, :n)
    """), {"sid": farm_id, "ts": ts, "sm": round(sm, 1), "temp": round(temp, 1), "n": round(n, 1)})

conn.commit()
conn.close()
print(f"Updated 24h telemetry for farm #{farm_id} with varied data.")
