/* =========================================================================
   RoadWatch — shared frontend core
   Talks to the FastAPI backend (default: http://localhost:8000).
   Split across 4 files, loaded in this order (see index.html):
     script.js    — API base, toast, tabs, health check, Detect view
     auth.js       — login/register, JWT storage, role-gated UI
     citizen.js    — Track / Map & heatmap / My reports (public + citizen)
     admin.js      — Tickets / Analytics / Model monitor / Alerts (admin)
   ========================================================================= */

const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : ""; // same-origin in production; adjust as needed

// Shared X-API-Key for the /predict endpoints. Matches config.py's API_KEY.
// For a real deployment, don't hardcode this in frontend JS — proxy
// requests through your own authenticated backend instead. Fine for a demo.
const API_KEY = "roadwatch-demo-key";

document.getElementById("apiBaseNote").textContent = API_BASE || window.location.origin;

// PWA: installable app shell (see service-worker.js). Safe to skip if the
// page isn't served over http(s) (e.g. opened as a local file://).
if ("serviceWorker" in navigator && (location.protocol === "http:" || location.protocol === "https:")) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("service-worker.js").catch(() => { /* PWA install just won't be offered */ });
  });
}

/* ---------------- Toast ---------------- */
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 3200);
}

/* ---------------- Small fetch helper ----------------
   Adds JSON handling + a readable error message. Auth headers are merged
   in by the caller (Auth.headers() from auth.js) where needed. */
async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, opts);
  } catch (e) {
    const err = new Error(`Cannot reach the backend at ${API_BASE || window.location.origin}. Start uvicorn on port 8000 and refresh.`);
    err.cause = e;
    err.status = 0;
    throw err;
  }
  let body = null;
  try { body = await res.json(); } catch (e) { /* no body / not JSON */ }
  if (!res.ok) {
    const detail = (body && (body.detail || body.message)) || `Request failed (${res.status})`;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch (e) { return iso; }
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ---------------- Tabs ----------------
   Role-gated tabs (data-role="admin" / "user") are hidden by default in
   the HTML and revealed by auth.js's updateAuthUI() once we know who's
   logged in. Switching to a view lazy-loads its data. */
const VIEW_LOADERS = {
  tickets: () => window.Admin && Admin.loadTickets(),
  analytics: () => window.Admin && Admin.loadAnalytics(),
  monitor: () => window.Admin && Admin.loadMonitor(),
  alerts: () => window.Admin && Admin.loadAlerts(),
  dataset: () => window.Admin && Admin.loadDataset(),
  audit: () => window.Admin && Admin.loadAudit(),
  map: () => window.Citizen && Citizen.loadMap(),
  mine: () => window.Citizen && Citizen.loadMine(),
  zones: () => window.Citizen && Citizen.loadZones(),
};

function activateView(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  if (VIEW_LOADERS[name]) VIEW_LOADERS[name]();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => activateView(btn.dataset.view));
});

/* ---------------- API health ---------------- */
async function checkHealth() {
  const dot = document.getElementById("apiStatusDot");
  const text = document.getElementById("apiStatusText");
  try {
    const data = await api("/health");
    if (data.status === "ok" && data.model_loaded) {
      dot.classList.add("online");
      text.textContent = "Model online";
    } else {
      text.textContent = "Model not loaded";
    }
  } catch (e) {
    text.textContent = "Backend unreachable";
  }
}
checkHealth();

/* ======================================================================
   DETECT VIEW
   ====================================================================== */
let selectedFile = null;
let selectedLat = null;
let selectedLng = null;
let selectedAddress = null;
let mediaStream = null;
let cameraLocationPromise = null; // GPS fetch kicked off the moment camera opens

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("drag-over"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", (e) => {
  if (e.target.files.length) handleFile(e.target.files[0]);
});

function handleFile(file, source = "upload") {
  selectedFile = file;
  selectedLat = null;
  selectedLng = null;
  selectedAddress = null;
  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById("previewImg").src = e.target.result;
    document.getElementById("previewWrap").style.display = "block";
  };
  reader.readAsDataURL(file);
  document.getElementById("resultsCard").style.display = "none";
  stopCamera();

  if (source === "upload") {
    setLocationStatus("checking", "Checking photo for location data…");
    tryReadExifLocation(file);
  }
}

function setLocationStatus(state, message) {
  const row = document.getElementById("locationRow");
  const valueEl = document.getElementById("locationValue");
  row.style.display = "flex";
  row.classList.remove("loc-ok", "loc-warn", "loc-checking");
  row.classList.add(state === "ok" ? "loc-ok" : state === "warn" ? "loc-warn" : "loc-checking");
  valueEl.textContent = message;
}

// Reads embedded GPS EXIF tags from an uploaded photo, if present. Most
// gallery photos don't have GPS data (phones strip it, or location
// services were off) — tell the user clearly instead of silently doing nothing.
function tryReadExifLocation(file) {
  if (typeof EXIF === "undefined") {
    setLocationStatus("warn", "Location not available for this photo — attach it manually or use the camera.");
    return;
  }
  EXIF.getData(file, function () {
    const lat = EXIF.getTag(this, "GPSLatitude");
    const lon = EXIF.getTag(this, "GPSLongitude");
    const latRef = EXIF.getTag(this, "GPSLatitudeRef") || "N";
    const lonRef = EXIF.getTag(this, "GPSLongitudeRef") || "E";

    if (lat && lon) {
      selectedLat = dmsToDecimal(lat, latRef);
      selectedLng = dmsToDecimal(lon, lonRef);
      setLocationStatus("ok", `Detected from photo: ${selectedLat.toFixed(5)}, ${selectedLng.toFixed(5)}`);
    } else {
      setLocationStatus("warn",
        "Can't access location for this photo — gallery images often don't include GPS data. " +
        "Attach it manually below, or use the camera for auto-location.");
    }
  });
}

function dmsToDecimal(dms, ref) {
  const toNum = (v) => (v && v.numerator !== undefined ? v.numerator / v.denominator : v);
  const degrees = toNum(dms[0]);
  const minutes = toNum(dms[1]);
  const seconds = toNum(dms[2]);
  let dd = degrees + minutes / 60 + seconds / 3600;
  if (ref === "S" || ref === "W") dd = -dd;
  return dd;
}

document.getElementById("btnReset").addEventListener("click", () => {
  selectedFile = null;
  selectedLat = null;
  selectedLng = null;
  fileInput.value = "";
  document.getElementById("previewWrap").style.display = "none";
  document.getElementById("resultsCard").style.display = "none";
  document.getElementById("locationRow").style.display = "none";
});

/* ---------------- Camera capture ---------------- */
const cameraWrap = document.getElementById("cameraWrap");
const cameraVideo = document.getElementById("cameraVideo");
const cameraCanvas = document.getElementById("cameraCanvas");

document.getElementById("btnCamera").addEventListener("click", async () => {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    cameraVideo.srcObject = mediaStream;
    cameraWrap.style.display = "block";

    if (navigator.geolocation) {
      cameraLocationPromise = new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
          (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
          () => resolve(null),
          { timeout: 8000 }
        );
      });
    } else {
      cameraLocationPromise = Promise.resolve(null);
    }
  } catch (e) {
    toast("Could not access camera: " + e.message);
  }
});

document.getElementById("btnCapture").addEventListener("click", async () => {
  const w = cameraVideo.videoWidth, h = cameraVideo.videoHeight;
  cameraCanvas.width = w;
  cameraCanvas.height = h;
  const ctx = cameraCanvas.getContext("2d");
  ctx.drawImage(cameraVideo, 0, 0, w, h);
  cameraCanvas.toBlob(async (blob) => {
    const file = new File([blob], `capture_${Date.now()}.jpg`, { type: "image/jpeg" });
    handleFile(file, "camera");
    stopCamera();

    setLocationStatus("checking", "Getting your location…");
    const loc = cameraLocationPromise ? await cameraLocationPromise : null;
    if (loc) {
      selectedLat = loc.lat;
      selectedLng = loc.lng;
      setLocationStatus("ok", `Auto-attached from device GPS: ${loc.lat.toFixed(5)}, ${loc.lng.toFixed(5)}`);
    } else {
      setLocationStatus("warn", "Couldn't get device location — check location permission, or attach it manually below.");
    }
  }, "image/jpeg", 0.92);
});

document.getElementById("btnCloseCamera").addEventListener("click", stopCamera);

function stopCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
  cameraWrap.style.display = "none";
}

/* ---------------- GPS location ---------------- */
document.getElementById("btnLocation").addEventListener("click", () => {
  if (!navigator.geolocation) {
    toast("Geolocation not supported by this browser.");
    return;
  }
  setLocationStatus("checking", "Fetching your location…");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      selectedLat = pos.coords.latitude;
      selectedLng = pos.coords.longitude;
      selectedAddress = null;
      setLocationStatus("ok", `Manually attached: ${selectedLat.toFixed(5)}, ${selectedLng.toFixed(5)}`);
      toast("Location attached.");
    },
    (err) => setLocationStatus("warn", "Location error: " + err.message)
  );
});

/* ---------------- Run detection ---------------- */
document.getElementById("btnDetect").addEventListener("click", runDetection);

async function runDetection() {
  if (!selectedFile) {
    toast("Please choose or capture an image first.");
    return;
  }
  const btn = document.getElementById("btnDetect");
  const originalLabel = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Detecting…`;

  const form = new FormData();
  form.append("file", selectedFile);
  if (selectedLat !== null) form.append("latitude", selectedLat);
  if (selectedLng !== null) form.append("longitude", selectedLng);
  if (selectedAddress) form.append("address", selectedAddress);
  const notifyEmail = document.getElementById("notifyEmail").value.trim();
  if (notifyEmail) form.append("notify_email", notifyEmail);

  const headers = { "X-API-Key": API_KEY };
  if (window.Auth && Auth.token()) headers.Authorization = `Bearer ${Auth.token()}`;

  try {
    const data = await api("/predict", { method: "POST", headers, body: form });
    renderResult(data);
  } catch (e) {
    toast("Detection failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalLabel;
  }
}

function renderResult(data) {
  const card = document.getElementById("resultsCard");
  card.style.display = "block";
  document.getElementById("resultImg").src = `${API_BASE}${data.annotated_image}`;

  const meta = document.getElementById("resultMeta");
  const sevClass = `sev-${data.overall_severity}`;
  meta.innerHTML = `
    <div class="meta-box"><div class="label">Potholes Found</div><div class="value">${data.num_potholes}</div></div>
    <div class="meta-box"><div class="label">Max Confidence</div><div class="value">${(data.max_confidence * 100).toFixed(1)}%</div></div>
    <div class="meta-box"><div class="label">Severity</div><div class="value"><span class="severity-badge ${sevClass}">${data.overall_severity}</span></div></div>
    ${data.confidence_band ? `<div class="meta-box"><div class="label">Detection Quality</div><div class="value">${data.confidence_band}</div></div>` : ""}
  `;

  const note = document.getElementById("complaintNote");
  if (data.duplicate) {
    const d = data.duplicate;
    const why = d.reason === "same_location"
      ? `it's ${d.distance_m} m from an existing report`
      : `the photo closely matches an existing report`;
    note.innerHTML = `🔁 Linked to existing ticket <strong>#${d.of}</strong> (${why}) — now reported ${d.report_count}× `
      + (d.escalated ? `and <strong>escalated</strong> to a higher severity. ` : "")
      + `Check the Track tab.`;
  } else if (data.complaint) {
    note.innerHTML = `✅ Complaint <strong>#${data.complaint.complaint_id}</strong> filed automatically — track it from the Track tab.`;
  } else {
    note.innerHTML = `No potholes detected — road looks clear, no complaint filed.`;
  }

  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
