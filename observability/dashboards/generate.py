#!/usr/bin/env python3
"""
Grafana dashboard generator for Tailord.
Single source of truth for all dashboard JSON.

Usage (from repo root):
  python3 observability/dashboards/generate.py           # regenerate all JSON files
  python3 observability/dashboards/generate.py --check   # CI gate: exit 1 if files are out of sync
"""

import difflib
import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


# ─── Environment configs ──────────────────────────────────────────────────────

ENVS = {
    "local": {
        "suffix":  "Local",
        "uid_sfx": "local",
        "env_lbl": "local",
        "prom": {"uid": "__PROMETHEUS_UID__", "type": "prometheus"},
        "logs": {"uid": "__LOKI_UID__",       "type": "loki"},
        "pg":   {"uid": "__POSTGRES_UID__",   "type": "postgres"},
    },
    "prod": {
        "suffix":  "Prod",
        "uid_sfx": "prod",
        "env_lbl": "production",
        "prom": {"uid": "__PROMETHEUS_UID__",    "type": "prometheus"},
        "logs": {"uid": "__AZURE_MONITOR_UID__", "type": "grafana-azure-monitor-datasource"},
        "pg":   {"uid": "__POSTGRES_UID__",      "type": "postgres"},
    },
}


# ─── Structural helpers ───────────────────────────────────────────────────────

def base_dash(uid_base, title_base, c, *, refresh="30s", time=None, templating=None):
    """Return common top-level dashboard structure."""
    return {
        "uid":           f"tailord-{uid_base}-{c['uid_sfx']}",
        "title":         f"{title_base} ({c['suffix']})",
        "schemaVersion": 39,
        "version":       1,
        "editable":      True,
        "timezone":      "utc",
        "refresh":       refresh,
        "time":          time or {"from": "now-1h", "to": "now"},
        "templating":    templating or {"list": []},
        "panels":        [],
    }


def gp(x, y, w, h):
    """Grid position shorthand."""
    return {"x": x, "y": y, "w": w, "h": h}


def panel(pid, title, ptype, grid, ds, targets, field_config=None, options=None, description=None):
    """Construct a Grafana panel dict."""
    p = {
        "id":          pid,
        "title":       title,
        "type":        ptype,
        "gridPos":     grid,
        "datasource":  ds,
        "targets":     targets,
        "fieldConfig": field_config or {"defaults": {}, "overrides": []},
    }
    if description is not None:
        p["description"] = description
    if options is not None:
        p["options"] = options
    return p


# ─── Target helpers ───────────────────────────────────────────────────────────

def pt(ref, expr, legend):
    """Prometheus target."""
    return {"refId": ref, "expr": expr, "legendFormat": legend}


def pg(ref, sql, fmt="table"):
    """PostgreSQL target."""
    return {"refId": ref, "rawSql": sql, "format": fmt}


# ─── Log panel targets (env-specific) ─────────────────────────────────────────

def _is_local(c):
    return c["uid_sfx"] == "local"


def log_scrape_failures_ts(c):
    """Scrape failures timeseries target — LogQL (local) or KQL (prod)."""
    if _is_local(c):
        return {
            "refId":        "A",
            "datasource":   c["logs"],
            "expr":         'sum by (event) (count_over_time({job="tailord-backend"} | json | event =~ `playwright_scrape_failed|playwright_timeout|job_content_invalid` [$__interval]))',
            "queryType":    "range",
            "legendFormat": "{{event}}",
        }
    return {
        "refId":      "A",
        "datasource": c["logs"],
        "queryType":  "Azure Log Analytics",
        "azureLogAnalytics": {
            "query": "\n".join([
                "ContainerAppConsoleLogs_CL",
                "| where TimeGenerated > ago(1h)",
                '| where ContainerAppName_s == "tailord-backend-prod"',
                "| extend p = parse_json(Log_s)",
                '| where tostring(p.event) in ("playwright_scrape_failed", "playwright_timeout", "job_content_invalid")',
                "| summarize count() by bin(TimeGenerated, 5m), event=tostring(p.event)",
                "| order by TimeGenerated asc",
            ]),
        },
    }


def log_scrape_failures_stat(c):
    """Scrape failures stat target — LogQL (local) or KQL (prod)."""
    if _is_local(c):
        return {
            "refId":        "A",
            "datasource":   c["logs"],
            "expr":         'sum by (event) (count_over_time({job="tailord-backend"} | json | event =~ `playwright_scrape_failed|playwright_timeout|job_content_invalid` [1h]))',
            "queryType":    "range",
            "legendFormat": "{{event}}",
        }
    return {
        "refId":      "A",
        "datasource": c["logs"],
        "queryType":  "Azure Log Analytics",
        "azureLogAnalytics": {
            "query": "\n".join([
                "ContainerAppConsoleLogs_CL",
                "| where TimeGenerated > ago(1h)",
                '| where ContainerAppName_s == "tailord-backend-prod"',
                "| extend p = parse_json(Log_s)",
                '| where tostring(p.event) in ("playwright_scrape_failed", "playwright_timeout", "job_content_invalid")',
                "| summarize count() by event=tostring(p.event)",
            ]),
        },
    }


def log_tailoring_timeline(c):
    """Per-tailoring log timeline target — LogQL (local) or KQL (prod)."""
    if _is_local(c):
        return {
            "refId":      "A",
            "datasource": c["logs"],
            "expr":       '{job="tailord-backend"} | json | tailoring_id = "$tailoring_id"',
            "queryType":  "range",
        }
    return {
        "refId":      "A",
        "datasource": c["logs"],
        "queryType":  "Azure Log Analytics",
        "azureLogAnalytics": {
            "query": "\n".join([
                "ContainerAppConsoleLogs_CL",
                "| where TimeGenerated > ago(1h)",
                '| where ContainerAppName_s == "tailord-backend-prod"',
                "| extend p = parse_json(Log_s)",
                '| where tostring(p.tailoring_id) == "$tailoring_id"',
                "| project TimeGenerated, Log_s",
                "| order by TimeGenerated asc",
            ]),
        },
    }


# ─── Dashboard 01: Platform Health ───────────────────────────────────────────

def platform_health(c):
    e = c["env_lbl"]
    d = base_dash("platform-health", "Platform Health", c)
    d["panels"] = [
        panel(1, "Request Rate by Endpoint", "timeseries", gp(0, 0, 12, 8),
              c["prom"],
              [pt("A", f'sum(rate(http_requests_total{{environment="{e}"}}[5m])) by (endpoint)', "{{endpoint}}")],
              {"defaults": {"unit": "reqps"}, "overrides": []}),
        panel(2, "HTTP Error Rate %", "stat", gp(12, 0, 6, 4),
              c["prom"],
              [pt("A", f'100 * sum(rate(http_requests_total{{status_code=~"5..",environment="{e}"}}[5m])) / sum(rate(http_requests_total{{environment="{e}"}}[5m]))', "Error Rate %")],
              {"defaults": {"unit": "percent", "thresholds": {"mode": "absolute", "steps": [
                  {"color": "green", "value": None},
                  {"color": "yellow", "value": 1},
                  {"color": "red", "value": 5},
              ]}}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}}),
        panel(3, "P50 Latency", "stat", gp(18, 0, 6, 4),
              c["prom"],
              [pt("A", f'histogram_quantile(0.50, sum(rate(http_request_duration_ms_bucket{{environment="{e}"}}[5m])) by (le))', "P50 ms")],
              {"defaults": {"unit": "ms"}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}}),
        panel(4, "Active Generations", "gauge", gp(12, 4, 6, 4),
              c["prom"],
              [pt("A", f'tailoring_active_generations{{environment="{e}"}}', "Active")],
              {"defaults": {"unit": "short", "min": 0, "max": 10, "thresholds": {"mode": "absolute", "steps": [
                  {"color": "green", "value": None},
                  {"color": "yellow", "value": 5},
                  {"color": "red", "value": 8},
              ]}}, "overrides": []}),
        panel(5, "P95 Latency by Endpoint", "timeseries", gp(0, 8, 12, 8),
              c["prom"],
              [pt("A", f'histogram_quantile(0.95, sum(rate(http_request_duration_ms_bucket{{environment="{e}"}}[5m])) by (le, endpoint))', "p95 {{endpoint}}")],
              {"defaults": {"unit": "ms"}, "overrides": []}),
        panel(6, "P95 Latency (Overall)", "stat", gp(18, 4, 6, 4),
              c["prom"],
              [pt("A", f'histogram_quantile(0.95, sum(rate(http_request_duration_ms_bucket{{environment="{e}"}}[5m])) by (le))', "P95 ms")],
              {"defaults": {"unit": "ms", "thresholds": {"mode": "absolute", "steps": [
                  {"color": "green", "value": None},
                  {"color": "yellow", "value": 2000},
                  {"color": "red", "value": 5000},
              ]}}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}}),
    ]
    return d


# ─── Dashboard 02: LLM Observability ─────────────────────────────────────────

def llm_observability(c):
    e = c["env_lbl"]
    d = base_dash("llm-observability", "LLM Observability", c)
    d["panels"] = [
        panel(1, "LLM Call Rate", "timeseries", gp(0, 0, 12, 8),
              c["prom"],
              [pt("A", f'sum(rate(llm_call_duration_ms_count{{environment="{e}"}}[5m])) by (model, prompt_type)', "{{model}} / {{prompt_type}}")],
              {"defaults": {"unit": "reqps"}, "overrides": []}),
        panel(2, "Model Distribution (24h)", "piechart", gp(12, 0, 12, 8),
              c["prom"],
              [pt("A", f'sum(increase(llm_call_duration_ms_count{{environment="{e}"}}[24h])) by (model)', "{{model}}")],
              {"defaults": {}, "overrides": []}),
        panel(3, "P50 Latency by Prompt Type", "timeseries", gp(0, 8, 12, 8),
              c["prom"],
              [pt("A", f'histogram_quantile(0.50, sum(rate(llm_call_duration_ms_bucket{{environment="{e}"}}[5m])) by (le, prompt_type))', "p50 {{prompt_type}}")],
              {"defaults": {"unit": "ms"}, "overrides": []}),
        panel(4, "P95 Latency by Prompt Type", "timeseries", gp(12, 8, 12, 8),
              c["prom"],
              [pt("A", f'histogram_quantile(0.95, sum(rate(llm_call_duration_ms_bucket{{environment="{e}"}}[5m])) by (le, prompt_type))', "p95 {{prompt_type}}")],
              {"defaults": {"unit": "ms"}, "overrides": []}),
        panel(5, "Input Tokens/s", "timeseries", gp(0, 16, 8, 7),
              c["prom"],
              [pt("A", f'sum(rate(llm_tokens_total{{direction="input",environment="{e}"}}[5m])) by (prompt_type)', "{{prompt_type}}")],
              {"defaults": {"unit": "short"}, "overrides": []}),
        panel(6, "Output Tokens/s", "timeseries", gp(8, 16, 8, 7),
              c["prom"],
              [pt("A", f'sum(rate(llm_tokens_total{{direction="output",environment="{e}"}}[5m])) by (prompt_type)', "{{prompt_type}}")],
              {"defaults": {"unit": "short"}, "overrides": []}),
        panel(7, "LLM Error Rate", "timeseries", gp(16, 16, 8, 7),
              c["prom"],
              [pt("A", f'sum(rate(llm_errors_total{{environment="{e}"}}[5m])) by (error_type)', "{{error_type}}")],
              {"defaults": {"unit": "reqps", "color": {"mode": "fixed", "fixedColor": "red"}}, "overrides": []}),
        panel(8, "LLM Retry Rate", "timeseries", gp(0, 23, 12, 7),
              c["prom"],
              [pt("A", f'sum(rate(llm_retries_total{{environment="{e}"}}[5m])) by (prompt_type)', "{{prompt_type}}")],
              {"defaults": {"unit": "reqps"}, "overrides": []}),
    ]
    return d


# ─── Dashboard 03: Tailoring Pipeline ────────────────────────────────────────

def tailoring_pipeline(c):
    e = c["env_lbl"]
    d = base_dash("tailoring-pipeline", "Tailoring Pipeline", c)
    d["panels"] = [
        panel(1, "Generation Rate by Status", "timeseries", gp(0, 0, 12, 8),
              c["prom"],
              [pt("A", f'sum(rate(tailoring_generations_total{{environment="{e}"}}[5m])) by (status)', "{{status}}")],
              {"defaults": {"unit": "reqps"}, "overrides": []}),
        panel(2, "Success Rate % (1h)", "stat", gp(12, 0, 6, 4),
              c["prom"],
              [pt("A", f'100 * sum(rate(tailoring_generations_total{{status="success",environment="{e}"}}[1h])) / sum(rate(tailoring_generations_total{{environment="{e}"}}[1h]))', "Success %")],
              {"defaults": {"unit": "percent", "thresholds": {"mode": "absolute", "steps": [
                  {"color": "red", "value": None},
                  {"color": "yellow", "value": 80},
                  {"color": "green", "value": 95},
              ]}}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}}),
        panel(3, "Total Generation P95 (1h)", "stat", gp(18, 0, 6, 4),
              c["prom"],
              [pt("A", f'histogram_quantile(0.95, sum(rate(tailoring_generation_duration_ms_bucket{{environment="{e}"}}[1h])) by (le))', "P95 ms")],
              {"defaults": {"unit": "ms", "thresholds": {"mode": "absolute", "steps": [
                  {"color": "green", "value": None},
                  {"color": "yellow", "value": 30000},
                  {"color": "red", "value": 60000},
              ]}}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}}),
        panel(4, "Phase P95 Durations", "bargauge", gp(12, 4, 12, 4),
              c["prom"],
              [pt("A", f'histogram_quantile(0.95, sum(rate(tailoring_phase_duration_ms_bucket{{environment="{e}"}}[5m])) by (le, phase))', "{{phase}}")],
              {"defaults": {"unit": "ms"}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}, "orientation": "horizontal"}),
        panel(5, "Matching Mode Distribution (24h)", "piechart", gp(0, 8, 12, 8),
              c["prom"],
              [pt("A", f'sum(increase(tailoring_generations_total{{environment="{e}"}}[24h])) by (matching_mode)', "{{matching_mode}}")],
              {"defaults": {}, "overrides": []}),
        panel(6, "Experience Processing Rate", "timeseries", gp(12, 8, 12, 8),
              c["prom"],
              [pt("A", f'sum(rate(experience_processing_total{{environment="{e}"}}[5m])) by (status)', "{{status}}")],
              {"defaults": {"unit": "reqps"}, "overrides": []}),
        panel(7, "Job Scrape Failures by Type", "timeseries", gp(0, 16, 16, 8),
              c["logs"],
              [log_scrape_failures_ts(c)],
              {"defaults": {"unit": "short"}, "overrides": []},
              description="Log-based. Events: playwright_scrape_failed (bot protection / hard error), playwright_timeout, job_content_invalid (expired/removed listing or non-job page)."),
        panel(8, "Scrape Failures (Time Range)", "stat", gp(16, 16, 8, 8),
              c["logs"],
              [log_scrape_failures_stat(c)],
              {"defaults": {"unit": "short"}, "overrides": []},
              options={"reduceOptions": {"calcs": ["sum"]}, "orientation": "horizontal"}),
    ]
    return d


# ─── Dashboard 04: Per-Tailoring Debug ───────────────────────────────────────

def per_tailoring_debug(c):
    tailoring_id_var = {
        "name":    "tailoring_id",
        "label":   "Tailoring ID",
        "type":    "textbox",
        "current": {"value": ""},
        "hide":    0,
    }
    d = base_dash("per-tailoring-debug", "Per-Tailoring Debug", c,
                  refresh="10s",
                  templating={"list": [tailoring_id_var]})
    d["panels"] = [
        panel(1, "Tailoring Metadata", "table", gp(0, 0, 24, 4),
              c["pg"],
              [pg("A", "SELECT id, generation_status, generation_stage, generation_duration_ms, model, created_at, generated_at FROM tailorings WHERE id = '$tailoring_id'::uuid")],
              {"defaults": {}, "overrides": []},
              options={"footer": {"show": False}}),
        panel(2, "Log Timeline", "logs", gp(0, 4, 24, 12),
              c["logs"],
              [log_tailoring_timeline(c)],
              {"defaults": {}, "overrides": []},
              options={"showTime": True, "showLabels": False, "wrapLogMessage": True, "sortOrder": "Ascending"}),
        panel(3, "TailoringDebugLog Events", "table", gp(0, 16, 24, 8),
              c["pg"],
              [pg("A", "SELECT created_at, event_type, payload FROM tailoring_debug_logs WHERE tailoring_id = '$tailoring_id'::uuid ORDER BY created_at ASC")],
              {"defaults": {}, "overrides": []},
              options={"footer": {"show": False}}),
    ]
    return d


# ─── Dashboard 05: User Activity ─────────────────────────────────────────────

def user_activity(c):
    d = base_dash("user-activity", "User Activity", c,
                  refresh="5m",
                  time={"from": "now-30d", "to": "now"})
    d["panels"] = [
        panel(1, "Total Users", "stat", gp(0, 0, 4, 4),
              c["pg"],
              [pg("A", "SELECT COUNT(*) AS value FROM users")],
              {"defaults": {"unit": "short"}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}}),
        panel(2, "Approved Users", "stat", gp(4, 0, 4, 4),
              c["pg"],
              [pg("A", "SELECT COUNT(*) AS value FROM users WHERE status = 'approved'")],
              {"defaults": {"unit": "short"}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}}),
        panel(3, "Experience Success Rate (7d)", "stat", gp(8, 0, 4, 4),
              c["pg"],
              [pg("A", "SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'ready') / NULLIF(COUNT(*), 0), 1) AS value FROM experiences WHERE processed_at >= NOW() - INTERVAL '7 days'")],
              {"defaults": {"unit": "percent", "thresholds": {"mode": "absolute", "steps": [
                  {"color": "red", "value": None},
                  {"color": "yellow", "value": 80},
                  {"color": "green", "value": 95},
              ]}}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}}),
        panel(4, "Generation Status Distribution", "bargauge", gp(12, 0, 12, 4),
              c["pg"],
              [pg("A", "SELECT generation_status AS metric, COUNT(*) AS value FROM tailorings GROUP BY generation_status")],
              {"defaults": {"unit": "short"}, "overrides": []},
              options={"reduceOptions": {"calcs": ["lastNotNull"]}, "orientation": "horizontal"}),
        panel(5, "Tailorings per Day (30d)", "timeseries", gp(0, 4, 12, 9),
              c["pg"],
              [pg("A", "SELECT date_trunc('day', created_at) AS time, COUNT(*) AS tailorings FROM tailorings WHERE created_at >= NOW() - INTERVAL '30 days' GROUP BY 1 ORDER BY 1", "time_series")],
              {"defaults": {"unit": "short"}, "overrides": []}),
        panel(6, "Active Users per Day (30d)", "timeseries", gp(12, 4, 12, 9),
              c["pg"],
              [pg("A", "SELECT date_trunc('day', created_at) AS time, COUNT(DISTINCT user_id) AS users FROM tailorings WHERE created_at >= NOW() - INTERVAL '30 days' GROUP BY 1 ORDER BY 1", "time_series")],
              {"defaults": {"unit": "short"}, "overrides": []}),
    ]
    return d


# ─── Dashboard registry ───────────────────────────────────────────────────────

DASHBOARDS = [
    ("01-platform-health",    platform_health),
    ("02-llm-observability",  llm_observability),
    ("03-tailoring-pipeline", tailoring_pipeline),
    ("04-per-tailoring-debug", per_tailoring_debug),
    ("05-user-activity",      user_activity),
]


# ─── Generate ─────────────────────────────────────────────────────────────────

def generate(out_root=None, quiet=False):
    if out_root is None:
        out_root = SCRIPT_DIR
    out_root = Path(out_root)

    for env_name, cfg in ENVS.items():
        env_dir = out_root / env_name
        env_dir.mkdir(parents=True, exist_ok=True)
        for fname, fn in DASHBOARDS:
            text = json.dumps(fn(cfg), indent=2) + "\n"
            (env_dir / f"{fname}.json").write_text(text)
            if not quiet:
                print(f"  wrote {env_name}/{fname}.json")

    if not quiet:
        print(f"\nGenerated {len(DASHBOARDS) * len(ENVS)} files.")


# ─── Check ────────────────────────────────────────────────────────────────────

def check():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        generate(out_root=tmp_path, quiet=True)

        out_of_sync = []
        for env_name in ENVS:
            for fname, _ in DASHBOARDS:
                committed = SCRIPT_DIR / env_name / f"{fname}.json"
                generated = tmp_path / env_name / f"{fname}.json"
                gen_text = generated.read_text()
                com_text = committed.read_text() if committed.exists() else ""
                if gen_text != com_text:
                    out_of_sync.append((env_name, fname, com_text, gen_text))

        if out_of_sync:
            print("check-dashboards FAILED: files out of sync. Run 'make generate-dashboards'.\n")
            for env_name, fname, old, new in out_of_sync:
                rel = f"{env_name}/{fname}.json"
                print(f"  {rel}")
                lines = list(difflib.unified_diff(
                    old.splitlines(keepends=True),
                    new.splitlines(keepends=True),
                    fromfile=f"committed/{rel}",
                    tofile=f"generated/{rel}",
                    n=2,
                ))
                for line in lines[:40]:
                    sys.stdout.write("    " + line)
                if len(lines) > 40:
                    print(f"    ... ({len(lines) - 40} more lines)")
                print()
            sys.exit(1)

        print("check-dashboards: OK")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    if "--check" in sys.argv:
        check()
    else:
        generate()


if __name__ == "__main__":
    main()
