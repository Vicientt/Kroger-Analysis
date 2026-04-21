{#
  staging: read from raw.kroger_products_all, map cols
#}

select
    "State" as state,
    "Store Name" as store_name,
    "Store ID" as store_id,
    "Product Category" as category,
    "Product ID" as product_id,
    "Description" as description,
    "Brand" as brand,
    "Regular Price" as regular_price,
    "Promo Price" as promo_price,
    "Size" as size,
    load_date
from {{ source('kroger_raw', 'kroger_products_all') }}
