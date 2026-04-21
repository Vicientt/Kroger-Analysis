TZ ?= America/Chicago

run:
	uv run python main.py

serve:
	uv run prefect flow serve prefect_flows.py:kroger_daily_flow \
		-n kroger-daily --cron "0 18 * * *" --timezone $(TZ)

stop:
	pkill -f "prefect flow serve" || true

ui:
	uv run prefect server start

dbt:
	uv run dbt run --project-dir kroger_analysis --profiles-dir kroger_analysis
