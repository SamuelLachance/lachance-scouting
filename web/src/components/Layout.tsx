import { Outlet, Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Trophy, GitCompareArrows, LayoutGrid } from "lucide-react";

export default function Layout() {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-grid-rink bg-[length:48px_48px]">
      <header className="sticky top-0 z-50 glass border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-ice-500 to-ice-700 flex items-center justify-center shadow-lg shadow-ice-500/20 group-hover:shadow-ice-500/40 transition-shadow">
              <Trophy className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-display font-bold text-lg leading-tight tracking-tight">
                Lachance Scouting
              </h1>
              <p className="text-[10px] text-ice-400/80 font-mono uppercase tracking-widest">
                NHL 2026 · NORTHSTAR
              </p>
            </div>
          </Link>

          <nav className="flex items-center gap-1">
            <NavLink to="/" active={pathname === "/"} icon={<LayoutGrid className="w-4 h-4" />}>
              Classement
            </NavLink>
            <NavLink to="/compare" active={pathname === "/compare"} icon={<GitCompareArrows className="w-4 h-4" />}>
              Comparer
            </NavLink>
          </nav>
        </div>
      </header>

      <motion.main
        key={pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="max-w-7xl mx-auto px-4 sm:px-6 py-6"
      >
        <Outlet />
      </motion.main>

      <footer className="border-t border-white/5 mt-12 py-6 text-center text-xs text-slate-500">
        <p>Lachance Scouting · NORTHSTAR · Sources: DPH, DFO, EP, Central Scouting</p>
      </footer>
    </div>
  );
}

function NavLink({
  to,
  active,
  icon,
  children,
}: {
  to: string;
  active: boolean;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
        active
          ? "bg-ice-500/15 text-ice-300 border border-ice-500/25"
          : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
      }`}
    >
      {icon}
      <span className="hidden sm:inline">{children}</span>
    </Link>
  );
}
