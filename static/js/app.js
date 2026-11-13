// Small, dependency-free helpers. Everything works without JS too (forms are normal POSTs);
// this file only adds live updates.

// 1. Notification bell + pop-up toasts live in toast.js (they share one poll).

// 2. The live job board on the dashboard lives in dashboard.js (it only loads on that page).

// 3. Type-to-filter for long <select> lists (e.g. choosing a vehicle).
document.querySelectorAll("[data-filter-select]").forEach((input) => {
  const select = document.querySelector(input.dataset.filterSelect);
  if (!select) return;
  input.addEventListener("input", () => {
    const term = input.value.toLowerCase();
    Array.from(select.options).forEach((o) => { o.hidden = term && !o.text.toLowerCase().includes(term); });
  });
});

// 4. Poll an M-Pesa request until it is paid or failed, then reload.
(function pollMpesa() {
  const box = document.querySelector("[data-mpesa-status-url]");
  if (!box) return;
  const timer = setInterval(() => {
    fetch(box.dataset.mpesaStatusUrl)
      .then((r) => r.json())
      .then((d) => { if (d.status !== "pending") { clearInterval(timer); location.href = location.pathname; } })
      .catch(() => {});
  }, 4000);
})();
