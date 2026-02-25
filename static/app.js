/* ═══════════════════════════════════════════════════════════
   TerraLive — Dashboard Logic + Gemini Live Audio Streaming
   ═══════════════════════════════════════════════════════════ */
console.log("TerraLive Frontend Initialized");

// ═══════════════════════════════════════════════════════════
//  FIREBASE AUTH
// ═══════════════════════════════════════════════════════════
const firebaseConfig = {
    apiKey: "AIzaSyCbyAWDwQwHp0i6IC81ZeIjyUBXL1DvtEI",
    authDomain: "terralive-agent.firebaseapp.com",
    projectId: "terralive-agent",
    storageBucket: "terralive-agent.firebasestorage.app",
    messagingSenderId: "660628975415",
    appId: "1:660628975415:web:a1e07d780430ea76b334b2",
};

firebase.initializeApp(firebaseConfig);
const fbAuth = firebase.auth();
const googleProvider = new firebase.auth.GoogleAuthProvider();

let globalIdToken = null;

// Auth DOM refs
const loginScreen = document.getElementById("loginScreen");
const btnGoogleLogin = document.getElementById("btn-google-login");
const btnLogout = document.getElementById("btn-logout");
const userProfile = document.getElementById("user-profile");
const userAvatar = document.getElementById("user-avatar");
const userName = document.getElementById("user-name");
const userEmail = document.getElementById("user-email");

/**
 * Helper — returns headers object with Bearer token for API calls.
 */
function authHeaders(extra = {}) {
    const h = { ...extra };
    if (globalIdToken) h["Authorization"] = "Bearer " + globalIdToken;
    return h;
}

fbAuth.onAuthStateChanged(async (user) => {
    if (user) {
        // Signed in
        globalIdToken = await user.getIdToken();
        loginScreen.style.display = "none";

        // Sidebar profile
        userProfile.style.display = "flex";
        userName.textContent = user.displayName || "User";
        userEmail.textContent = user.email || "";
        userAvatar.src = user.photoURL || "";

        // Init and load
        initMap();
        initChart();

        // Ping backend
        try {
            const res = await fetch("/health");
            const data = await res.json();
            if (data.status === "ok") {
                statusDot.classList.add("online");
                statusText.textContent = "Online";
            }
        } catch {
            statusText.textContent = "Offline";
        }

        await loadSectors();
    } else {
        // Signed out
        globalIdToken = null;
        loginScreen.style.display = "flex";
        userProfile.style.display = "none";
    }
});

btnGoogleLogin.addEventListener("click", () => {
    fbAuth.signInWithPopup(googleProvider).catch((err) => {
        console.error("Google login failed:", err);
        alert("Login failed. Please try again.");
    });
});

btnLogout.addEventListener("click", () => {
    fbAuth.signOut();
});

// ── DOM refs ────────────────────────────────────────────────
const sectorList = document.getElementById("sector-list");
const btnAddSector = document.getElementById("btn-add-sector");
const btnLiveAudio = document.getElementById("btn-live-audio");
const modalBackdrop = document.getElementById("modal-backdrop");
const btnCancelMdl = document.getElementById("btn-cancel-modal");
const formAdd = document.getElementById("form-add-sector");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const mapOverlay = document.getElementById("map-overlay");

// NDVI elements
const ndviValue = document.getElementById("ndvi-value");
const ndviLabel = document.getElementById("ndvi-label");
const ndviBar = document.getElementById("ndvi-bar");

// Latest-reading elements
const valTemp = document.getElementById("val-temp");
const valMoisture = document.getElementById("val-moisture");
const valNitrogen = document.getElementById("val-nitrogen");

// Weather elements
const weatherContainer = document.getElementById("weatherContainer");

// Logs elements
const logsContainer = document.getElementById("logsContainer");

// Financials elements
const valYield = document.getElementById("val-yield");
const valRevenue = document.getElementById("val-revenue");
const valCurrency = document.getElementById("val-currency");
const valRisk = document.getElementById("val-risk");
const valRiskCurrency = document.getElementById("val-risk-currency");

// Locate Me button
const btnLocate = document.getElementById("btn-locate");

// IoT elements
const iotContainer = document.getElementById("iotContainer");

// ── State ───────────────────────────────────────────────────
let map = null;
let markers = [];
let telemetryChart = null;
let activeSector = null;
let locateMarker = null;  // temporary geolocation marker

// AI Audio state
let aiWs = null;   // WebSocket to /ws/agent
let micStream = null;   // MediaStream
let audioCtxCapture = null;  // AudioContext for mic capture
let workletNode = null;   // AudioWorkletNode

// Camera vision state
let videoStream = null;       // camera MediaStream
let frameInterval = null;     // setInterval id for JPEG frames
const cameraPreview = document.getElementById("cameraPreview");
const cameraCanvas = document.getElementById("cameraCanvas");
const btnCamera = document.getElementById("btn-toggle-camera");
let audioCtxPlay = null;   // AudioContext for AI playback
let isAIActive = false;
let playbackQueue = [];     // queued PCM buffers for gapless playback
let isPlaying = false;

// ═════════════════════════════════════════════════════════════
//  LEAFLET MAP
// ═════════════════════════════════════════════════════════════
function initMap() {
    map = L.map("farmMap", {
        center: [0, 20],
        zoom: 3,
        zoomControl: true,
        attributionControl: false,
    });

    // Satellite imagery base
    const satellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
    });

    // Dark labels overlay (roads + place names)
    const labels = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png", {
        maxZoom: 19,
        subdomains: "abcd",
        pane: "overlayPane",
    });

    // Dark base (fallback)
    const darkBase = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        maxZoom: 19,
        subdomains: "abcd",
    });

    // Default to satellite + labels
    satellite.addTo(map);
    labels.addTo(map);

    // Layer control
    L.control.layers(
        { "Satellite": satellite, "Dark": darkBase },
        { "Labels": labels },
        { position: "bottomleft", collapsed: true }
    ).addTo(map);

    setTimeout(() => map.invalidateSize(), 200);
}

// ═════════════════════════════════════════════════════════════
//  CHART.JS
// ═════════════════════════════════════════════════════════════
function initChart() {
    const ctx = document.getElementById("telemetryChart").getContext("2d");

    // Create gradient fills
    const moistureGrad = ctx.createLinearGradient(0, 0, 0, 250);
    moistureGrad.addColorStop(0, "rgba(0, 194, 255, 0.25)");
    moistureGrad.addColorStop(1, "rgba(0, 194, 255, 0.01)");

    const nitrogenGrad = ctx.createLinearGradient(0, 0, 0, 250);
    nitrogenGrad.addColorStop(0, "rgba(255, 159, 67, 0.20)");
    nitrogenGrad.addColorStop(1, "rgba(255, 159, 67, 0.01)");

    telemetryChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Soil Moisture (%)",
                    data: [],
                    borderColor: "#00c2ff",
                    backgroundColor: moistureGrad,
                    borderWidth: 2.5,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: "#00c2ff",
                    pointHoverBorderColor: "#fff",
                    pointHoverBorderWidth: 2,
                },
                {
                    label: "Nitrogen (mg/kg)",
                    data: [],
                    borderColor: "#ff9f43",
                    backgroundColor: nitrogenGrad,
                    borderWidth: 2.5,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: "#ff9f43",
                    pointHoverBorderColor: "#fff",
                    pointHoverBorderWidth: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: {
                    labels: { color: "#8899aa", font: { size: 10, weight: "500" }, boxWidth: 12, padding: 12 },
                },
                tooltip: {
                    backgroundColor: "rgba(13, 17, 23, 0.92)",
                    titleColor: "#fff",
                    bodyColor: "#aabbcc",
                    borderColor: "rgba(0, 255, 136, 0.2)",
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 8,
                    displayColors: true,
                    boxPadding: 4,
                },
            },
            scales: {
                x: {
                    ticks: { color: "#3f5c73", font: { size: 9 }, maxTicksLimit: 6, maxRotation: 0 },
                    grid: { display: false },
                    border: { color: "rgba(30,42,53,0.3)" },
                },
                y: {
                    ticks: { color: "#3f5c73", font: { size: 9 }, padding: 8 },
                    grid: { color: "rgba(30,42,53,0.3)", drawBorder: false },
                    border: { display: false },
                    suggestedMin: 30,
                    suggestedMax: 60,
                },
            },
        },
    });
}

// ═════════════════════════════════════════════════════════════
//  SECTOR HELPERS
// ═════════════════════════════════════════════════════════════
function createMarkerIcon() {
    return L.divIcon({
        className: "custom-marker",
        html: `<div style="
            width:14px; height:14px; border-radius:50%;
            background:#00ff88; border:2px solid #0b0f12;
            box-shadow:0 0 8px rgba(0,255,136,0.5);
        "></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
    });
}

async function loadSectors() {
    try {
        const res = await fetch("/api/sectors", { headers: authHeaders() });
        const data = await res.json();

        sectorList.innerHTML = "";
        markers.forEach(m => map.removeLayer(m));
        markers = [];

        if (data.length === 0) {
            sectorList.innerHTML = `<li class="empty-state"><i class="fa-solid fa-satellite-dish"></i> No farms registered</li>`;
            return;
        }

        data.forEach(sector => {
            const li = document.createElement("li");

            // Build crop subtitle
            let subtitle = "";
            if (sector.crop_type) {
                subtitle = sector.crop_type;
                if (sector.plant_date) {
                    const days = Math.floor((Date.now() - new Date(sector.plant_date).getTime()) / 86400000);
                    subtitle += ` · Day ${days}`;
                }
            } else {
                subtitle = "Fallow";
            }
            subtitle += ` · ${sector.area_hectares ?? 1} ha`;

            li.innerHTML = `
                <i class="fa-solid fa-map-location-dot"></i>
                <div class="sector-info">
                    <span class="sector-name">${sector.name}</span>
                    <span class="sector-sub">${subtitle}</span>
                </div>
            `;
            li.dataset.id = sector.id;
            li.dataset.lat = sector.latitude;
            li.dataset.lon = sector.longitude;
            li.addEventListener("click", () => selectSector(sector.id, sector.latitude, sector.longitude, li, sector));
            sectorList.appendChild(li);

            const marker = L.marker([sector.latitude, sector.longitude], { icon: createMarkerIcon() })
                .bindTooltip(sector.name, { direction: "top", offset: [0, -10] })
                .addTo(map);
            marker.on("click", () => selectSector(sector.id, sector.latitude, sector.longitude, li, sector));
            markers.push(marker);
        });

        // Auto-select the first farm so dashboard is never empty
        if (data.length > 0) {
            const first = data[0];
            const firstLi = sectorList.querySelector("li");
            selectSector(first.id, first.latitude, first.longitude, firstLi, first);
        }
    } catch (err) {
        console.error("Failed to load farms:", err);
    }
}

// ═════════════════════════════════════════════════════════════
//  SELECT SECTOR — fetch health & update UI
// ═════════════════════════════════════════════════════════════
async function selectSector(sectorId, lat, lon, liElement, sectorData) {
    activeSector = sectorId;

    document.querySelectorAll("#sector-list li").forEach(el => el.classList.remove("active"));
    if (liElement) liElement.classList.add("active");

    map.flyTo([lat, lon], 14, { duration: 1.2 });
    mapOverlay.innerHTML = `<span><i class="fa-solid fa-crosshairs"></i> Farm #${sectorId} — ${lat.toFixed(4)}, ${lon.toFixed(4)}</span>`;

    // ── Visual farm boundary on map ─────────────────────
    if (window._farmBoundary) map.removeLayer(window._farmBoundary);
    if (window._farmPulse) map.removeLayer(window._farmPulse);
    const ha = sectorData?.area_hectares || 1;
    const radiusM = Math.sqrt(ha * 10000 / Math.PI);  // Circle equiv. of hectare area
    window._farmBoundary = L.circle([lat, lon], {
        radius: radiusM,
        color: "#00ff88",
        weight: 2,
        opacity: 0.7,
        fillColor: "#00ff88",
        fillOpacity: 0.08,
        dashArray: "6 4",
    }).addTo(map);
    // Inner pulse dot
    window._farmPulse = L.circleMarker([lat, lon], {
        radius: 6,
        color: "#00ff88",
        fillColor: "#00ff88",
        fillOpacity: 0.6,
        weight: 2,
    }).addTo(map);

    // ── Crop Intelligence Pane ─────────────────────────────
    const ciPane = document.getElementById("cropIntelPane");
    const ciImg = document.getElementById("cropIntelImg");
    const ciTitle = document.getElementById("cropIntelTitle");
    const ciStage = document.getElementById("cropIntelStage");
    const ciAction = document.getElementById("cropIntelAction");

    if (sectorData) {
        const cropType = (sectorData.crop_type || "").toLowerCase();

        // Icon by crop (flat design PNGs)
        const cropImages = {
            coffee: "https://cdn-icons-png.flaticon.com/512/751/751621.png",
            maize: "https://cdn-icons-png.flaticon.com/512/1529/1529747.png",
            tea: "https://cdn-icons-png.flaticon.com/512/2935/2935307.png",
            wheat: "https://cdn-icons-png.flaticon.com/512/4391/4391378.png",
        };
        ciImg.src = cropImages[cropType] || "https://cdn-icons-png.flaticon.com/512/628/628324.png";

        ciTitle.textContent = sectorData.crop_type ? `${sectorData.crop_type} — ${sectorData.name}` : sectorData.name;

        // Growth stage
        let stage = "Seedling / Early Growth";
        if (sectorData.plant_date) {
            const daysAgo = Math.floor((Date.now() - new Date(sectorData.plant_date).getTime()) / 86400000);
            if (daysAgo > 150) stage = `Fruiting / Maturation (Day ${daysAgo})`;
            else if (daysAgo > 60) stage = `Vegetative Growth (Day ${daysAgo})`;
            else stage = `Seedling / Early Growth (Day ${daysAgo})`;
        }
        ciStage.textContent = `Stage: ${stage}`;

        ciAction.textContent = "Action: Dispatching Copper Fungicide protocol via IoT Irrigation.";

        ciPane.classList.add("active");
    }

    try {
        ndviLabel.textContent = "Loading…";

        const res = await fetch(`/api/sector/${sectorId}/health`, { headers: authHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const health = await res.json();

        // NDVI
        if (health.ndvi !== null && health.ndvi !== undefined) {
            const v = health.ndvi;
            ndviValue.textContent = v.toFixed(3);
            ndviBar.style.width = `${Math.max(0, Math.min(100, ((v + 1) / 2) * 100))}%`;

            if (v > 0.6) { ndviLabel.textContent = "Excellent Vegetation"; ndviValue.style.color = "#00ff88"; }
            else if (v > 0.3) { ndviLabel.textContent = "Moderate Vegetation"; ndviValue.style.color = "#ff9f43"; }
            else { ndviLabel.textContent = "Low / Stressed"; ndviValue.style.color = "#ff5252"; }
        } else {
            ndviValue.textContent = "N/A";
            ndviLabel.textContent = "No satellite data available";
            ndviBar.style.width = "0%";
        }

        // Latest reading
        if (health.latest_telemetry) {
            const t = health.latest_telemetry;
            valTemp.textContent = t.temperature.toFixed(1);
            valMoisture.textContent = t.soil_moisture.toFixed(1);
            valNitrogen.textContent = t.nitrogen_level.toFixed(1);
        } else {
            valTemp.textContent = valMoisture.textContent = valNitrogen.textContent = "—";
        }

        // Chart
        updateChart(health.telemetry_history || []);

        // Weather
        fetchWeather(sectorId);

        // Action Logs
        fetchLogs(sectorId);

        // Economics / Financials
        fetchEconomics(sectorId);

        // IoT Infrastructure
        fetchIoT(sectorId);

    } catch (err) {
        console.error("Failed to fetch sector health:", err);
        ndviValue.textContent = "ERR";
        ndviLabel.textContent = "Could not reach API";
    }
}

// ═══════════════════════════════════════════════════════════
//  IoT INFRASTRUCTURE
// ═══════════════════════════════════════════════════════════
async function fetchIoT(sectorId) {
    try {
        const res = await fetch(`/api/sector/${sectorId}/iot`, { headers: authHeaders() });
        if (!res.ok) return;
        const devices = await res.json();
        renderIoT(devices);
    } catch (err) {
        console.error("Failed to fetch IoT devices:", err);
    }
}

function renderIoT(devices) {
    if (!iotContainer) return;
    if (!devices || devices.length === 0) {
        iotContainer.innerHTML = `<span class="iot-empty"><i class="fa-solid fa-plug-circle-xmark"></i> No devices</span>`;
        return;
    }
    iotContainer.innerHTML = devices.map(d => {
        const isActive = d.status === "ON" || d.status === "OPEN";
        const iconMap = {
            VALVE: "fa-faucet-drip",
            DOOR: "fa-door-open",
            PUMP: "fa-water",
            FAN: "fa-fan",
        };
        const icon = iconMap[d.device_type] || "fa-microchip";
        return `
            <div class="iot-device ${isActive ? 'iot-active' : 'iot-inactive'}">
                <i class="fa-solid ${icon} iot-icon"></i>
                <span class="iot-name">${d.device_name}</span>
                <span class="iot-badge ${isActive ? 'badge-on' : 'badge-off'}">
                    ${d.status}
                </span>
            </div>
        `;
    }).join("");
}

// ═════════════════════════════════════════════════════════════
//  CHART UPDATE
// ═════════════════════════════════════════════════════════════
function updateChart(history) {
    const sorted = [...history].reverse();

    const labels = sorted.map(t => {
        const d = new Date(t.timestamp);
        return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    });
    const moisture = sorted.map(t => t.soil_moisture);
    const nitrogen = sorted.map(t => t.nitrogen_level);

    telemetryChart.data.labels = labels;
    telemetryChart.data.datasets[0].data = moisture;
    telemetryChart.data.datasets[1].data = nitrogen;
    telemetryChart.update();
}

// ═════════════════════════════════════════════════════════════════
//  WEATHER
// ═════════════════════════════════════════════════════════════════
async function fetchWeather(sectorId) {
    try {
        const res = await fetch(`/api/sector/${sectorId}/weather`, { headers: authHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderWeatherForecast(data);

        // Update wind compass
        const cur = data.current || {};
        const windCompass = document.getElementById("windCompass");
        const windArrow = document.getElementById("windArrow");
        const windSpeed = document.getElementById("windSpeed");
        const windDir = document.getElementById("windDir");

        if (cur.wind_speed_kmh != null && windCompass) {
            const deg = cur.wind_direction_deg || 0;
            const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
            const cardinal = dirs[Math.round(deg / 45) % 8];

            windArrow.style.transform = `rotate(${deg}deg)`;
            windSpeed.textContent = `${cur.wind_speed_kmh.toFixed(1)} km/h`;
            windDir.textContent = `Wind ${cardinal}`;
            windCompass.style.display = "flex";
        }
    } catch (err) {
        console.error("Failed to fetch weather:", err);
        weatherContainer.innerHTML = `<span class="weather-empty"><i class="fa-solid fa-triangle-exclamation"></i> Weather unavailable</span>`;
    }
}

function getWeatherIcon(precipMm, cloudPct) {
    if (precipMm > 5) return "fa-cloud-showers-heavy";
    if (precipMm > 0.5) return "fa-cloud-rain";
    if (cloudPct > 60) return "fa-cloud";
    if (cloudPct > 25) return "fa-cloud-sun";
    return "fa-sun";
}

function renderWeatherForecast(data) {
    const days = data.daily_forecast || [];
    if (days.length === 0) {
        weatherContainer.innerHTML = `<span class="weather-empty">No forecast data</span>`;
        return;
    }

    const currentWeather = data.current || {};

    let html = "";
    days.forEach((day, i) => {
        const d = new Date(day.date + "T00:00:00");
        const dayName = i === 0 ? "Today" : d.toLocaleDateString(undefined, { weekday: "short" });
        const icon = getWeatherIcon(day.precipitation_sum_mm || 0, 50);
        const precip = day.precipitation_sum_mm != null ? day.precipitation_sum_mm.toFixed(1) : "—";
        const probPct = day.precipitation_probability_pct != null ? day.precipitation_probability_pct : "—";
        const hi = day.temp_max_c != null ? Math.round(day.temp_max_c) : "—";
        const lo = day.temp_min_c != null ? Math.round(day.temp_min_c) : "—";

        html += `
            <div class="weather-day${i === 0 ? " today" : ""}">
                <span class="wd-label">${dayName}</span>
                <i class="fa-solid ${icon} wd-icon"></i>
                <span class="wd-temp">${hi}° <small>${lo}°</small></span>
                <span class="wd-precip"><i class="fa-solid fa-droplet"></i> ${precip}mm</span>
            </div>
        `;
    });

    weatherContainer.innerHTML = html;
}

// ═════════════════════════════════════════════════════════════
//  ACTION LOGS
// ═════════════════════════════════════════════════════════════
async function fetchLogs(sectorId) {
    try {
        const res = await fetch(`/api/sector/${sectorId}/logs`, { headers: authHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const logs = await res.json();
        renderLogs(logs);
    } catch (err) {
        console.error("Failed to fetch logs:", err);
        logsContainer.innerHTML = `<span class="logs-empty"><i class="fa-solid fa-triangle-exclamation"></i> Logs unavailable</span>`;
    }
}

function renderLogs(logs) {
    if (!logs || logs.length === 0) {
        logsContainer.innerHTML = `<span class="logs-empty"><i class="fa-solid fa-inbox"></i> No logs yet</span>`;
        return;
    }

    const urgencyColor = {
        CRITICAL: "#ff5252",
        HIGH: "#ff9f43",
        MEDIUM: "#ffd32a",
        LOW: "#00ff88",
    };

    function pickIcon(text) {
        const t = (text || "").toLowerCase();
        if (t.includes("disease") || t.includes("threat") || t.includes("bug")) return "fa-bug";
        if (t.includes("irrigation") || t.includes("water") || t.includes("moisture") || t.includes("pump")) return "fa-droplet";
        if (t.includes("valve") || t.includes("door") || t.includes("gear") || t.includes("device")) return "fa-gear";
        if (t.includes("ndvi") || t.includes("vegetation") || t.includes("satellite")) return "fa-satellite";
        if (t.includes("soil") || t.includes("nitrogen") || t.includes("analysis")) return "fa-flask";
        if (t.includes("prevention") || t.includes("shield") || t.includes("protect")) return "fa-shield-halved";
        if (t.includes("radar") || t.includes("alert") || t.includes("warning")) return "fa-triangle-exclamation";
        return "fa-clipboard-list";
    }

    let html = "";
    logs.forEach(log => {
        const color = urgencyColor[log.urgency] || "#888";
        const urgClass = (log.urgency || "low").toLowerCase();
        const icon = pickIcon((log.title || "") + " " + (log.description || ""));
        const ts = log.timestamp
            ? new Date(log.timestamp).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
            : "";
        html += `
            <div class="log-item urgency-${urgClass}">
                <div class="log-header">
                    <i class="fa-solid ${icon} log-icon" style="color: ${color}"></i>
                    <span class="log-title">${log.title || "Untitled"}</span>
                    <span class="log-badge log-badge-${urgClass}">${log.urgency || "?"}</span>
                </div>
                <p class="log-desc">${log.description || ""}</p>
                <span class="log-time">${ts}</span>
            </div>
        `;
    });

    logsContainer.innerHTML = html;
}

// ═════════════════════════════════════════════════════════════
//  ECONOMICS / FINANCIALS
// ═════════════════════════════════════════════════════════════
function fmtNum(n) {
    return n != null ? n.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—";
}

async function fetchEconomics(sectorId) {
    try {
        const res = await fetch(`/api/sector/${sectorId}/economics`, { headers: authHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.error) {
            valYield.textContent = "—";
            valRevenue.textContent = "—";
            valRisk.textContent = "—";
            valCurrency.textContent = "";
            valRiskCurrency.textContent = "";
            return;
        }

        valYield.textContent = fmtNum(data.projected_yield_kg);
        valRevenue.textContent = fmtNum(data.projected_revenue);
        valCurrency.textContent = data.currency || "";
        valRisk.textContent = fmtNum(data.health_penalty);
        valRiskCurrency.textContent = data.currency || "";

        // Color the risk value
        if (data.health_penalty > 0) {
            valRisk.style.color = "#ff5252";
        } else {
            valRisk.style.color = "#00ff88";
        }
    } catch (err) {
        console.error("Failed to fetch economics:", err);
        valYield.textContent = valRevenue.textContent = valRisk.textContent = "ERR";
    }
}

// ═════════════════════════════════════════════════════════════
//  GEOLOCATION — LOCATE ME
// ═════════════════════════════════════════════════════════════
const COUNTRY_TO_CURRENCY = {
    US: "USD", GB: "GBP", KE: "KES", IN: "INR", BR: "BRL",
    NG: "NGN", ZA: "ZAR", DE: "EUR", FR: "EUR", IT: "EUR",
    ES: "EUR", NL: "EUR", PT: "EUR", BE: "EUR", AT: "EUR",
    IE: "EUR", FI: "EUR", GR: "EUR", TZ: "TZS", UG: "UGX",
    ET: "ETB", GH: "GHS", EG: "EGP", CN: "CNY", JP: "JPY",
    AU: "AUD", CA: "CAD", MX: "MXN", RW: "RWF", MW: "MWK",
    ZM: "ZMW", MZ: "MZN", CM: "XAF", SN: "XOF", CI: "XOF",
};

async function locateMe() {
    if (!navigator.geolocation) {
        alert("Geolocation is not supported by your browser.");
        return;
    }

    btnLocate.disabled = true;
    btnLocate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Locating…';

    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;

            // Fly to location
            map.flyTo([lat, lon], 13, { duration: 1.5 });

            // Add/update temporary marker
            if (locateMarker) map.removeLayer(locateMarker);
            locateMarker = L.marker([lat, lon], {
                icon: L.divIcon({
                    className: "locate-marker",
                    html: '<i class="fa-solid fa-street-view" style="font-size:1.6rem;color:#00c2ff;"></i>',
                    iconSize: [30, 30],
                    iconAnchor: [15, 15],
                }),
            }).addTo(map).bindPopup("📍 You are here").openPopup();

            // Auto-fill lat/lon in modal
            document.getElementById("inp-lat").value = lat.toFixed(6);
            document.getElementById("inp-lon").value = lon.toFixed(6);

            // Reverse geocode
            try {
                const geoRes = await fetch(
                    `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=en`
                );
                if (geoRes.ok) {
                    const geo = await geoRes.json();
                    const countryName = geo.countryName || "Unknown";
                    const countryCode = geo.countryCode || "";

                    document.getElementById("inp-country").value = countryName;
                    const currency = COUNTRY_TO_CURRENCY[countryCode] || "USD";
                    document.getElementById("inp-currency").value = currency;
                }
            } catch (geoErr) {
                console.warn("Reverse geocode failed:", geoErr);
            }

            btnLocate.disabled = false;
            btnLocate.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Locate Me';
        },
        (err) => {
            console.error("Geolocation error:", err);
            alert("Could not get your location. Please allow location access.");
            btnLocate.disabled = false;
            btnLocate.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Locate Me';
        },
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

btnLocate.addEventListener("click", locateMe);

// ═════════════════════════════════════════════════════════════
//  ADD SECTOR MODAL
// ═════════════════════════════════════════════════════════════
function openModal() { modalBackdrop.classList.add("open"); }
function closeModal() { modalBackdrop.classList.remove("open"); formAdd.reset(); }

btnAddSector.addEventListener("click", openModal);
btnCancelMdl.addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", (e) => { if (e.target === modalBackdrop) closeModal(); });

formAdd.addEventListener("submit", async (e) => {
    e.preventDefault();

    const name = document.getElementById("inp-name").value.trim();
    const lat = parseFloat(document.getElementById("inp-lat").value);
    const lon = parseFloat(document.getElementById("inp-lon").value);
    const area = parseFloat(document.getElementById("inp-area").value) || 1.0;
    const country = document.getElementById("inp-country").value.trim() || "Unknown";
    const currency = document.getElementById("inp-currency").value.trim().toUpperCase() || "USD";

    if (!name || isNaN(lat) || isNaN(lon)) return;

    try {
        const res = await fetch("/api/sectors", {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ name, latitude: lat, longitude: lon, area_hectares: area, country, currency }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        closeModal();
        await loadSectors();
    } catch (err) {
        console.error("Failed to create farm:", err);
        alert("Failed to create farm. Check console for details.");
    }
});

// ═════════════════════════════════════════════════════════════
//  GEMINI LIVE — AI AUDIO ASSISTANT
// ═════════════════════════════════════════════════════════════

/**
 * Convert an ArrayBuffer of Int16 PCM samples to a base64 string.
 */
function int16BufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

/**
 * Decode a base64 string into an Int16Array of PCM samples.
 */
function base64ToInt16Array(b64) {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return new Int16Array(bytes.buffer);
}

/**
 * Schedule an Int16 PCM buffer (24 kHz) for playback through the speakers.
 */
function playPcmChunk(int16Array, sampleRate = 24000) {
    if (!audioCtxPlay) {
        audioCtxPlay = new AudioContext({ sampleRate });
    }

    // Convert Int16 → Float32
    const float32 = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
        float32[i] = int16Array[i] / (int16Array[i] < 0 ? 0x8000 : 0x7FFF);
    }

    // Queue buffer for gapless playback
    playbackQueue.push(float32);
    if (!isPlaying) drainPlaybackQueue(sampleRate);
}

/**
 * Drain the playback queue sequentially so chunks don't overlap.
 */
function drainPlaybackQueue(sampleRate) {
    if (playbackQueue.length === 0) {
        isPlaying = false;
        return;
    }
    isPlaying = true;

    const float32 = playbackQueue.shift();
    const buffer = audioCtxPlay.createBuffer(1, float32.length, sampleRate);
    buffer.getChannelData(0).set(float32);

    const source = audioCtxPlay.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtxPlay.destination);
    source.onended = () => drainPlaybackQueue(sampleRate);
    source.start();
}

/**
 * Start the AI audio assistant:
 * 1. Request mic access
 * 2. Set up AudioWorklet for PCM capture
 * 3. Open WebSocket to /ws/agent
 * 4. Bridge mic → WS → Gemini → WS → speakers
 */
async function startAIAssistant() {
    try {
        // 1. Mic access
        micStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                sampleRate: 16000,
                echoCancellation: true,
                noiseSuppression: true,
            },
        });

        // 2. AudioContext + Worklet
        audioCtxCapture = new AudioContext({ sampleRate: 16000 });

        // Resume context (required by some browsers)
        if (audioCtxCapture.state === "suspended") {
            await audioCtxCapture.resume();
        }

        await audioCtxCapture.audioWorklet.addModule("/static/audio_worklet.js");

        const source = audioCtxCapture.createMediaStreamSource(micStream);
        workletNode = new AudioWorkletNode(audioCtxCapture, "pcm-processor");

        // When the worklet posts a PCM buffer, send it over the WebSocket
        workletNode.port.onmessage = (event) => {
            if (event.data.type === "pcm" && aiWs && aiWs.readyState === WebSocket.OPEN) {
                const b64 = int16BufferToBase64(event.data.buffer);
                aiWs.send(JSON.stringify({ type: "audio", data: b64 }));
            }
        };

        source.connect(workletNode);
        workletNode.connect(audioCtxCapture.destination); // Required to keep the node alive

        // 3. Open WebSocket
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        aiWs = new WebSocket(`${protocol}//${location.host}/ws/agent`);

        aiWs.onopen = () => {
            console.log("[AI] WebSocket connected");
        };

        aiWs.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                if (msg.type === "session_ready") {
                    console.log("[AI] Gemini session ready — speak now!");
                    return;
                }

                if (msg.type === "audio" && msg.data) {
                    // Parse sample rate from mimeType (e.g. "audio/pcm;rate=24000")
                    let sr = 24000;
                    if (msg.mimeType) {
                        const m = msg.mimeType.match(/rate=(\d+)/);
                        if (m) sr = parseInt(m[1], 10);
                    }
                    const pcm = base64ToInt16Array(msg.data);
                    playPcmChunk(pcm, sr);
                    return;
                }

                if (msg.type === "turn_complete") {
                    console.log("[AI] Turn complete");
                    // Remove typing indicator if present
                    const typingEl = document.querySelector("#chatMessages .typing-indicator");
                    if (typingEl) typingEl.remove();
                    return;
                }

                // ── Text response → chat window ──
                if (msg.type === "text" && msg.data) {
                    appendChatMessage("ai", msg.data);
                    // Remove typing indicator
                    const typingEl = document.querySelector("#chatMessages .typing-indicator");
                    if (typingEl) typingEl.remove();
                    return;
                }
            } catch (err) {
                console.warn("[AI] Failed to parse WS message:", err);
            }
        };

        aiWs.onclose = () => {
            console.log("[AI] WebSocket closed");
            stopAIAssistant();
        };

        aiWs.onerror = (err) => {
            console.error("[AI] WebSocket error:", err);
        };

        // 4. Update UI
        isAIActive = true;
        setFabActive(true);
        console.log("[AI] Assistant started — microphone active");

    } catch (err) {
        console.error("[AI] Failed to start assistant:", err);
        alert("Could not start AI assistant. Check mic permissions and console.");
        stopAIAssistant();
    }
}

/**
 * Stop the AI assistant and clean up all resources.
 */
function stopAIAssistant() {
    // Close WebSocket
    if (aiWs) {
        aiWs.onclose = null; // prevent re-entry
        aiWs.close();
        aiWs = null;
    }

    // Disconnect worklet
    if (workletNode) {
        workletNode.disconnect();
        workletNode = null;
    }

    // Close capture context
    if (audioCtxCapture) {
        audioCtxCapture.close();
        audioCtxCapture = null;
    }

    // Stop mic tracks
    if (micStream) {
        micStream.getTracks().forEach(t => t.stop());
        micStream = null;
    }

    // Close playback context
    if (audioCtxPlay) {
        audioCtxPlay.close();
        audioCtxPlay = null;
    }

    playbackQueue = [];
    isPlaying = false;
    isAIActive = false;
    setFabActive(false);

    // Also stop camera if running
    if (videoStream) stopCamera();

    console.log("[AI] Assistant stopped");
}

/**
 * Toggle the FAB button appearance between idle and active states.
 */
function setFabActive(active) {
    if (active) {
        btnLiveAudio.classList.add("active");
        btnLiveAudio.innerHTML = `<i class="fa-solid fa-stop"></i>`;
        btnLiveAudio.title = "Stop AI Assistant";
    } else {
        btnLiveAudio.classList.remove("active");
        btnLiveAudio.innerHTML = `<i class="fa-solid fa-microphone-lines"></i>`;
        btnLiveAudio.title = "TerraLive AI Assistant";
    }
}

// FAB click handler — toggle
btnLiveAudio.addEventListener("click", () => {
    if (isAIActive) {
        stopAIAssistant();
    } else {
        startAIAssistant();
    }
});

// ═════════════════════════════════════════════════════════════
//  CAMERA VISION — JPEG FRAME CAPTURE
// ═════════════════════════════════════════════════════════════

/**
 * Start the camera, show preview, and begin sending JPEG frames
 * to the Gemini WebSocket every 2.5 seconds.
 */
async function startCamera() {
    try {
        videoStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment", width: 640, height: 480 },
        });
        cameraPreview.srcObject = videoStream;
        cameraPreview.classList.add("visible");
        btnCamera.classList.add("active");

        // Set canvas dimensions to match video
        cameraCanvas.width = 640;
        cameraCanvas.height = 480;
        const ctx = cameraCanvas.getContext("2d");

        // Capture & send a JPEG every 2.5 seconds
        frameInterval = setInterval(() => {
            if (!aiWs || aiWs.readyState !== WebSocket.OPEN) return;
            ctx.drawImage(cameraPreview, 0, 0, 640, 480);
            const dataUrl = cameraCanvas.toDataURL("image/jpeg", 0.6);
            // Strip the "data:image/jpeg;base64," prefix
            const b64 = dataUrl.split(",")[1];
            aiWs.send(JSON.stringify({ type: "image", data: b64 }));
        }, 2500);

        console.log("[Camera] Started — sending frames every 2.5s");
    } catch (err) {
        console.error("[Camera] Failed to access camera:", err);
        alert("Could not access camera. Check permissions.");
    }
}

/**
 * Stop the camera, hide preview, and clear the frame interval.
 */
function stopCamera() {
    if (frameInterval) {
        clearInterval(frameInterval);
        frameInterval = null;
    }
    if (videoStream) {
        videoStream.getTracks().forEach(t => t.stop());
        videoStream = null;
    }
    cameraPreview.srcObject = null;
    cameraPreview.classList.remove("visible");
    btnCamera.classList.remove("active");
    console.log("[Camera] Stopped");
}

/**
 * Toggle the camera on / off.
 */
function toggleCamera() {
    if (videoStream) {
        stopCamera();
    } else {
        if (!isAIActive) {
            alert("Start the AI Assistant first, then enable the camera.");
            return;
        }
        startCamera();
    }
}

btnCamera.addEventListener("click", toggleCamera);

// ═════════════════════════════════════════════════════════════
//  HEALTH CHECK (boot is now driven by Firebase auth observer)
// ═════════════════════════════════════════════════════════════
// Boot is now handled by fbAuth.onAuthStateChanged above.

// ═════════════════════════════════════════════════════════════
//  TEXT CHAT INTERFACE
// ═════════════════════════════════════════════════════════════

const chatWindow = document.getElementById("aiChatWindow");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");
const closeChatBtn = document.getElementById("closeChatBtn");
const toggleChatBtn = document.getElementById("btn-toggle-chat");

/**
 * Append a message bubble to the chat window.
 * @param {"user"|"ai"} role
 * @param {string} text
 */
function appendChatMessage(role, text) {
    if (!chatMessages) return;
    const div = document.createElement("div");
    div.className = `message ${role === "user" ? "user-message" : "ai-message"}`;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/** Show a typing indicator in the chat */
function showTypingIndicator() {
    if (!chatMessages) return;
    // Don't add duplicates
    if (chatMessages.querySelector(".typing-indicator")) return;
    const el = document.createElement("div");
    el.className = "typing-indicator";
    el.innerHTML = "<span></span><span></span><span></span>";
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Ensure the WebSocket to Gemini is open. If it's not connected
 * (e.g. the user hasn't pressed mic), open a text-only WS.
 */
function ensureChatWs() {
    if (aiWs && aiWs.readyState === WebSocket.OPEN) return true;

    // Open a lightweight WS for text-only chat  
    const proto = location.protocol === "https:" ? "wss" : "ws";
    aiWs = new WebSocket(`${proto}://${location.host}/ws/agent`);

    aiWs.onopen = () => {
        console.log("[Chat] WebSocket connected for text chat");
    };

    aiWs.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);

            if (msg.type === "session_ready") {
                console.log("[Chat] Gemini session ready");
                return;
            }

            if (msg.type === "text" && msg.data) {
                appendChatMessage("ai", msg.data);
                const typingEl = document.querySelector("#chatMessages .typing-indicator");
                if (typingEl) typingEl.remove();
                return;
            }

            if (msg.type === "audio" && msg.data) {
                let sr = 24000;
                if (msg.mimeType) {
                    const m = msg.mimeType.match(/rate=(\d+)/);
                    if (m) sr = parseInt(m[1], 10);
                }
                const pcm = base64ToInt16Array(msg.data);
                playPcmChunk(pcm, sr);
                return;
            }

            if (msg.type === "turn_complete") {
                const typingEl = document.querySelector("#chatMessages .typing-indicator");
                if (typingEl) typingEl.remove();
                return;
            }
        } catch (err) {
            console.warn("[Chat] Parse error:", err);
        }
    };

    aiWs.onclose = () => {
        console.log("[Chat] WebSocket closed");
        aiWs = null;
    };

    aiWs.onerror = (err) => {
        console.error("[Chat] WebSocket error:", err);
    };

    return false; // not immediately open; messages will queue
}

/**
 * Send a text message from the chat input to Gemini.
 */
function sendTextMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Show user message in chat
    appendChatMessage("user", text);
    chatInput.value = "";

    // Ensure WS is available
    ensureChatWs();

    // Send after a small delay if WS is still connecting
    const send = () => {
        if (aiWs && aiWs.readyState === WebSocket.OPEN) {
            aiWs.send(JSON.stringify({ type: "text", data: text }));
            showTypingIndicator();
        } else {
            // Retry once after 1s
            setTimeout(() => {
                if (aiWs && aiWs.readyState === WebSocket.OPEN) {
                    aiWs.send(JSON.stringify({ type: "text", data: text }));
                    showTypingIndicator();
                } else {
                    appendChatMessage("ai", "Unable to connect. Please try again.");
                }
            }, 1500);
        }
    };

    if (aiWs && aiWs.readyState === WebSocket.OPEN) {
        send();
    } else {
        // Wait for connection to open
        setTimeout(send, 800);
    }
}

// ── Chat UI Event Listeners ──
if (toggleChatBtn) {
    toggleChatBtn.addEventListener("click", () => {
        chatWindow.classList.toggle("hidden");
        if (!chatWindow.classList.contains("hidden")) {
            chatInput.focus();
        }
    });
}

if (closeChatBtn) {
    closeChatBtn.addEventListener("click", () => {
        chatWindow.classList.add("hidden");
    });
}

if (sendChatBtn) {
    sendChatBtn.addEventListener("click", sendTextMessage);
}

if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendTextMessage();
        }
    });
}
