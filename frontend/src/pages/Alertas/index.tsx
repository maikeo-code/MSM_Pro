import { Bell } from "lucide-react";

export default function Alertas() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Alertas</h1>
        <p className="text-muted-foreground mt-1">
          Configure alertas para seus anuncios
        </p>
      </div>

      <div className="rounded-lg border bg-card p-12 text-center">
        <Bell className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
        <p className="font-medium text-foreground">Modulo de Alertas</p>
        <p className="text-sm text-muted-foreground mt-1">
          Disponivel no Sprint 4. Configure alertas para conversao baixa,
          estoque critico e mudancas de preco de concorrentes.
        </p>
      </div>
    </div>
  );
}
