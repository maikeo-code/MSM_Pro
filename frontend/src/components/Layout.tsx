import { Outlet, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Tag,
  Package,
  Users,
  Bell,
  Settings,
  Shield,
  TrendingUp,
  DollarSign,
  Megaphone,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/anuncios", label: "Anuncios", icon: Tag },
  { to: "/analise-anuncios", label: "Analise", icon: BarChart3 },
  { to: "/produtos", label: "Produtos", icon: Package },
  { to: "/concorrencia", label: "Concorrencia", icon: Users },
  { to: "/reputacao", label: "Reputacao", icon: Shield },
  { to: "/financeiro", label: "Financeiro", icon: DollarSign },
  { to: "/publicidade", label: "Publicidade", icon: Megaphone },
  { to: "/alertas", label: "Alertas", icon: Bell },
  { to: "/configuracoes", label: "Configuracoes", icon: Settings },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r bg-card flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-2 px-6 py-5 border-b">
          <TrendingUp className="h-6 w-6 text-primary" />
          <span className="font-bold text-lg text-foreground">MSM Pro</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t text-xs text-muted-foreground">
          MSM Pro v1.0.0
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
