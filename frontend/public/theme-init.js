// Sets the saved theme before the first paint, so a light-mode user never sees a dark flash (dark is the default).
// A separate file, not an inline script: the production page only allows scripts from its own origin (see vite.config.ts).
try {
  document.documentElement.dataset.theme = localStorage.getItem("finhelp_theme") === "light" ? "light" : "dark";
} catch (e) {
  document.documentElement.dataset.theme = "dark";
}
