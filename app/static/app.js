(() => {
  const NS = "http://www.w3.org/2000/svg";
  const SERIES = [
    { key: "depression", name: "Depression" },
    { key: "adhd", name: "ADHD" },
  ];
  const $ = (s) => document.querySelector(s);
  const tooltip = $("#tooltip");
  let days = 30;
  let rows = [];

  function el(tag, attrs = {}, text) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    return n;
  }
  const fmtDate = (ts) => new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const fmtWhen = (ts) => new Date(ts * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

  function showTip(evt, when, lines, meds) {
    tooltip.replaceChildren();
    const w = document.createElement("div");
    w.className = "when";
    w.textContent = when;
    tooltip.append(w);
    for (const s of lines) {
      const r = document.createElement("div");
      r.className = "r";
      const key = document.createElement("i");
      key.className = `key ${s.key}`;
      const v = document.createElement("strong");
      v.textContent = s.value;
      const k = document.createElement("span");
      k.className = "k";
      k.textContent = s.name;
      r.append(key, v, k);
      tooltip.append(r);
    }
    if (meds !== undefined) {
      const mr = document.createElement("div");
      mr.className = "r";
      const mk = document.createElement("i");
      mk.className = `key med ${meds ? "on" : "off"}`;
      const mv = document.createElement("strong");
      mv.textContent = meds ? "\u2713" : "\u2715";
      const ml = document.createElement("span");
      ml.className = "k";
      ml.textContent = meds ? "Meds taken" : "Meds missed";
      mr.append(mk, mv, ml);
      tooltip.append(mr);
    }
    tooltip.hidden = false;
    const x = Math.min(evt.clientX + 12, window.innerWidth - tooltip.offsetWidth - 8);
    tooltip.style.left = x + "px";
    tooltip.style.top = Math.max(8, evt.clientY - tooltip.offsetHeight - 12) + "px";
  }
  const hideTip = () => { tooltip.hidden = true; };

  function lineChart(container, data) {
    const W = container.clientWidth || 600, H = container.clientHeight || 280;
    const m = { t: 12, r: 40, b: 48, l: 36 };
    const strip = { gap: 8, size: 10 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    container.replaceChildren(svg);
    if (!data.length) {
      svg.append(el("text", { class: "empty", x: W / 2, y: H / 2, "text-anchor": "middle" }, "No entries in range"));
      return;
    }
    const y = (v) => m.t + ih - (v / 100) * ih;
    for (const t of [0, 25, 50, 75, 100]) {
      svg.append(el("line", { class: t ? "grid" : "axis", x1: m.l, x2: m.l + iw, y1: y(t), y2: y(t) }));
      svg.append(el("text", { x: m.l - 8, y: y(t) + 4, "text-anchor": "end" }, t));
    }
    const t0 = data[0].created_at, t1 = data[data.length - 1].created_at;
    const x = (t) => m.l + (t1 === t0 ? iw / 2 : ((t - t0) / (t1 - t0)) * iw);
    const xs = data.map((d) => x(d.created_at));
    for (const t of t1 === t0 ? [t0] : [t0, (t0 + t1) / 2, t1]) {
      svg.append(el("text", { x: x(t), y: H - 8, "text-anchor": "middle" }, fmtDate(t)));
    }

    // Medication strip: one square per entry under the plot. Filled = taken, hollow = missed.
    const stripY = m.t + ih + strip.gap;
    const minGap = xs.length > 1 ? Math.min(...xs.slice(1).map((v, i) => v - xs[i])) : Infinity;
    const sz = Math.max(4, Math.min(strip.size, minGap - 2));
    svg.append(el("text", { class: "strip-label", x: m.l - 8, y: stripY + sz / 2 + 4, "text-anchor": "end" }, "Meds"));
    data.forEach((d, i) => {
      svg.append(el("rect", {
        class: `med ${d.meds_taken ? "on" : "off"}`,
        x: xs[i] - sz / 2, y: stripY, width: sz, height: sz, rx: 2,
      }));
    });

    // Direct end-labels: nudge apart only if they would collide.
    const last = data[data.length - 1];
    const ends = SERIES.map((s) => ({ s, y: y(last[s.key]) })).sort((a, b) => a.y - b.y);
    if (ends.length === 2 && ends[1].y - ends[0].y < 14) {
      const mid = (ends[0].y + ends[1].y) / 2;
      ends[0].y = mid - 7;
      ends[1].y = mid + 7;
    }

    for (const s of SERIES) {
      const pts = data.map((d, i) => [xs[i], y(d[s.key])]);
      if (pts.length > 1) {
        svg.append(el("path", { class: `line ${s.key}`, d: pts.map((p, i) => (i ? "L" : "M") + p[0] + " " + p[1]).join(" ") }));
      }
      for (const p of pts) svg.append(el("circle", { class: `dot ${s.key}`, cx: p[0], cy: p[1], r: 4 }));
      const e = ends.find((q) => q.s === s);
      svg.append(el("text", { class: "label", x: xs[xs.length - 1] + 8, y: e.y + 4 }, last[s.key]));
    }

    const cross = el("line", { class: "crosshair", y1: m.t, y2: stripY + sz, visibility: "hidden" });
    svg.append(cross);
    const hit = el("rect", { class: "hit", x: m.l, y: m.t, width: iw, height: stripY + sz - m.t });
    hit.addEventListener("pointermove", (evt) => {
      const r = svg.getBoundingClientRect();
      const px = ((evt.clientX - r.left) / r.width) * W;
      let best = 0;
      for (let i = 1; i < xs.length; i++) if (Math.abs(xs[i] - px) < Math.abs(xs[best] - px)) best = i;
      cross.setAttribute("x1", xs[best]);
      cross.setAttribute("x2", xs[best]);
      cross.setAttribute("visibility", "visible");
      showTip(evt, fmtWhen(data[best].created_at), SERIES.map((s) => ({ ...s, value: data[best][s.key] })), data[best].meds_taken);
    });
    hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
    svg.append(hit);
  }

  // Synthetic mood check-ins (daily, with gaps) and PHQ-9 totals (weekly), 12 weeks ending today.
  // Same shape as data/sample/self_report.json; deterministic so the chart is stable across reloads.
  function fakeMoodData() {
    let seed = 0x9e3779b9;
    const rand = () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const gauss = (sd) => sd * Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(2 * Math.PI * rand());
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, Math.round(v)));
    // Latent wellbeing 0..1: improve, stressor dip, recover.
    const knots = [[0, 0.05], [37, 0.62], [40, 0.48], [52, 0.10], [60, 0.30], [83, 0.92]];
    const h = (day) => {
      for (let i = 1; i < knots.length; i++) {
        const [x0, y0] = knots[i - 1], [x1, y1] = knots[i];
        if (day <= x1) return y0 + ((y1 - y0) * (day - x0)) / (x1 - x0);
      }
      return knots[knots.length - 1][1];
    };
    const DAYS = 84;
    const midnight = new Date(); midnight.setHours(0, 0, 0, 0);
    const dayTs = (i) => Math.floor(midnight.getTime() / 1000) - (DAYS - 1 - i) * 86400;
    const moods = [], phq9 = [];
    for (let i = 0; i < DAYS; i++) {
      const hv = h(i);
      if (i % 7 === 0) phq9.push({ at: dayTs(i) + 20 * 3600, total: clamp(20 - 14 * hv + gauss(1.2), 0, 27) });
      if (rand() > (i >= 38 && i < 56 ? 0.62 : 0.85)) continue;
      moods.push({ at: dayTs(i) + 21 * 3600, mood: clamp(2.6 + 5.0 * hv + gauss(0.8), 1, 10) });
    }
    return { moods, phq9 };
  }
  const FAKE = fakeMoodData();

  function moodChart(container, moods, phq9) {
    const W = container.clientWidth || 600, H = container.clientHeight || 360;
    const m = { t: 20, r: 40, b: 28, l: 36 }, gap = 36;
    const iw = W - m.l - m.r, ph = (H - m.t - m.b - gap) / 2;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    container.replaceChildren(svg);
    if (!moods.length && !phq9.length) {
      svg.append(el("text", { class: "empty", x: W / 2, y: H / 2, "text-anchor": "middle" }, "No entries in range"));
      return;
    }
    const all = [...moods.map((d) => d.at), ...phq9.map((d) => d.at)];
    const t0 = Math.min(...all), t1 = Math.max(...all);
    const x = (t) => m.l + (t1 === t0 ? iw / 2 : ((t - t0) / (t1 - t0)) * iw);

    // Two panels, one x-axis: mood (1-10) on top, PHQ-9 (0-27) below. Different scales, so no shared y.
    const panels = [
      { key: "mood", title: "Mood (1–10)", top: m.t, lo: 1, hi: 10, ticks: [1, 5, 10], data: moods, v: (d) => d.mood },
      { key: "phq9", title: "PHQ-9 (0–27)", top: m.t + ph + gap, lo: 0, hi: 27, ticks: [0, 9, 18, 27], data: phq9, v: (d) => d.total },
    ];
    for (const p of panels) {
      p.y = (v) => p.top + ph - ((v - p.lo) / (p.hi - p.lo)) * ph;
      svg.append(el("text", { class: "panel", x: m.l, y: p.top - 8 }, p.title));
      for (const t of p.ticks) {
        svg.append(el("line", { class: t === p.lo ? "axis" : "grid", x1: m.l, x2: m.l + iw, y1: p.y(t), y2: p.y(t) }));
        svg.append(el("text", { x: m.l - 8, y: p.y(t) + 4, "text-anchor": "end" }, t));
      }
      const pts = p.data.map((d) => [x(d.at), p.y(p.v(d))]);
      if (pts.length > 1) {
        svg.append(el("path", { class: `line ${p.key}`, d: pts.map((q, i) => (i ? "L" : "M") + q[0] + " " + q[1]).join(" ") }));
      }
      for (const q of pts) svg.append(el("circle", { class: `dot ${p.key}`, cx: q[0], cy: q[1], r: p.key === "phq9" ? 5 : 3 }));
      if (pts.length) {
        const last = pts[pts.length - 1];
        svg.append(el("text", { class: "label", x: last[0] + 8, y: last[1] + 4 }, p.v(p.data[p.data.length - 1])));
      }
    }
    for (const t of t1 === t0 ? [t0] : [t0, (t0 + t1) / 2, t1]) {
      svg.append(el("text", { x: x(t), y: H - 8, "text-anchor": "middle" }, fmtDate(t)));
    }

    const cross = el("line", { class: "crosshair", y1: m.t, y2: H - m.b, visibility: "hidden" });
    svg.append(cross);
    const hit = el("rect", { class: "hit", x: m.l, y: m.t, width: iw, height: H - m.t - m.b });
    hit.addEventListener("pointermove", (evt) => {
      const r = svg.getBoundingClientRect();
      const px = ((evt.clientX - r.left) / r.width) * W;
      // Snap to the nearest point across both panels; show its own value plus the other series at/before that time.
      const cands = [...moods.map((d) => ({ at: d.at, x: x(d.at) })), ...phq9.map((d) => ({ at: d.at, x: x(d.at) }))];
      let best = cands[0];
      for (const c of cands) if (Math.abs(c.x - px) < Math.abs(best.x - px)) best = c;
      cross.setAttribute("x1", best.x);
      cross.setAttribute("x2", best.x);
      cross.setAttribute("visibility", "visible");
      const lines = [];
      const md = moods.filter((d) => Math.abs(d.at - best.at) < 86400).pop();
      if (md) lines.push({ key: "mood", name: "Mood", value: md.mood });
      const pq = phq9.filter((d) => d.at <= best.at + 3600).pop();
      if (pq) lines.push({ key: "phq9", name: `PHQ-9 (${fmtDate(pq.at)})`, value: pq.total });
      showTip(evt, fmtDate(best.at), lines);
    });
    hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
    svg.append(hit);
  }

  function tiles(data) {
    $("#t-count").textContent = data.length;
    const last = data[data.length - 1], prev = data[data.length - 2];
    for (const s of SERIES) {
      $(`#t-${s.key}`).textContent = last ? last[s.key] : "–";
      const d = $(`#d-${s.key}`);
      d.className = "delta";
      d.textContent = "";
      if (!last || !prev) continue;
      const delta = last[s.key] - prev[s.key];
      d.textContent = `${delta > 0 ? "+" : ""}${delta} vs previous entry`;
      if (delta) d.classList.add(delta > 0 ? "up" : "down");
    }
  }

  function table(data) {
    const body = $("#table tbody");
    body.replaceChildren();
    for (const d of [...data].reverse()) {
      const tr = document.createElement("tr");
      [fmtWhen(d.created_at), d.depression, d.adhd, d.meds_taken ? "\u2713 Taken" : "\u2715 Missed", d.note].forEach((c, i) => {
        const td = document.createElement("td");
        if (i === 1 || i === 2) td.className = "num";
        if (i === 3) td.className = d.meds_taken ? "med on" : "med off";
        td.textContent = c;
        tr.append(td);
      });
      const td = document.createElement("td");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Delete";
      btn.addEventListener("click", async () => {
        await fetch(`/api/entries/${d.id}`, { method: "DELETE" });
        load();
      });
      td.append(btn);
      tr.append(td);
      body.append(tr);
    }
  }

  function render() {
    tiles(rows);
    lineChart($("#chart-line"), rows);
    const since = days ? Math.floor(Date.now() / 1000) - days * 86400 : 0;
    moodChart($("#chart-mood"), FAKE.moods.filter((d) => d.at >= since), FAKE.phq9.filter((d) => d.at >= since));
    table(rows);
  }

  async function load() {
    const res = await fetch(`/api/entries?days=${days}`);
    rows = (await res.json()).entries;
    render();
  }

  const form = $("#entry");
  form.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    const body = {
      depression: Number(form.depression.value), adhd: Number(form.adhd.value),
      meds_taken: form.meds_taken.checked, note: form.note.value,
    };
    const res = await fetch("/api/entries", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const msg = $("#form-msg");
    if (res.ok) { form.note.value = ""; form.meds_taken.checked = false; msg.textContent = "Saved."; load(); }
    else msg.textContent = (await res.json()).error || "Error";
    setTimeout(() => { msg.textContent = ""; }, 2000);
  });
  for (const r of form.querySelectorAll('input[type="range"]')) {
    r.addEventListener("input", () => { r.nextElementSibling.value = r.value; });
  }

  for (const b of document.querySelectorAll(".filters [data-days]")) {
    b.addEventListener("click", () => {
      document.querySelectorAll(".filters [data-days]").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      days = Number(b.dataset.days);
      load();
    });
  }
  $("#toggle-table").addEventListener("click", () => {
    const card = $("#table-card");
    card.hidden = !card.hidden;
    $("#toggle-table").textContent = card.hidden ? "Table view" : "Hide table";
  });
  window.addEventListener("resize", render);

  fetch("/api/health").then((r) => r.json()).then((h) => { $("#backend").textContent = h.backend; });
  load();
})();
