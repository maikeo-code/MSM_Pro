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
  ShoppingCart,
  Headphones,
  BarChart2,
  PieChart,
  Lightbulb,
  Brain,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Secao principal do menu ──────────────────────────────────────────────────
const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/anuncios", label: "Anuncios", icon: Tag },
  { to: "/pedidos", label: "Pedidos", icon: ShoppingCart },
  { to: "/precos", label: "Sugestao Precos", icon: Sparkles },
  { to: "/atendimento", label: "Atendimento", icon: Headphones },
  { to: "/analise-anuncios", label: "Analise", icon: BarChart3 },
  { to: "/produtos", label: "Produtos", icon: Package },
  { to: "/concorrencia", label: "Concorrencia", icon: Users },
  { to: "/reputacao", label: "Reputacao", icon: Shield },
  { to: "/financeiro", label: "Financeiro", icon: DollarSign },
  { to: "/publicidade", label: "Publicidade", icon: Megaphone },
  { to: "/alertas", label: "Alertas", icon: Bell },
  { to: "/configuracoes", label: "Configuracoes", icon: Settings },
];

// ─── Secao Inteligencia (Intel) ───────────────────────────────────────────────
const intelItems = [
  { to: "/intel/pareto", label: "Pareto 80/20", icon: BarChart2 },
  { to: "/intel/forecast", label: "Projecao", icon: TrendingUp },
  { to: "/intel/distribution", label: "Distribuicao", icon: PieChart },
  { to: "/intel/insights", label: "Insights IA", icon: Lightbulb },
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

        {/* Nav — scrollavel para acomodar todos os itens */}
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {/* Menu principal */}
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

          {/* ─── Divisor: secao Inteligencia ─────────────────────────────────── */}
          <div className="pt-4 pb-1">
            <NavLink
              to="/intel"
              end
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider transition-colors",
                  isActive
                    ? "text-primary"
                    : "text-muted-foreground/70 hover:text-muted-foreground"
                )
              }
            >
              <Brain className="h-3.5 w-3.5 shrink-0" />
              Inteligencia
            </NavLink>
          </div>

          {intelItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ml-2",
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
