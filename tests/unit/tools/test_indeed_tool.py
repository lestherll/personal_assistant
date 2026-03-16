"""Unit tests for personal_assistant.tools.indeed_tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from personal_assistant.config import Settings
from personal_assistant.tools.indeed_tool import IndeedJobSearchTool, _format_results

_NO_KEY = Settings(rapidapi_key="")
_WITH_KEY = Settings(rapidapi_key="test-key")


class TestIndeedJobSearchToolStructure:
    def test_name(self) -> None:
        tool = IndeedJobSearchTool()
        assert tool.name == "indeed_job_search"

    def test_description_mentions_indeed(self) -> None:
        tool = IndeedJobSearchTool()
        assert "indeed" in tool.description.lower()

    def test_args_schema_has_query(self) -> None:
        tool = IndeedJobSearchTool()
        fields = tool.args_schema.model_fields
        assert "query" in fields

    def test_args_schema_has_location(self) -> None:
        tool = IndeedJobSearchTool()
        fields = tool.args_schema.model_fields
        assert "location" in fields

    def test_args_schema_has_num_results(self) -> None:
        tool = IndeedJobSearchTool()
        fields = tool.args_schema.model_fields
        assert "num_results" in fields


class TestIndeedJobSearchToolRun:
    def test_fallback_returned_when_no_api_key(self) -> None:
        with patch("personal_assistant.tools.indeed_tool.get_settings", return_value=_NO_KEY):
            tool = IndeedJobSearchTool()
            result = tool._run(query="Software Engineer", location="London")
        assert "RAPIDAPI_KEY" in result or "rapidapi" in result.lower()

    def test_fallback_includes_indeed_url(self) -> None:
        with patch("personal_assistant.tools.indeed_tool.get_settings", return_value=_NO_KEY):
            tool = IndeedJobSearchTool()
            result = tool._run(query="Python Developer")
        assert "indeed.com" in result

    def test_rapidapi_search_parses_results(self) -> None:
        payload = {
            "results": [
                {
                    "jobtitle": "Python Dev",
                    "company": "ACME",
                    "formattedLocation": "London",
                    "snippet": "Great role",
                    "url": "https://indeed.com/job/1",
                    "date": "2024-01-01",
                }
            ]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(payload).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("personal_assistant.tools.indeed_tool.get_settings", return_value=_WITH_KEY):
            with patch("urllib.request.urlopen", return_value=mock_response):
                tool = IndeedJobSearchTool()
                result = tool._run(query="Python Dev", location="London")

        assert "Python Dev" in result
        assert "ACME" in result

    def test_rapidapi_search_handles_request_error(self) -> None:
        with patch("personal_assistant.tools.indeed_tool.get_settings", return_value=_WITH_KEY):
            with patch("urllib.request.urlopen", side_effect=OSError("network error")):
                tool = IndeedJobSearchTool()
                result = tool._run(query="Python Dev")

        assert "failed" in result.lower()


class TestFormatResults:
    def test_empty_results(self) -> None:
        assert _format_results([]) == "No job listings found."

    def test_single_result(self) -> None:
        results = [
            {
                "jobtitle": "Engineer",
                "company": "ACME",
                "formattedLocation": "London",
            }
        ]
        output = _format_results(results)
        assert "Engineer" in output
        assert "ACME" in output

    def test_multiple_results_numbered(self) -> None:
        results = [
            {"jobtitle": "A", "company": "C1", "formattedLocation": "L1"},
            {"jobtitle": "B", "company": "C2", "formattedLocation": "L2"},
        ]
        output = _format_results(results)
        assert "1." in output
        assert "2." in output

    def test_optional_fields_included_when_present(self) -> None:
        results = [
            {
                "jobtitle": "Dev",
                "company": "Corp",
                "formattedLocation": "NYC",
                "snippet": "Exciting opportunity",
                "url": "https://example.com/job",
                "date": "2024-01-15",
            }
        ]
        output = _format_results(results)
        assert "Exciting opportunity" in output
        assert "https://example.com/job" in output
        assert "2024-01-15" in output
