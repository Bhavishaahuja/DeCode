"""HTTP client for the Stratum tools service."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import httpx


class ToolAPIError(RuntimeError):
    """Raised when the tools service rejects a call or is unavailable."""


class ToolsClient:
    def __init__(self, base_url: str, timeout: float = 12.0, log_path: Path | None = None):
        self.base_url = base_url.rstrip("/")
        self.log_path = log_path or Path(__file__).parent / "logs" / "tool_calls.jsonl"
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout)
        self._log_lock = threading.Lock()

    def close(self) -> None:
        self._http.close()

    def search_evidence(self, query: str, site: str | None = None,
                        system: str | None = None, k: int = 8) -> dict[str, Any]:
        return self._post("search_evidence", "/tools/search_evidence", {
            "query": query, "site": site, "system": system, "k": k,
        })

    def get_claims(self, site: str | None = None, system: str | None = None) -> dict[str, Any]:
        result, fallback = self._request("get_claims", "POST", "/tools/claims", {
            "site": site, "system": system,
        })
        result["_fallback"] = fallback
        return result

    def get_presets(self) -> dict[str, Any]:
        return self._request("get_presets", "GET", "/tools/presets", None)[0]

    def estimate(self, **values: Any) -> dict[str, Any]:
        return self._post("estimate", "/tools/estimate", values)

    def haul_force(self, **values: Any) -> dict[str, Any]:
        return self._post("haul_force", "/tools/haul_force", values)

    def carbon(self, **values: Any) -> dict[str, Any]:
        return self._post("carbon", "/tools/carbon", values)

    def _post(self, name: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(name, "POST", path, payload)[0]

    def _request(self, name: str, method: str, path: str,
                 payload: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
        started = time.perf_counter()
        status_code = None
        try:
            response = self._http.request(method, path, json=payload)
            status_code = response.status_code
            response.raise_for_status()
            result = response.json()
            fallback = response.headers.get("X-Stratum-Fallback") is not None
            self._write_log({
                "tool": name,
                "method": method,
                "path": path,
                "input": payload,
                "output": result,
                "status": status_code,
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "fallback": fallback,
            })
            return result, fallback
        except (httpx.HTTPError, ValueError) as error:
            detail: Any = str(error)
            if isinstance(error, httpx.HTTPStatusError):
                try:
                    detail = error.response.json()
                except ValueError:
                    detail = error.response.text
            self._write_log({
                "tool": name,
                "method": method,
                "path": path,
                "input": payload,
                "error": detail,
                "status": status_code,
                "ms": round((time.perf_counter() - started) * 1000, 1),
            })
            raise ToolAPIError(f"{name} failed: {detail}") from error

    def _write_log(self, event: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_lock:
            with self.log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(event, ensure_ascii=True) + "\n")