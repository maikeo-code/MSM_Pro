import { Link } from "react-router-dom";
import { ArrowLeft, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface ListingInfo {
  thumbnail?: string | null;
  title: string;
  mlb_id: string;
  listing_type: string;
  status: string;
}

interface SkuInfo {
  id?: string | null;
  sku?: string | null;
  cost?: number;
}

interface AnuncioHeaderProps {
  analysis: {
    listing: ListingInfo;
    sku?: SkuInfo | null;
  };
  days: number;
  setDays: (d: number) => void;
  onConsultor: () => void;
}

export function AnuncioHeader({ analysis, days, setDays, onConsultor }: AnuncioHeaderProps) {
  return (
    <div className="mb-8">
      <Link
        to="/anuncios"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar para Anuncios
      </Link>

      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            {analysis.listing.thumbnail && (
              <img
                src={analysis.listing.thumbnail}
                alt={analysis.listing.title}
                className="h-12 w-12 rounded object-cover"
              />
            )}
            <div>
              <h1 className="text-3xl font-bold text-foreground">
                {analysis.listing.title}
              </h1>
              <p className="text-sm text-muted-foreground">
                {analysis.listing.mlb_id}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 mt-4">
            <span className={cn(
              "inline-flex items-center rounded-full px-3 py-1 text-sm font-medium",
              analysis.listing.listing_type === "full"
                ? "bg-purple-100 text-purple-700"
                : analysis.listing.listing_type === "premium"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-700",
            )}>
              {analysis.listing.listing_type}
            </span>

            <span className="inline-flex items-center rounded-full px-3 py-1 text-sm font-medium bg-green-100 text-green-700">
              {analysis.listing.status}
            </span>

            {analysis.sku && (
              <span className="text-sm text-muted-foreground">
                SKU: <strong>{analysis.sku.sku}</strong>
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "px-4 py-2 rounded-md text-sm font-medium transition-colors",
                days === d
                  ? "bg-primary text-primary-foreground"
                  : "border bg-background hover:bg-accent",
              )}
            >
              {d}d
            </button>
          ))}
          <button
            onClick={onConsultor}
            className="inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:from-blue-700 hover:to-violet-700 transition-all"
          >
            <Sparkles className="h-4 w-4" />
            Analisar com IA
          </button>
        </div>
      </div>
    </div>
  );
}
