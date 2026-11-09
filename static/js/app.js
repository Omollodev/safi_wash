// Small, dependency-free helpers. Everything works without JS too (forms are normal POSTs);
// this file only adds live updates.

// 1. Notification bell + pop-up toasts live in toast.js (they share one poll).

// 2. Live job board on the dashboard: any element with data-board-url refreshes itself.
(function liveBoard() {
  const root = document.querySelector("[data-board-url]");
  if (!root) return;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const detailUrl = root.dataset.detailUrl; // contains the placeholder 0
  const render = (jobs) =>
    jobs.length
      ? jobs.map((j) => `
        <a class="card job-card priority-${esc(j.priority)} mb-2 text-decoration-none text-reset" href="${detailUrl.replace("/0/", "/" + j.id + "/")}">
          <div class="card-body py-2">
            <div class="d-flex justify-content-between"><strong>#${esc(j.queue)} ${esc(j.plate)}</strong>
              ${j.need_alert ? '<i class="bi bi-exclamation-triangle-fill text-warning" title="Extra services pending"></i>' : ""}</div>
            <div class="small text-secondary">${esc(j.customer)} &middot; ${j.worker ? esc(j.worker) : "<em>unassigned</em>"}</div>
          </div></a>`).join("")
      : '<p class="text-secondary small mb-0">Nothing here.</p>';
  const refresh = () =>
    fetch(root.dataset.boardUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((r) => r.json())
      .then(({ board }) => {
        for (const status of Object.keys(board)) {
          const col = root.querySelector(`[data-col="${status}"]`);
          if (col) col.innerHTML = render(board[status]);
        }
      })
      .catch(() => {});
  refresh();
  setInterval(refresh, 10000);
})();

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
