from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from pydantic import BaseModel, Field

from personal_assistant.core.tool import AssistantTool

_INDEED_API = "https://indeed-indeed.p.rapidapi.com/apisearch"


class JobSearchInput(BaseModel):
    query: str = Field(description="Job title, keywords, or company name to search for.")
    location: str = Field(
        default="",
        description="City, state, or 'remote'. Leave empty for all locations.",
    )
    num_results: int = Field(
        default=5,
        ge=1,
        le=25,
        description="Number of job listings to return (1-25).",
    )


class IndeedJobSearchTool(AssistantTool[str]):
    """Search for job listings via the Indeed public search endpoint.

    Requires RAPIDAPI_KEY environment variable (Indeed via RapidAPI) or falls
    back to a DuckDuckGo-style job search URL if the key is absent.

    Wired into CareerAgent automatically by the default workspace factory.
    """

    name: str = "indeed_job_search"
    description: str = (
        "Search for job listings on Indeed. "
        "Useful for job searching, career research, and salary benchmarking. "
        "Provide a job title or keywords and optionally a location."
    )
    args_schema: type[BaseModel] = JobSearchInput

    def _run(self, query: str, location: str = "", num_results: int = 5) -> str:
        import os

        api_key = os.getenv("RAPIDAPI_KEY", "")
        if api_key:
            return self._search_rapidapi(query, location, num_results, api_key)
        return self._search_fallback(query, location, num_results)

    def _search_rapidapi(self, query: str, location: str, num_results: int, api_key: str) -> str:
        params = urllib.parse.urlencode(
            {
                "publisher": "2",
                "v": "2",
                "format": "json",
                "q": query,
                "l": location,
                "limit": num_results,
            }
        )
        url = f"{_INDEED_API}?{params}"
        req = urllib.request.Request(
            url,
            headers={
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "indeed-indeed.p.rapidapi.com",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode())
        except Exception as exc:
            return f"Job search request failed: {exc}"

        results: list[dict[str, Any]] = data.get("results", [])
        return _format_results(results)

    def _search_fallback(self, query: str, location: str, num_results: int) -> str:
        loc_part = f" in {location}" if location else ""
        return (
            f"No RAPIDAPI_KEY configured. "
            f"To search for '{query}'{loc_part}, set RAPIDAPI_KEY in your .env file "
            f"(sign up at https://rapidapi.com/indeed/api/indeed). "
            f"Alternatively, visit https://www.indeed.com/jobs?q={urllib.parse.quote(query)}"
            + (f"&l={urllib.parse.quote(location)}" if location else "")
        )


def _format_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No job listings found."
    lines: list[str] = []
    for i, job in enumerate(results, 1):
        title = job.get("jobtitle", "Unknown Title")
        company = job.get("company", "Unknown Company")
        loc = job.get("formattedLocation", job.get("city", "Unknown Location"))
        date = job.get("date", "")
        snippet = job.get("snippet", "")
        url = job.get("url", "")
        line = f"{i}. {title} at {company} ({loc})"
        if date:
            line += f" — posted {date}"
        if snippet:
            line += f"\n   {snippet}"
        if url:
            line += f"\n   {url}"
        lines.append(line)
    return "\n".join(lines)
