from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class FarmSector(Base):
    """A monitored geographic sector of a farm."""

    __tablename__ = "farm_sectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    crop_type = Column(String(100), nullable=True)
    plant_date = Column(DateTime, nullable=True)
    area_hectares = Column(Float, default=1.0)
    country = Column(String(100), default="Unknown")
    currency = Column(String(10), default="USD")
    user_id = Column(String(128), index=True, nullable=True)

    telemetry = relationship("Telemetry", back_populates="sector", lazy="selectin")

    def __repr__(self) -> str:
        return f"<FarmSector id={self.id} name={self.name!r}>"


class Telemetry(Base):
    """Real IoT telemetry reading from a farm sector."""

    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sector_id = Column(Integer, ForeignKey("farm_sectors.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    soil_moisture = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    nitrogen_level = Column(Float, nullable=False)

    sector = relationship("FarmSector", back_populates="telemetry")

    def __repr__(self) -> str:
        return f"<Telemetry id={self.id} sector_id={self.sector_id} ts={self.timestamp}>"


class IoTDevice(Base):
    """A physical IoT device attached to a farm sector (valve, door, pump, etc.)."""

    __tablename__ = "iot_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sector_id = Column(Integer, ForeignKey("farm_sectors.id"), nullable=False)
    device_name = Column(String(255), nullable=False)
    device_type = Column(String(50), nullable=False)   # VALVE, DOOR, PUMP, FAN …
    status = Column(String(20), default="OFF")          # ON, OFF, OPEN, CLOSE

    sector = relationship("FarmSector")

    def __repr__(self) -> str:
        return f"<IoTDevice id={self.id} name={self.device_name!r} status={self.status}>"


class DiseaseThreat(Base):
    """A geo-tagged disease report logged to the global threat radar."""

    __tablename__ = "disease_threats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disease_name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    reported_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<DiseaseThreat id={self.id} disease={self.disease_name!r}>"
