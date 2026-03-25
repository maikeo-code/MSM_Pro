import { useEffect, useState, useRef } from "react";
import { ChevronDown, Layers } from "lucide-react";
import { useAccountStore } from "@/store/accountStore";
import authService, { type MLAccountOut } from "@/services/authService";
import { cn } from "@/lib/utils";

interface AccountSelectorProps {
  className?: string;
  /** Quando true, o botão ocupa toda a largura e sempre mostra o label (uso no sidebar mobile) */
  fullWidth?: boolean;
}

export function AccountSelector({ className, fullWidth = false }: AccountSelectorProps) {
  const [accounts, setAccounts] = useState<MLAccountOut[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const { activeAccountId, setActiveAccount, clearActiveAccount } = useAccountStore();

  // Carregar contas ao montar
  useEffect(() => {
    const loadAccounts = async () => {
      try {
        const data = await authService.listMLAccounts();
        setAccounts(data);
      } catch (error) {
        console.error("Erro ao carregar contas ML:", error);
        setAccounts([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadAccounts();
  }, []);

  // Fechar dropdown ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Buscar a conta ativa no array
  const activeAccount = accounts.find((acc) => acc.id === activeAccountId);

  // Se tem apenas 1 conta, não mostrar o seletor
  if (accounts.length <= 1) {
    return null;
  }

  const getAccountBadgeColor = (index: number) => {
    const colors = [
      "bg-blue-100 text-blue-800",
      "bg-purple-100 text-purple-800",
      "bg-pink-100 text-pink-800",
      "bg-green-100 text-green-800",
      "bg-orange-100 text-orange-800",
      "bg-red-100 text-red-800",
      "bg-cyan-100 text-cyan-800",
      "bg-indigo-100 text-indigo-800",
    ];
    return colors[index % colors.length];
  };

  const getStatusBadge = (account: MLAccountOut) => {
    if (!account.token_expires_at) {
      return <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded">Expirado</span>;
    }

    const expiresAt = new Date(account.token_expires_at);
    const now = new Date();
    const daysUntilExpiry = Math.floor((expiresAt.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

    if (daysUntilExpiry < 0) {
      return <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded">Expirado</span>;
    } else if (daysUntilExpiry < 7) {
      return <span className="text-xs px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded">Vence em {daysUntilExpiry}d</span>;
    } else {
      return <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">Ativo</span>;
    }
  };

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-md bg-accent text-accent-foreground hover:bg-accent/90 transition-colors text-sm",
          fullWidth && "w-full",
        )}
      >
        {isLoading ? (
          <div className="h-4 w-4 bg-muted-foreground/50 rounded animate-pulse" />
        ) : activeAccount ? (
          <>
            <div className={cn("h-6 w-6 rounded flex items-center justify-center text-xs font-bold shrink-0", getAccountBadgeColor(accounts.indexOf(activeAccount)))}>
              {activeAccount.nickname.charAt(0).toUpperCase()}
            </div>
            <span className={cn("truncate", fullWidth ? "flex-1 text-left" : "hidden sm:inline max-w-[120px]")}>
              {activeAccount.nickname}
            </span>
          </>
        ) : (
          <>
            <Layers className="h-4 w-4 shrink-0" />
            <span className={cn(fullWidth ? "flex-1 text-left" : "hidden sm:inline")}>Todas as contas</span>
          </>
        )}
        <ChevronDown className={cn("h-4 w-4 transition-transform shrink-0", isOpen ? "rotate-180" : "")} />
      </button>

      {/* Dropdown menu */}
      {isOpen && !isLoading && (
        <div className={cn(
          "absolute mt-2 rounded-md shadow-lg bg-popover border border-border z-50",
          fullWidth ? "left-0 right-0 w-auto" : "right-0 w-56",
        )}>
          {/* Opção "Todas as contas" */}
          <button
            onClick={() => {
              clearActiveAccount();
              setIsOpen(false);
            }}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-accent transition-colors text-left border-b border-border",
              !activeAccountId ? "bg-accent text-accent-foreground" : "text-foreground",
            )}
          >
            <Layers className="h-4 w-4 shrink-0" />
            <div className="flex-1">
              <div className="font-medium">Todas as contas</div>
              <div className="text-xs text-muted-foreground">{accounts.length} contas</div>
            </div>
            {!activeAccountId && <div className="h-2 w-2 rounded-full bg-current" />}
          </button>

          {/* Lista de contas */}
          {accounts.map((account, index) => (
            <button
              key={account.id}
              onClick={() => {
                setActiveAccount(account.id);
                setIsOpen(false);
              }}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-accent transition-colors text-left",
                activeAccountId === account.id ? "bg-accent text-accent-foreground" : "text-foreground",
              )}
            >
              <div className={cn("h-6 w-6 rounded flex items-center justify-center text-xs font-bold text-white shrink-0", getAccountBadgeColor(index))}>
                {account.nickname.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{account.nickname}</div>
                <div className="text-xs text-muted-foreground truncate">{account.ml_user_id}</div>
              </div>
              {getStatusBadge(account)}
              {activeAccountId === account.id && <div className="h-2 w-2 rounded-full bg-current shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
