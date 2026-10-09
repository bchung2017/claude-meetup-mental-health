(() => {
  const KEY = "tether.history";
  const patientSelect = document.querySelector("#patient-select");
  const patientId = () => (patientSelect && patientSelect.value) || "";
  const storageKey = () => (patientId() ? `${KEY}:${patientId()}` : KEY);
  const $ = (s) => document.querySelector(s);
  const log = $("#tether-log");
  const form = $("#tether-form");
  const input = form.text;
  const status = $("#tether-status");
  let history = [];
  let busy = false;
  let tts = false;
  let player = null;

  const load = () => { try { history = JSON.parse(sessionStorage.getItem(storageKey()) || "[]"); } catch { history = []; } };
  const save = () => { try { sessionStorage.setItem(storageKey(), JSON.stringify(history)); } catch {} };
  load();

  const textOf = (m) => typeof m.content === "string"
    ? m.content
    : m.content.filter((b) => b.type === "text").map((b) => b.text).join("");

  function bubble(role, text) {
    const d = document.createElement("div");
    d.className = `msg ${role}`;
    setText(d, text);
    log.append(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }
  function setText(el, text) {
    el.dataset.raw = text;
    if (el.classList.contains("assistant")) window.renderMarkdown(text, el);
    else el.textContent = text;
  }
  const plain = (md) => md.replace(/```[\s\S]*?```/g, " ").replace(/[#*_`>|]+/g, " ").replace(/\s+/g, " ").trim();
  function stopSpeaking() {
    if (!player) return;
    player.audio.pause();
    if (player.url) URL.revokeObjectURL(player.url);
    player.btn.textContent = "Speak";
    player = null;
  }
  async function speak(bubbleEl, btn) {
    if (player && player.btn === btn) {
      if (player.audio.paused && player.url) { // blocked autoplay: this click is the gesture
        player.audio.play().then(() => { btn.textContent = "Stop"; }).catch((e) => notice(`Playback blocked: ${e.message}`));
        return;
      }
      stopSpeaking();
      return;
    }
    stopSpeaking();
    const audio = new Audio(); // created inside the click so the gesture carries to play()
    player = { audio, btn, url: null };
    btn.textContent = "Loading…";
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 90000);
    try {
      const res = await fetch("/api/tether/speak", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: plain(bubbleEl.dataset.raw || bubbleEl.textContent) }),
        signal: ctl.signal,
      });
      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { msg = (await res.json()).error || msg; } catch {}
        throw new Error(msg);
      }
      const blob = await res.blob();
      if (player?.audio !== audio) return; // stopped or replaced while loading
      player.url = URL.createObjectURL(blob);
      audio.src = player.url;
      audio.addEventListener("ended", stopSpeaking);
      try {
        await audio.play();
        btn.textContent = "Stop";
      } catch (e) {
        btn.textContent = "Play"; // autoplay blocked (Safari/iOS): next click plays within a gesture
        notice(`Audio ready; tap Play (${e.name}).`);
      }
    } catch (err) {
      if (player?.audio === audio) stopSpeaking();
      btn.textContent = "Speak";
      notice(err.name === "AbortError" ? "Speech timed out after 90s." : `Speech error: ${err.message}`);
    } finally {
      clearTimeout(timer);
    }
  }
  function addSpeakButton(bubbleEl) {
    if (!tts) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "speak";
    btn.textContent = "Speak";
    btn.addEventListener("click", () => speak(bubbleEl, btn));
    const wrap = document.createElement("div");
    wrap.className = "msg-tools";
    wrap.append(btn);
    bubbleEl.after(wrap);
  }
  function notice(text) {
    const d = document.createElement("div");
    d.className = "msg notice";
    d.textContent = text;
    log.append(d);
    log.scrollTop = log.scrollHeight;
  }
  function render() {
    log.replaceChildren();
    for (const m of history) {
      if (m.role === "system") continue;
      const b = bubble(m.role, textOf(m));
      if (m.role === "assistant") addSpeakButton(b);
    }
  }
  function setBusy(b) {
    busy = b;
    input.disabled = b;
    form.querySelector("button").disabled = b;
  }

  async function* sse(res) {
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, i);
        buf = buf.slice(i + 2);
        let event = "message", data = "";
        for (const line of chunk.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (data) yield { event, data: JSON.parse(data) };
      }
    }
  }

  async function send(text) {
    const userMsg = { role: "user", content: text };
    history.push(userMsg);
    save();
    bubble("user", text);
    setBusy(true);
    const out = bubble("assistant", "");
    out.classList.add("pending");
    try {
      const res = await fetch("/api/tether/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history, patient_id: patientId() || undefined }),
      });
      if (!res.ok) throw new Error((await res.json()).error || `HTTP ${res.status}`);
      for await (const { event, data } of sse(res)) {
        if (event === "context") {
          history.push(data);
        } else if (event === "text") {
          out.classList.remove("pending");
          setText(out, (out.dataset.raw || "") + data);
          log.scrollTop = log.scrollHeight;
        } else if (event === "done") {
          if (data.stop_reason === "refusal" || !data.content.some((b) => b.type === "text")) {
            out.remove();
            history.splice(history.indexOf(userMsg));
            notice("Tether couldn't respond to that one. Try rephrasing.");
          } else {
            history.push({ role: "assistant", content: data.content });
            addSpeakButton(out);
          }
          if (data.stop_reason === "max_tokens") notice("Reply was cut off at the length limit.");
        } else if (event === "error") {
          throw new Error(data.error);
        }
      }
    } catch (err) {
      out.remove();
      history.splice(history.indexOf(userMsg));
      notice(`Error: ${err.message}`);
      input.value = text;
    } finally {
      out.classList.remove("pending");
      save();
      setBusy(false);
      input.focus();
    }
  }

  form.addEventListener("submit", (evt) => {
    evt.preventDefault();
    const text = input.value.trim();
    if (!text || busy) return;
    input.value = "";
    send(text);
  });
  input.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter" && !evt.shiftKey) { evt.preventDefault(); form.requestSubmit(); }
  });
  $("#tether-new").addEventListener("click", () => {
    if (busy) return;
    stopSpeaking();
    history = [];
    save();
    render();
  });

  function refreshStatus() {
    const q = patientId() ? `?patient_id=${encodeURIComponent(patientId())}` : "";
    fetch(`/api/tether/health${q}`).then((r) => r.json()).then((h) => {
      status.textContent = h.configured ? [h.patient, h.model].filter(Boolean).join(" · ") : "ANTHROPIC_API_KEY not set";
      if (!h.configured) setBusy(true);
      tts = !!h.tts;
      render();
    });
  }
  document.addEventListener("patientchange", () => {
    if (busy) return;
    stopSpeaking();
    load();
    refreshStatus();
  });
  refreshStatus();
})();
