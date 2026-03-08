{#
  STAGING: Flatten raw_data (JSON) into rows per product per store per category.
  DuckDB syntax.
  One row per product with: state, store_id, store_name, category, product_id, brand, description, regular_price, promo_price, size
#}

with

raw_source as (
    select
        raw_data,
        json_extract_string(raw_data::varchar, '$.state') as state,
        json_extract_string(raw_data::varchar, '$.store_id') as store_id,
        json_extract_string(raw_data::varchar, '$.store_name') as store_name
    from {{ source('kroger_raw', 'kroger_products_raw') }}
),

flatten_categories as (
    select
        r.state,
        r.store_id,
        r.store_name,
        json_extract_string(f.val::varchar, '$.term') as category,
        json_extract(f.val::varchar, '$.products') as products_array
    from raw_source r,
    unnest(from_json(json_extract(r.raw_data::varchar, '$.search_results'), '["JSON"]')) as f(val)
),

flatten_products as (
    select
        fc.state,
        fc.store_id,
        fc.store_name,
        fc.category,
        json_extract_string(p.val::varchar, '$.productId') as product_id,
        json_extract_string(p.val::varchar, '$.brand') as brand,
        json_extract_string(p.val::varchar, '$.description') as description,
        json_extract_string(json_extract(p.val::varchar, '$.items[0].price'), '$.regular') as regular_price,
        json_extract_string(json_extract(p.val::varchar, '$.items[0].price'), '$.promo') as promo_price,
        json_extract_string(json_extract(p.val::varchar, '$.items[0]'), '$.size') as size
    from flatten_categories fc,
    unnest(from_json(json_extract(fc.products_array::varchar, '$'), '["JSON"]')) as p(val)
)

select * from flatten_products
