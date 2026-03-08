{#
  MART: Summary by category (like category_summary.csv).
  One row per category with: total_products, states_with_products, unique_brands.
#}

with

stg as (
    select * from {{ ref('stg_kroger_products') }}
),

-- Aggregate by category: count products, unique states, unique brands.
category_summary as (
    select
        category,
        count(*) as total_products,
        count(distinct state) as states_with_products,
        count(distinct brand) as unique_brands
    from stg
    group by category
)

select * from category_summary
order by total_products desc
