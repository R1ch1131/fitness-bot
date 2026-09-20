import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from config import API_KEY, API_BASE_URL

class HevyClient:
    """Client for interacting with the official Hevy REST API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or API_KEY
        self.base_url = (base_url or API_BASE_URL).rstrip("/")
        if not self.api_key:
            raise ValueError("HEVY_API_KEY is not set. Please specify it in .env or pass it to HevyClient.")

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retries: int = 3) -> Dict[str, Any]:
        """Performs a GET request to the Hevy API with automatic retries."""
        import time
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            url = f"{url}?{query}"

        headers = {
            "api-key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "HevyCoach/1.0"
        }

        last_error = None
        for attempt in range(retries):
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    content = response.read().decode("utf-8")
                    return json.loads(content)
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8") if e.fp else ""
                raise RuntimeError(f"Hevy API error ({e.code}): {e.reason}. Body: {error_body}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                reason = getattr(e, "reason", str(e))
                raise RuntimeError(f"Failed to connect to Hevy API: {reason}") from e

        raise RuntimeError(f"Request failed after {retries} attempts: {last_error}")

    def get_workouts_count(self) -> int:
        """Returns the total number of workouts logged in the account."""
        data = self._request("workouts/count")
        return data.get("workout_count", 0)

    def get_workouts(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """
        Fetches a paginated list of workouts.
        Note: Hevy API supports max pageSize=10 for workouts.
        """
        page_size = min(page_size, 10)
        return self._request("workouts", {"page": page, "pageSize": page_size})

    def get_all_workouts(self, max_pages: int = 50) -> List[Dict[str, Any]]:
        """Fetches all workouts by traversing pages."""
        workouts = []
        page = 1
        while page <= max_pages:
            res = self.get_workouts(page=page, page_size=10)
            page_items = res.get("workouts", [])
            if not page_items:
                break
            workouts.extend(page_items)
            page_count = res.get("page_count", 1)
            if page >= page_count:
                break
            page += 1
        return workouts

    def get_workout(self, workout_id: str) -> Dict[str, Any]:
        """Fetches a specific workout by ID."""
        return self._request(f"workouts/{workout_id}")

    def get_routines(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """Fetches routines (workout programs)."""
        page_size = min(page_size, 10)
        return self._request("routines", {"page": page, "pageSize": page_size})

    def get_all_routines(self) -> List[Dict[str, Any]]:
        """Fetches all routines across all pages."""
        routines = []
        page = 1
        while True:
            res = self.get_routines(page=page, page_size=10)
            page_items = res.get("routines", [])
            if not page_items:
                break
            routines.extend(page_items)
            if page >= res.get("page_count", 1):
                break
            page += 1
        return routines

    def get_exercise_templates(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """Fetches exercise templates."""
        page_size = min(page_size, 10)
        return self._request("exercise_templates", {"page": page, "pageSize": page_size})

    def get_all_exercise_templates(self, max_pages: int = 20) -> List[Dict[str, Any]]:
        """Fetches exercise templates."""
        templates = []
        page = 1
        while page <= max_pages:
            res = self.get_exercise_templates(page=page, page_size=10)
            items = res.get("exercise_templates", [])
            if not items:
                break
            templates.extend(items)
            if page >= res.get("page_count", 1):
                break
            page += 1
        return templates
