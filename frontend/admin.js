/* =========================================================================
   RoadWatch — admin.js
   Admin-only views: Tickets, Analytics, Model monitor, Alerts.
   Exposes window.Admin for script.js's view-loader table and auth.js's bell badge.
   ========================================================================= */

const Admin = (() => {
  const severityColor = { Low: "#2f8f5b", Medium: "#f2b705", High: "#e8590c", Critical: "#d13b2f" };
  let departments = [];
  let charts = {}; // name -> Chart.js instance, destroyed/recreated on reload

  function setChart(name, cfg) {
    if (charts[name]) charts[name].destroy();
    charts[name] = new Chart(document.getElementById(cfg.id), cfg.config);
  }

  async function ensureDepartments() {
    if (departments.length) return departments;
    try {
      departments = await api("/departments");
      const sel = document.getElementById("fDept");
      departments.forEach((d) => sel.insertAdjacentHTML("beforeend", `<option>${escapeHtml(d)}</option>`));
    } catch (e) { /* ignore — filter just won't have options yet */ }
    return departments;
  }

  /* ======================================================================
     TICKETS
     ====================================================================== */
  const ticketsBody = document.getElementById("ticketsBody");
  const ticketsEmpty = document.getElementById("ticketsEmpty");

  document.getElementById("btnFilter").addEventListener("click", loadTickets);
  document.getElementById("fSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") loadTickets(); });

  // Export buttons: these endpoints require an admin bearer token, so a
  // plain window.open (no auth header) would 401 — fetch as a blob instead.
  async function downloadBlob(path, filename) {
    try {
      const res = await fetch(`${API_BASE}${path}`, { headers: Auth.headers() });
      if (!res.ok) { toast(`Export failed (${res.status})`); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (e) { toast("Export failed: " + e.message); }
  }

  function currentFilterParams() {
    const params = new URLSearchParams();
    const search = document.getElementById("fSearch").value.trim();
    const status = document.getElementById("fStatus").value;
    const severity = document.getElementById("fSeverity").value;
    const department = document.getElementById("fDept").value;
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (severity) params.set("severity", severity);
    if (department) params.set("department", department);
    return params;
  }

  document.getElementById("btnExport").addEventListener("click", () => downloadBlob(`/complaints/export.csv?${currentFilterParams()}`, "roadwatch_report.csv"));
  document.getElementById("btnExportPdf").addEventListener("click", () => downloadBlob(`/complaints/export.pdf?${currentFilterParams()}`, "roadwatch_report.pdf"));
  document.getElementById("btnExportXlsx").addEventListener("click", () => downloadBlob(`/complaints/export.xlsx?${currentFilterParams()}`, "roadwatch_report.xlsx"));

  async function loadTickets() {
    await ensureDepartments();
    const params = currentFilterParams();
    params.set("limit", "200");
    const sortBy = document.getElementById("fSort").value;
    if (sortBy) params.set("sort_by", sortBy);

    ticketsBody.innerHTML = "";
    try {
      const data = await api(`/complaints?${params}`, { headers: Auth.headers() });
      const items = data.items || [];
      ticketsEmpty.style.display = items.length ? "none" : "block";
      ticketsBody.innerHTML = items.map(rowHtml).join("");
      ticketsBody.querySelectorAll("tr[data-id]").forEach((tr) => {
        tr.addEventListener("click", (e) => {
          if (e.target.closest("select, button")) return;
          openTicketModal(tr.dataset.id);
        });
      });
    } catch (e) {
      ticketsBody.innerHTML = `<tr><td colspan="10">Could not load tickets: ${escapeHtml(e.message)}</td></tr>`;
    }
  }

  function rowHtml(c) {
    const loc = (c.latitude && c.longitude) ? `${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)}` : (c.address || "—");
    return `
      <tr data-id="${escapeHtml(c.complaint_id)}" style="cursor:pointer">
        <td><img class="thumb" src="${API_BASE}${c.annotated_image_path || c.image_path}" alt=""></td>
        <td><strong>#${escapeHtml(c.complaint_id)}</strong></td>
        <td><span class="severity-badge sev-${c.severity}">${c.severity}</span></td>
        <td>${c.confidence ? (c.confidence * 100).toFixed(1) + "%" : "—"}</td>
        <td>${c.report_count > 1 ? `${c.report_count}×` : "1"}</td>
        <td>${escapeHtml(loc)}</td>
        <td>${fmtDate(c.date_reported)}</td>
        <td>${escapeHtml(c.department || "—")}</td>
        <td><span class="severity-badge" style="background:var(--asphalt-700)">${escapeHtml(c.status)}</span></td>
        <td>›</td>
      </tr>
    `;
  }

  /* ---------------- Ticket detail modal ---------------- */
  const ticketModal = document.getElementById("ticketModal");
  const ticketModalBody = document.getElementById("ticketModalBody");
  document.getElementById("ticketModalClose").addEventListener("click", () => { ticketModal.hidden = true; });
  ticketModal.addEventListener("click", (e) => { if (e.target === ticketModal) ticketModal.hidden = true; });

  async function openTicketModal(id) {
    ticketModalBody.innerHTML = `<p class="card-desc">Loading #${escapeHtml(id)}…</p>`;
    ticketModal.hidden = false;
    try {
      const c = await api(`/complaints/${encodeURIComponent(id)}`);
      renderTicketModal(c);
    } catch (e) {
      ticketModalBody.innerHTML = `<div class="empty-state">${escapeHtml(e.message)}</div>`;
    }
  }

  function renderTicketModal(c) {
    const deptOptions = departments.map((d) => `<option ${d === c.department ? "selected" : ""}>${escapeHtml(d)}</option>`).join("");
    const statusOptions = c.allowed_next.map((s) => `<option value="${s}">Move to ${s}</option>`).join("");
    const timeline = (c.events || []).map((e) => `
      <li><span class="ev-type">${escapeHtml(e.event_type.replace("_", " "))}</span>
        <div class="ev-note">${escapeHtml(e.note || (e.to_status ? `→ ${e.to_status}` : ""))}</div>
        <span class="ev-actor">${escapeHtml(e.actor || "system")} · ${fmtDate(e.created_at)}</span></li>
    `).join("") || "<li>No events yet.</li>";

    ticketModalBody.innerHTML = `
      <div class="ticket-detail-head">
        <div><h2 style="margin:0">#${escapeHtml(c.complaint_id)}</h2><span class="severity-badge sev-${c.severity}">${c.severity}</span></div>
        <span class="severity-badge" style="background:var(--asphalt-700)">${escapeHtml(c.status)}</span>
      </div>
      <p class="card-desc">${c.num_potholes} pothole(s) · avg confidence ${c.avg_confidence ? (c.avg_confidence * 100).toFixed(1) + "%" : "—"}
        · reported ${c.report_count || 1}× ${c.reporter ? `· by ${escapeHtml(c.reporter)}` : ""}</p>
      <div class="ticket-detail-imgs">
        ${c.annotated_image_path ? `<img src="${API_BASE}${c.annotated_image_path}" alt="detected">` : ""}
        ${c.after_annotated_path ? `<img src="${API_BASE}${c.after_annotated_path}" alt="after repair">` : ""}
      </div>
      <div class="ticket-actions">
        <select class="field" id="mDept">${deptOptions || '<option value="">No departments configured</option>'}</select>
        <button class="btn btn-secondary btn-sm" id="mAssign">Assign</button>
        ${c.allowed_next.length ? `
          <select class="field" id="mStatus">${statusOptions}</select>
          <button class="btn btn-secondary btn-sm" id="mStatusGo">Go</button>
        ` : ""}
      </div>
      ${c.status === "In Progress" || c.status === "Resolved" ? `
        <div class="ticket-actions">
          <input type="file" accept="image/*" id="mAfterFile" class="field">
          <button class="btn btn-outline btn-sm" id="mAfterGo">Upload after-repair photo</button>
        </div>
      ` : ""}
      <h3 class="sub-h">Human-in-the-loop review${c.verified ? ` — <span class="muted">${c.verified}${c.corrected_by ? ` by ${escapeHtml(c.corrected_by)}` : ""}</span>` : ""}</h3>
      <p class="card-desc">Confirm the model got this right, or correct its severity/pothole count. The original detection is kept for error analysis.</p>
      <div class="ticket-actions">
        <button class="btn btn-outline btn-sm" id="mVerifyCorrect">✓ Model was correct</button>
        <select class="field" id="mCorrSeverity"><option value="">Correct severity…</option>${["Low", "Medium", "High", "Critical"].map((s) => `<option ${s === c.corrected_severity ? "selected" : ""}>${s}</option>`).join("")}</select>
        <input class="field" id="mCorrCount" type="number" min="0" placeholder="Correct pothole count" style="max-width:170px" value="${c.corrected_num_potholes ?? ""}">
        <button class="btn btn-secondary btn-sm" id="mCorrGo">Save correction</button>
      </div>
      <h3 class="sub-h">Timeline</h3>
      <ul class="timeline">${timeline}</ul>
    `;

    const assignBtn = document.getElementById("mAssign");
    if (assignBtn) assignBtn.addEventListener("click", async () => {
      const department = document.getElementById("mDept").value;
      if (!department) { toast("Pick a department first."); return; }
      try {
        const form = new FormData(); form.append("department", department);
        await api(`/complaints/${c.complaint_id}/assign`, { method: "PATCH", headers: Auth.headers(), body: form });
        toast("Department assigned."); openTicketModal(c.complaint_id); loadTickets();
      } catch (e) { toast(e.message); }
    });

    const statusBtn = document.getElementById("mStatusGo");
    if (statusBtn) statusBtn.addEventListener("click", async () => {
      const status = document.getElementById("mStatus").value;
      try {
        const form = new FormData(); form.append("status", status);
        await api(`/complaints/${c.complaint_id}/status`, { method: "PATCH", headers: Auth.headers(), body: form });
        toast(`Moved to ${status}.`); openTicketModal(c.complaint_id); loadTickets();
      } catch (e) { toast(e.message); }
    });

    const afterBtn = document.getElementById("mAfterGo");
    if (afterBtn) afterBtn.addEventListener("click", async () => {
      const fileEl = document.getElementById("mAfterFile");
      if (!fileEl.files.length) { toast("Choose a repair photo first."); return; }
      const form = new FormData(); form.append("file", fileEl.files[0]);
      try {
        await api(`/complaints/${c.complaint_id}/after-image`, { method: "POST", headers: Auth.headers(), body: form });
        toast("Repair photo uploaded."); openTicketModal(c.complaint_id); loadTickets();
      } catch (e) { toast(e.message); }
    });

    document.getElementById("mVerifyCorrect").addEventListener("click", async () => {
      try {
        const form = new FormData(); form.append("verified", "correct");
        await api(`/complaints/${c.complaint_id}/correct`, { method: "PATCH", headers: Auth.headers(), body: form });
        toast("Marked as correct."); openTicketModal(c.complaint_id);
      } catch (e) { toast(e.message); }
    });

    document.getElementById("mCorrGo").addEventListener("click", async () => {
      const severity = document.getElementById("mCorrSeverity").value;
      const count = document.getElementById("mCorrCount").value;
      if (!severity && count === "") { toast("Pick a corrected severity or count."); return; }
      try {
        const form = new FormData();
        if (severity) form.append("corrected_severity", severity);
        if (count !== "") form.append("corrected_num_potholes", count);
        await api(`/complaints/${c.complaint_id}/correct`, { method: "PATCH", headers: Auth.headers(), body: form });
        toast("Correction saved."); openTicketModal(c.complaint_id); loadTickets();
      } catch (e) { toast(e.message); }
    });
  }

  /* ======================================================================
     ANALYTICS
     ====================================================================== */
  let trendPeriod = "daily";
  document.querySelectorAll("#trendPeriod .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#trendPeriod .seg-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      trendPeriod = btn.dataset.p;
      loadTrend();
    });
  });

  async function loadAnalytics() {
    try {
      const data = await api("/insights", { headers: Auth.headers() });
      renderStats(data);
      renderSeverityChart(data.by_severity);
      renderDeptChart(data.by_department);
    } catch (e) {
      document.getElementById("statRow").innerHTML = `<div class="empty-state">Could not load analytics: ${escapeHtml(e.message)}</div>`;
    }
    loadTrend();
    loadConfidence();
    loadHotspots();
  }

  function renderStats(data) {
    document.getElementById("statRow").innerHTML = `
      <div class="stat-card"><div class="num">${data.total_complaints}</div><div class="lab">Total Complaints</div></div>
      <div class="stat-card"><div class="num">${data.urgent_open}</div><div class="lab">Urgent Open</div></div>
      <div class="stat-card"><div class="num">${data.unassigned_open}</div><div class="lab">Unassigned Open</div></div>
      <div class="stat-card"><div class="num">${data.by_status.Resolved || 0}</div><div class="lab">Resolved</div></div>
      <div class="stat-card"><div class="num">${data.avg_resolution_hours != null ? data.avg_resolution_hours + "h" : "—"}</div><div class="lab">Avg Resolution Time</div></div>
      <div class="stat-card"><div class="num">${data.duplicates_merged}</div><div class="lab">Duplicate Reports Merged</div></div>
    `;
  }

  function renderSeverityChart(bySeverity) {
    const labels = Object.keys(bySeverity), values = Object.values(bySeverity);
    setChart("severity", { id: "severityChart", config: {
      type: "doughnut",
      data: { labels, datasets: [{ data: values, backgroundColor: labels.map((l) => severityColor[l]) }] },
      options: { plugins: { legend: { position: "bottom" } } },
    }});
  }

  function renderDeptChart(byDept) {
    const labels = Object.keys(byDept), values = Object.values(byDept);
    setChart("dept", { id: "deptChart", config: {
      type: "bar",
      data: { labels, datasets: [{ data: values, backgroundColor: "#e8590c" }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
    }});
  }

  async function loadTrend() {
    try {
      const t = await api(`/insights/trends?period=${trendPeriod}`, { headers: Auth.headers() });
      const labels = t.points.map((p) => p.period);
      setChart("trend", { id: "trendChart", config: {
        type: "line",
        data: { labels, datasets: [
          { label: "Total", data: t.points.map((p) => p.total), borderColor: "#16181a", backgroundColor: "rgba(22,24,26,0.06)", tension: 0.3, fill: true },
          { label: "Moving avg", data: t.points.map((p) => p.moving_avg), borderColor: "#e8590c", borderDash: [4, 3], pointRadius: 0, tension: 0.3 },
        ]},
        options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
      }});
      const change = t.change_pct;
      document.getElementById("trendSummary").textContent =
        `${t.total} complaints over this window` +
        (change != null ? ` · ${change >= 0 ? "+" : ""}${change}% vs previous period` : "") +
        (t.peak ? ` · peak ${t.peak.period} (${t.peak.total})` : "");
    } catch (e) { toast("Could not load trend."); }
  }

  async function loadConfidence() {
    try {
      const c = await api("/insights/confidence", { headers: Auth.headers() });
      if (!c.count) {
        document.getElementById("confSummary").textContent = "No detections yet.";
        document.getElementById("confBands").innerHTML = "";
        return;
      }
      setChart("conf", { id: "confChart", config: {
        type: "bar",
        data: { labels: c.histogram.map((h) => h.range), datasets: [{ data: c.histogram.map((h) => h.count), backgroundColor: "#f2b705" }] },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
      }});
      document.getElementById("confSummary").textContent =
        `mean ${(c.mean * 100).toFixed(1)}% · median ${(c.median * 100).toFixed(1)}% · ${c.count} detections`;
      document.getElementById("confBands").innerHTML = `
        <div class="band-chip"><b>${c.bands.High}</b>High (≥${(c.thresholds.high * 100) | 0}%)</div>
        <div class="band-chip"><b>${c.bands.Medium}</b>Medium</div>
        <div class="band-chip"><b>${c.bands.Low}</b>Low (&lt;${(c.thresholds.medium * 100) | 0}%)</div>
      `;
      document.getElementById("reviewList").innerHTML = c.needs_review.length
        ? c.needs_review.map((r) => `
            <div class="review-item"><span>#${escapeHtml(r.complaint_id)} <span class="severity-badge sev-${r.severity}">${r.severity}</span></span>
            <span class="conf">${(r.min_confidence * 100).toFixed(1)}% · ${escapeHtml(r.status)}</span></div>`).join("")
        : `<div class="empty-state">Nothing needs review.</div>`;
    } catch (e) { document.getElementById("reviewList").innerHTML = `<div class="empty-state">Could not load confidence analysis: ${escapeHtml(e.message)}</div>`; }
  }

  async function loadHotspots() {
    try {
      const h = await api("/insights/hotspots", { headers: Auth.headers() });
      document.getElementById("hotspotList").innerHTML = h.hotspots.length
        ? h.hotspots.map((s, i) => `
            <div class="hotspot-item"><span>#${i + 1} — ${s.lat.toFixed(4)}, ${s.lng.toFixed(4)}
              <span class="severity-badge sev-${s.max_severity}">${s.max_severity}</span></span>
            <span class="score">${s.complaints} complaint(s) · score ${s.score}</span></div>`).join("")
        : `<div class="empty-state">Not enough geotagged data yet.</div>`;
    } catch (e) { document.getElementById("hotspotList").innerHTML = `<div class="empty-state">Could not load hotspots: ${escapeHtml(e.message)}</div>`; }
  }

  /* ======================================================================
     MODEL MONITOR
     ====================================================================== */
  async function loadMonitor() {
    loadPerformance();
    loadDrift();
    loadVersions();
  }

  async function loadPerformance() {
    try {
      const p = await api("/models/performance", { headers: Auth.headers() });
      const m = p.metrics;
      const pct = (v) => (v != null ? (v * 100).toFixed(1) + "%" : "—");
      document.getElementById("perfRow").innerHTML = `
        <div class="stat-card"><div class="num">${pct(m.precision)}</div><div class="lab">Precision</div></div>
        <div class="stat-card"><div class="num">${pct(m.recall)}</div><div class="lab">Recall</div></div>
        <div class="stat-card"><div class="num">${pct(m.f1)}</div><div class="lab">F1 Score</div></div>
        <div class="stat-card"><div class="num">${pct(m["mAP50"])}</div><div class="lab">mAP@50</div></div>
        <div class="stat-card"><div class="num">${pct(m["mAP50-95"])}</div><div class="lab">mAP@50-95</div></div>
        <div class="stat-card"><div class="num">${p.avg_inference_ms != null ? p.avg_inference_ms.toFixed(0) + "ms" : "—"}</div><div class="lab">Avg. Inference Time</div></div>
      `;
      document.getElementById("perfSummary").textContent = p.run_name
        ? `${p.run_name}${p.is_confirmed_active ? " (currently serving)" : " (best logged run — active weights untagged)"}`
        : (p.message || "No training runs logged yet.");
    } catch (e) { document.getElementById("perfRow").innerHTML = `<div class="empty-state">Could not load model performance: ${escapeHtml(e.message)}</div>`; }
  }

  async function loadDrift() {
    try {
      const d = await api("/drift", { headers: Auth.headers() });
      const label = d.status === "drift_detected" ? "Drift detected" : d.status === "stable" ? "Stable" : "Insufficient data";
      document.getElementById("driftBox").innerHTML = `
        <span class="drift-status ${d.status}">${label}</span>
        <p class="card-desc" style="margin-top:10px">${escapeHtml(d.message)}</p>
        ${d.reasons && d.reasons.length ? `<ul class="drift-reasons">${d.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>` : ""}
        ${d.live_mean_confidence != null ? `
          <div class="result-meta" style="margin-top:14px">
            <div class="meta-box"><div class="label">Live Mean Conf.</div><div class="value">${(d.live_mean_confidence * 100).toFixed(1)}%</div></div>
            <div class="meta-box"><div class="label">Baseline Mean</div><div class="value">${(d.baseline_mean_confidence * 100).toFixed(1)}%</div></div>
            <div class="meta-box"><div class="label">Z-score</div><div class="value">${d.z_score}</div></div>
            ${d.psi != null ? `<div class="meta-box"><div class="label">PSI</div><div class="value">${d.psi}</div></div>` : ""}
          </div>` : ""}
      `;
    } catch (e) { document.getElementById("driftBox").innerHTML = `<div class="empty-state">Could not load drift status.</div>`; }

    try {
      const h = await api("/drift/history?days=30", { headers: Auth.headers() });
      if (!h.points || !h.points.length) {
        const canvas = document.getElementById("driftChart");
        const parent = canvas.parentElement;
        canvas.style.display = "none";
        let msg = parent.querySelector(".chart-empty");
        if (!msg) { msg = document.createElement("div"); msg.className = "empty-state chart-empty"; parent.appendChild(msg); }
        msg.textContent = "Not enough detection history to plot drift yet.";
        return;
      }
      document.getElementById("driftChart").style.display = "block";
      const oldMsg = document.querySelector("#driftChart + .chart-empty");
      if (oldMsg) oldMsg.remove();
      setChart("drift", { id: "driftChart", config: {
        type: "line",
        data: { labels: h.points.map((p) => p.date), datasets: [
          { label: "Mean confidence", data: h.points.map((p) => p.mean_confidence), borderColor: "#e8590c", tension: 0.3 },
          ...(h.baseline_mean_confidence != null ? [{ label: "Baseline", data: h.points.map(() => h.baseline_mean_confidence), borderColor: "#8b8778", borderDash: [4, 3], pointRadius: 0 }] : []),
        ]},
        options: { scales: { y: { min: 0, max: 1 } } },
      }});
    } catch (e) { /* chart just won't render */ }

    try {
      const dist = await api("/drift/distribution", { headers: Auth.headers() });
      if (!dist.n_live || !dist.labels || !dist.labels.length) {
        const canvas = document.getElementById("distChart");
        const parent = canvas.parentElement;
        canvas.style.display = "none";
        let msg = parent.querySelector(".dist-chart-empty");
        if (!msg) { msg = document.createElement("div"); msg.className = "empty-state dist-chart-empty"; parent.appendChild(msg); }
        msg.textContent = "Not enough recent detections for a confidence distribution.";
        return;
      }
      document.getElementById("distChart").style.display = "block";
      const oldMsg = document.querySelector("#distChart + .dist-chart-empty");
      if (oldMsg) oldMsg.remove();
      setChart("dist", { id: "distChart", config: {
        type: "bar",
        data: { labels: dist.labels, datasets: [
          { label: `Live (n=${dist.n_live})`, data: dist.live, backgroundColor: "#e8590c" },
          { label: "Baseline", data: dist.baseline, backgroundColor: "rgba(22,24,26,0.25)" },
        ]},
        options: { scales: { y: { beginAtZero: true } } },
      }});
    } catch (e) { /* chart just won't render */ }
  }

  async function loadVersions() {
    const box = document.getElementById("versionsBox");
    try {
      const v = await api("/models/versions", { headers: Auth.headers() });
      if (!v.available) { box.innerHTML = `<div class="empty-state">${escapeHtml(v.message)}</div>`; return; }
      box.innerHTML = v.runs.map((r) => `
        <div class="version-row ${r.is_best ? "best" : ""} ${r.is_active ? "active" : ""}">
          <div>
            <strong>${escapeHtml(r.name)}</strong> <span class="muted">${escapeHtml(r.run_id.slice(0, 8))}</span>
            <div class="vmeta">${r.status} · ${fmtDate(r.started)}${r.duration_s ? ` · ${Math.round(r.duration_s)}s` : ""}
              · epochs=${r.params.epochs || "?"} imgsz=${r.params.imgsz || "?"}</div>
          </div>
          <div class="metrics">
            ${["precision", "recall", "mAP50", "mAP50-95"].map((m) => `<span>${m}: ${r.metrics[m] != null ? r.metrics[m].toFixed(3) : "—"}</span>`).join("")}
          </div>
        </div>
      `).join("") || `<div class="empty-state">No training runs logged yet.</div>`;
    } catch (e) { box.innerHTML = `<div class="empty-state">Could not load model versions: ${escapeHtml(e.message)}</div>`; }
  }

  /* ======================================================================
     ALERTS
     ====================================================================== */
  document.getElementById("bellBtn").addEventListener("click", () => activateView("alerts"));
  document.getElementById("btnAckAll").addEventListener("click", async () => {
    try { await api("/alerts/ack-all", { method: "PATCH", headers: Auth.headers() }); loadAlerts(); refreshBellBadge(); }
    catch (e) { toast(e.message); }
  });

  async function loadAlerts() {
    const box = document.getElementById("alertList");
    try {
      const data = await api("/alerts", { headers: Auth.headers() });
      box.innerHTML = data.alerts.length ? data.alerts.map((a) => `
        <div class="alert-item ${a.acknowledged ? "" : "unread"}" data-id="${a.id}">
          <div class="msg"><span class="severity-badge sev-${a.severity}">${a.severity}</span> ${escapeHtml(a.message)}
            <span class="time">${fmtDate(a.created_at)}</span></div>
          ${a.acknowledged ? "" : `<button class="btn btn-outline btn-sm ackBtn">Acknowledge</button>`}
        </div>
      `).join("") : `<div class="empty-state">No alerts yet.</div>`;
      box.querySelectorAll(".ackBtn").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
          const id = e.target.closest("[data-id]").dataset.id;
          try { await api(`/alerts/${id}/ack`, { method: "PATCH", headers: Auth.headers() }); loadAlerts(); refreshBellBadge(); }
          catch (err) { toast(err.message); }
        });
      });
    } catch (e) { box.innerHTML = `<div class="empty-state">Could not load alerts.</div>`; }
    refreshBellBadge();
  }

  async function refreshBellBadge() {
    if (!Auth.isAdmin()) return;
    try {
      const { unread } = await api("/alerts/unread-count", { headers: Auth.headers() });
      const badge = document.getElementById("bellBadge");
      badge.hidden = unread === 0;
      badge.textContent = unread > 99 ? "99+" : unread;
    } catch (e) { /* silent — bell is a nice-to-have */ }
  }

  /* ======================================================================
     ZONES / ROAD HEALTH (create — admin only; the public list lives in citizen.js)
     ====================================================================== */
  const btnCreateZone = document.getElementById("btnCreateZone");
  if (btnCreateZone) btnCreateZone.addEventListener("click", async () => {
    const name = document.getElementById("zName").value.trim();
    const lat = document.getElementById("zLat").value.trim();
    const lng = document.getElementById("zLng").value.trim();
    const radius = document.getElementById("zRadius").value.trim() || "2";
    const errEl = document.getElementById("zoneErr");
    errEl.textContent = "";
    if (!name || !lat || !lng) { errEl.textContent = "Name, latitude and longitude are required."; return; }
    try {
      const form = new FormData();
      form.append("name", name); form.append("latitude", lat); form.append("longitude", lng); form.append("radius_km", radius);
      await api("/zones", { method: "POST", headers: Auth.headers(), body: form });
      document.getElementById("zName").value = "";
      document.getElementById("zLat").value = "";
      document.getElementById("zLng").value = "";
      toast(`Zone "${name}" created.`);
      if (window.Citizen) Citizen.loadZones();
    } catch (e) { errEl.textContent = e.message; }
  });

  /* ======================================================================
     DATASET MANAGEMENT
     ====================================================================== */
  const btnDsUpload = document.getElementById("btnDsUpload");
  if (btnDsUpload) btnDsUpload.addEventListener("click", async () => {
    const imgEl = document.getElementById("dsImage");
    const labelEl = document.getElementById("dsLabel");
    const notes = document.getElementById("dsNotes").value.trim();
    const errEl = document.getElementById("dsErr");
    errEl.textContent = "";
    if (!imgEl.files.length) { errEl.textContent = "Choose an image first."; return; }
    const form = new FormData();
    form.append("file", imgEl.files[0]);
    if (labelEl.files.length) form.append("label", labelEl.files[0]);
    if (notes) form.append("notes", notes);
    try {
      await api("/dataset/images", { method: "POST", headers: Auth.headers(), body: form });
      imgEl.value = ""; labelEl.value = ""; document.getElementById("dsNotes").value = "";
      toast("Image uploaded to the dataset staging area.");
      loadDataset();
    } catch (e) { errEl.textContent = e.message; }
  });

  async function loadDataset() {
    try {
      const data = await api("/dataset/images?limit=100", { headers: Auth.headers() });
      document.getElementById("dsCount").textContent = `${data.total} image(s) staged · ${data.labeled_on_page} labeled on this page`;
      document.getElementById("dsList").innerHTML = data.items.length ? data.items.map((img) => `
        <div class="hotspot-item">
          <span><img class="thumb" src="${API_BASE}${img.url}" alt=""> ${escapeHtml(img.original_name || img.filename)}
            ${img.has_label ? '<span class="severity-badge" style="background:#2f8f5b">labeled</span>' : '<span class="severity-badge" style="background:var(--asphalt-700)">unlabeled</span>'}
            ${img.notes ? `<div class="muted">${escapeHtml(img.notes)}</div>` : ""}
          </span>
          <button class="btn btn-outline btn-sm dsDelete" data-id="${img.id}">Delete</button>
        </div>
      `).join("") : `<div class="empty-state">No images staged yet.</div>`;
      document.getElementById("dsList").querySelectorAll(".dsDelete").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try { await api(`/dataset/images/${btn.dataset.id}`, { method: "DELETE", headers: Auth.headers() }); loadDataset(); }
          catch (e) { toast(e.message); }
        });
      });
    } catch (e) { document.getElementById("dsList").innerHTML = `<div class="empty-state">Could not load dataset images: ${escapeHtml(e.message)}</div>`; }
  }

  /* ======================================================================
     AUDIT LOG
     ====================================================================== */
  const btnAuditFilter = document.getElementById("btnAuditFilter");
  if (btnAuditFilter) btnAuditFilter.addEventListener("click", loadAudit);

  async function loadAudit() {
    const params = new URLSearchParams({ limit: "100" });
    const actor = document.getElementById("auActor").value.trim();
    const action = document.getElementById("auAction").value.trim();
    if (actor) params.set("actor", actor);
    if (action) params.set("action", action);
    try {
      const data = await api(`/audit?${params}`, { headers: Auth.headers() });
      document.getElementById("auditList").innerHTML = data.items.length ? data.items.map((a) => `
        <div class="alert-item">
          <div class="msg"><strong>${escapeHtml(a.actor)}</strong> — ${escapeHtml(a.action.replace(/_/g, " "))}
            ${a.target_type ? ` <span class="muted">${escapeHtml(a.target_type)}${a.target_id ? " #" + escapeHtml(a.target_id) : ""}</span>` : ""}
            ${a.details ? `<div class="muted">${escapeHtml(a.details)}</div>` : ""}
            <span class="time">${fmtDate(a.created_at)}</span></div>
        </div>
      `).join("") : `<div class="empty-state">No matching audit entries.</div>`;
    } catch (e) { document.getElementById("auditList").innerHTML = `<div class="empty-state">Could not load the audit log: ${escapeHtml(e.message)}</div>`; }
  }

  return { loadTickets, loadAnalytics, loadMonitor, loadAlerts, loadDataset, loadAudit, refreshBellBadge };
})();
window.Admin = Admin;

// admin is logged in already (e.g. page reload) — poll the alert badge periodically
setInterval(() => { if (window.Auth && Auth.isAdmin()) Admin.refreshBellBadge(); }, 60000);
