# Mercado Livre API Registry
# Extracted from Nubimetrics Competitor Intelligence — 72 VTT Transcripts

**Source:** `MSM_Pro/docs/nubimetrics_transcripts/` (72 video transcripts)
**Generated:** 2026-03-18
**Purpose:** Comprehensive map of all ML API data used by Nubimetrics to power their competitor intelligence platform, with implementation priorities for MSM_Pro

---

## Table of Contents

1. [Priority Legend](#priority-legend)
2. [Core Seller Endpoints — P0](#core-seller-endpoints--p0)
3. [Item and Listing Endpoints — P0](#item-and-listing-endpoints--p0)
4. [Sales and Orders Endpoints — P0](#sales-and-orders-endpoints--p0)
5. [Visits and Traffic Endpoints — P0](#visits-and-traffic-endpoints--p0)
6. [Search and Demand Endpoints — P1](#search-and-demand-endpoints--p1)
7. [Category and Market Endpoints — P1](#category-and-market-endpoints--p1)
8. [Competitor and Rankings Endpoints — P1](#competitor-and-rankings-endpoints--p1)
9. [Shipping and Logistics Endpoints — P2](#shipping-and-logistics-endpoints--p2)
10. [Advertising Endpoints — P2](#advertising-endpoints--p2)
11. [Authentication Endpoints — P0](#authentication-endpoints--p0)
12. [Data Types Pulled by Nubimetrics](#data-types-pulled-by-nubimetrics)
13. [Metrics Calculated from Raw Data](#metrics-calculated-from-raw-data)
14. [Data Refresh Cadence](#data-refresh-cadence)
15. [Filters and Dimensions Available](#filters-and-dimensions-available)
16. [ML API Structure Reference](#ml-api-structure-reference)
17. [Feature-to-Endpoint Dependency Map](#feature-to-endpoint-dependency-map)

---

## Priority Legend

| Priority | Meaning | Implementation Deadline |
|----------|---------|------------------------|
| P0 | Already used or immediately required — MSM_Pro breaks without it | Sprint 2 (current) |
| P1 | High value — powers core Nubimetrics differentiators, build next | Sprint 3 |
| P2 | Medium value — needed for full feature parity with Nubimetrics | Sprint 4 |
| P3 | Low value — niche features, seasonal, or marginal intelligence value | Backlog |

---

## Core Seller Endpoints — P0

### GET /users/{seller_id}

**Priority:** P0
**Base URL:** `https://api.mercadolibre.com`
**Auth:** Bearer token (OAuth 2.0)

**Data fields extracted by Nubimetrics:**
- `id` — seller_id (ml_user_id)
- `nickname` — display name
- `seller_reputation.level_id` — medal level: `1_red`, `2_orange`, `3_yellow`, `4_light_green`, `5_green` (Platino)
- `seller_reputation.transactions.total` — total completed transactions
- `seller_reputation.transactions.ratings.positive` — positive rating percentage
- `seller_reputation.power_seller_status` — `silver`, `gold`, `platinum`
- `address.city` — geolocation for filter
- `address.state` — geolocation for filter

**Nubimetrics usage:**
- Competitor profile identification in Ranking de Vendedores
- Medal classification for market distribution analysis
- Geolocation filtering in Performance de Vendas
- Competitor tracking in the Concorrencia module

**MSM_Pro feature dependencies:**
- `GET /api/v1/auth/ml/accounts` — to display linked ML accounts
- Competitor medal badges in dashboard
- Saturation analysis (Platino medal concentration in category)

**Rate limit notes:** Standard 1 req/sec. Cache seller profiles for 24h minimum as reputation changes slowly.

---

### GET /users/{seller_id}/items/search

**Priority:** P0
**Full path:** `GET /users/{seller_id}/items/search?status=active&limit=50&offset=0`
**Auth:** Bearer token

**Query parameters:**
- `status` — `active`, `paused`, `closed`, `under_review` — filter by listing status
- `limit` — max 50 per page (default 50)
- `offset` — for pagination
- `category_id` — filter by ML category ID (e.g., `MLB1051`)
- `search_type` — `scan` for complete result sets (avoids result cap)

**Data returned:**
- `results[]` — array of item IDs (e.g., `MLB1234567890`)
- `paging.total` — total listing count
- `paging.offset` — current offset

**Nubimetrics usage:**
- Enumerating all active listings for a seller
- Building the complete listing inventory for "Meu Negocio" module
- Concorrencia module — enumerating competitor listings from their seller_id

**MSM_Pro feature dependencies:**
- Listing sync via Celery task
- Dashboard listing table
- KPI calculation requires full listing set

**Pagination strategy:** Iterate with offset until `offset >= paging.total`. Use `search_type=scan` for sellers with 1000+ listings.

---

## Item and Listing Endpoints — P0

### GET /items/{item_id}

**Priority:** P0
**Auth:** Bearer token

**Data fields extracted by Nubimetrics:**

*Pricing fields:*
- `price` — current sale price (always present, already discounted)
- `original_price` — original price before seller-applied discount
- `sale_price` — marketplace promotional price (rarely populated for seller promotions)
- `base_price` — base price used for calculations

*Listing classification:*
- `listing_type_id` — `gold_special` (Classico), `gold_premium` (Premium), `gold_pro` (Full)
- `status` — `active`, `paused`, `closed`, `under_review`
- `catalog_listing` — `true/false` — whether listing is in ML Catalog (catálogo)
- `catalog_product_id` — the catalog product ID when `catalog_listing=true`

*Shipping:*
- `shipping.mode` — `me2` (Mercado Envios), `custom`, `not_specified`
- `shipping.free_shipping` — boolean
- `shipping.tags[]` — `"self_service_in"`, `"mandatory_free_shipping"`, `"fulfillment"` (Full)
- `shipping.logistic_type` — `fulfillment` (Full), `drop_off`, `xd_drop_off`, `cross_docking`

*Inventory and attributes:*
- `available_quantity` — current stock
- `sold_quantity` — total units sold (lifetime)
- `condition` — `new`, `used`
- `title` — full listing title
- `category_id` — ML category ID (full path, e.g., `MLB1051`)
- `attributes[]` — product technical specifications (ficha técnica)
  - `id` — attribute identifier
  - `name` — attribute label
  - `value_name` — attribute value
- `pictures[]` — array of image objects
  - `url` — image URL
  - `size` — resolution
- `tags[]` — `"good_quality_picture"`, `"good_quality_thumbnail"`, `"immediate_payment"`, `"dragged_visits_and_conversions"`, `"best_seller_candidate"`
- `health` — ML's own listing health score (0-100)

*Seller data:*
- `seller_id` — owner seller ID
- `seller_address.city.name` — city of seller
- `seller_address.state.name` — state of seller

**Batch endpoint (P0 — CRITICAL for performance):**
`GET /items?ids=MLB111,MLB222,MLB333` — returns up to 20 items per call. Reduces API calls by 20x.

**Nubimetrics usage:**
- Full listing data for Explorador de Anuncios (10,000 result exports)
- Listing quality analysis (Otimizador de Anuncios — 4 composite indices)
- Catálogo vs tradicional classification
- Shipping type distribution (Flex/Full/standard breakdown)
- Price comparison across competitor listings
- SKU registration via EAN/GTIN, part number, and brand fields

**MSM_Pro feature dependencies:**
- `GET /api/v1/listings/` — listing table
- Price history snapshots
- `original_price` for detecting discounted listings
- `listing_type_id` for ML fee calculation (Classico 11%, Premium 16%, Full 16%+frete)
- `catalog_listing` flag for catálogo sales segmentation

---

### GET /items/{item_id}/variations

**Priority:** P2
**Auth:** Bearer token

**Data fields:**
- `variations[]` — array of SKU variants
  - `id` — variation ID
  - `price` — variation-specific price
  - `available_quantity` — variation stock
  - `sold_quantity` — variation units sold
  - `attribute_combinations[]` — e.g., `[{id: "COLOR", value_name: "Azul"}, {id: "SIZE", value_name: "M"}]`
  - `picture_ids[]` — photos for this variation

**Nubimetrics usage:**
- SKU-level sales analysis
- Variation-specific inventory tracking
- Understanding which variants drive revenue (80/20 at variation level)

---

### GET /items/{item_id}/description

**Priority:** P2
**Auth:** Bearer token

**Data fields:**
- `plain_text` — full listing description text

**Nubimetrics usage:**
- Listing quality scoring (description completeness)
- Micro-experiment tracking: before/after description changes

---

## Sales and Orders Endpoints — P0

### GET /orders/search

**Priority:** P0
**Full path:** `GET /orders/search?seller={seller_id}&order.date_created.from={ISO8601}&order.date_created.to={ISO8601}&sort=date_desc&limit=50&offset=0`
**Auth:** Bearer token (seller's own orders only)

**Query parameters:**
- `seller` — seller_id
- `buyer` — buyer_id (for buyer-side queries)
- `order.date_created.from` — ISO 8601 datetime
- `order.date_created.to` — ISO 8601 datetime
- `order.status` — `paid`, `pending`, `cancelled`, `invalid`
- `sort` — `date_asc`, `date_desc`
- `limit` — max 50 per page
- `offset` — pagination

**Data fields returned:**
- `results[].id` — order ID
- `results[].status` — `paid`, `pending`, `cancelled`, `invalid`
- `results[].status_detail` — granular reason (e.g., `expired`, `fraud`)
- `results[].date_created` — order creation timestamp
- `results[].date_closed` — order completion timestamp
- `results[].total_amount` — order total in local currency (BRL)
- `results[].currency_id` — `BRL`
- `results[].order_items[]` — line items
  - `item.id` — listing ID (MLB)
  - `item.title` — listing title at time of sale
  - `item.category_id` — category
  - `quantity` — units sold in this order
  - `unit_price` — price per unit at time of sale
  - `full_unit_price` — price before any discount
- `results[].shipping.id` — shipment ID
- `results[].shipping.status` — `handling`, `shipped`, `delivered`, `cancelled`
- `results[].payments[].status` — payment status
- `results[].payments[].payment_method_id` — payment method
- `results[].payments[].installments` — installment count
- `results[].buyer.id` — buyer ID

**Nubimetrics usage:**
- Revenue calculation per listing and per category
- Unit sales calculation
- Cancellation rate analysis (status_detail filtering)
- Performance de Vendas module: filters by `order.status=cancelled` (status da remessa)
- Faturamento historial vs current month comparison
- End-of-month projection calculation
- Ticket medio = `total_amount` / `quantity`
- Frete grátis cost analysis using shipping correlation

**MSM_Pro feature dependencies:**
- `GET /api/v1/listings/kpi/summary` — daily/weekly/monthly KPIs
- Revenue by listing, category, and period
- Cancellation analysis
- Ticket medio KPI

**Pagination:** Required. Use `offset` in 50-item increments until `paging.total` reached. For high-volume sellers, parallelize by date range.

---

### GET /shipments/{shipment_id}

**Priority:** P2
**Auth:** Bearer token

**Data fields:**
- `status` — shipment status
- `substatus` — detailed sub-status
- `logistic_type` — `fulfillment`, `drop_off`, `xd_drop_off`
- `mode` — `me2` (Mercado Envios)
- `shipping_option.shipping_method_id` — method
- `shipping_option.cost` — shipping cost charged to seller or buyer
- `shipping_option.currency_id` — currency
- `date_created`, `date_first_printed`, `delivered_at` — timestamps

**Nubimetrics usage:**
- Frete grátis cost tracking per listing
- Full vs Flex vs standard logistics classification
- Shipping delivery performance analysis

---

## Visits and Traffic Endpoints — P0

### GET /users/{seller_id}/items_visits

**Priority:** P0 — CRITICAL (batch endpoint, most efficient)
**Full path:** `GET /users/{seller_id}/items_visits?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`
**Auth:** Bearer token

**Data returned:**
- `date_from` — query start date
- `date_to` — query end date
- `user_id` — seller_id
- `total_visits` — aggregate visits across ALL listings
- `visits_detail[]` — per-listing breakdown
  - `item_id` — listing ID
  - `quantity` — visits for that item in the period

**Nubimetrics usage:**
- Single API call retrieves visits for ALL listings simultaneously
- Powers taxa de conversao calculation: `(orders_count / visits) * 100`
- Required for Modulo 2 Diagnostico — identifying "fuga de dinheiro" (high visits, low conversion)
- Historical visit trends per listing
- Identifying listings with traffic but no sales (price/quality problem signal)

**MSM_Pro feature dependencies:**
- Visits column in listing table
- Conversion rate per listing
- The KPI "visitas hoje" / "visitas ontem"

**Note:** This single endpoint replaces N individual item visit calls. Always prefer this over `/items/{item_id}/visits/time_window` for bulk operations.

---

### GET /items/{item_id}/visits/time_window

**Priority:** P0 — use for single-item real-time queries
**Full path:** `GET /items/{item_id}/visits/time_window?last=1&unit=day`
**Auth:** Bearer token

**Query parameters:**
- `last` — number of time units to look back (integer)
- `unit` — `day`, `week`, `month`
- `ending` — ISO date for end of window (optional, defaults to now)

**Data returned:**
- `item_id` — listing ID
- `date_from` — window start
- `date_to` — window end
- `total_visits` — visits in window
- `visits_by_day[]` — array of `{date, quantity}` objects

**Nubimetrics usage:**
- Single-listing detailed visit trend
- Real-time position monitoring for micro-experiments
- Before/after comparison when testing listing changes (free shipping, title change, photo quality)

---

## Search and Demand Endpoints — P1

### GET /trends/{site_id}

**Priority:** P1 — powers Ranking de Demanda and demand alignment scoring
**Full path:** `GET /trends/{site_id}` where `site_id = MLB` (Brazil)
**Auth:** Public (no auth required for basic) / Bearer for extended data

**Data returned:**
- `keyword` — search term
- `url` — ML search URL for the term
- List of top trending searches nationally

**Nubimetrics usage:**
- Ranking de Demanda top searches (updated daily)
- Keyword volume data used in Demand Alignment scoring (0-10 scale)
- Daily top searches shown in Modulo 3 (less stable than monthly)

---

### GET /trends/{site_id}/search

**Priority:** P1
**Full path:** `GET /trends/{site_id}/search?q={keyword}`
**Auth:** Bearer token

**Data returned:**
- `keyword` — the queried term
- `related_terms[]` — terms buyers also searched
- `trend` — relative search volume score

**Nubimetrics usage:**
- Keyword expansion for listing titles
- Finding related search terms buyers use
- Demand alignment word suggestion engine

---

### GET /sites/{site_id}/search

**Priority:** P1 — most important endpoint for supply-side data
**Full path:** `GET /sites/{site_id}/search?q={keyword}&category={cat_id}&sort={criteria}&limit=50&offset=0`
**Auth:** Public (no auth) / Bearer for extended data

**Query parameters:**
- `q` — search term (keyword)
- `category` — ML category ID (e.g., `MLB1051`)
- `sort` — `relevance`, `price_asc`, `price_desc`, `sold_quantity_desc` (vendas desc)
- `listing_type_id` — `gold_special`, `gold_premium` — filter by listing type
- `filters[FULL_TEXT_SEARCH]` — full text match
- `filters[catalog_listing]` — `true/false` — filter catálogo listings
- `filters[SHIPPING]` — `fulfillment` (Full), `le` (Flex)
- `filters[BRAND]` — brand filter
- `filters[OFFICIAL_STORE]` — filter official stores
- `price_from`, `price_to` — price range filter
- `limit` — max 50 per page (up to 1000 total results via offset)
- `offset` — pagination

**Data returned per result:**
- `results[].id` — listing ID
- `results[].title` — listing title
- `results[].price` — current price
- `results[].original_price` — pre-discount price
- `results[].condition` — `new`, `used`
- `results[].sold_quantity` — units sold (lifetime)
- `results[].available_quantity` — current stock
- `results[].listing_type_id` — Classico/Premium/Full indicator
- `results[].shipping.free_shipping` — free shipping flag
- `results[].shipping.logistic_type` — `fulfillment` for Full
- `results[].seller.id` — seller ID
- `results[].seller.nickname` — seller nickname
- `results[].catalog_listing` — in catalog or not
- `results[].catalog_product_id` — catalog product identifier
- `results[].tags[]` — ML-assigned tags
- `results[].winner_item_id` — winner listing in catalog group
- `filters[]` — available filter facets with counts
- `available_filters[]` — additional filterable dimensions
- `sort.id` — current sort criteria
- `available_sorts[]` — other sort options
- `paging.total` — total matching listings
- `paging.primary_results` — count of main results (vs related)

**Nubimetrics usage:**
- Explorador de Anuncios — searches the ML marketplace by keyword
- Ranking de Publicacoes — sorted by `sold_quantity` to find best-selling listings
- Market saturation analysis: `paging.total` = total supply for a keyword
- Demand vs supply ratio calculation
- Price range mapping across a category
- Brand filtering for Ranking de Marcas
- Catálogo filtering for catálogo-specific analysis
- Full/Flex filtering for shipping type distribution
- Export up to 10,000 results (200 pages x 50 per page via offset)

**MSM_Pro feature dependencies:**
- Competitor discovery and tracking
- Market opportunity analysis
- Keyword demand vs listing supply ratio

---

### GET /sites/{site_id}/search (trending/top sellers)

**Priority:** P1
**Full path:** `GET /sites/{site_id}/search?category={cat_id}&sort=sold_quantity_desc&limit=50`

**Nubimetrics usage:**
- Ranking de Publicacoes — top-selling listings in a category sorted by units sold
- Modern seller research methodology: check ranking dos mais vendidos FIRST, then cross-reference with demand data to avoid oversaturated categories
- Identifies products with revenue but low competition (demand-side opportunity)

---

## Category and Market Endpoints — P1

### GET /sites/{site_id}/categories

**Priority:** P1
**Full path:** `GET /sites/{site_id}/categories` where `site_id = MLB`
**Auth:** No auth required

**Data returned:**
- `id` — top-level category ID
- `name` — category name
- `total_items_in_this_category` — total active listings

**Nubimetrics usage:**
- Root category tree for Analise de Categorias navigation
- Level 1 (L1) category filter in Explorador de Anuncios
- Building category hierarchy for ranking views

---

### GET /categories/{category_id}

**Priority:** P1
**Auth:** No auth required

**Data returned:**
- `id` — category ID
- `name` — category name
- `path_from_root[]` — full category path from L1 to final (leaf) category
  - `id` — ancestor category ID
  - `name` — ancestor category name
- `children_categories[]` — direct subcategories
- `settings.buying_allowed` — whether listings can exist here
- `settings.immediate_payment` — whether immediate payment is required
- `attribute_types[]` — available technical attributes for this category
- `channels[]` — marketplace channels where this category is active

**Nubimetrics usage:**
- Full category path resolution (`categoria completa` field in Explorador)
- `codigo completo da categoria` (full category code) — added in Explorador updates
- Subcategory drill-down in Analise de Categorias
- Category L1 vs final category filter separation

---

### GET /categories/{category_id}/attributes

**Priority:** P1
**Auth:** No auth required

**Data returned:**
- `id` — attribute ID
- `name` — attribute display name
- `type` — `string`, `list`, `boolean`, `number`
- `values[]` — allowed values (for list type)
- `tags` — attribute role tags: `"catalog_required"`, `"required"`, `"recommended"`
- `relevance` — ranking importance weight

**Nubimetrics usage:**
- Otimizador de Anuncios — identifying missing technical attributes (ficha técnica completion)
- AI positioning index: which attributes top-ranked listings fill vs user's listing
- Micro-experiment suggestions: "fill these attributes to improve positioning"
- Demand alignment: which attribute values buyers filter by most

---

### GET /highlights/{site_id}/category/{category_id}

**Priority:** P1
**Full path:** `GET /highlights/{site_id}/category/{category_id}`
**Auth:** No auth required / Bearer for more data

**Data returned:**
- Top highlighted/featured listings in the category
- Ranking position data
- `items[]` — ordered list of featured item IDs

**Nubimetrics usage:**
- Category ranking monitoring (who is in position 1-10)
- Tracking movement of competitor listings in rankings
- Micro-experiments: measuring before/after position change

---

### GET /sites/{site_id}/listing_exposures

**Priority:** P2
**Auth:** No auth required

**Data returned:**
- Exposure level definitions: `gold_special` (Classico), `gold_premium` (Premium)
- Price per listing type
- Benefits per type (visibility multiplier estimates)

**Nubimetrics usage:**
- Classico vs Premium filter in Projete suas Vendas (tipo de exposicao filter)
- Fee calculation basis

---

## Competitor and Rankings Endpoints — P1

### GET /items/{item_id}/product_identifiers

**Priority:** P2
**Auth:** Bearer token

**Data returned:**
- `ean` — EAN/GTIN barcode
- `part_number` — manufacturer part number
- `brand` — brand name
- `model` — model identifier
- `sku` — seller's own SKU

**Nubimetrics usage:**
- SKU field in Explorador de Anuncios
- EAN/GTIN registration for catalog product matching
- Part number for identifying identical products across competitors

---

### GET /items/{item_id}/catalog_item

**Priority:** P1
**Auth:** Bearer token

**Data returned:**
- `catalog_product_id` — canonical product in ML catalog
- `catalog_listing` — whether item is in catalog
- `winner_item_id` — the current buy-box winner for this catalog product
- `is_catalog_winner` — whether this specific listing currently wins the buy box

**Nubimetrics usage:**
- Ranking do Catalogo — groups sales by product/model across all vendors
- Identifying who wins the catalog buy-box
- Catálogo percentage calculation in category analysis
- Market share analysis: catalog listings vs traditional listings

---

### GET /sites/{site_id}/search?seller_id={id}

**Priority:** P1
**Full path:** `GET /sites/{site_id}/search?seller_id={seller_id}&sort=sold_quantity_desc`
**Auth:** No auth required

**Data returned:**
- All listings from a specific seller, sortable by sold_quantity
- Same fields as standard search results

**Nubimetrics usage:**
- Ranking de Vendedores — top earners per category with their full listing portfolio
- Competitor analysis: viewing all listings a competitor sells
- Growing vendor identification (new entrants gaining market share)
- Explorador de Anuncios vendor filter

---

### GET /users/{seller_id}/items/search (competitor variation)

**Priority:** P1
**Used for:** Configuring concorrencia — after finding a competitor via search, track their full listing catalog

**Nubimetrics usage:**
- Concorrencia module: after identifying competitor seller, enumerate ALL their listings
- Configure which competitor listings to track vs user's own listings
- Competitor snapshot: track price, stock, visits delta, sold_quantity delta daily

---

## Shipping and Logistics Endpoints — P2

### GET /sites/{site_id}/shipping_methods

**Priority:** P2
**Auth:** No auth required

**Data returned:**
- Shipping method definitions
- `id` — method ID
- `name` — method name (e.g., "Mercado Envios", "Flex", "Full")
- `delivery_time` — estimated delivery days
- `tracking` — tracking availability

**Nubimetrics usage:**
- Flex vs Full vs standard classification
- Shipping type distribution in Performance de Vendas
- Micro-experiment: adding Flex or Full and measuring position change

---

### GET /items/{item_id}/shipping_options

**Priority:** P2
**Auth:** No auth required (buyer perspective) / Bearer for seller

**Data returned:**
- Available shipping options for a listing
- `options[]` — list of shipping methods with costs and estimated times
- `free_shipping_flag` — whether free shipping applies

**Nubimetrics usage:**
- Frete gratis cost analysis
- Custo medio de frete gratis in Projete suas Vendas
- Shipping cost impact on margin calculation

---

## Advertising Endpoints — P2

### GET /sites/{site_id}/ads/{ad_id}

**Priority:** P2
**Note:** Mercado Ads / EDS (Endorsed by Seller) API — separate from core ML API

**Context from transcripts:**
Nubimetrics references "Mercado Ads" (also called "Mercado EDS") as a key algorithm factor. ML's ads system gives boosted visibility. The ads API is separate from the main API and requires additional authorization scopes.

**Nubimetrics usage:**
- Identifying which listings are boosted by Mercado Ads
- Understanding why certain listings appear above organic results
- Advising sellers to use Central de Promocoes (1M daily visits to offers section)
- Mercado Ads integration as a positioning lever alongside organic optimization

**Scopes required:** `read` + `ads:read` (additional OAuth scope)
**Base URL for ads:** `https://api.mercadolibre.com/advertising` (separate namespace)

---

### GET /users/{seller_id}/promotions

**Priority:** P2
**Full path:** `GET /users/{seller_id}/promotions`
**Auth:** Bearer token with `promotions:read` scope

**Data returned:**
- Active promotional deals
- `type` — `price_discount`, `bundle`, `free_shipping`
- Discount percentage and effective dates
- Participation in Central de Promocoes

**Nubimetrics usage:**
- Promotion identification in listing analysis
- Distinguishing vendor promotions (uses `original_price`) from marketplace promotions (`sale_price`)
- Tracking competitor promotional activity

---

## Authentication Endpoints — P0

### POST /oauth/token

**Priority:** P0 — all other endpoints depend on this
**Full path:** `POST https://api.mercadolibre.com/oauth/token`
**Content-Type:** `application/x-www-form-urlencoded`

**Grant types:**

*Authorization code (initial OAuth):*
```
grant_type=authorization_code
&code={auth_code}
&redirect_uri={redirect_uri}
&client_id={app_id}
&client_secret={secret}
```

*Refresh token (renew expired access):*
```
grant_type=refresh_token
&refresh_token={stored_refresh_token}
&client_id={app_id}
&client_secret={secret}
```

**Response data:**
- `access_token` — Bearer token (expires ~6 hours)
- `token_type` — `bearer`
- `expires_in` — seconds until expiry (typically 21600 = 6h)
- `scope` — granted permissions
- `user_id` — ML seller ID (ml_user_id)
- `refresh_token` — long-lived token for renewal

**ML Authorization URL (Brazil):**
```
https://auth.mercadolivre.com.br/authorization?response_type=code
&client_id={app_id}
&redirect_uri={redirect_uri}
```

**Nubimetrics usage:**
- Per-account token management
- Multi-account support (one token set per ML account)
- Automatic refresh before expiry

**MSM_Pro implementation notes:**
- CRITICAL: Store tokens in database encrypted, NOT plaintext (known critical problem #2)
- Refresh proactively at 5h mark, not after expiry
- Each ML account in multi-account setup has independent token lifecycle

---

---

## Data Types Pulled by Nubimetrics

Based on transcript analysis, Nubimetrics pulls the following data categories from the ML API:

### Category 1: Demand Data (Search/Keyword Intelligence)
- **Search term volume** — how many times each keyword is searched per month
- **Keyword trends** — monthly historical trend (more stable than daily)
- **Daily top searches** — current day's trending terms (volatile)
- **Related search terms** — buyer search expansion suggestions
- **Search volume per term** — absolute demand for specific keywords

**Primary endpoint:** `GET /trends/MLB` and `GET /trends/MLB/search?q={keyword}`
**Update frequency:** Monthly historical (stable), Daily current

### Category 2: Supply Data (Listings/Market Inventory)
- **Total listing count** per keyword/category (market saturation indicator)
- **Listing type distribution** — % Classico vs Premium (destaque type)
- **Catálogo percentage** — what fraction of market is catalog listings
- **Shipping distribution** — % Full, % Flex, % standard
- **Brand distribution** — market share by brand
- **Price range** — min/max/median prices in a segment
- **SKU registration data** — EAN, GTIN, part number, brand from sellers

**Primary endpoint:** `GET /sites/MLB/search` with various filters
**Update frequency:** Weekly for rankings, continuous for prices

### Category 3: Sales Data (Revenue/Volume Intelligence)
- **Faturamento** — revenue per listing, per seller, per category (in BRL)
- **Unidades vendidas** — unit sales count
- **Vendas historicas** — lifetime sales tied to listing active days
- **Vendas em moeda local** — sales in local currency (30-60 day windows)
- **Sold quantity delta** — units sold between snapshots (competitor tracking)

**Primary endpoint:** `GET /orders/search`, `GET /sites/MLB/search` (sold_quantity field)
**Update frequency:** Real-time for own orders, daily snapshot for competitor sold_quantity delta

### Category 4: Visitor/Traffic Data
- **Total visitas** — visits per listing per period
- **Visitas por dia** — daily visit breakdown
- **Taxe de conversao** — visits-to-sales ratio

**Primary endpoint:** `GET /users/{id}/items_visits` (batch), `GET /items/{id}/visits/time_window`
**Update frequency:** Daily

### Category 5: Seller Profile Data
- **Medal level** — reputation tier (Platino, Gold, Silver, etc.)
- **Seller reputation score** — positive rating percentage
- **Total transactions** — lifetime completed orders
- **Power seller status** — silver, gold, platinum designation

**Primary endpoint:** `GET /users/{seller_id}`
**Update frequency:** Weekly (reputation changes slowly)

### Category 6: Category Metadata
- **Category tree** — full hierarchy from L1 to leaf
- **Required attributes** — mandatory technical specs for category
- **Catalog product structure** — how products are grouped in catálogo
- **Available filters** — what ML exposes as filterable dimensions

**Primary endpoint:** `GET /categories/{id}`, `GET /categories/{id}/attributes`
**Update frequency:** Monthly (rarely changes)

---

## Metrics Calculated from Raw Data

Nubimetrics derives all these metrics from raw ML API data — none are returned directly by ML:

### Core Business Metrics (Meu Negocio Module)

| Metric | Calculation | Source Endpoints |
|--------|------------|-----------------|
| Faturamento total | SUM(order.total_amount) | /orders/search |
| Faturamento por anuncio | SUM(order.total_amount) WHERE item.id = X | /orders/search |
| Unidades vendidas | SUM(order_items.quantity) | /orders/search |
| Ticket medio | faturamento / unidades_vendidas | /orders/search |
| Taxa de conversao | (orders_in_period / visits_in_period) * 100 | /orders/search + /items_visits |
| Projecao mensal | (faturamento_acumulado / dias_passados) * dias_mes | /orders/search |
| Valor do estoque | SUM(item.available_quantity * item.price) | /items (batch) |
| Custo medio de frete gratis | SUM(shipping_cost) / COUNT(free_shipping_orders) | /orders + /shipments |
| Gasto total frete gratis | SUM(shipping_cost WHERE free_shipping = true) | /orders + /shipments |

### Pareto/Concentration Metrics (Modulo 1)

| Metric | Calculation | Purpose |
|--------|------------|---------|
| Indice de concentracao 80/20 | Cumulative % faturamento per listing sorted desc | Identify top 20% listings |
| Anuncios eficientes | Listings in top 20% by revenue | Protect these |
| Anuncios duvidosos | Bottom 80% of listings by revenue | Liquidate or fix |
| Capital ocioso | SUM(available_quantity * cost_price) for low-turnover SKUs | Inventory optimization |

### Positioning Metrics (Otimizador de Anuncios — 4 Composite Indices)

| Index | Calculation | Source |
|-------|------------|--------|
| Indice de alinhamento de demanda | (demand_keywords_in_title / total_demand_keywords) * 10 | /trends + item.title |
| Indice de posicionamento IA | AI comparison of listing attributes vs top-ranked listings | /items + /highlights + /categories/attributes |
| Taxa de conformidade de conversao | AI match rate of listing characteristics vs top converters | /items + /orders aggregate |
| Indice de eficiencia de conversao | (seller_conversion / best_in_category_conversion) * 10 | /items_visits + /orders |
| Indice qualidade ML (health) | item.health field (ML's own score 0-100) | /items |

### Market Analysis Metrics (Mercado Module)

| Metric | Calculation | Source |
|--------|------------|--------|
| Saturacao do mercado | COUNT(results) from /search for keyword | /sites/MLB/search |
| % catálogo | COUNT(catalog_listing=true) / COUNT(all) | /sites/MLB/search |
| % Full (fulfillment) | COUNT(logistic_type=fulfillment) / COUNT(all) | /sites/MLB/search |
| % Flex | COUNT(tags contains flex) / COUNT(all) | /sites/MLB/search |
| Distribuicao por medalha | GROUP BY seller reputation level | /users (multiple) |
| Faturamento do lider | MAX(revenue) per seller in category | /orders + /users |
| GAP para o top | (leader_revenue - my_revenue) / leader_revenue | /orders aggregate |
| Score de demanda por keyword | relative search volume on 0-100 scale | /trends/MLB |

### Demand Alignment Metrics (Modulo 3)

| Metric | Calculation | Source |
|--------|------------|--------|
| Score de alinhamento | (matched_demand_words / total_demand_words) * 10 | /trends + item.title |
| Palavras no anuncio | tokenize(item.title) intersect demand_keywords | /trends + /items |
| Palavras sugeridas | demand_keywords NOT IN title, sorted by demand% | /trends + /items |
| Percentual de demanda da palavra | (word_searches / total_category_searches) * 100 | /trends |

---

## Data Refresh Cadence

Based on transcript evidence from Nubimetrics educational content:

| Data Type | Cadence | Source Evidence |
|-----------|---------|----------------|
| Ranking de Publicacoes | Weekly (accumulates to month end) | "actualizados semanalmente, acumulado hasta fin de mes" |
| Ranking de Demanda (keywords) | Weekly for historical, Daily for current | "mensal mais estavel que diario, tendencias mensais" |
| Ranking do Catalogo | Weekly | "mesma cadencia dos rankings" |
| Ranking de Marcas | Weekly | Same cadence as other rankings |
| Ranking de Vendedores | Weekly | Same cadence |
| Category performance data | Weekly | "dados da semana atual e mes anterior" |
| Own sales data (faturamento) | Real-time / Daily sync | Celery task recommendation |
| Competitor sold_quantity delta | Daily snapshot | "snapshot diario dos concorrentes" |
| Otimizador scoring | Continuous (AI learning) | "atualizado continuamente via aprendizado de IA" |
| Seller reputation/medal | Weekly | Reputation changes slowly |
| Price data | Real-time / Daily snapshot | Price monitoring requires daily pull |
| Visit data | Daily | Via /items_visits endpoint |
| Conversion rate | Daily (depends on visits + orders) | Calculated from daily data |
| Seasonal/demand trends | Monthly stable, Weekly for ranking | "trends mensais mais confiaveis" |

**Recommended MSM_Pro sync schedule:**
- 06:00 BRT daily — `/orders/search`, `/items_visits`, `/items` batch (price/stock)
- Weekly (Sunday 02:00) — category rankings, seller reputation updates
- On-demand — triggered by user when they want fresh competitor data

---

## Filters and Dimensions Available

The following filters are available in Nubimetrics and map to ML API parameters:

### Explorador de Anuncios Filters

| Filter | ML API Parameter | Values |
|--------|-----------------|--------|
| Categoria L1 | `category` (top-level) | ML category IDs |
| Categoria final (leaf) | `category` (leaf category ID) | ML leaf category IDs |
| Catálogo | `filters[catalog_listing]` | `true`, `false` |
| Flex | `filters[SHIPPING]` = `le` | Flex shipping tag |
| Full | `filters[SHIPPING]` = `fulfillment` | Fulfillment logistics |
| Marca | `filters[BRAND]` | Brand string |
| Tipo de anuncio | `listing_type_id` | `gold_special`, `gold_premium` |
| Periodo (30 vs 60 dias) | Date range on /orders/search | 30d or 60d window |

### Performance de Vendas Filters (Meu Negocio)

| Filter | Implementation Source |
|--------|----------------------|
| Catálogo sales only | `catalog_listing=true` on item lookup |
| Envio type (Full/Flex/standard) | `shipping.logistic_type` from /items |
| SKU | Internal MSM_Pro SKU mapping |
| Status da remessa (including canceladas) | `order.status=cancelled` in /orders/search |
| Destaque type (Classico/Premium) | `listing_type_id` from /items |
| Geolocalização | `seller_address.state` from /users + order buyer location |
| Payment status | `payments[].status` from /orders/search |

### Projete suas Vendas Filters

| Filter | Implementation |
|--------|---------------|
| Categoria | Filter /orders by item.category_id |
| Tipo de exposicao (Classico/Premium) | Filter by item.listing_type_id |

### Analise de Categorias Sort Dimensions

| Sort/Dimension | Calculation |
|----------------|------------|
| Ranking | Position in category ranking (by revenue) |
| Faturamento | Total revenue for category period |
| Eficiencia de conversao | Conversion rate vs category average |
| Faturamento do lider | Max revenue by any single seller |
| Variacao (growth) | Current month vs previous month delta |

---

## ML API Structure Reference

### Rate Limiting

| Plan | Calls/sec | Calls/day |
|------|-----------|-----------|
| Free (no app) | 0.5/sec | 3,600/day |
| Standard app | 1/sec | 86,400/day |
| Enterprise | 10/sec | Custom |

**MSM_Pro strategy:**
- Use batch endpoints wherever possible (`/items?ids=...` for up to 20 items)
- Use `/users/{id}/items_visits` (1 call = all listings) instead of per-item visit calls
- Implement exponential backoff on 429 responses
- Cache category metadata for 24h minimum
- Cache seller profiles for 6h minimum

### OAuth 2.0 Scopes Required

| Scope | Required For |
|-------|-------------|
| `read` | All basic GET endpoints |
| `write` | Item modifications (not used by MSM_Pro) |
| `offline_access` | Refresh token grant (REQUIRED for persistent auth) |
| `orders` | /orders/search endpoint |
| `promotions:read` | /users/{id}/promotions |
| `ads:read` | Mercado Ads API |

**Auth URL (Brazil):** `https://auth.mercadolivre.com.br/authorization`
**Token URL:** `https://api.mercadolibre.com/oauth/token`
**Token expiry:** 21,600 seconds (6 hours)
**Refresh token expiry:** Variable, up to 6 months with use

### Webhook Events (Notifications API)

**Base path:** `GET /users/{id}/applications/{app_id}/feed`
**Webhook registration:** `POST /users/{id}/applications/{app_id}/feed`

| Topic | Event | Relevance |
|-------|-------|-----------|
| `orders_v2` | `created`, `payment.updated` | New sale notification |
| `items` | `updated`, `listed`, `delisted` | Competitor listing changes |
| `questions` | `created` | Question monitoring |
| `visits` | `updated` | Visit spike alerts |
| `prices` | `updated` | Competitor price change alert |
| `stock` | `updated` | Stock level changes |

**Nubimetrics usage:**
- Real-time competitor price change alerts (Modulo 2 — "Alerta automatico quando concorrente muda preco")
- Near real-time listing change detection
- Competitor stock-out detection (opportunity window)

**MSM_Pro relevance:** Webhooks would replace the daily Celery polling approach for critical events. Currently not implemented (noted as pending feature in CLAUDE.md).

### Sandbox Environment

- **Sandbox base URL:** `https://api.mercadolibre.com` (same URL, different test credentials)
- **Test users:** Create via `POST /users/test_user`
- **Test items:** Use `test_item` flag in item creation
- **Auth for sandbox:** Same OAuth flow with sandbox app credentials

---

## Feature-to-Endpoint Dependency Map

Maps each major Nubimetrics feature (and its MSM_Pro equivalent) to required endpoints:

### Meu Negocio Module

| Feature | Required Endpoints | Priority |
|---------|-------------------|----------|
| Dashboard KPIs (faturamento, unidades, ticket medio) | /orders/search | P0 |
| Listing table with price, stock, visits, conversao | /items?ids + /items_visits | P0 |
| Valor do estoque | /items (price + quantity) | P0 |
| Projete suas Vendas (monthly projection) | /orders/search (current month) | P0 |
| Lei de Pareto / 80-20 listing concentration | /orders/search (all listings) | P0 |
| Fuga de dinheiro (high visits, low conversion) | /orders/search + /items_visits | P1 |
| Vendas historicas (lifecycle-adjusted) | /orders/search + item.date_created | P1 |
| Sazonalidade graph (12-month trend) | /orders/search (monthly aggregates) | P1 |
| Filter by catálogo | /items (catalog_listing) + /orders | P1 |
| Filter by envio type (Full/Flex) | /items (logistic_type) + /orders | P1 |
| Filter by order status (canceladas) | /orders/search (status filter) | P1 |
| Gasto total frete gratis | /orders + /shipments | P2 |

### Mercado Module — Rankings

| Feature | Required Endpoints | Priority |
|---------|-------------------|----------|
| Ranking de Demanda (keywords, buyer searches) | /trends/MLB | P1 |
| Ranking de Publicacoes (best-selling listings) | /sites/MLB/search (sort=sold_quantity_desc) | P1 |
| Ranking do Catalogo (by product model) | /sites/MLB/search + /items (catalog_product_id) | P1 |
| Ranking de Marcas (by brand) | /sites/MLB/search (filters[BRAND]) | P1 |
| Ranking de Vendedores (top earners) | /sites/MLB/search + /users | P1 |
| Market saturation (supply count) | /sites/MLB/search (paging.total) | P1 |
| Category distribution (medal, catálogo, envio) | /sites/MLB/search + /users | P1 |
| Faturamento do lider da categoria | /sites/MLB/search + /orders (if accessible) | P2 |

### Analise de Categorias

| Feature | Required Endpoints | Priority |
|---------|-------------------|----------|
| Category list with sales (current month) | /categories + /sites/MLB/search | P1 |
| Subcategory drill-down | /categories/{id} children | P1 |
| GAP to reach top 50/10/3/leader | /sites/MLB/search ranking analysis | P1 |
| Nearest 10 competitors with medal + revenue | /sites/MLB/search + /users | P1 |
| Growth/seasonality graph | Historical /sites/MLB/search + /trends | P2 |
| AI conversion efficiency suggestions | /categories/attributes + /items analysis | P2 |

### Concorrencia Module

| Feature | Required Endpoints | Priority |
|---------|-------------------|----------|
| Explorador de Anuncios (keyword search with sales) | /sites/MLB/search | P1 |
| Configure competitors (by publication or vendor) | /users/{id}/items/search | P1 |
| Competitor listing group comparison | /items?ids + /items_visits | P1 |
| Price variation tracking | /items (price, original_price) daily snapshot | P1 |
| Sold quantity delta (daily competitor change) | /items (sold_quantity) daily diff | P1 |
| Visits, conversion per listing | /items_visits | P1 |
| Competitor vendor analysis (all their listings) | /sites/MLB/search?seller_id= | P1 |

### Otimizador / Diagnostico

| Feature | Required Endpoints | Priority |
|---------|-------------------|----------|
| Demand alignment index | /trends/MLB + item.title | P1 |
| AI positioning index | /highlights/{category} + /items + /categories/attributes | P1 |
| Conversion conformity rate | /orders aggregate + /items_visits | P1 |
| Conversion efficiency index | Own conversion vs category best | P1 |
| ML quality health score | item.health field from /items | P0 |
| Attribute completeness (ficha técnica) | /categories/attributes + /items | P2 |
| Micro-experiment positioning before/after | /items + /highlights (repeated polling) | P2 |
| Demand word alignment scoring (0-10) | /trends/MLB + /items (title parsing) | P1 |
| Mobile demand alignment view | /trends/MLB (same data, different UI) | P2 |

---

## Implementation Notes for MSM_Pro

### Immediate Actions (Sprint 2 — In Progress)

1. **Batch items fetch:** Replace N individual `/items/{id}` calls with `/items?ids=id1,id2,...` (20 per call). Reduces Celery sync time by ~95%.

2. **Visits batch:** Ensure `/users/{id}/items_visits` is used (1 call for all listings) — do NOT iterate per-item. This is already noted in CLAUDE.md as a planned improvement.

3. **Orders pagination:** Implement proper offset-based pagination on `/orders/search` for sellers with 50+ orders per day.

4. **KPI fix:** Use `COUNT(DISTINCT listing_id)` not `COUNT(snapshot.id)` — already identified as critical bug.

### Sprint 3 Priorities (New Work)

1. **Trends/demand data:** Implement `/trends/MLB` and `/trends/MLB/search` integration to power keyword demand scoring.

2. **Market search:** Implement `/sites/MLB/search` for competitor listing discovery and market analysis.

3. **Category metadata:** Pull and cache `/categories/{id}` and `/categories/{id}/attributes` for listing quality analysis.

4. **Catalog detection:** Use `catalog_listing` field from `/items` to segment catálogo vs traditional sales.

5. **Competitor tracking:** Implement daily sold_quantity snapshot diffs for tracked competitor listings.

### Known API Constraints

- `/sites/MLB/search` returns max 1000 results per query (offset cap at 950 with limit 50). For complete market scans use multiple filtered queries.
- `/orders/search` requires seller to have authorized the app — cannot read competitor orders (only own).
- `sold_quantity` on `/sites/MLB/search` results is a cumulative lifetime counter — calculate delta between daily snapshots to get periodic sales.
- Trends API may have different rate limits from core API. Confirm at `https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br`.
- Webhook notifications require a publicly accessible HTTPS endpoint — Railway deployment satisfies this requirement.
- Large ML accounts (10,000+ listings) require `search_type=scan` parameter to avoid result truncation.

---

*Registry compiled from: 72 Nubimetrics video transcripts (VTT format), MSM_Pro/CLAUDE.md existing endpoint documentation, and Mercado Livre official API documentation references.*
*All endpoints use base URL: `https://api.mercadolibre.com` (note: "libre" not "livre")*
