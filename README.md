![terra_image2_compressed](https://github.com/user-attachments/assets/a441a3df-d001-4834-9190-8b8e98b155cb)

#🌱 TerraLive: Elastic-Powered Agritech Agent

**TerraLive** is a multi-step AI agent utilizing Elasticsearch vector search and telemetry analytics to autonomously diagnose crop health, trigger IoT irrigation, and mitigate agricultural threats. 

Built as a submission for the **Elasticsearch Agent Builder Hackathon**, this project demonstrates a true "tool-driven agent" that orchestrates real-world precision agriculture workflows.

---

## 💡 Inspiration
Agriculture is the backbone of global food security, yet most farmers are overwhelmed by fragmented data—weather apps, manual soil testing, and disconnected hardware. I realized that simply putting a chatbot wrapper around an LLM wouldn't solve this. Real, brittle, operational work requires a **context-driven agent** that can seamlessly retrieve precise domain knowledge, parse real-time telemetry, and actually execute multi-step tasks. 

I was inspired to build an agent that doesn't just tell a farmer what *might* be wrong, but actively queries real-time satellite data, cross-references local agronomy databases using Elastic Vector Search, and autonomously actuates IoT irrigation systems to mitigate the problem.

## 🚀 What it does
TerraLive operates through a sleek, real-time dashboard, performing a complete operational loop:

* **Real-Time Context Ingestion:** It constantly monitors farm telemetry (soil moisture, nitrogen) and pulls live Sentinel-2 satellite health scores (NDVI) via Google Earth Engine. 
* **Elastic-Powered RAG & Analytics:** Instead of relying on generic LLM knowledge, TerraLive uses **Elasticsearch** as its core retrieval engine. It uses ES|QL to aggregate and analyze unstructured telemetry, and **Elastic Vector Search** to query hundreds of vectorized agricultural manuals for highly specific disease and treatment protocols.
* **Autonomous Tool Execution:** When the agent detects an anomaly, it executes a multi-step workflow. It calculates exact fertilizer/water deficits, logs the financial "Value at Risk," pushes a "Community Radar" threat warning to neighboring farms, and can autonomously trigger physical IoT infrastructure (e.g., turning on a main pump).
* **Multimodal Interface:** Users can interact with the agent via a text interface, real-time voice, or by streaming camera frames for live crop diagnosis.

## 🛠️ How I built it
I built TerraLive focusing on a robust backend architecture that supports a multi-tool agent:

* **The Agent Engine:** I utilized the **Gemini 2.0 Multimodal API** as the primary reasoning engine, granting it access to distinct server-side tools.
* **Retrieval & State (The Elastic Core):** I integrated **Elasticsearch Serverless** to act as the agent's memory and knowledge base. Vector search handles the retrieval of complex agronomic protocols, while ES|QL handles the rapid querying of time-series telemetry data.
* **Backend:** Built with **Python and FastAPI**, handling low-latency WebSockets for the agent's multimodal audio/vision streams. I used **TiDB** (Serverless MySQL) for transactional relational data (IoT digital twins, user state) and **Firebase** for secure multi-tenant authentication and action logging.
* **APIs & Integrations:** Google Earth Engine (live NDVI indexing), Open-Meteo (7-day forecasting), and custom algorithms for geospatial Haversine threat calculations.
* **Frontend:** A vanilla **HTML, JavaScript, and CSS** glassmorphic UI, featuring Leaflet maps with dynamic geospatial overlays and Chart.js for telemetry visualization.

## 🏆 Accomplishments
I am incredibly proud of achieving a true "closed-loop" agent. TerraLive goes beyond passive monitoring. When the agent uses its vision tool to spot "Coffee Berry Disease," it logs the GPS coordinates, alerts farms within a 15km radius using a geospatial threat radar, queries Elastic for the fungicide protocol, calculates the financial impact, and schedules the IoT spray. 

Seeing the UI dynamically update its interactive map, action logs, and IoT hardware switches autonomously based on the agent's reasoning is the realization of this vision.

## 🔮 What's Next
The immediate next step is expanding TerraLive's Elastic knowledge base to cover a global dataset of crops, soil profiles, and regional climate strategies. I plan to transition the simulated IoT infrastructure into physical hardware integrations using MQTT protocols, allowing the agent to control real farm equipment directly. 

Finally, I plan to evolve the system into a **Multi-Agent architecture** using Elastic Workflows: separating data analytics, financial market prediction, and master orchestration into specialized, communicating agents.
