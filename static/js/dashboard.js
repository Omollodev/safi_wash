// Staff dashboard: live job board, headline numbers and refresh status.
// Everything on the page is already rendered by Django; this file keeps it fresh and handles the card buttons.
// No libraries. All text is escaped before it goes into the page.
(function () {
  const root = document.querySelector("[data-board-url]");
  if (!root) return;
  const cfg = window.CARWASH;
  const REFRESH_MS = 10000;
  const $ = (sel, ctx = root) => ctx.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const icon = (name, extra) => cfg.iconHtml(name, extra);
  const withId = (url, id) => url.replace("/0/", "/" + id + "/");

  const statusBadge = { waiting: "bg-secondary", in_progress: "bg-primary", awaiting_extra: "bg-warning" };
  const EMPTY = {
    waiting: { icon: "clock", title: "No jobs waiting", text: "New bookings and walk-ins queue up here.", link: true },
    in_progress: { icon: "droplets", title: "Nothing in progress", text: "Start a waiting job and it moves here." },
    awaiting_extra: { icon: "circle-check", title: "No extra services pending", text: "Jobs waiting on an add-on show up here." },
  };
  // What the main button on a card does, using the existing status endpoint and its allowed transitions.
  const ACTIONS = {
    waiting: { to: "in_progress", label: "Start", icon: "play", style: "btn-primary" },
    in_progress: { to: "completed", label: "Complete", icon: "circle-check", style: "btn-outline-primary", confirm: true },
    awaiting_extra: { to: "in_progress", label: "Resume", icon: "play", style: "btn-primary" },
  };

  // ---------- time helpers
  const fmtTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const fmtMinutes = (m) => (m >= 60 ? Math.floor(m / 60) + "h " + (m % 60) + "m" : Math.max(m, 0) + "m");
  const since = (iso) => fmtMinutes(Math.floor((Date.now() - new Date(iso).getTime()) / 60000));

  // ---------- one job card (heading link + footer actions, per the card pattern)
  function card(job) {
    const act = ACTIONS[job.status];
    const timeRow = job.started_at
      ? `<li>${icon("clock")}<span>Started ${esc(fmtTime(job.started_at))}</span></li>
         <li>${icon("timer")}<span>Elapsed <b data-since="${esc(job.started_at)}">${esc(since(job.started_at))}</b></span></li>`
      : `<li>${icon("clock")}<span>Arrived ${esc(fmtTime(job.created_at))}</span></li>
         <li>${icon("timer")}<span>Waiting <b data-since="${esc(job.created_at)}">${esc(since(job.created_at))}</b></span></li>`;
    return `
      <article class="job-card priority-${esc(job.priority)}" data-status="${esc(job.status)}" data-job="${job.id}">
        <div class="job-card__top">
          <h4 class="job-card__title"><span class="job-card__queue">#${esc(job.queue)}</span>
            <a class="card-link" href="${withId(root.dataset.detailUrl, job.id)}"><span class="plate">${esc(job.plate)}</span></a></h4>
          <div class="job-card__badges">
            ${job.priority !== "normal" ? `<span class="badge ${job.priority === "urgent" ? "bg-danger" : "bg-warning"}">${esc(job.priority_display)}</span>` : ""}
            <span class="badge ${statusBadge[job.status] || "bg-secondary"}">${esc(job.status_display)}</span>
          </div>
        </div>
        <ul class="job-card__meta">
          <li>${icon("user")}<span>${esc(job.customer)}</span></li>
          <li>${icon("contact")}${job.worker ? `<span>${esc(job.worker)}</span>` : '<span class="is-unassigned">Unassigned</span>'}</li>
          <li>${icon("tags")}<span title="${esc(job.services.join(", "))}">${job.service_summary ? esc(job.service_summary) : "No services"}</span></li>
        </ul>
        <ul class="job-card__meta job-card__times">${timeRow}</ul>
        <div class="job-card__foot">
          <span class="job-card__amount">${esc(job.total_display)}${job.need_alert ? ` <span class="job-card__alert" title="Extra services pending">${icon("triangle-alert")}<span class="visually-hidden">Extra services pending</span></span>` : ""}</span>
          <div class="job-card__actions">
            ${act ? `<button type="button" class="btn ${act.style}" data-act="${act.to}" data-job="${job.id}" data-label="${esc(act.label)}" ${act.confirm ? "data-confirm" : ""}>${icon(act.icon)}${act.label}</button>` : ""}
          </div>
        </div>
      </article>`;
  }

  function empty(status) {
    const e = EMPTY[status];
    return `<div class="empty-state"><span class="empty-state__icon">${icon(e.icon, "icon-lg m-0")}</span>
      <p class="empty-state__title">${e.title}</p><p class="empty-state__text">${e.text}</p>
      ${e.link ? `<a class="btn btn-sm btn-outline-primary" href="${esc(root.dataset.newUrl)}">New job</a>` : ""}</div>`;
  }

  function render(board) {
    for (const status of Object.keys(EMPTY)) {
      const jobs = board[status] || [];
      const col = $(`[data-col="${status}"]`);
      if (col) col.innerHTML = jobs.length ? jobs.map(card).join("") : empty(status);
      const chip = $(`[data-count="${status}"]`);
      if (chip) chip.textContent = jobs.length;
    }
    // the two live headline numbers come straight from the same data
    setStat("waiting", (board.waiting || []).length);
    setStat("in_progress", (board.in_progress || []).length);
  }
  const setStat = (key, value) => { const el = document.querySelector(`[data-stat="${key}"]`); if (el) el.textContent = value; };

  // ---------- refresh + status
  const status = $(".refresh-status");
  const label = $("[data-refresh-label]");
  const stamp = $("[data-refresh-time]");
  let timer = null, inFlight = false;

  function setState(state, text) {
    status.classList.toggle("is-loading", state === "loading");
    status.classList.toggle("is-offline", state === "offline");
    status.classList.toggle("is-paused", state === "paused");
    if (text) label.textContent = text;
  }

  async function refresh() {
    if (inFlight) return;
    inFlight = true;
    setState("loading");
    try {
      const headers = { "X-Requested-With": "XMLHttpRequest" };
      const [boardRes, statsRes] = await Promise.all([
        fetch(root.dataset.boardUrl, { headers, credentials: "same-origin" }),
        fetch(document.querySelector("[data-stats-url]").dataset.statsUrl, { headers, credentials: "same-origin" }),
      ]);
      if (!boardRes.ok) throw new Error("board " + boardRes.status);
      render((await boardRes.json()).board);
      if (statsRes.ok) {
        const s = await statsRes.json();
        setStat("completed_today", s.completed_today);
        const money = Number(s.collected_today);
        const cur = document.querySelector("[data-currency]").dataset.currency;
        if (!Number.isNaN(money)) setStat("collected_today", cur + " " + money.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
      }
      setState("ok", "Live");
      stamp.textContent = "· updated " + new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
    } catch {
      setState("offline", "Offline");
      stamp.textContent = "· retrying in a few seconds";
    } finally {
      inFlight = false;
    }
  }

  function schedule() {
    clearInterval(timer);
    timer = setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { setState("paused", "Paused"); stamp.textContent = "· tab is in the background"; }
    else { refresh(); schedule(); }
  });
  $("[data-refresh]").addEventListener("click", () => { refresh(); schedule(); });

  // keep "Elapsed 42m" ticking between refreshes
  setInterval(() => root.querySelectorAll("[data-since]").forEach((el) => { el.textContent = since(el.dataset.since); }), 30000);

  // ---------- card buttons (Start / Complete / Resume) use the existing status endpoint
  const flash = $("[data-flash]");
  const announce = $("[data-announce]");
  let flashTimer;
  function say(message, isError) {
    flash.innerHTML = icon(isError ? "circle-alert" : "circle-check") + "<span>" + esc(message) + "</span>";
    flash.classList.toggle("is-error", !!isError);
    flash.hidden = false;
    announce.textContent = message;
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => { flash.hidden = true; }, 6000);
  }

  root.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-act]");
    if (!btn) return;
    const card = btn.closest(".job-card");
    const plate = card ? card.querySelector(".plate").textContent : "";
    if (btn.hasAttribute("data-confirm") && !window.confirm("Mark " + plate + " as complete? The customer is notified.")) return;
    btn.disabled = true;
    try {
      const body = new FormData();
      body.append("status", btn.dataset.act);
      const token = document.querySelector('meta[name="csrf-token"]').content;
      const res = await fetch(withId(root.dataset.statusUrl, btn.dataset.job), {
        method: "POST", body, credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": token },
      });
      const data = await res.json().catch(() => ({}));
      say(data.message || (res.ok ? "Job updated." : "That did not work. Try again."), !res.ok);
      await refresh();
    } catch {
      say("Could not reach the server. Check your connection and try again.", true);
      btn.disabled = false;
    }
  });

  // press / to jump to the search box
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    const box = document.querySelector("[data-quick-search]");
    if (box) { e.preventDefault(); box.focus(); }
  });

  // first paint comes from the page itself (no extra request), then keep it live
  try { render(JSON.parse(document.getElementById("board-data").textContent)); } catch { /* the first poll fills it in */ }
  stamp.textContent = "· updated " + new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
  schedule();
})();
