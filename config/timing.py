"""Measures every request so slow pages can be diagnosed on the server.

- Adds a Server-Timing header (browser DevTools > Network > a request > Timing shows app/db time).
- Writes slow requests to the server log, e.g. on Render > Logs:
    [timing] SLOW 4.12s GET /search/ | database 3.80s in 41 queries
- Logs how long the first request came after the server process started (cold start).
"""
import time

from django.db import connection

SLOW_SECONDS = 1.0
_PROCESS_STARTED = time.time()
_first_request_seen = False


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        global _first_request_seen
        stats = {"queries": 0, "db": 0.0}

        def count(execute, sql, params, many, context):
            t = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                stats["queries"] += 1
                stats["db"] += time.perf_counter() - t

        started = time.perf_counter()
        with connection.execute_wrapper(count):
            response = self.get_response(request)
        total = time.perf_counter() - started

        response["Server-Timing"] = (f'app;dur={total * 1000:.0f}, '
                                     f'db;dur={stats["db"] * 1000:.0f};desc="{stats["queries"]} queries"')
        if not _first_request_seen:
            _first_request_seen = True
            print(f"[timing] first request {time.time() - _PROCESS_STARTED:.1f}s after the server process started",
                  flush=True)
        if total >= SLOW_SECONDS:
            print(f"[timing] SLOW {total:.2f}s {request.method} {request.path} | "
                  f"database {stats['db']:.2f}s in {stats['queries']} queries", flush=True)
        return response
