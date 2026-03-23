/**
 * Componente EmptyState unificado
 * Exibe ícone, título, descrição e ação opcional quando não há dados
 */
export interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
      <div className="h-16 w-16 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
        {icon}
      </div>
      <div className="space-y-2">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="text-sm text-muted-foreground max-w-sm">{description}</p>
      </div>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
