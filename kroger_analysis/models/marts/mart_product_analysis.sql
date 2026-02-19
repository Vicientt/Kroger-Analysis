{#
  MART: Product-level analysis (like all_products.csv flattened).
  Same grain as staging; adds computed column has_promo.
#}

with
stg as (
    select * from {{ ref('stg_kroger_products') }}
),

-- Pass through all columns and add has_promo
product_analysis as (
    select
        *,
        case
            when promo_price is not null and promo_price != 'N/A' then true
            else false
        end as has_promo
    from stg
)

select * from product_analysis
