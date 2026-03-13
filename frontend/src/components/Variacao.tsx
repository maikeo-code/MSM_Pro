import { TrendingUp, TrendingDown } from "lucide-react";

interface VariacaoProps {
  value?: number | null;
  unit?: string;
}

/**
 * Badge de variacao percentual com seta verde (positivo) ou vermelha (negativo).
 * Renderiza null quando value e nulo/undefined.
 */
export function Variacao({ value, unit = "%" }: VariacaoProps) {
  if (value == null) return null;
  const isPositive = value >= 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const color = isPositive ? "text-green-600" : "text-red-500";
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${color}`}>
      <Icon className="h-3 w-3" />
      {Math.abs(value).toFixed(1)}{unit}
    </span>
  );
}
