#!/bin/bash
# Download all Portuguese Nubimetrics video transcripts
# Videos filtered: Portuguese tutorials/features only

OUTDIR="C:/Users/Maikeo/MSM_Imports_Mercado_Livre/MSM_Pro/docs/nubimetrics_transcripts"

# All Portuguese videos (tutorials, features, strategies)
PT_VIDEOS=(
  # === TUTORIAIS DE FEATURES (CORE) ===
  "nkNdnITRR2U|Treinamento especial - Analise suas categorias"
  "OKIo8HMb3f0|Como configurar o modulo Concorrencia"
  "1XoXZwF1szA|Como usar os rankings de Mercado"
  "IgarAjV88Gk|Alinhamento a demanda - App Mobile"
  "D9Rr0Be-Haw|Concorrencia - como acompanhar concorrentes"
  "vCRg-MDIEk4|Otimizador de anuncios"
  "NbSow_P0tbc|Atualizacoes Explorador de anuncios"
  "C_PQopLGWv4|Explorador de anuncios"
  "jL9HvePmmGM|Analise suas categorias"
  "NrVtkD45Bu0|Redesenho da Oportunidade"
  "3QPCJRRB7I4|Performance de Vendas"
  "I_5jI7L_1ug|Projete suas vendas"
  "XYJt8nNE6Gc|Como controlar precos"
  "zTJJDEhVHx8|Como usar as palavras mais buscadas"
  "6g1bUQtU7NE|Como controlar os gastos com frete gratis"
  "If27XL2NodA|Como controlar os precos"
  "Y9XosOHBZos|Como usar Pareto 80-20"
  "5k53nm4HZjk|Como editar grupos"
  "Gsqzp23G5C4|Como adicionar usuarios"
  "g03yDDuzC08|Controle de precos BR"

  # === ESTRATEGIA E MERCADO (PT-BR) ===
  "Qz5h-uGRRI0|Como medir o desempenho da sua loja no ML"
  "AXi_kfKwu8U|Dia do Consumidor - como se preparar"
  "dUZLUyVsv7Q|Astrologia no e-commerce oportunidades"
  "0iL9Eg43sEo|Como criar anuncios que vendem no ML"
  "JzV7_rF_BtE|Carnaval no e-commerce sazonalidade"
  "tn6apGiuj0A|Estrategias para 2026 crescimento"
  "LE6wWdGMPW4|Tendencias primeiro trimestre"
  "h1pvc4b1RU4|Algoritmo do Mercado Livre"
  "hOOislUq6Yk|Tendencias de mercado 2026"
  "UW7zHjKy2mc|Volta as Aulas 2026"
  "eTV48XYhYeg|Mercado Livre 2025 o que mudou"
  "ndG4kVc55Z4|Planeje 2026 calendario comercial"
  "uflg1ALlJDs|Beleza em alta tendencias"
  "kosqFbnylO8|Produtos que vendem rapido"
  "y8HDuw0I43Q|Natal e Fim de Ano alta demanda"
  "RCGCRnGdbwY|Como identificar e acompanhar demanda"
  "qEJP2ImVgvM|Produtos fitness alta demanda"
  "qCGLwlix05w|Como usar funil de vendas"
  "teb25ZxbuNY|Como usar analise de dados para vendas"
  "WLumC1JGgoE|Estrategias avancadas para vender mais no ML"
  "i0pK9VoLKhw|Utensilios de cozinha em alta"
  "ymj4EPxnENY|Dia das Criancas 2025 tendencias"
  "VWyM3mt7ztk|Produtos chineses o que vale vender"
  "jbKeSDLeupA|Qual o melhor dia para vender no marketplace"
  "tl30b34HIIY|Conta suspensa no ML como evitar"
  "Hm1-fIgQ5lk|Dia do Cliente 2025"
  "167RiGMjTz4|Produtos eletronicos tendencias"
  "-jyPxgZ_Qj8|Como comecar a vender no ML guia"
  "JwskeCVGnXM|Pet Shop tendencias e oportunidades"
  "48oXAnOXxUE|Dia dos Pais 2025 tendencias"
  "4P_tK34-fB4|Produtos de ticket baixo volume"
  "W5Pf8OnmWZU|Como usar sazonalidade"
  "4RMqG16u5NM|Oportunidades escondidas demanda insatisfeita"
  "pKeX_ewUWQ8|Tendencias Dia dos Namorados"
  "gdArR6XMmXs|Como IA esta transformando vendas online"
  "J56OOA445Jo|Nicho de motos o que vender"
  "yCO17vwLnLA|Como identificar tendencias e-commerce"
  "_RXDhn_xRvU|Fim de Ano 2025 datas estrategicas"
  "_XJxXr500L0|Black Friday 2025 prepare sua loja"

  # === WEBINARS/TREINAMENTOS LONGOS (PT-BR) ===
  "ZfMC6ibMIqg|Integracao e automacao da loja online"
  "EQ1yMbUV-jg|Como posicionar anuncios Black Friday"
  "ve_UWzZBFP8|Black Friday tendencias e impulsione negocio"
  "-THdvgULDlQ|Black Friday prepare seu negocio"
  "HhRSAq3l7mk|Black Friday marcas e empreendedores"
  "xHWiutpiEW8|Masterclass Vender em novos nichos"
  "hLfoKwyk6cg|Masterclass Como encontrar produtos para vender no ML"

  # === MODULOS DO CURSO (PT-BR) ===
  "zo8nBU0WrY0|Introducao Geral"
  "kpceiWmyKxk|Modulo 1 Lei de Pareto"
  "cBBNBAiOxpE|Modulo 1 Concentracao das suas vendas"
  "LSyAJtOzejE|Modulo 1 Compare anuncios"
  "k5OJi8aaOd8|Modulo 2 Diagnostico e Correcao"
  "deeRc6HywXs|Modulo 2 Fuga de dinheiro"
  "5Qb8PhM0etE|Modulo 3 Alinhar oferta e demanda"
  "WyIParKcG9I|Modulo 3 Micro Experimentos"
  "x8g8L5cJ63w|Modulo 4 Introducao"
  "rwZNf0UVQ0c|Modulo 4 Segredos Lucrativos"
  "SmeQf5t0xQo|Modulo 4 Nichos lucrativos"
  "yBQYDgk6FhU|Modulo 4 Ame seu concorrente"
)

echo "=== Iniciando download de ${#PT_VIDEOS[@]} videos ==="
SUCCESS=0
FAIL=0

for entry in "${PT_VIDEOS[@]}"; do
  IFS='|' read -r vid_id vid_title <<< "$entry"

  # Clean title for filename
  clean_title=$(echo "$vid_title" | sed 's/[^a-zA-Z0-9_-]/_/g' | head -c 80)
  outfile="${OUTDIR}/${clean_title}__${vid_id}"

  if [ -f "${outfile}.pt.vtt" ] || [ -f "${outfile}.pt-orig.vtt" ]; then
    echo "[SKIP] Already exists: ${vid_title}"
    ((SUCCESS++))
    continue
  fi

  echo "[DOWN] ${vid_title} (${vid_id})..."
  yt-dlp --write-auto-sub --sub-lang pt --skip-download --sub-format vtt \
    -o "${outfile}" \
    "https://www.youtube.com/watch?v=${vid_id}" 2>/dev/null

  if [ $? -eq 0 ] && ls "${outfile}"*.vtt 1>/dev/null 2>&1; then
    ((SUCCESS++))
    echo "  [OK]"
  else
    ((FAIL++))
    echo "  [FAIL] No subtitles"
  fi
done

echo ""
echo "=== RESULTADO ==="
echo "Sucesso: ${SUCCESS}"
echo "Falha: ${FAIL}"
echo "Total: ${#PT_VIDEOS[@]}"
