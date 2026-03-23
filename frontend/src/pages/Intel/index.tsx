import { Link } from "react-router-dom";
import { BarChart2, TrendingUp, PieChart, Lightbulb, ChevronRight, Calendar, Package, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Card de navegacao para sub-modulo ────────────────────────────────────────
interface IntelCardProps {
  to: string;
  icon: React.ReactNode;
  iconBg: string;
  title: string;
  description: string;
  tag?: string;
}

function IntelCard({ to, icon, iconBg, title, description, tag }: IntelCardProps) {
  return (
    <Link
      to={to}
      className="group flex flex-col gap-4 rounded-lg border bg-card p-6 shadow-sm hover:shadow-md hover:border-primary/30 transition-all duration-200"
    >
      <div className="flex items-start justify-between">
        <span className={cn("inline-flex h-12 w-12 items-center justify-center rounded-lg", iconBg)}>
          {icon}
        </span>
        {tag && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
            {tag}
          </span>
        )}
      </div>
      <div className="flex-1">
        <h2 className="text-base font-semibold text-foreground group-hover:text-primary transition-colors">
          {title}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
          {description}
        </p>
      </div>
      <div className="flex items-center gap-1 text-sm font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
        Acessar
        <ChevronRight className="h-4 w-4" />
      </div>
    </Link>
  );
}

// ─── Pagina hub do modulo Intel ───────────────────────────────────────────────
export default function Intel() {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Inteligencia de Negocios</h1>
        <p className="text-muted-foreground mt-1">
          Analises avancadas para decisoes estrategicas baseadas em dados
        </p>
      </div>

      {/* Grid de cards 2x2 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 max-w-4xl">
        <IntelCard
          to="/intel/pareto"
          icon={<BarChart2 className="h-6 w-6 text-violet-600" />}
          iconBg="bg-violet-50"
          title="Pareto 80/20"
          description="Identifique os anuncios que geram 80% da sua receita. Descubra quais sao os pilares do seu negocio e onde concentrar esforcos."
          tag="Core"
        />
        <IntelCard
          to="/intel/forecast"
          icon={<TrendingUp className="h-6 w-6 text-blue-600" />}
          iconBg="bg-blue-50"
          title="Projecao de Vendas"
          description="Previsao de vendas por anuncio para os proximos 7 e 30 dias com intervalo de confianca e indicador de tendencia."
        />
        <IntelCard
          to="/intel/distribution"
          icon={<PieChart className="h-6 w-6 text-emerald-600" />}
          iconBg="bg-emerald-50"
          title="Distribuicao de Vendas"
          description="Visualize como a receita esta distribuida entre seus anuncios. Mapa visual de proporcao e coeficiente de Gini."
        />
        <IntelCard
          to="/intel/insights"
          icon={<Lightbulb className="h-6 w-6 text-amber-600" />}
          iconBg="bg-amber-50"
          title="Insights com IA"
          description="Recomendacoes automaticas geradas por inteligencia artificial baseadas nos seus dados de vendas, estoque e conversao."
          tag="IA"
        />
      </div>

      {/* Nota informativa */}
      <div className="mt-10 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-4 max-w-4xl">
        <p className="text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Nota:</span> Os dados de inteligencia sao calculados a partir dos snapshots sincronizados do Mercado Livre.
          Para resultados mais precisos, mantenha a sincronizacao diaria ativa e aguarde ao menos 7 dias de historico.
        </p>
      </div>
    </div>
  );
}
