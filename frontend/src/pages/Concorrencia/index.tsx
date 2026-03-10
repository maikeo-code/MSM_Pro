import { Users } from "lucide-react";

export default function Concorrencia() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Concorrencia</h1>
        <p className="text-muted-foreground mt-1">
          Monitore os precos dos seus concorrentes
        </p>
      </div>

      <div className="rounded-lg border bg-card p-12 text-center">
        <Users className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
        <p className="font-medium text-foreground">Modulo de Concorrencia</p>
        <p className="text-sm text-muted-foreground mt-1">
          Disponivel no Sprint 3. Aqui voce podera vincular anuncios de concorrentes
          e acompanhar variacoes de preco.
        </p>
      </div>
    </div>
  );
}
