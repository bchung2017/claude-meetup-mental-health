(() => {
  const NS = "http://www.w3.org/2000/svg";
  const $ = (s) => document.querySelector(s);
  const tooltip = $("#tooltip");
  const DAY = 86400000;
  let patients = [];
  let data = null;
  let weeks = 0;

  // ---- helpers ----
  const el = (tag, attrs = {}, text) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const h = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const tDate = (ymd) => { const [y, m, d] = ymd.split("-").map(Number); return new Date(y, m - 1, d, 12).getTime(); };
  const tIso = (iso) => new Date(iso).getTime();
  const fmtDate = (t) => new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const fmtDateTime = (t) => new Date(t).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  const age = (dob) => Math.floor((Date.now() - tDate(dob)) / (365.25 * DAY));
  const bandLabel = (b) => (b || "").replace(/_/g, " ");

  function showTip(evt, when, lines, note) {
    tooltip.replaceChildren();
    tooltip.append(h("div", "when", when));
    for (const l of lines) {
      const r = h("div", "r");
      const key = h("i", `key ${l.cls}`);
      const v = h("strong", null, l.value);
      const k = h("span", "k", l.name);
      r.append(key, v, k);
      tooltip.append(r);
    }
    if (note) tooltip.append(h("div", "note", note));
    tooltip.hidden = false;
    const x = Math.min(evt.clientX + 12, window.innerWidth - tooltip.offsetWidth - 8);
    tooltip.style.left = x + "px";
    tooltip.style.top = Math.max(8, evt.clientY - tooltip.offsetHeight - 12) + "px";
  }
  const hideTip = () => { tooltip.hidden = true; };

  // ---- generic multi-series line chart over time ----
  // opts: rows[{t,...}], series[{key,name,cls,fmt?}], yMin, yMax, yTicks[{v,label?}], bands[{from,to,label}],
  //       events[{t,label}], markers[t], domain[t0,t1], dots(bool), endLabel(bool), note(row)=>string
  function lineChart(container, o) {
    const W = container.clientWidth || 600, H = container.clientHeight || 260;
    const m = { t: 20, r: o.endLabel ? 44 : 16, b: 26, l: 36 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    container.replaceChildren(svg);
    const rows = o.rows.filter((r) => r.t >= o.domain[0] && r.t <= o.domain[1]);
    const [t0, t1] = o.domain;
    const x = (t) => m.l + ((t - t0) / (t1 - t0)) * iw;
    const y = (v) => m.t + ih - ((v - o.yMin) / (o.yMax - o.yMin)) * ih;

    for (const b of o.bands || []) {
      svg.append(el("rect", { class: "band", x: m.l, y: y(b.to), width: iw, height: y(b.from) - y(b.to) }));
      svg.append(el("text", { class: "band-label", x: m.l + iw - 4, y: y(b.to) + 11, "text-anchor": "end" }, b.label));
    }
    for (const tk of o.yTicks) {
      svg.append(el("line", { class: tk.v === o.yMin ? "axis" : "grid", x1: m.l, x2: m.l + iw, y1: y(tk.v), y2: y(tk.v) }));
      svg.append(el("text", { x: m.l - 8, y: y(tk.v) + 4, "text-anchor": "end" }, tk.label ?? tk.v));
    }
    for (let i = 0; i <= 3; i++) {
      const t = t0 + ((t1 - t0) * i) / 3;
      svg.append(el("text", { x: x(t), y: H - 8, "text-anchor": i === 0 ? "start" : i === 3 ? "end" : "middle" }, fmtDate(t)));
    }
    for (const mk of o.markers || []) {
      if (mk < t0 || mk > t1) continue;
      svg.append(el("path", { class: "marker", d: `M${x(mk) - 4} ${m.t + ih + 1} h8 l-4 -6 Z` }));
    }
    for (const ev of o.events || []) {
      if (ev.t < t0 || ev.t > t1) continue;
      svg.append(el("line", { class: "event-line", x1: x(ev.t), x2: x(ev.t), y1: m.t - 4, y2: m.t + ih }));
      const anchor = x(ev.t) > m.l + iw * 0.8 ? "end" : "start";
      svg.append(el("text", { class: "event-label", x: x(ev.t) + (anchor === "end" ? -4 : 4), y: m.t - 8, "text-anchor": anchor }, ev.label));
    }
    if (!rows.length) {
      svg.append(el("text", { class: "empty", x: W / 2, y: H / 2, "text-anchor": "middle" }, "No data in range"));
      return;
    }
    const xs = rows.map((r) => x(r.t));
    for (const s of o.series) {
      let d = "", pen = false;
      rows.forEach((r, i) => {
        const v = r[s.key];
        if (v === null || v === undefined) { pen = false; return; }
        d += (pen ? "L" : "M") + xs[i] + " " + y(v);
        pen = true;
      });
      if (d) svg.append(el("path", { class: `line ${s.cls}`, d }));
      if (o.dots) {
        rows.forEach((r, i) => {
          const v = r[s.key];
          if (v !== null && v !== undefined) svg.append(el("circle", { class: `dot ${s.cls}`, cx: xs[i], cy: y(v), r: o.dots }));
        });
      }
      if (o.endLabel) {
        const last = [...rows].reverse().find((r) => r[s.key] !== null && r[s.key] !== undefined);
        if (last) svg.append(el("text", { class: "label", x: x(last.t) + 8, y: y(last[s.key]) + 4 }, (s.fmt || String)(last[s.key])));
      }
    }
    const cross = el("line", { class: "crosshair", y1: m.t, y2: m.t + ih, visibility: "hidden" });
    svg.append(cross);
    const hit = el("rect", { class: "hit", x: m.l, y: m.t - 10, width: iw, height: ih + 10 });
    hit.addEventListener("pointermove", (evt) => {
      const rect = svg.getBoundingClientRect();
      const px = ((evt.clientX - rect.left) / rect.width) * W;
      let best = 0;
      for (let i = 1; i < xs.length; i++) if (Math.abs(xs[i] - px) < Math.abs(xs[best] - px)) best = i;
      cross.setAttribute("x1", xs[best]); cross.setAttribute("x2", xs[best]); cross.setAttribute("visibility", "visible");
      const r = rows[best];
      const lines = o.series.map((s) => ({ cls: s.cls, name: s.name, value: r[s.key] == null ? "–" : (s.fmt || String)(r[s.key]) }));
      showTip(evt, o.when ? o.when(r) : fmtDate(r.t), lines, o.note && o.note(r));
    });
    hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
    svg.append(hit);
  }

  // ---- rendering ----
  function domain() {
    const enr = data.enrollments[0];
    const end = enr ? tDate(enr.window_end) + DAY / 2 : Date.now();
    const start = enr ? tDate(enr.window_start) - DAY / 2 : end - 90 * DAY;
    return [weeks ? Math.max(start, end - weeks * 7 * DAY) : start, end];
  }

  function renderPatient() {
    const p = data.patient;
    $("#p-name").textContent = p.display_name || p.patient_id;
    $("#p-meta").textContent = [p.pronouns, p.date_of_birth && `age ${age(p.date_of_birth)}`, p.patient_id, p.is_synthetic ? "synthetic" : null]
      .filter(Boolean).join(" · ");
    const dx = $("#p-dx");
    dx.replaceChildren();
    if (!data.diagnoses.length) dx.append(h("span", "chip", "No diagnosis on file"));
    for (const d of data.diagnoses) dx.append(h("span", `chip ${d.rank}`, `${d.icd10} ${d.description}`));
    const facts = $("#p-facts");
    facts.replaceChildren();
    const enr = data.enrollments[0];
    const add = (k, v) => { const div = h("div"); div.append(h("span", "k", k + " "), h("span", null, v)); facts.append(div); };
    if (enr) add("Program", `${enr.program.replace(/_/g, " ")}, ${enr.window_start} → ${enr.window_end}`);
    add("Medications", data.medications.length ? data.medications.map((m) => `${m.name} ${m.dose || ""} ${m.frequency || ""}`.trim()).join("; ") : "none");
    add("Care team", data.care_team.map((c) => `${c.name} (${c.role.replace(/_/g, " ")})`).join("; "));
    const attended = data.encounters.filter((e) => e.attended).length;
    add("Encounters", `${attended} of ${data.encounters.length} attended`);
  }

  function tile(label, value, sub, cls) {
    const t = h("div", "tile");
    t.append(h("div", "label", label));
    t.append(h("div", `value ${cls || ""}`, value));
    if (sub) t.append(h("div", "sub", sub));
    return t;
  }

  function renderTiles() {
    const tiles = $("#tiles");
    tiles.replaceChildren();
    const byInst = (inst) => data.assessments.filter((a) => a.instrument === inst);
    for (const inst of ["PHQ-9", "GAD-7"]) {
      const rows = byInst(inst);
      if (!rows.length) continue;
      const last = rows[rows.length - 1], base = rows.find((a) => a.is_baseline) || rows[0];
      const delta = last.total_score - base.total_score;
      tiles.append(tile(`${inst}, latest`, `${last.total_score}/${last.max_score}`,
        `${bandLabel(last.severity_band)} · ${delta > 0 ? "+" : ""}${delta} vs baseline ${base.total_score}`));
    }
    const sig = data.safety_signals.length;
    tiles.append(tile("Safety signals", String(sig), sig ? `highest priority ${Math.min(...data.safety_signals.map((s) => s.priority))}` : "none in window", sig ? "critical" : "ok"));
    const [, end] = domain();
    const recent = data.mood_checkins.filter((m) => tIso(m.logged_at) >= end - 7 * DAY).length;
    tiles.append(tile("Check-ins, last 7 days", String(recent), recent < 4 ? "low engagement" : null, recent < 4 ? "critical" : ""));
    const sleep = data.sleep_sessions[data.sleep_sessions.length - 1];
    tiles.append(tile("Last night's sleep", sleep ? `${(sleep.total_asleep_min / 60).toFixed(1)} h` : "–",
      sleep ? `${sleep.night_of} · efficiency ${Math.round(sleep.sleep_efficiency * 100)}%` : "no session"));
    const rtm = data.rtm_periods[0];
    if (rtm) tiles.append(tile("RTM monitoring days", String(rtm.monitoring_days), `${rtm.threshold_met ? "meets" : "below"} ${rtm.threshold_days}-day threshold`));
  }

  const PHQ_BANDS = [[0, 4, "minimal"], [5, 9, "mild"], [10, 14, "moderate"], [15, 19, "mod. severe"], [20, 27, "severe"]];
  const GAD_BANDS = [[0, 4, "minimal"], [5, 9, "mild"], [10, 14, "moderate"], [15, 21, "severe"]];

  function renderAssessments() {
    const wrap = $("#assessment-charts");
    wrap.replaceChildren();
    const events = data.clinical_events.map((e) => ({ t: tIso(e.onset_at), label: e.label.replace(/_/g, " ") }));
    const markers = data.encounters.filter((e) => e.attended).map((e) => tIso(e.scheduled_start));
    for (const inst of ["PHQ-9", "GAD-7"]) {
      const rows = data.assessments.filter((a) => a.instrument === inst).map((a) => ({ t: tIso(a.administered_at), v: a.total_score, band: a.severity_band, item9: a.phq9_item9_score }));
      if (!rows.length) continue;
      const max = inst === "PHQ-9" ? 27 : 21;
      const bands = (inst === "PHQ-9" ? PHQ_BANDS : GAD_BANDS).filter((_, i) => i % 2 === 1).map(([from, to, label]) => ({ from, to: to + 1, label }));
      const card = h("section", "card");
      const head = h("div", "chart-head");
      head.append(h("h2", null, `${inst} weekly total`));
      card.append(head);
      const chart = h("div", "chart");
      card.append(chart);
      wrap.append(card);
      lineChart(chart, {
        rows, series: [{ key: "v", name: inst, cls: "s1" }], yMin: 0, yMax: max, dots: 4, endLabel: true,
        yTicks: [0, 5, 10, 15, 20, max].filter((v, i, a) => a.indexOf(v) === i).map((v) => ({ v })),
        bands, events, markers, domain: domain(),
        note: (r) => `${bandLabel(r.band)}${r.item9 > 0 ? " · item 9 positive" : ""}`,
      });
    }
  }

  function renderMood() {
    const rows = data.mood_checkins.map((m) => ({ t: tIso(m.logged_at), mood: m.mood, anxiety: m.anxiety, energy: m.energy, note: m.note }));
    lineChart($("#chart-mood"), {
      rows, series: [{ key: "mood", name: "Mood", cls: "s1" }, { key: "anxiety", name: "Anxiety", cls: "s2" }, { key: "energy", name: "Energy", cls: "s3" }],
      yMin: 1, yMax: 10, yTicks: [1, 4, 7, 10].map((v) => ({ v })), dots: 3,
      events: data.clinical_events.map((e) => ({ t: tIso(e.onset_at), label: e.label.replace(/_/g, " ") })),
      markers: data.encounters.filter((e) => e.attended).map((e) => tIso(e.scheduled_start)),
      domain: domain(), when: (r) => fmtDateTime(r.t), note: (r) => r.note,
    });
  }

  function renderMhss() {
    const rows = data.mhss_daily.map((d) => ({ t: tDate(d.obs_date), anxiety: d.mhss_anxiety, stress: d.mhss_stress, depression: d.mhss_depression, adhd: d.mhss_adhd }));
    lineChart($("#chart-mhss"), {
      rows, series: [{ key: "anxiety", name: "Anxiety", cls: "s1" }, { key: "stress", name: "Stress", cls: "s2" },
                     { key: "depression", name: "Depression", cls: "s3" }, { key: "adhd", name: "ADHD", cls: "s4" }],
      yMin: 0, yMax: 100, yTicks: [0, 25, 50, 75, 100].map((v) => ({ v })), domain: domain(),
      series_fmt: (v) => `${v}%`,
    });
  }

  function renderBody() {
    const wrap = $("#body-charts");
    wrap.replaceChildren();
    const sleepBy = Object.fromEntries(data.sleep_sessions.map((s) => [s.night_of, s]));
    const rows = data.healthkit_daily.map((d) => ({
      t: tDate(d.obs_date), sleep: sleepBy[d.obs_date] ? +(sleepBy[d.obs_date].total_asleep_min / 60).toFixed(1) : null,
      hrv: d.hrv_sdnn_ms, steps: d.step_count, worn: d.watch_worn,
    }));
    const panels = [
      ["Sleep, hours asleep", "sleep", 0, 10, [0, 4, 8], (v) => `${v} h`],
      ["HRV (SDNN), ms", "hrv", 0, 100, [0, 50, 100], (v) => `${Math.round(v)} ms`],
      ["Steps", "steps", 0, 14000, [0, 7000, 14000], (v) => Math.round(v).toLocaleString()],
    ];
    const charts = panels.map(([title]) => {
      const card = h("section", "card");
      card.append(h("h2", null, title));
      const chart = h("div", "chart");
      card.append(chart);
      wrap.append(card);
      return chart;
    });
    panels.forEach(([title, key, yMin, yMax, ticks, fmt], i) => {
      lineChart(charts[i], {
        rows, series: [{ key, name: title.split(",")[0], cls: "s1", fmt }], yMin, yMax,
        yTicks: ticks.map((v) => ({ v, label: key === "steps" ? `${v / 1000}k` : v })), domain: domain(), endLabel: true,
        note: (r) => (r.worn ? null : "watch not worn"),
      });
    });
  }

  function renderFeeds() {
    const safety = $("#safety-feed");
    safety.replaceChildren();
    if (!data.safety_signals.length) { const li = h("li"); li.append(h("span", "empty", "No safety signals in this window.")); safety.append(li); }
    for (const s of data.safety_signals) {
      const li = h("li");
      li.append(h("span", "when", s.signal_at.slice(0, 10)));
      const body = h("span");
      body.append(h("span", `tag p${s.priority}`, `P${s.priority}`), h("span", null, `${s.signal.replace(/_/g, " ")}: ${s.detail}`));
      li.append(body);
      safety.append(li);
    }
    const narr = $("#narrative-feed");
    narr.replaceChildren();
    const [t0, t1] = domain();
    const recent = data.narratives.filter((n) => { const t = tIso(n.created_at); return t >= t0 && t <= t1; }).slice(-6).reverse();
    if (!recent.length) { const li = h("li"); li.append(h("span", "empty", "No entries in range.")); narr.append(li); }
    for (const n of recent) {
      const li = h("li");
      li.append(h("span", "when", n.created_at.slice(0, 10)));
      const body = h("span");
      body.append(h("span", "tag", n.medium === "voice_note" ? "voice" : "journal"), h("span", "body", n.ai_summary || n.body_text),
        h("span", "sent", n.sentiment_score == null ? "" : `${n.sentiment_score > 0 ? "+" : ""}${n.sentiment_score.toFixed(2)}`));
      li.append(body);
      narr.append(li);
    }
  }

  function renderPractices() {
    const wrap = $("#practices");
    wrap.replaceChildren();
    const practices = data.practices.filter((p) => p.track === "make_it_happen");
    if (!practices.length) { wrap.append(h("p", "muted", "No practices defined.")); return; }
    const grid = h("div", "practice-grid");
    grid.append(h("span", "name", ""));
    for (let w = 1; w <= 11; w++) grid.append(h("span", "wk", `wk ${w}`));
    for (const p of practices) {
      grid.append(h("span", "name", `${p.name} (${p.target_per_week}/wk)`));
      for (let w = 1; w <= 11; w++) {
        const c = data.practice_weekly_cycles.find((x) => x.practice_id === p.practice_id && x.week === w);
        const cell = h("span", `cell ${c && c.met_target ? "met" : ""}`, c ? String(c.completed) : "");
        cell.title = c ? `week ${w}: ${c.completed}/${c.target}` : "";
        grid.append(cell);
      }
    }
    wrap.append(grid);
  }

  function render() {
    if (!data) return;
    renderPatient(); renderTiles(); renderAssessments(); renderMood(); renderMhss(); renderBody(); renderFeeds(); renderPractices();
  }

  async function loadPatient(pid) {
    const res = await fetch(`/api/patients/${pid}/dashboard`);
    data = await res.json();
    try { localStorage.setItem("patient", pid); } catch (_) { /* ignore */ }
    render();
  }

  async function init() {
    fetch("/api/health").then((r) => r.json()).then((hh) => { $("#backend").textContent = hh.backend; });
    patients = (await (await fetch("/api/patients")).json()).patients;
    const sel = $("#patient-select");
    sel.replaceChildren();
    for (const p of patients) {
      const opt = h("option", null, `${p.display_name} · ${p.diagnoses.length ? p.diagnoses.map((d) => d.icd10).join(", ") : "no diagnosis"}${p.safety_signals ? " · ⚠" : ""}`);
      opt.value = p.patient_id;
      sel.append(opt);
    }
    let saved = null;
    try { saved = localStorage.getItem("patient"); } catch (_) { /* ignore */ }
    const initial = patients.find((p) => p.patient_id === saved) ? saved : patients[0]?.patient_id;
    if (!initial) { $("#p-name").textContent = "No patients loaded"; return; }
    sel.value = initial;
    sel.addEventListener("change", () => loadPatient(sel.value));
    await loadPatient(initial);
  }

  for (const b of document.querySelectorAll(".filters [data-weeks]")) {
    b.addEventListener("click", () => {
      document.querySelectorAll(".filters [data-weeks]").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      weeks = Number(b.dataset.weeks);
      render();
    });
  }
  window.addEventListener("resize", render);
  init();
})();
