/**
 * Badge indicando dias para zerar estoque.
 * Verde (>30d), amarelo (7-30d), vermelho (<7d).
 */
export function DiasBadge({ dias }: { dias?: number | null }) {
  if (dias == null) {
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-gray-100 text-gray-500">
        —
      </span>
    );
  }
  if (dias > 30) {
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">
        {dias}d
      </span>
    );
  }
  if (dias >= 7) {
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800">
        {dias}d
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800">
      {dias}d
    </span>
  );
}
