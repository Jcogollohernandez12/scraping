"""
E) Network interceptor:
Uses Playwright to intercept ALL network requests made by the browser
while loading a page. Captures API calls, JSON responses, GraphQL queries,
auth tokens in headers, and WebSocket messages.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table

console = Console()

API_PATTERNS = re.compile(
    r'/api/|/graphql|/v\d+/|\.json|/rest/|/data/|/query|/search|/fetch|/ajax',
    re.I
)


def intercept(
    url: str,
    headless: bool = True,
    wait_seconds: int = 5,
    capture_responses: bool = True,
    filter_api_only: bool = True,
) -> dict:
    """
    Open url in Playwright, intercept all network traffic.

    Returns:
        {
            "requests": [...],
            "api_calls": [...],   # filtered API/XHR calls
            "graphql": [...],     # GraphQL operations
            "json_responses": [...],
            "cookies": [...],
            "auth_headers": [...],
        }
    """
    from playwright.sync_api import sync_playwright

    requests_log = []
    responses_log = []
    json_responses = []
    graphql_ops = []
    auth_headers_found = []
    ws_messages = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        page = context.new_page()

        # ── Intercept requests ────────────────────────────────────────
        def on_request(request):
            headers = dict(request.headers)
            auth = {}
            for h in ["authorization", "x-api-key", "x-auth-token", "bearer", "token"]:
                if h in headers:
                    auth[h] = headers[h][:60] + "..." if len(headers[h]) > 60 else headers[h]

            entry = {
                "method": request.method,
                "url": request.url,
                "resource_type": request.resource_type,
                "headers": {k: v for k, v in headers.items() if k.lower() not in ["cookie", "user-agent"]},
            }

            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    body = request.post_data
                    if body:
                        try:
                            entry["body"] = json.loads(body)
                        except Exception:
                            entry["body"] = body[:500]
                except Exception:
                    pass

            if auth:
                auth_headers_found.append({"url": request.url, "auth": auth})

            requests_log.append(entry)

        # ── Intercept responses ───────────────────────────────────────
        def on_response(response):
            content_type = response.headers.get("content-type", "")
            entry = {
                "url": response.url,
                "status": response.status,
                "content_type": content_type,
            }

            if "json" in content_type:
                try:
                    body = response.body()
                    if body:
                        parsed = json.loads(body)
                        entry["json"] = parsed
                        json_responses.append({"url": response.url, "data": parsed})
                except Exception:
                    pass

            responses_log.append(entry)

        # ── WebSocket ─────────────────────────────────────────────────
        def on_websocket(ws):
            def on_message(msg):
                ws_messages.append({"url": ws.url, "data": str(msg)[:500]})
            ws.on("framereceived", on_message)

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("websocket", on_websocket)

        console.print(f"  [dim]Opening browser and intercepting network for:[/dim] {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        import time
        time.sleep(wait_seconds)

        cookies = context.cookies()
        browser.close()

    # ── Filter API calls ──────────────────────────────────────────────
    api_calls = []
    for req in requests_log:
        req_url = req["url"]
        rtype = req.get("resource_type", "")
        is_api = (
            rtype in ("xhr", "fetch") or
            API_PATTERNS.search(req_url) or
            req.get("body") is not None
        )
        if is_api or not filter_api_only:
            api_calls.append(req)

    # ── Detect GraphQL ────────────────────────────────────────────────
    for req in requests_log:
        body = req.get("body")
        if isinstance(body, dict) and ("query" in body or "mutation" in body):
            graphql_ops.append({
                "url": req["url"],
                "operation": body.get("operationName", ""),
                "query": str(body.get("query", ""))[:500],
                "variables": body.get("variables", {}),
            })

    return {
        "all_requests": requests_log,
        "api_calls": api_calls,
        "json_responses": json_responses,
        "graphql_operations": graphql_ops,
        "websocket_messages": ws_messages,
        "cookies": [{"name": c["name"], "domain": c["domain"], "value": c["value"][:30]} for c in cookies],
        "auth_headers": auth_headers_found,
        "stats": {
            "total_requests": len(requests_log),
            "api_calls": len(api_calls),
            "json_responses": len(json_responses),
            "graphql_ops": len(graphql_ops),
            "ws_messages": len(ws_messages),
        },
    }


def print_network_report(data: dict):
    stats = data.get("stats", {})
    console.print(f"\n[bold]Network Intercept Report[/bold]")
    console.print(f"  Total requests: [cyan]{stats.get('total_requests', 0)}[/cyan]")
    console.print(f"  API/XHR calls:  [cyan]{stats.get('api_calls', 0)}[/cyan]")
    console.print(f"  JSON responses: [cyan]{stats.get('json_responses', 0)}[/cyan]")
    console.print(f"  GraphQL ops:    [cyan]{stats.get('graphql_ops', 0)}[/cyan]")
    console.print(f"  WebSocket msgs: [cyan]{stats.get('ws_messages', 0)}[/cyan]")

    if data.get("api_calls"):
        table = Table(title="API Calls", show_lines=True)
        table.add_column("Method", style="yellow", no_wrap=True)
        table.add_column("URL", style="cyan", overflow="fold")
        table.add_column("Type", style="dim")
        for call in data["api_calls"][:30]:
            table.add_row(call["method"], call["url"][:100], call.get("resource_type", ""))
        console.print(table)

    if data.get("graphql_operations"):
        table = Table(title="GraphQL Operations", show_lines=True)
        table.add_column("Operation", style="yellow")
        table.add_column("Query preview", style="white", overflow="fold")
        for op in data["graphql_operations"]:
            table.add_row(op.get("operation", "anonymous"), op.get("query", "")[:150])
        console.print(table)

    if data.get("auth_headers"):
        console.print("\n[bold yellow]Auth Headers Found:[/bold yellow]")
        for entry in data["auth_headers"][:5]:
            console.print(f"  {entry['url'][:80]}")
            for k, v in entry["auth"].items():
                console.print(f"    [red]{k}[/red]: {v}")
