/**
 * Componente TableSkeleton para estado de carregamento
 * Simula linhas e colunas com animação de pulse
 */
export interface TableSkeletonProps {
  rows?: number;
  cols?: number;
}

export function TableSkeleton({ rows = 5, cols = 6 }: TableSkeletonProps) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div
          key={rowIdx}
          className="border border-border rounded-lg p-4 flex gap-4 animate-pulse"
        >
          {Array.from({ length: cols }).map((_, colIdx) => (
            <div
              key={colIdx}
              className="flex-1 h-6 bg-muted rounded"
              style={{
                flex: colIdx === 0 ? "0 0 20%" : undefined,
              }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * Componente KpiSkeleton para carregamento de KPI Cards
 */
export interface KpiSkeletonProps {
  count?: number;
}

export function KpiSkeleton({ count = 4 }: KpiSkeletonProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className="border border-border rounded-lg bg-card p-6 space-y-4 animate-pulse"
        >
          <div className="flex items-center justify-between">
            <div className="h-4 bg-muted rounded w-24" />
            <div className="h-10 w-10 bg-muted rounded-lg" />
          </div>
          <div className="h-8 bg-muted rounded w-32" />
          <div className="h-4 bg-muted rounded w-20" />
        </div>
      ))}
    </div>
  );
}
