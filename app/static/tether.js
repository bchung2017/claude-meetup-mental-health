(() => {
  const KEY = "tether.history";
  const $ = (s) => document.querySelector(s);
  const log = $("#tether-log");
  const form = $("#tether-form");
  const input = form.text;
  const status = $("#tether-status");
  let history = [];
  let busy = false;

  try { history = JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch { history = []; }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(history)); } catch {} };

  const textOf = (m) => typeof m.content === "string"
    ? m.content
    : m.content.filter((b) => b.type === "text").map((b) => b.text).join("");

  function bubble(role, text) {
    const d = document.createElement("div");
    d.className = `msg ${role}`;
    d.textContent = text;
    log.append(d);
    log.scrollTop = log.scrollHeight;
    return d;
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
    for (const m of history) if (m.role !== "system") bubble(m.role, textOf(m));
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
        body: JSON.stringify({ messages: history }),
      });
      if (!res.ok) throw new Error((await res.json()).error || `HTTP ${res.status}`);
      for await (const { event, data } of sse(res)) {
        if (event === "context") {
          history.push(data);
        } else if (event === "text") {
          out.classList.remove("pending");
          out.textContent += data;
          log.scrollTop = log.scrollHeight;
        } else if (event === "done") {
          if (data.stop_reason === "refusal" || !data.content.some((b) => b.type === "text")) {
            out.remove();
            history.splice(history.indexOf(userMsg));
            notice("Tether couldn't respond to that one. Try rephrasing.");
          } else {
            history.push({ role: "assistant", content: data.content });
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
    history = [];
    save();
    render();
  });

  fetch("/api/tether/health").then((r) => r.json()).then((h) => {
    status.textContent = h.configured ? [h.patient, h.model].filter(Boolean).join(" · ") : "ANTHROPIC_API_KEY not set";
    if (!h.configured) setBusy(true);
  });
  render();
})();
