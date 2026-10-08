// Minimal Markdown -> DOM renderer for chat replies. Builds nodes directly (never innerHTML),
// so model output cannot inject markup. Covers: headings, paragraphs, bullet and numbered
// lists, pipe tables, horizontal rules, fenced code, and inline bold / italic / code.
window.renderMarkdown = (() => {
  const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|(?<![\w*])\*(?!\s)[^*]+?\*(?![\w*])|(?<![\w_])_(?!\s)[^_]+?_(?![\w_]))/g;

  function inline(parent, text) {
    let last = 0;
    for (const m of text.matchAll(INLINE)) {
      if (m.index > last) parent.append(text.slice(last, m.index));
      const s = m[0];
      let node;
      if (s.startsWith("**")) { node = document.createElement("strong"); node.textContent = s.slice(2, -2); }
      else if (s.startsWith("`")) { node = document.createElement("code"); node.textContent = s.slice(1, -1); }
      else { node = document.createElement("em"); node.textContent = s.slice(1, -1); }
      parent.append(node);
      last = m.index + s.length;
    }
    if (last < text.length) parent.append(text.slice(last));
  }

  function lines(parent, arr) {
    arr.forEach((l, i) => { if (i) parent.append(document.createElement("br")); inline(parent, l); });
  }

  const isRow = (l) => /^\s*\|.*\|\s*$/.test(l);
  const isSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
  const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

  return function render(md, root) {
    root.replaceChildren();
    const src = md.replace(/\r\n?/g, "\n").split("\n");
    let i = 0;
    while (i < src.length) {
      const line = src[i];
      if (!line.trim()) { i++; continue; }

      if (line.startsWith("```")) {
        const buf = [];
        i++;
        while (i < src.length && !src[i].startsWith("```")) buf.push(src[i++]);
        i++;
        const pre = document.createElement("pre");
        const code = document.createElement("code");
        code.textContent = buf.join("\n");
        pre.append(code);
        root.append(pre);
        continue;
      }

      const h = /^(#{1,4})\s+(.*)$/.exec(line);
      if (h) { const el = document.createElement(`h${h[1].length + 2 > 6 ? 6 : h[1].length + 2}`); inline(el, h[2].trim()); root.append(el); i++; continue; }

      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { root.append(document.createElement("hr")); i++; continue; }

      if (isRow(line) && i + 1 < src.length && isSep(src[i + 1])) {
        const table = document.createElement("table");
        const thead = document.createElement("thead"), tr = document.createElement("tr");
        for (const c of cells(line)) { const th = document.createElement("th"); inline(th, c); tr.append(th); }
        thead.append(tr); table.append(thead);
        const tbody = document.createElement("tbody");
        i += 2;
        while (i < src.length && isRow(src[i])) {
          const r = document.createElement("tr");
          for (const c of cells(src[i])) { const td = document.createElement("td"); inline(td, c); r.append(td); }
          tbody.append(r); i++;
        }
        table.append(tbody); root.append(table);
        continue;
      }

      const li = /^\s*(?:([-*+])|(\d+)[.)])\s+(.*)$/.exec(line);
      if (li) {
        const ordered = !!li[2];
        const list = document.createElement(ordered ? "ol" : "ul");
        if (ordered) list.start = Number(li[2]);
        while (i < src.length) {
          const m = /^\s*(?:([-*+])|(\d+)[.)])\s+(.*)$/.exec(src[i]);
          if (!m || !!m[2] !== ordered) break;
          const item = document.createElement("li");
          const cont = [m[3]];
          i++;
          while (i < src.length && /^\s{2,}\S/.test(src[i]) && !/^\s*(?:[-*+]|\d+[.)])\s/.test(src[i])) cont.push(src[i++].trim());
          lines(item, cont);
          list.append(item);
        }
        root.append(list);
        continue;
      }

      const para = [];
      while (i < src.length && src[i].trim() && !/^(#{1,4}\s|```|\s*(?:[-*+]|\d+[.)])\s)/.test(src[i]) && !(isRow(src[i]) && isSep(src[i + 1] || ""))) para.push(src[i++]);
      const p = document.createElement("p");
      lines(p, para);
      root.append(p);
    }
  };
})();
