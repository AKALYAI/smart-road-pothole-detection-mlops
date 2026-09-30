/* =========================================================================
   RoadWatch — citizen.js
   Public / citizen views: Track a complaint, Map & heatmap, My reports.
   Exposes window.Citizen for script.js's view-loader table.
   ========================================================================= */

const Citizen = (() => {

  /* ---------------- Track a complaint (public) ---------------- */
  const trackInput = document.getElementById("trackInput");
  const trackResult = document.getElementById("trackResult");

  document.getElementById("btnTrack").addEventListener("click", trackComplaint);
  trackInput.addEventListener("keydown", (e) => { if (e.key === "Enter") trackComplaint(); });

  async function trackComplaint() {
    const id = trackInput.value.trim();
    if (!id) { toast("Enter a ticket ID."); return; }
    trackResult.innerHTML = `<p class="card-desc">Looking up #${escapeHtml(id)}…</p>`;
    try {
      const c = await api(`/complaints/${encodeURIComponent(id)}`);
      renderTrackResult(c);
    } catch (e) {
      trackResult.innerHTML = `<div class="empty-state">${e.status === 404 ? "No complaint found with that ID." : escapeHtml(e.message)}</div>`;
    }
  }

  function renderTrackResult(c) {
    const stages = ["Open", "Assigned", "In Progress", "Resolved"];
    const idx = stages.indexOf(c.status);
    const stageStrip = stages.map((s, i) => `
      <li class="pipeline-tag" style="opacity:${i <= idx ? 1 : 0.35}">${s}</li>
    `).join("");

    const timeline = (c.events || []).map((e) => `
      <li>
        <span class="ev-type">${escapeHtml(e.event_type.replace("_", " "))}</span>
        <div class="ev-note">${escapeHtml(e.note || (e.to_status ? `→ ${e.to_status}` : ""))}</div>
        <span class="ev-actor">${escapeHtml(e.actor || "system")} · ${fmtDate(e.created_at)}</span>
      </li>
    `).join("") || "<li>No events yet.</li>";

    trackResult.innerHTML = `
      <div class="ticket-detail-head">
        <div>
          <h3 style="margin:0">#${escapeHtml(c.complaint_id)}</h3>
          <span class="severity-badge sev-${c.severity}">${c.severity}</span>
        </div>
        <div class="muted">${c.report_count > 1 ? `Reported ${c.report_count}× by different visits` : "Reported once"}</div>
      </div>
      <p class="card-desc">${stageStrip.replace(/<\/?ol.*?>/g, "")}</p>
      <div class="result-meta">
        <div class="meta-box"><div class="label">Potholes</div><div class="value">${c.num_potholes}</div></div>
        <div class="meta-box"><div class="label">Status</div><div class="value">${escapeHtml(c.status)}</div></div>
        <div class="meta-box"><div class="label">Department</div><div class="value" style="font-size:14px">${escapeHtml(c.department || "—")}</div></div>
        <div class="meta-box"><div class="label">Filed</div><div class="value" style="font-size:13px">${fmtDate(c.date_reported)}</div></div>
      </div>
      ${c.annotated_image_path ? `<div class="ticket-detail-imgs"><img src="${API_BASE}${c.annotated_image_path}" alt="detected"> ${c.after_annotated_path ? `<img src="${API_BASE}${c.after_annotated_path}" alt="after repair">` : ""}</div>` : ""}
      <h3 class="sub-h">Timeline</h3>
      <ul class="timeline">${timeline}</ul>
    `;
  }

  /* ---------------- Map & heatmap (public) ---------------- */
  let leafletMap = null, markersLayer = null, heatLayer = null;
  const severityColor = { Low: "#2f8f5b", Medium: "#f2b705", High: "#e8590c", Critical: "#d13b2f" };
  let mapMode = "markers"; // markers | heat | both

  document.querySelectorAll("#mapMode .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#mapMode .seg-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      mapMode = btn.dataset.mode;
      applyMapMode();
    });
  });
  document.getElementById("mapResolved").addEventListener("change", loadMap);

  async function loadMap() {
    const includeResolved = document.getElementById("mapResolved").checked;
    try {
      const data = await api(`/insights/map?include_resolved=${includeResolved}`);
      renderMap(data);
    } catch (e) {
      toast("Could not load map — is the backend running?");
    }
  }

  function ensureMap() {
    if (leafletMap) return;
    leafletMap = L.map("map").setView([20.5937, 78.9629], 5); // default: India
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(leafletMap);
    markersLayer = L.layerGroup();
    heatLayer = L.heatLayer([], { radius: 28, blur: 22, maxZoom: 15 });
  }

  function renderMap(data) {
    ensureMap();
    markersLayer.clearLayers();

    document.getElementById("mapCount").textContent = `${data.locations.length} geotagged complaint(s)`;

    // Make the empty-data state explicit instead of leaving a blank map.
    let emptyNotice = document.getElementById("mapEmptyNotice");
    if (!emptyNotice) {
      emptyNotice = document.createElement("div");
      emptyNotice.id = "mapEmptyNotice";
      emptyNotice.className = "map-empty-notice";
      document.getElementById("map").appendChild(emptyNotice);
    }
    if (!data.locations.length) {
      emptyNotice.innerHTML = `<strong>No geotagged complaints yet.</strong><span>Attach device GPS or use the location button when filing a complaint to show markers and heatmap points.</span>`;
      emptyNotice.hidden = false;
    } else {
      emptyNotice.hidden = true;
    }

    const bounds = [];
    data.locations.forEach((loc) => {
      const marker = L.circleMarker([loc.lat, loc.lng], {
        radius: 8 + Math.min(loc.report_count - 1, 4) * 2,
        color: "#16181a", weight: 1, fillColor: severityColor[loc.severity] || "#888", fillOpacity: 0.9,
      }).bindPopup(
        `<strong>#${loc.complaint_id}</strong><br>Severity: ${loc.severity}<br>Status: ${loc.status}` +
        (loc.department ? `<br>Dept: ${loc.department}` : "") +
        (loc.report_count > 1 ? `<br>Reported ${loc.report_count}×` : "")
      );
      markersLayer.addLayer(marker);
      bounds.push([loc.lat, loc.lng]);
    });

    heatLayer.setLatLngs(data.heat.map(([lat, lng, w]) => [lat, lng, w]));

    if (bounds.length) leafletMap.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
    applyMapMode();
  }

  function applyMapMode() {
    if (!leafletMap) return;
    leafletMap.removeLayer(markersLayer);
    leafletMap.removeLayer(heatLayer);
    if (mapMode === "markers" || mapMode === "both") markersLayer.addTo(leafletMap);
    if (mapMode === "heat" || mapMode === "both") heatLayer.addTo(leafletMap);
  }

  /* ---------------- My reports (logged-in citizen) ---------------- */
  const mineList = document.getElementById("mineList");

  async function loadMine() {
    if (!Auth.isLoggedIn()) { mineList.innerHTML = `<div class="empty-state">Log in to see your reports.</div>`; return; }
    try {
      const data = await api("/complaints/mine?limit=100", { headers: Auth.headers() });
      if (!data.items.length) { mineList.innerHTML = `<div class="empty-state">No reports filed while logged in yet.</div>`; return; }
      mineList.innerHTML = data.items.map((c) => `
        <div class="version-row">
          <div>
            <strong>#${escapeHtml(c.complaint_id)}</strong>
            <span class="severity-badge sev-${c.severity}">${c.severity}</span>
            <div class="muted">${fmtDate(c.date_reported)} · ${escapeHtml(c.department || "unassigned")}</div>
          </div>
          <div class="vmeta">${escapeHtml(c.status)}${c.report_count > 1 ? ` · ${c.report_count}×` : ""}</div>
        </div>
      `).join("");
    } catch (e) {
      mineList.innerHTML = `<div class="empty-state">Could not load your reports.</div>`;
    }
  }

  /* ---------------- Zones / Road Health (public read) ---------------- */
  async function loadZones() {
    const box = document.getElementById("zoneList");
    try {
      const data = await api("/zones");
      box.innerHTML = data.zones.length ? data.zones.map((z) => `
        <div class="hotspot-item">
          <span><strong>${escapeHtml(z.name)}</strong>
            ${z.description ? `<span class="muted"> — ${escapeHtml(z.description)}</span>` : ""}
            <div class="muted">${z.total_complaints} complaint(s) · ${z.unresolved} unresolved
              ${z.avg_resolution_days != null ? `· avg resolution ${z.avg_resolution_days}d` : ""}</div>
          </span>
          <span class="score" style="font-size:16px;font-family:var(--font-display);color:${z.score >= 70 ? "#2f8f5b" : z.score >= 40 ? "#e8590c" : "#d13b2f"}">${z.score}/100</span>
        </div>
      `).join("") : `<div class="empty-state">No zones yet.${Auth.isAdmin() ? " Create one above." : ""}</div>`;
    } catch (e) {
      box.innerHTML = `<div class="empty-state">Could not load zones: ${escapeHtml(e.message)}</div>`;
    }
  }

  return { loadMap, loadMine, loadZones };
})();
window.Citizen = Citizen;
