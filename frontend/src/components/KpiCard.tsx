import { Variacao } from "@/components/Variacao";

export interface KpiCardProps {
  label: string;
  value: string;
  sub?: string;
  variacao?: number | null;
  icon: React.ReactNode;
  iconColor?: string;
  iconBg?: string;
}

/**
 * Componente KPI Card unificado
 * Usa tokens de design system: bg-card, text-foreground, text-muted-foreground, border-border
 * Inclui variacao percentual e suporte a label descritivo
 */
export function KpiCard({
  label,
  value,
  sub,
  variacao,
  icon,
  iconBg = "bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400",
}: KpiCardProps) {
  return (
    <div className="rounded-lg border bg-card border-border p-6 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground font-medium">{label}</p>
        <span className={`p-2 rounded-lg ${iconBg}`}>{icon}</span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      <Variacao value={variacao} />
    </div>
  );
}
