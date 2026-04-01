import { useState, useEffect } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
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
  Sparkles,
  Menu,
  X,
  Moon,
  Sun,
  LogOut,
  User,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { useAccountStore } from "@/store/accountStore";
import { AccountSelector } from "@/components/AccountSelector";
import { NotificationBell } from "@/components/NotificationBell";
import authService from "@/services/authService";

// ─── Secao principal do menu com agrupamento semantico ──────────────────────
const menuSections = [
  {
    section: "VISÃO GERAL",
    items: [{ to: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    section: "OPERAÇÕES",
    items: [
      { to: "/pedidos", label: "Pedidos", icon: ShoppingCart },
      { to: "/atendimento", label: "Atendimento", icon: Headphones },
    ],
  },
  {
    section: "CATÁLOGO",
    items: [
      { to: "/anuncios", label: "Anuncios", icon: Tag },
      { to: "/produtos", label: "Produtos", icon: Package },
      { to: "/precos", label: "Preços", icon: Sparkles, badge: "pending" },
    ],
  },
  {
    section: "INTELIGÊNCIA",
    items: [
      { to: "/analise-anuncios", label: "Análise", icon: BarChart3 },
      { to: "/concorrencia", label: "Concorrência", icon: Users },
      { to: "/financeiro", label: "Financeiro", icon: DollarSign },
    ],
  },
  {
    section: "MARKETING",
    items: [{ to: "/publicidade", label: "Publicidade", icon: Megaphone }],
  },
];

// ─── Secao Inteligencia (Intel) ───────────────────────────────────────────────
const intelItems = [
  { to: "/intel/pareto", label: "Pareto 80/20", icon: BarChart2 },
  { to: "/intel/forecast", label: "Projeção", icon: TrendingUp },
  { to: "/intel/distribution", label: "Distribuição", icon: PieChart },
  { to: "/intel/insights", label: "Insights IA", icon: Lightbulb },
];

// ─── Secao de Configuracoes ───────────────────────────────────────────────────
const configItems = [
  { to: "/alertas", label: "Alertas", icon: Bell },
  { to: "/reputacao", label: "Reputação", icon: Shield },
  { to: "/configuracoes", label: "Configurações", icon: Settings },
];

// ─── Componente NavItem ─────────────────────────────────────────────────────
function NavItem({ to, label, icon: Icon, badge }: { to: string; label: string; icon: any; badge?: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors group",
          isActive
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="flex-1">{label}</span>
      {badge && (
        <span className="inline-flex h-2 w-2 rounded-full bg-yellow-500 opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </NavLink>
  );
}

// ─── Componente SectionHeader ───────────────────────────────────────────────
function SectionHeader({ label }: { label: string }) {
  return (
    <div className="pt-4 pb-2 px-3">
      <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
        {label}
      </div>
    </div>
  );
}

// ─── Componente Topbar ─────────────────────────────────────────────────────
function Topbar({ onMenuToggle }: { onMenuToggle: () => void }) {
  const location = useLocation();
  const { user, clearAuth } = useAuthStore();
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  // Gerar breadcrumb simples
  const getBreadcrumb = () => {
    const path = location.pathname;
    const segments = path.split("/").filter(Boolean);
    if (segments.length === 0) return "Dashboard";
    return segments[0].charAt(0).toUpperCase() + segments[0].slice(1).replace(/[-]/g, " ");
  };

  const handleLogout = () => {
    clearAuth();
    window.location.href = "/login";
  };

  return (
    <header className="h-14 border-b bg-card flex items-center justify-between px-6 sticky top-0 z-40">
      {/* Left: Hamburger + Breadcrumb */}
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuToggle}
          className="lg:hidden p-2 hover:bg-accent rounded-md transition-colors"
        >
          <Menu className="h-5 w-5" />
        </button>
        <nav className="hidden md:block text-sm text-muted-foreground">
          <span>{getBreadcrumb()}</span>
        </nav>
      </div>

      {/* Right: Account selector + Sync indicator + Notifications + User menu */}
      <div className="flex items-center gap-4">
        {/* Account selector */}
        <AccountSelector className="hidden md:block" />

        {/* Última sync */}
        <div className="hidden sm:flex items-center gap-2 text-xs text-muted-foreground">
          <div className="h-2 w-2 rounded-full bg-green-500" />
          <span>Última sync: 14:35</span>
        </div>

        {/* Notification bell */}
        <NotificationBell />

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className="flex items-center gap-2 p-2 hover:bg-accent rounded-md transition-colors"
          >
            <div className="h-6 w-6 rounded-full bg-primary flex items-center justify-center text-xs font-bold text-primary-foreground">
              {user?.email?.charAt(0).toUpperCase() || "U"}
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </button>

          {/* Dropdown menu */}
          {isUserMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 rounded-md shadow-lg bg-popover border border-border z-50">
              <div className="p-3 border-b border-border">
                <p className="text-sm font-medium">{user?.email}</p>
              </div>
              <button
                onClick={() => {
                  setIsUserMenuOpen(false);
                  window.location.href = "/configuracoes";
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <User className="h-4 w-4" />
                Perfil
              </button>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-accent transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

// ─── Layout principal ───────────────────────────────────────────────────────
export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const { isAuthenticated } = useAuthStore();
  const { activeAccountId, setActiveAccount } = useAccountStore();

  // Sincronizar dark mode com localStorage
  useEffect(() => {
    const isDark = localStorage.getItem("msm-dark-mode") === "true";
    setDarkMode(isDark);
    if (isDark) {
      document.documentElement.classList.add("dark");
    }
  }, []);

  // Carregar preferência de conta ativa do backend (fire-and-forget, sem sync de volta)
  useEffect(() => {
    if (isAuthenticated && !activeAccountId) {
      authService
        .getPreferences()
        .then((pref) => {
          if (pref.active_ml_account_id) {
            setActiveAccount(pref.active_ml_account_id, false);
          }
        })
        .catch(() => {});
    }
  }, [isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleDarkMode = () => {
    const newDarkMode = !darkMode;
    setDarkMode(newDarkMode);
    localStorage.setItem("msm-dark-mode", String(newDarkMode));
    if (newDarkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      {/* Overlay mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 lg:hidden z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed lg:static w-64 h-screen border-r bg-card flex flex-col transition-transform duration-200 z-40 lg:z-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between gap-2 px-6 py-5 border-b">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <TrendingUp className="h-4 w-4 text-primary-foreground" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-sm text-foreground">MSM Pro</span>
              <span className="text-[10px] text-muted-foreground">Mercado Livre Intel</span>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-2 hover:bg-accent rounded-md transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Nav — scrollavel para acomodar todos os itens */}
        <nav className="flex-1 py-4 px-3 space-y-4 overflow-y-auto">
          {/* AccountSelector no sidebar — visivel apenas em mobile */}
          <div className="md:hidden pb-2 border-b border-border">
            <AccountSelector fullWidth />
          </div>

          {/* Menu principal com agrupamento */}
          {menuSections.map((section) => (
            <div key={section.section}>
              <SectionHeader label={section.section} />
              <div className="space-y-1">
                {section.items.map((item) => (
                  <NavItem key={item.to} {...item} />
                ))}
              </div>
            </div>
          ))}

          {/* Separador */}
          <div className="h-px bg-border my-2" />

          {/* Inteligência (Intel) */}
          <div>
            <SectionHeader label="ANALYTICS" />
            <div className="space-y-1">
              {intelItems.map((item) => (
                <NavItem key={item.to} {...item} />
              ))}
            </div>
          </div>

          {/* Separador */}
          <div className="h-px bg-border my-2" />

          {/* Configurações */}
          <div>
            <SectionHeader label="CONFIGURAÇÕES" />
            <div className="space-y-1">
              {configItems.map((item) => (
                <NavItem key={item.to} {...item} />
              ))}
            </div>
          </div>
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t space-y-3">
          {/* Dark mode toggle */}
          <button
            onClick={toggleDarkMode}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground rounded-md transition-colors"
          >
            {darkMode ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
            <span>{darkMode ? "Light" : "Dark"}</span>
          </button>

          {/* Version */}
          <div className="text-xs text-muted-foreground/70">
            MSM Pro v1.0.0
          </div>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col">
        {/* Topbar */}
        <Topbar onMenuToggle={() => setSidebarOpen(!sidebarOpen)} />

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
