(() => {
  const tabs = [...document.querySelectorAll('.tabs [role="tab"]')];
  function show(name) {
    for (const t of tabs) {
      const on = t.dataset.tab === name;
      t.setAttribute("aria-selected", on);
      document.getElementById(`tab-${t.dataset.tab}`).hidden = !on;
    }
    window.dispatchEvent(new Event("resize")); // tracker re-renders its chart at the now-visible width
  }
  for (const t of tabs) {
    t.addEventListener("click", () => { location.hash = t.dataset.tab; show(t.dataset.tab); });
  }
  const initial = location.hash.slice(1);
  show(tabs.some((t) => t.dataset.tab === initial) ? initial : tabs[0].dataset.tab);
})();
