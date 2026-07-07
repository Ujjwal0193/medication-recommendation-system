import { NavLink, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="site">
      <nav className="nav">
        <NavLink to="/" className="brand">🛡️ MediGuard</NavLink>
        <div className="navlinks">
          <NavLink to="/" end>Home</NavLink>
          <NavLink to="/demo">Live Demo</NavLink>
          <NavLink to="/about">About</NavLink>
          <NavLink to="/docs">Docs</NavLink>
        </div>
      </nav>

      <main className="page">
        <Outlet />
      </main>

      <footer className="footer">
        <div>
          <strong>MediGuard</strong> — a safe, explainable neuro-symbolic clinical
          decision-support system.
        </div>
        <div className="footnote">
          Research prototype · advisory only · not a medical device. M.Tech project,
          NIT Rourkela.
        </div>
      </footer>
    </div>
  );
}
