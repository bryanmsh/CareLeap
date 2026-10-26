import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useHashRoute } from "./lib/router";
import type { Route } from "./lib/router";
import { SUPPORTED, setLanguage } from "./i18n";
import type { Lang } from "./i18n";
import { Audit } from "./routes/Audit";
import { Planner } from "./routes/Planner";
import { About } from "./routes/About";

function NavLink({ to, route, label }: { to: Route; route: Route; label: string }) {
  return (
    <a href={`#${to}`} aria-current={route === to ? "page" : undefined}>
      <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        {to === "/audit" ? <><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M4 10h16M10 10v10"/></> : to === "/planner" ? <><path d="M5 19 19 5M5 5h14v14"/></> : <><circle cx="12" cy="12" r="8"/><path d="M12 11v6M12 7v1"/></>}
      </svg>
      {label}
    </a>
  );
}

export default function App() {
  const { t, i18n } = useTranslation();
  const route = useHashRoute();
  const current = (i18n.resolvedLanguage ?? "en") as Lang;

  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("careleap-theme") ?? "system"; }
    catch { return "system"; }
  });
  useEffect(() => {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("careleap-theme", theme); } catch { /* storage is optional */ }
  }, [theme]);

  return (
    <>
      <a className="skip-link" href="#main">
        {t("app.skipToContent")}
      </a>
      <header className="app-header">
        <a className="brand" href="#/audit"><span className="brand-mark" aria-hidden="true">&#8599;</span>{t("app.brand")}</a>
        <span className="workspace-label">{t("design.workspace")}</span>
        <nav className="app-nav" aria-label={t("app.brand")}>
          <NavLink to="/audit" route={route} label={t("app.nav.audit")} />
          <NavLink to="/planner" route={route} label={t("app.nav.planner")} />
          <NavLink to="/about" route={route} label={t("app.nav.about")} />
        </nav>
        <div className="sidebar-note"><span className="region-dot" aria-hidden="true" />{t("design.region")}<strong>{t("design.tagline")}</strong></div>
        <label className="theme-switch">{t("design.theme")}
          <select value={theme} onChange={(e) => setTheme(e.target.value)}>
            <option value="system">{t("design.system")}</option>
            <option value="light">{t("design.light")}</option>
            <option value="dark">{t("design.dark")}</option>
          </select>
        </label>
        <div className="lang-switch" role="group" aria-label={t("app.language")}>
          {SUPPORTED.map((lng) => (
            <button
              key={lng}
              type="button"
              aria-pressed={current === lng}
              onClick={() => setLanguage(lng)}
            >
              {lng.toUpperCase()}
            </button>
          ))}
        </div>
      </header>
      <main className="app-main" id="main">
        {route === "/audit" && <Audit />}
        {route === "/planner" && <Planner />}
        {route === "/about" && <About />}
      </main>
    </>
  );
}
