{#
  MART: Summary by state (like state_summary.csv).
  One row per state with: store_name, total_products, unique_brands, categories_found.
#}

with
stg as (
    select * from {{ ref('stg_kroger_products') }}
),

-- CTE 2: state_summary
state_summary as (
    select
        state,
        max(store_name) as store_name, -- although each state has one store_name, use max to have correct value,
        count(*) as total_products,
        count(distinct brand) as unique_brands,
        count(distinct category) as categories_found
    from stg
    group by state
)

select * from state_summary
order by total_products desc
