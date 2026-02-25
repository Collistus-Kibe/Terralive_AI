"""
Gemini Multimodal Live API — WebSocket relay client with Tool Calling.

Connects to Google's BidiGenerateContent streaming endpoint, relays
PCM audio between the browser and Gemini 2.0 Flash, and executes
function calls (get_all_sectors, get_sector_health, get_weather_forecast,
search_agronomy_database, log_farm_action, calculate_field_treatment,
update_crop_lifecycle, forecast_global_revenue, actuate_iot,
log_disease_threat) against TiDB, Earth Engine, Open-Meteo,
Elasticsearch RAG, Firebase Firestore, the precision-ag calculator,
the global economics engine, IoT infrastructure, and the threat radar.
"""

import asyncio
import json
from datetime import datetime, timezone

import websockets
from sqlalchemy import select

from core.config import settings
from core.database import AsyncSessionLocal
from core.models import FarmSector, Telemetry, IoTDevice
from services.earth_engine import get_real_ndvi
from services.weather import get_real_weather
from services.rag_engine import search_agronomy_knowledge
from services.firebase_client import get_firestore_client
from services.precision_ag import calculate_treatment
from services.economics import calculate_global_economics
from services.threat_radar import log_global_threat

# ── Gemini Live WebSocket endpoint ───────────────────────────
_GEMINI_WS_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
    f"?key={settings.GEMINI_API_KEY}"
)

# ── Function Declarations ────────────────────────────────────
_TOOL_DECLARATIONS = [
    {
        "functionDeclarations": [
            {
                "name": "get_all_sectors",
                "description": (
                    "Retrieves a list of all registered farm sectors, "
                    "returning their IDs, names, and coordinates."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                },
            },
            {
                "name": "get_sector_health",
                "description": (
                    "Fetches the current soil moisture, temperature, "
                    "nitrogen levels, and real satellite NDVI health "
                    "for a specific sector ID."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "sector_id": {
                            "type": "INTEGER",
                            "description": "The numeric ID of the farm sector to query.",
                        },
                    },
                    "required": ["sector_id"],
                },
            },
            {
                "name": "get_weather_forecast",
                "description": (
                    "Fetches the current weather conditions and 7-day "
                    "precipitation/temperature forecast for a specific "
                    "farm sector."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "sector_id": {
                            "type": "INTEGER",
                            "description": "The numeric ID of the farm sector to query.",
                        },
                    },
                    "required": ["sector_id"],
                },
            },
            {
                "name": "search_agronomy_database",
                "description": (
                    "Searches the official agricultural knowledge base "
                    "for specific crop diseases, treatments, fertiliser "
                    "recommendations, and best practices. Use this "
                    "whenever the farmer asks about identifying or "
                    "treating a crop problem."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "search_query": {
                            "type": "STRING",
                            "description": "Natural-language search query about the crop issue.",
                        },
                    },
                    "required": ["search_query"],
                },
            },
            {
                "name": "log_farm_action",
                "description": (
                    "Creates a task, alert, or log entry in the farm "
                    "management system. Use this when the user asks to "
                    "schedule a spray, log a disease sighting, set a "
                    "reminder, or remember a task."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "sector_id": {
                            "type": "INTEGER",
                            "description": "The numeric ID of the farm sector this action relates to.",
                        },
                        "title": {
                            "type": "STRING",
                            "description": "Short title for the action log.",
                        },
                        "urgency": {
                            "type": "STRING",
                            "description": "Urgency level.",
                            "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                        },
                        "description": {
                            "type": "STRING",
                            "description": "Detailed description of the action or observation.",
                        },
                    },
                    "required": ["sector_id", "title", "urgency", "description"],
                },
            },
            {
                "name": "calculate_field_treatment",
                "description": (
                    "Calculates the exact litres of water and kilograms "
                    "of fertiliser needed for a sector based on its area, "
                    "crop type, and live telemetry. Always confirm the "
                    "crop type and area before giving volume recommendations."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "sector_id": {
                            "type": "INTEGER",
                            "description": "The numeric ID of the farm sector.",
                        },
                    },
                    "required": ["sector_id"],
                },
            },
            {
                "name": "update_crop_lifecycle",
                "description": (
                    "Updates the database when a farmer plants a new crop "
                    "or harvests an existing one. Sets the crop type and "
                    "planting date on PLANT, or clears them on HARVEST."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "sector_id": {
                            "type": "INTEGER",
                            "description": "The numeric ID of the farm sector.",
                        },
                        "crop_type": {
                            "type": "STRING",
                            "description": "Name of the crop being planted (e.g. Maize, Coffee, Tea).",
                        },
                        "action": {
                            "type": "STRING",
                            "description": "PLANT or HARVEST.",
                            "enum": ["PLANT", "HARVEST"],
                        },
                    },
                    "required": ["sector_id", "action"],
                },
            },
            {
                "name": "forecast_global_revenue",
                "description": (
                    "Forecasts the projected crop yield and revenue for "
                    "a sector in the farmer's local currency. Uses live "
                    "NDVI health data to adjust projections. Always "
                    "highlight the financial value at risk due to poor "
                    "crop health."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "sector_id": {
                            "type": "INTEGER",
                            "description": "The numeric ID of the farm sector.",
                        },
                    },
                    "required": ["sector_id"],
                },
            },
            {
                "name": "actuate_iot",
                "description": (
                    "Turns farm infrastructure on/off or opens/closes "
                    "doors and valves. Use this when the user asks to "
                    "turn on irrigation, open a greenhouse door, etc."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "device_id": {
                            "type": "INTEGER",
                            "description": "The numeric ID of the IoT device.",
                        },
                        "command": {
                            "type": "STRING",
                            "description": "ON, OFF, OPEN, or CLOSE.",
                            "enum": ["ON", "OFF", "OPEN", "CLOSE"],
                        },
                    },
                    "required": ["device_id", "command"],
                },
            },
            {
                "name": "log_disease_threat",
                "description": (
                    "Logs a confirmed crop disease to the global "
                    "geospatial radar so nearby farmers are warned via "
                    "automated alerts. Use this after visually "
                    "identifying a disease via camera or when the user "
                    "reports a disease."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "disease_name": {
                            "type": "STRING",
                            "description": "Name of the disease (e.g. Fall Armyworm, Maize Lethal Necrosis).",
                        },
                        "latitude": {
                            "type": "NUMBER",
                            "description": "Latitude of the disease sighting.",
                        },
                        "longitude": {
                            "type": "NUMBER",
                            "description": "Longitude of the disease sighting.",
                        },
                    },
                    "required": ["disease_name", "latitude", "longitude"],
                },
            },
        ]
    }
]

# ── Setup payload ────────────────────────────────────────────
_SETUP_MESSAGE = {
    "setup": {
        "model": "models/gemini-2.0-flash-exp",
        "generationConfig": {
            "responseModalities": ["AUDIO", "TEXT"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": "Aoede"
                    }
                }
            },
        },
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "You are TerraLive, an expert AI agronomist, farm "
                        "management co-pilot, and global agricultural "
                        "financial advisor. You are deeply aware of local "
                        "farming contexts worldwide. If the user speaks "
                        "Swahili, reply fluently in Swahili. You will "
                        "receive financial projections in the user's local "
                        "currency — speak naturally using their currency "
                        "name (e.g., Dollars, Euros, Shillings, Rupees). "
                        "Always highlight the financial value at risk due "
                        "to crop health when presenting revenue forecasts. "
                        "You have tools to calculate exact fertiliser and "
                        "irrigation volumes — always confirm the crop type "
                        "and field area before giving volume recommendations. "
                        "You have physical control over the farm's IoT "
                        "infrastructure. If the user asks to turn on "
                        "irrigation, open doors, or control any device, use "
                        "the actuate_iot tool. If you identify a crop disease "
                        "visually, ALWAYS log it using the log_disease_threat "
                        "tool so neighboring farms are warned. "
                        "When asked, suggest the best crops to plant, optimal "
                        "planting dates, weeding schedules, and harvest times. "
                        "When a farmer asks about a crop disease or treatment, "
                        "ALWAYS use the search_agronomy_database tool first. "
                        "When the user asks to schedule, log, or remember "
                        "something, use the log_farm_action tool. Keep "
                        "responses concise, professional, and directly useful "
                        "to a farmer in the field."
                    )
                }
            ]
        },
        "tools": _TOOL_DECLARATIONS,
    }
}


# ══════════════════════════════════════════════════════════════
#  Tool Execution
# ══════════════════════════════════════════════════════════════
async def _execute_tool(name: str, args: dict) -> dict:
    """
    Execute a declared tool by querying TiDB / Earth Engine
    and return a result dict that will be sent back to Gemini.
    """
    if name == "get_all_sectors":
        return await _tool_get_all_sectors()
    elif name == "get_sector_health":
        sector_id = int(args.get("sector_id", 0))
        return await _tool_get_sector_health(sector_id)
    elif name == "get_weather_forecast":
        sector_id = int(args.get("sector_id", 0))
        return await _tool_get_weather_forecast(sector_id)
    elif name == "search_agronomy_database":
        query = args.get("search_query", "")
        result_text = await search_agronomy_knowledge(query)
        return {"excerpts": result_text}
    elif name == "log_farm_action":
        return await _tool_log_farm_action(args)
    elif name == "calculate_field_treatment":
        sector_id = int(args.get("sector_id", 0))
        return await _tool_calculate_field_treatment(sector_id)
    elif name == "update_crop_lifecycle":
        return await _tool_update_crop_lifecycle(args)
    elif name == "forecast_global_revenue":
        sector_id = int(args.get("sector_id", 0))
        return await _tool_forecast_global_revenue(sector_id)
    elif name == "actuate_iot":
        device_id = int(args.get("device_id", 0))
        command = args.get("command", "OFF").upper()
        return await _tool_actuate_iot(device_id, command)
    elif name == "log_disease_threat":
        disease = args.get("disease_name", "Unknown Disease")
        lat = float(args.get("latitude", 0))
        lon = float(args.get("longitude", 0))
        return await log_global_threat(disease, lat, lon)
    else:
        return {"error": f"Unknown tool: {name}"}


async def _tool_get_all_sectors() -> dict:
    """Query TiDB for every FarmSector and return as a list of dicts."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(FarmSector).order_by(FarmSector.id))
        sectors = result.scalars().all()

        sector_list = [
            {
                "id": s.id,
                "name": s.name,
                "latitude": s.latitude,
                "longitude": s.longitude,
            }
            for s in sectors
        ]

    return {"sectors": sector_list, "count": len(sector_list)}


async def _tool_get_sector_health(sector_id: int) -> dict:
    """
    Fetch the latest telemetry from TiDB and live NDVI from Earth Engine
    for the given sector.
    """
    async with AsyncSessionLocal() as db:
        # Get sector
        result = await db.execute(
            select(FarmSector).where(FarmSector.id == sector_id)
        )
        sector = result.scalar_one_or_none()
        if sector is None:
            return {"error": f"Sector {sector_id} not found"}

        # Latest telemetry
        tel_result = await db.execute(
            select(Telemetry)
            .where(Telemetry.sector_id == sector_id)
            .order_by(Telemetry.timestamp.desc())
            .limit(1)
        )
        telemetry = tel_result.scalar_one_or_none()

    # Real satellite NDVI (outside the db session)
    ndvi = await get_real_ndvi(sector.latitude, sector.longitude)

    health = {
        "sector_id": sector.id,
        "sector_name": sector.name,
        "latitude": sector.latitude,
        "longitude": sector.longitude,
        "ndvi": ndvi,
    }

    if telemetry:
        health.update({
            "soil_moisture": telemetry.soil_moisture,
            "temperature": telemetry.temperature,
            "nitrogen_level": telemetry.nitrogen_level,
            "last_reading": telemetry.timestamp.isoformat(),
        })
    else:
        health["telemetry"] = "No readings available"

    return health


async def _tool_get_weather_forecast(sector_id: int) -> dict:
    """
    Look up the sector's coordinates from TiDB, then fetch real weather
    from Open-Meteo.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FarmSector).where(FarmSector.id == sector_id)
        )
        sector = result.scalar_one_or_none()
        if sector is None:
            return {"error": f"Sector {sector_id} not found"}

    weather = await get_real_weather(sector.latitude, sector.longitude)
    weather["sector_id"] = sector.id
    weather["sector_name"] = sector.name
    return weather


async def _tool_log_farm_action(args: dict) -> dict:
    """
    Write a new Farm Action Log document to Firestore.
    """
    import asyncio

    sector_id = int(args.get("sector_id", 0))
    title = args.get("title", "Untitled")
    urgency = args.get("urgency", "MEDIUM")
    description = args.get("description", "")

    doc = {
        "sector_id": sector_id,
        "title": title,
        "urgency": urgency,
        "description": description,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    def _write():
        db = get_firestore_client()
        db.collection("farm_action_logs").add(doc)

    await asyncio.to_thread(_write)
    print(f"[Tool] Logged farm action: {title} ({urgency})")
    return {"status": "success", "message": f"Action '{title}' logged for sector {sector_id}"}


async def _tool_calculate_field_treatment(sector_id: int) -> dict:
    """
    Query TiDB for sector crop info + latest telemetry, then use
    the precision-ag calculator to determine exact treatment volumes.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FarmSector).where(FarmSector.id == sector_id)
        )
        sector = result.scalar_one_or_none()
        if sector is None:
            return {"error": f"Sector {sector_id} not found"}

        if not sector.crop_type:
            return {"error": f"Sector '{sector.name}' has no crop planted. Ask the farmer what crop to set."}

        tel_result = await db.execute(
            select(Telemetry)
            .where(Telemetry.sector_id == sector_id)
            .order_by(Telemetry.timestamp.desc())
            .limit(1)
        )
        telemetry = tel_result.scalar_one_or_none()
        if telemetry is None:
            return {"error": f"No telemetry data for sector '{sector.name}'. Cannot calculate."}

    result = await calculate_treatment(
        crop_type=sector.crop_type,
        area_hectares=sector.area_hectares or 1.0,
        current_moisture=telemetry.soil_moisture,
        current_nitrogen=telemetry.nitrogen_level,
    )
    result["sector_name"] = sector.name
    print(f"[Tool] Treatment calculated for sector {sector.name}")
    return result


async def _tool_update_crop_lifecycle(args: dict) -> dict:
    """
    Set or clear crop lifecycle fields on a FarmSector row in TiDB.
    PLANT → set crop_type + plant_date.  HARVEST → clear both.
    """
    sector_id = int(args.get("sector_id", 0))
    action = args.get("action", "").upper()
    crop_type = args.get("crop_type", "")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FarmSector).where(FarmSector.id == sector_id)
        )
        sector = result.scalar_one_or_none()
        if sector is None:
            return {"error": f"Sector {sector_id} not found"}

        if action == "PLANT":
            if not crop_type:
                return {"error": "crop_type is required when planting."}
            sector.crop_type = crop_type
            sector.plant_date = datetime.now(timezone.utc)
            await db.commit()
            print(f"[Tool] Planted {crop_type} in sector {sector.name}")
            return {
                "status": "success",
                "message": f"{crop_type} planted in '{sector.name}' on {sector.plant_date.strftime('%Y-%m-%d')}.",
            }
        elif action == "HARVEST":
            old_crop = sector.crop_type or "Unknown"
            sector.crop_type = None
            sector.plant_date = None
            await db.commit()
            print(f"[Tool] Harvested {old_crop} from sector {sector.name}")
            return {
                "status": "success",
                "message": f"{old_crop} harvested from '{sector.name}'. Field is now fallow.",
            }
        else:
            return {"error": f"Unknown action '{action}'. Use PLANT or HARVEST."}


async def _tool_forecast_global_revenue(sector_id: int) -> dict:
    """
    Query sector for crop_type, currency, and area.  Fetch live NDVI.
    Feed everything into the global economics engine.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FarmSector).where(FarmSector.id == sector_id)
        )
        sector = result.scalar_one_or_none()
        if sector is None:
            return {"error": f"Sector {sector_id} not found"}

        if not sector.crop_type:
            return {"error": f"Sector '{sector.name}' has no crop planted. Cannot forecast revenue."}

    ndvi = await get_real_ndvi(sector.latitude, sector.longitude)
    if ndvi is None:
        ndvi = 0.5  # fallback for unavailable satellite data

    result = await calculate_global_economics(
        crop_type=sector.crop_type,
        area_hectares=sector.area_hectares or 1.0,
        ndvi_score=ndvi,
        currency=sector.currency or "USD",
    )
    result["sector_name"] = sector.name
    print(f"[Tool] Revenue forecast for sector {sector.name}: {result['currency']} {result['projected_revenue']:,.2f}")
    return result


async def _tool_actuate_iot(device_id: int, command: str) -> dict:
    """
    Update an IoT device status in TiDB (ON/OFF/OPEN/CLOSE).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(IoTDevice).where(IoTDevice.id == device_id)
        )
        device = result.scalar_one_or_none()
        if device is None:
            return {"error": f"IoT device {device_id} not found."}

        old_status = device.status
        device.status = command
        await db.commit()
        print(f"[IoT] Device '{device.device_name}' ({device.device_type}): {old_status} → {command}")
        return {
            "status": "success",
            "device_id": device.id,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "old_status": old_status,
            "new_status": command,
            "message": f"{device.device_name} is now {command}.",
        }

# ══════════════════════════════════════════════════════════════
#  GeminiLiveClient
# ══════════════════════════════════════════════════════════════
class GeminiLiveClient:
    """Async WebSocket bridge to the Gemini Live streaming API."""

    def __init__(self):
        self._ws = None

    async def connect(self) -> None:
        """Open the WebSocket to Gemini and send the setup handshake."""
        self._ws = await websockets.connect(
            _GEMINI_WS_URL,
            additional_headers={"Content-Type": "application/json"},
            max_size=None,
            ping_interval=30,
            ping_timeout=10,
        )
        # Send the initial setup message (includes tool declarations)
        await self._ws.send(json.dumps(_SETUP_MESSAGE))

        # Wait for the setup-complete acknowledgement
        raw = await self._ws.recv()
        setup_response = json.loads(raw)
        print("[Gemini] Setup acknowledged:", json.dumps(setup_response, indent=2)[:300])

    async def send_audio(self, pcm_base64_data: str) -> None:
        """
        Forward a chunk of base64-encoded PCM audio to Gemini
        using the realtimeInput wire format.
        """
        if self._ws is None:
            return

        msg = {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": pcm_base64_data,
                    }
                ]
            }
        }
        await self._ws.send(json.dumps(msg))

    async def send_image(self, base64_jpeg: str) -> None:
        """
        Forward a base64-encoded JPEG frame to Gemini
        using the realtimeInput wire format for vision.
        """
        if self._ws is None:
            return

        msg = {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": "image/jpeg",
                        "data": base64_jpeg,
                    }
                ]
            }
        }
        await self._ws.send(json.dumps(msg))

    async def send_text(self, text: str) -> None:
        """
        Send a user text message to Gemini using the clientContent
        wire format. This enables the text chat interface.
        """
        if self._ws is None:
            return

        msg = {
            "clientContent": {
                "turns": [
                    {
                        "role": "user",
                        "parts": [{"text": text}],
                    }
                ],
                "turnComplete": True,
            }
        }
        await self._ws.send(json.dumps(msg))

    async def receive_loop(self, client_ws) -> None:
        """
        Continuously read from the Gemini WebSocket.

        Handles two types of model output:
        1. **Audio**: inlineData in modelTurn.parts → forwarded to browser
        2. **Function calls**: functionCall in modelTurn.parts → executed
           locally, result sent back to Gemini as a toolResponse
        """
        if self._ws is None:
            return

        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # ── Check for toolCall at the top level ──
                tool_call = msg.get("toolCall")
                if tool_call:
                    await self._handle_tool_call(tool_call, client_ws)
                    continue

                # ── serverContent path ──
                server_content = msg.get("serverContent")
                if not server_content:
                    continue

                model_turn = server_content.get("modelTurn")
                if not model_turn:
                    if server_content.get("turnComplete"):
                        await client_ws.send_json({"type": "turn_complete"})
                    continue

                parts = model_turn.get("parts", [])
                for part in parts:
                    # ── Function call inside modelTurn ──
                    func_call = part.get("functionCall")
                    if func_call:
                        await self._handle_function_call_part(func_call, client_ws)
                        continue

                    # ── Audio data ──
                    inline = part.get("inlineData")
                    if inline and inline.get("data"):
                        await client_ws.send_json({
                            "type": "audio",
                            "data": inline["data"],
                            "mimeType": inline.get("mimeType", "audio/pcm;rate=24000"),
                        })

                    # ── Text response (for chat window) ──
                    text_content = part.get("text")
                    if text_content:
                        await client_ws.send_json({
                            "type": "text",
                            "data": text_content,
                        })

        except websockets.exceptions.ConnectionClosed as e:
            print(f"[Gemini] Connection closed: {e}")
        except Exception as e:
            print(f"[Gemini] receive_loop error: {e}")

    async def _handle_tool_call(self, tool_call: dict, client_ws) -> None:
        """Handle a top-level toolCall message from Gemini."""
        func_calls = tool_call.get("functionCalls", [])
        responses = []

        for fc in func_calls:
            name    = fc.get("name", "")
            call_id = fc.get("id", "")
            args    = fc.get("args", {})

            print(f"[Gemini] Tool call: {name}(id={call_id}, args={args})")
            await client_ws.send_json({"type": "tool_call", "name": name, "args": args})

            result = await _execute_tool(name, args)

            responses.append({
                "id": call_id,
                "name": name,
                "response": {"result": result},
            })

        # Send all responses back to Gemini
        response_msg = {
            "toolResponse": {
                "functionResponses": responses,
            }
        }
        await self._ws.send(json.dumps(response_msg))
        print(f"[Gemini] Sent toolResponse for {len(responses)} call(s)")

    async def _handle_function_call_part(self, func_call: dict, client_ws) -> None:
        """Handle a functionCall embedded in modelTurn.parts."""
        name    = func_call.get("name", "")
        call_id = func_call.get("id", "")
        args    = func_call.get("args", {})

        print(f"[Gemini] Function call (in-part): {name}(id={call_id}, args={args})")
        await client_ws.send_json({"type": "tool_call", "name": name, "args": args})

        result = await _execute_tool(name, args)

        response_msg = {
            "toolResponse": {
                "functionResponses": [
                    {
                        "id": call_id,
                        "name": name,
                        "response": {"result": result},
                    }
                ]
            }
        }
        await self._ws.send(json.dumps(response_msg))
        print(f"[Gemini] Sent toolResponse for {name}")

    async def close(self) -> None:
        """Gracefully close the Gemini WebSocket."""
        if self._ws:
            await self._ws.close()
            self._ws = None
