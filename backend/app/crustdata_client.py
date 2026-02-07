from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

AuthScheme = Literal["auto", "token", "bearer"]
ConcreteScheme = Literal["token", "bearer"]


class CrustDataError(RuntimeError):
    pass


class CrustDataAuthError(CrustDataError):
    pass


class CrustDataPermissionError(CrustDataError):
    pass


class CrustDataCreditsError(CrustDataError):
    pass


class CrustDataRequestError(CrustDataError):
    pass


@dataclass
class CacheEntry:
    expires_at: float
    payload: dict[str, Any]


class CrustDataClient:
    def __init__(
        self,
        token: str | None,
        auth_scheme: AuthScheme = "auto",
        base_url: str = "https://api.crustdata.com",
        timeout_seconds: float = 12.0,
        ttl_seconds: int = 90,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.auth_scheme = auth_scheme
        self.timeout_seconds = timeout_seconds
        self.ttl_seconds = max(60, min(120, ttl_seconds))
        self._client = httpx.Client(timeout=self.timeout_seconds)
        self._cache: dict[str, CacheEntry] = {}
        self._selected_scheme_by_path: dict[str, ConcreteScheme] = {}

    def get_company_enrich(
        self,
        company_domain: str | list[str],
        fields: list[str] | None = None,
        enrich_realtime: bool | None = None,
    ) -> dict[str, Any]:
        domains = company_domain if isinstance(company_domain, str) else ",".join(company_domain)
        params: dict[str, Any] = {"company_domain": domains}
        if fields:
            params["fields"] = ",".join(fields)
        if enrich_realtime is not None:
            params["enrich_realtime"] = str(enrich_realtime).lower()
        return self._request("GET", "/screener/company", params=params, preferred_scheme="token")

    def post_company_search(self, filters: list[dict[str, Any]], page: int = 1) -> dict[str, Any]:
        body = {"filters": filters, "page": page}
        return self._request("POST", "/screener/company/search", json_body=body, preferred_scheme="bearer")

    def post_web_search(
        self,
        query: str,
        geolocation: str | None = None,
        sources: list[str] | None = None,
        site: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        fetch_content: bool = False,
    ) -> dict[str, Any]:
        params = {"fetch_content": "true"} if fetch_content else None
        body: dict[str, Any] = {"query": query}
        if geolocation:
            body["geolocation"] = geolocation
        if sources:
            body["sources"] = sources
        if site:
            body["site"] = site
        if start_date:
            body["startDate"] = start_date
        if end_date:
            body["endDate"] = end_date
        return self._request("POST", "/screener/web-search", params=params, json_body=body, preferred_scheme="token")

    def post_web_fetch(self, urls: list[str]) -> dict[str, Any]:
        if not urls:
            raise ValueError("urls cannot be empty")
        if len(urls) > 10:
            raise ValueError("web-fetch supports at most 10 URLs")
        return self._request("POST", "/screener/web-fetch", json_body={"urls": urls}, preferred_scheme="token")

    def smoke_auth_probe(self) -> dict[str, Any]:
        """Try both auth schemes on endpoints we use and return scheme health without leaking token."""
        self._require_token()
        checks: list[tuple[str, str, str, dict[str, Any] | None, dict[str, Any] | None]] = [
            ("GET", "/screener/company", "token", {"company_domain": "openai.com", "fields": "company_name"}, None),
            (
                "POST",
                "/screener/company/search",
                "bearer",
                None,
                {
                    "filters": [
                        {"type": "JOB_OPPORTUNITIES", "op": "in", "value": ["Hiring"]},
                    ],
                    "page": 1,
                },
            ),
        ]
        result: dict[str, Any] = {"checks": []}
        selected = "unknown"
        for method, path, preferred, params, body in checks:
            endpoint_result = {"path": path, "preferred": preferred, "token": None, "bearer": None}
            for scheme in ("token", "bearer"):
                try:
                    self._request(method, path, params=params, json_body=body, forced_scheme=scheme, skip_cache=True)
                    endpoint_result[scheme] = "ok"
                    if scheme == preferred:
                        selected = "mixed" if selected not in ("unknown", scheme) else scheme
                except CrustDataError as exc:
                    endpoint_result[scheme] = exc.__class__.__name__
            result["checks"].append(endpoint_result)

        if selected == "unknown":
            selected = self.auth_scheme
        result["selected_scheme"] = selected
        return result

    def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        preferred_scheme: ConcreteScheme | None = None,
        forced_scheme: ConcreteScheme | None = None,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        self._require_token()

        cache_key = self._cache_key(method=method, path=path, params=params, json_body=json_body)
        now = time.time()
        if not skip_cache:
            cached = self._cache.get(cache_key)
            if cached and cached.expires_at > now:
                return cached.payload

        schemes = self._resolve_schemes(path, preferred_scheme=preferred_scheme, forced_scheme=forced_scheme)
        last_error: CrustDataError | None = None

        for scheme in schemes:
            headers = self._headers_for_scheme(scheme)
            try:
                response = self._client.request(
                    method,
                    f"{self.base_url}{path}",
                    params=params,
                    json=json_body,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise CrustDataRequestError("Crustdata request timed out.") from exc
            except httpx.HTTPError as exc:
                raise CrustDataRequestError("Failed to contact Crustdata.") from exc

            if response.status_code < 400:
                payload = self._safe_json(response)
                self._selected_scheme_by_path[path] = scheme
                if not skip_cache:
                    self._cache[cache_key] = CacheEntry(expires_at=now + self.ttl_seconds, payload=payload)
                return payload

            err = self._map_error(response)
            last_error = err
            if len(schemes) > 1 and response.status_code in (401, 403):
                continue
            raise err

        if last_error:
            raise last_error
        raise CrustDataRequestError("Crustdata request failed.")

    def _resolve_schemes(
        self,
        path: str,
        preferred_scheme: ConcreteScheme | None,
        forced_scheme: ConcreteScheme | None,
    ) -> list[ConcreteScheme]:
        if forced_scheme:
            return [forced_scheme]
        if self.auth_scheme in ("token", "bearer"):
            return [self.auth_scheme]
        remembered = self._selected_scheme_by_path.get(path)
        if remembered:
            return [remembered]

        first = preferred_scheme or "token"
        second: ConcreteScheme = "bearer" if first == "token" else "token"
        return [first, second]

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except ValueError:
            return {"raw": response.text}

    def _require_token(self) -> None:
        if not self.token:
            raise CrustDataAuthError("CRUSTDATA_TOKEN is not configured.")

    def _headers_for_scheme(self, scheme: ConcreteScheme) -> dict[str, str]:
        token = self.token or ""
        if scheme == "token":
            auth_value = f"Token {token}"
        else:
            auth_value = f"Bearer {token}"
        return {"Authorization": auth_value, "Content-Type": "application/json"}

    @staticmethod
    def _map_error(response: httpx.Response) -> CrustDataError:
        status = response.status_code
        body = response.text[:180]
        if status == 401:
            return CrustDataAuthError("Crustdata authentication failed (401).")
        if status == 403:
            return CrustDataPermissionError("Crustdata permission denied (403).")
        if status == 402:
            return CrustDataCreditsError("Crustdata credits exhausted (402).")
        if status == 400:
            return CrustDataRequestError(f"Crustdata rejected request (400): {body}")
        if status >= 500:
            return CrustDataRequestError("Crustdata upstream error.")
        return CrustDataRequestError(f"Crustdata request failed ({status}).")

    @staticmethod
    def _cache_key(
        method: str,
        path: str,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
    ) -> str:
        encoded = json.dumps(
            {
                "method": method,
                "path": path,
                "params": params or {},
                "json": json_body or {},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
