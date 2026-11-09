// Landing page behaviour. The page is fully readable without this file:
// tabs fall back to stacked panels, gallery photos are plain scrollable images.

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// ---------------------------------------------------------------- tabs (WAI-ARIA tabs pattern)
document.querySelectorAll("[data-tabs]").forEach((root) => {
  const tabs = Array.from(root.querySelectorAll('[role="tab"]'));
  const panels = tabs.map((t) => document.getElementById(t.getAttribute("aria-controls")));

  const select = (index, moveFocus) => {
    tabs.forEach((tab, i) => {
      const active = i === index;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      panels[i].hidden = !active;
    });
    if (moveFocus) tabs[index].focus();
  };

  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => select(i, false));
    tab.addEventListener("keydown", (event) => {
      const last = tabs.length - 1;
      const target = { ArrowRight: i === last ? 0 : i + 1, ArrowLeft: i === 0 ? last : i - 1, Home: 0, End: last }[event.key];
      if (target !== undefined) { event.preventDefault(); select(target, true); }
    });
  });
  select(0, false);
});

// ---------------------------------------------------------------- gallery arrows
const strip = document.querySelector("[data-gallery]");
if (strip) {
  const step = () => Math.max(strip.clientWidth * 0.8, 240);
  const scroll = (direction) =>
    strip.scrollBy({ left: direction * step(), behavior: reducedMotion.matches ? "auto" : "smooth" });
  document.querySelector("[data-gallery-prev]")?.addEventListener("click", () => scroll(-1));
  document.querySelector("[data-gallery-next]")?.addEventListener("click", () => scroll(1));
}

// ---------------------------------------------------------------- lightbox (<dialog>)
const dialog = document.getElementById("lightbox");
if (dialog) {
  const image = document.getElementById("lb-img");
  const caption = document.getElementById("lb-title");

  document.querySelectorAll(".lp-photo").forEach((button) => {
    button.addEventListener("click", () => {
      image.src = button.dataset.full;
      image.alt = button.dataset.alt;
      caption.textContent = button.dataset.title;
      dialog.showModal(); // modal: focus trapped, Esc closes, returns focus to the button
    });
  });

  // Browsers without <dialog closedby> (Safari): close when the backdrop is clicked.
  if (!("closedBy" in HTMLDialogElement.prototype)) {
    dialog.addEventListener("click", (event) => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      const inside =
        rect.top <= event.clientY && event.clientY <= rect.top + rect.height &&
        rect.left <= event.clientX && event.clientX <= rect.left + rect.width;
      if (!inside) dialog.close();
    });
  }
}
