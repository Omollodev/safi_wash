// Log in / sign up helpers. Both pages work without this file:
// the password toggle stays hidden and the checklist is only a hint (the server validates everything).

// ---- show / hide password
document.querySelectorAll(".pw").forEach((wrap) => {
  const input = wrap.querySelector("input");
  const button = wrap.querySelector(".pw__toggle");
  if (!input || !button) return;
  button.hidden = false;
  button.addEventListener("click", () => {
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    button.textContent = show ? "Hide" : "Show";
    button.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });
});

// ---- live password checklist (guidance only)
const rules = document.querySelector("[data-rules]");
const first = document.getElementById("id_password1");
const second = document.getElementById("id_password2");
if (rules && first && second) {
  const checks = {
    length: () => first.value.length >= 8,
    letters: () => first.value.length > 0 && !/^\d+$/.test(first.value),
    match: () => second.value.length > 0 && first.value === second.value,
  };
  const update = () => {
    rules.querySelectorAll("[data-rule]").forEach((item) => {
      const ok = checks[item.dataset.rule]();
      item.dataset.ok = String(ok);
      item.querySelector("[data-state]").textContent = ok ? "(done)" : "(not yet)";
    });
  };
  first.addEventListener("input", update);
  second.addEventListener("input", update);
  update();
}

// ---- stop double submits
document.querySelectorAll("form[data-busy-text]").forEach((form) => {
  form.addEventListener("submit", () => {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    // Disable after the browser has collected the form data.
    setTimeout(() => { button.disabled = true; button.textContent = form.dataset.busyText; }, 0);
  });
});
// Going back to the page (bfcache) must not leave a stuck button.
window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  document.querySelectorAll("form[data-busy-text] button[type=submit]").forEach((b) => { b.disabled = false; });
});
