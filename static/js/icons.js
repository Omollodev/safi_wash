// Lucide icons from the same sprite the templates use, for markup that JavaScript builds.
// window.CARWASH.icon("clock")        -> an <svg> element (safe: no innerHTML)
// window.CARWASH.iconHtml("clock")    -> an HTML string for templates literals (name is whitelisted)
(function () {
  const cfg = (window.CARWASH = window.CARWASH || {});
  const NS = "http://www.w3.org/2000/svg";
  const safe = (name) => (/^[a-z0-9-]{1,40}$/.test(name || "") ? name : "circle");
  cfg.icon = (name, extra) => {
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "icon" + (extra ? " " + extra : ""));
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const use = document.createElementNS(NS, "use");
    use.setAttribute("href", cfg.iconsUrl + "#" + safe(name));
    svg.appendChild(use);
    return svg;
  };
  cfg.iconHtml = (name, extra) =>
    '<svg class="icon' + (extra ? " " + String(extra).replace(/[^a-z0-9 _-]/gi, "") : "") + '" aria-hidden="true" focusable="false"><use href="' + cfg.iconsUrl + "#" + safe(name) + '"></use></svg>';
})();
