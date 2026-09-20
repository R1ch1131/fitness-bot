import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from config import WORKOUTS_CACHE_FILE, ROUTINES_CACHE_FILE, TEMPLATES_CACHE_FILE
from hevy_client import HevyClient

class Storage:
    """Manages local persistence and caching of Hevy workouts and routines."""

    def __init__(self, client: Optional[HevyClient] = None):
        self.client = client or HevyClient()

    def sync_all(self, verbose: bool = True) -> Dict[str, int]:
        """Downloads latest data from Hevy and updates local cache."""
        if verbose:
            print("Синхронизация с Hevy API...")

        workouts = self.client.get_all_workouts()
        with open(WORKOUTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(workouts, f, ensure_ascii=False, indent=2)

        routines = self.client.get_all_routines()
        with open(ROUTINES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(routines, f, ensure_ascii=False, indent=2)

        if verbose:
            print(f"Синхронизировано тренировок: {len(workouts)}, программ (routines): {len(routines)}")

        return {
            "workouts_count": len(workouts),
            "routines_count": len(routines)
        }

    def get_cached_workouts(self, auto_sync: bool = True) -> List[Dict[str, Any]]:
        """Returns workouts from cache, fetching from API if cache doesn't exist."""
        if not WORKOUTS_CACHE_FILE.exists():
            if auto_sync:
                self.sync_all()
            else:
                return []

        with open(WORKOUTS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_cached_routines(self, auto_sync: bool = True) -> List[Dict[str, Any]]:
        """Returns routines from cache, fetching from API if cache doesn't exist."""
        if not ROUTINES_CACHE_FILE.exists():
            if auto_sync:
                self.sync_all()
            else:
                return []

        with open(ROUTINES_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
