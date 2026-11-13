// Live notifications. Polls the server every few seconds and, when something new arrives,
// pops up a white card in the corner that fades away after a timeout.
// Hover or keyboard focus pauses the timer (so there is time to read), Esc or the x dismisses it.
// Without JS nothing breaks: the bell badge and the Notifications page still work.
(function () {
  const cfg = window.CARWASH;
  if (!cfg || !cfg.notificationsUrl) return;

  const POLL_MS = cfg.pollMs || 8000;
  const SHOW_MS = cfg.toastMs || 7000;
  const MAX_TOASTS = 3;
  const KEY = "safiwash.lastNotification";

  const store = {
    get() { try { const v = sessionStorage.getItem(KEY); return v === null ? null : Number(v); } catch { return null; } },
    set(v) { try { sessionStorage.setItem(KEY, String(v)); } catch { /* private mode: fine, we just may re-check */ } },
  };

  const region = document.createElement("div");
  region.className = "toasts";
  region.setAttribute("role", "region");
  region.setAttribute("aria-label", "New notifications");
  region.setAttribute("aria-live", "polite");
  document.body.appendChild(region);

  const make = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text; // textContent, never innerHTML: titles can contain customer-typed text
    return el;
  };

  function show(n) {
    const card = make("div", "toast-card" + (n.type === "alert" ? " toast-card--alert" : ""));
    card.setAttribute("role", "status");
    card.style.setProperty("--toast-ms", SHOW_MS + "ms");

    const icon = make("span", "toast-card__icon");
    icon.appendChild(window.CARWASH.icon(n.icon, "bell"));

    const body = make("div", "toast-card__body");
    body.appendChild(make("strong", "toast-card__title", n.title));
    if (n.message) body.appendChild(make("p", "toast-card__text", n.message));
    if (n.url && n.url.startsWith("/")) {
      const link = make("a", "toast-card__link", "View");
      link.href = n.url;
      body.appendChild(link);
    }

    const close = make("button", "toast-card__close");
    close.type = "button";
    close.setAttribute("aria-label", "Dismiss notification");
    close.appendChild(window.CARWASH.icon("x"));

    card.append(icon, body, close, make("span", "toast-card__bar"));
    region.prepend(card);
    requestAnimationFrame(() => card.classList.add("is-in"));

    let remaining = SHOW_MS, started = Date.now(), timer;
    const leave = () => {
      clearTimeout(timer);
      card.classList.remove("is-in");
      card.classList.add("is-out"); // opacity fade
      setTimeout(() => card.remove(), 450);
    };
    const start = () => { started = Date.now(); timer = setTimeout(leave, remaining); card.classList.remove("is-paused"); };
    const pause = () => { clearTimeout(timer); remaining -= Date.now() - started; card.classList.add("is-paused"); };

    card.addEventListener("mouseenter", pause);
    card.addEventListener("mouseleave", start);
    card.addEventListener("focusin", pause);
    card.addEventListener("focusout", start);
    card.addEventListener("keydown", (e) => { if (e.key === "Escape") leave(); });
    close.addEventListener("click", leave);
    start();

    while (region.children.length > MAX_TOASTS) region.lastElementChild.remove(); // oldest goes first
  }

  const badge = document.getElementById("bell-count");
  const bell = document.getElementById("bell-link");
  let busy = false;

  async function check() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const response = await fetch(cfg.notificationsUrl, { headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" });
      if (!response.ok) return;
      const data = await response.json();

      if (badge) {
        badge.textContent = data.unread > 99 ? "99+" : data.unread;
        badge.classList.toggle("d-none", data.unread === 0);
        if (bell) bell.setAttribute("aria-label", data.unread ? "Notifications, " + data.unread + " unread" : "Notifications");
      }

      const newest = data.results.reduce((max, n) => Math.max(max, n.id), 0);
      const seen = store.get();
      if (seen === null) { store.set(newest); return; } // first visit: don't replay old notifications
      const fresh = data.results.filter((n) => n.id > seen && !n.is_read).sort((a, b) => a.id - b.id);
      if (newest > seen) store.set(newest);

      if (fresh.length > MAX_TOASTS) {
        show({ title: fresh.length + " new notifications", message: "Open your notifications to see them all.", icon: "bell", type: "info", url: cfg.listUrl || "/notifications/" });
      } else {
        fresh.forEach(show);
      }
    } catch { /* offline or server restarting: try again next tick */ } finally { busy = false; }
  }

  check();
  setInterval(check, POLL_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) check(); }); // catch up as soon as the tab is back
})();
