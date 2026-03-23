/**
 * Badge visual para SLA Timer.
 * Calcula tempo restante baseado em date_created + 24h.
 * Verde (>12h), Amarelo (6-12h), Vermelho (<6h), Preto piscante (<1h)
 */

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface SLABadgeProps {
  dateCreated: string; // ISO 8601 string
  compact?: boolean; // Se true, mostra apenas icone e tempo
}

export function SLABadge({ dateCreated, compact = false }: SLABadgeProps) {
  const [timeRemaining, setTimeRemaining] = useState<string>("");
  const [status, setStatus] = useState<
    "green" | "yellow" | "red" | "black-blink"
  >("green");

  useEffect(() => {
    const updateSLA = () => {
      const created = new Date(dateCreated).getTime();
      const slaDeadline = created + 24 * 60 * 60 * 1000; // 24h em ms
      const now = Date.now();
      const remaining = slaDeadline - now;

      if (remaining <= 0) {
        setTimeRemaining("SLA vencido");
        setStatus("black-blink");
        return;
      }

      const hours = remaining / (60 * 60 * 1000);
      const mins = (remaining % (60 * 60 * 1000)) / (60 * 1000);

      // Determinar status
      if (hours > 12) {
        setStatus("green");
      } else if (hours > 6) {
        setStatus("yellow");
      } else if (hours > 1) {
        setStatus("red");
      } else {
        setStatus("black-blink");
      }

      // Formato do tempo restante
      if (hours > 1) {
        setTimeRemaining(
          `${Math.floor(hours)}h ${Math.floor(mins)}m restantes`
        );
      } else {
        setTimeRemaining(`${Math.floor(mins)}m restantes`);
      }
    };

    updateSLA();
    const interval = setInterval(updateSLA, 30000); // Atualizar a cada 30s
    return () => clearInterval(interval);
  }, [dateCreated]);

  const badgeStyles = {
    green: "bg-green-100 text-green-700",
    yellow: "bg-yellow-100 text-yellow-700",
    red: "bg-red-100 text-red-700",
    "black-blink": "bg-gray-900 text-white animate-pulse",
  };

  if (compact) {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-1 text-xs font-medium rounded-full px-2 py-1",
          badgeStyles[status]
        )}
      >
        <Clock className="h-3 w-3" />
        {timeRemaining.split(" ")[0]}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium rounded-full px-3 py-1.5",
        badgeStyles[status]
      )}
    >
      <Clock className="h-3.5 w-3.5" />
      {timeRemaining}
    </div>
  );
}

export function calculateHoursRemaining(dateCreated: string): number {
  const created = new Date(dateCreated).getTime();
  const slaDeadline = created + 24 * 60 * 60 * 1000;
  const remaining = slaDeadline - Date.now();
  return remaining / (60 * 60 * 1000);
}
