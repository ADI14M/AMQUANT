"""Supabase Database Gateway with RLS enforcement and test-mode fallback."""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any
import httpx
from fastapi import HTTPException, status
from backend.app.auth import AuthenticatedUser

logger = logging.getLogger("amquant.db")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


class SupabaseDbGateway:
    """Manages database operations against Supabase PostgREST API using the caller's JWT.
    
    By forwarding the caller's verified JWT in the Authorization header, PostgreSQL
    evaluates auth.uid() natively and enforces Row Level Security policies.
    """

    def __init__(self, supabase_url: str = SUPABASE_URL, anon_key: str = SUPABASE_ANON_KEY):
        self.supabase_url = supabase_url
        self.anon_key = anon_key
        # In-memory storage used for offline automated testing or unconfigured development
        self._test_mode = not (self.supabase_url and self.anon_key)
        self._memory_scenarios: dict[str, dict[str, Any]] = {}
        self._memory_history: dict[str, dict[str, Any]] = {}
        self._memory_profiles: dict[str, dict[str, Any]] = {}

    def _get_headers(self, user: AuthenticatedUser) -> dict[str, str]:
        return {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {user.jwt}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    # =========================================================================
    # PROFILES
    # =========================================================================
    async def get_profile(self, user: AuthenticatedUser) -> dict[str, Any]:
        """Fetch profile for the authenticated user."""
        if self._test_mode:
            prof = self._memory_profiles.get(str(user.id))
            if not prof:
                prof = {
                    "id": str(user.id),
                    "display_name": user.email.split("@")[0] if user.email else "Researcher",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                self._memory_profiles[str(user.id)] = prof
            return prof

        url = f"{self.supabase_url}/rest/v1/profiles?id=eq.{user.id}&select=*"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._get_headers(user))
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    return data[0]
                # If trigger hasn't fired yet or row missing, create it
                return await self.upsert_profile(user, display_name=user.email.split("@")[0] if user.email else "Researcher")
            logger.error("Failed to fetch profile: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to retrieve profile")

    async def upsert_profile(self, user: AuthenticatedUser, display_name: str) -> dict[str, Any]:
        """Update or insert display_name for the authenticated user."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if self._test_mode:
            prof = self._memory_profiles.get(str(user.id), {
                "id": str(user.id),
                "created_at": now_iso,
            })
            prof["display_name"] = display_name
            prof["updated_at"] = now_iso
            self._memory_profiles[str(user.id)] = prof
            return prof

        url = f"{self.supabase_url}/rest/v1/profiles"
        payload = {
            "id": str(user.id),
            "display_name": display_name,
            "updated_at": now_iso,
        }
        headers = self._get_headers(user)
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                data = resp.json()
                return data[0] if isinstance(data, list) and data else payload
            logger.error("Failed to upsert profile: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to update profile")

    # =========================================================================
    # SAVED SCENARIOS
    # =========================================================================
    async def create_scenario(
        self, user: AuthenticatedUser, title: str, module_name: str, scenario_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Save a new research scenario for the authenticated user."""
        scenario_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        record = {
            "id": scenario_id,
            "user_id": str(user.id),
            "title": title,
            "module_name": module_name,
            "scenario_data": scenario_data,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        if self._test_mode:
            self._memory_scenarios[scenario_id] = record
            return record

        url = f"{self.supabase_url}/rest/v1/saved_scenarios"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=self._get_headers(user), json=record)
            if resp.status_code in (200, 201):
                data = resp.json()
                return data[0] if isinstance(data, list) and data else record
            logger.error("Failed to insert scenario: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to save scenario")

    async def list_scenarios(
        self, user: AuthenticatedUser, module_name: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List scenarios owned by the authenticated user."""
        if self._test_mode:
            user_items = [
                s for s in self._memory_scenarios.values()
                if s["user_id"] == str(user.id) and (not module_name or s["module_name"] == module_name)
            ]
            # Order by created_at desc
            user_items.sort(key=lambda x: x["created_at"], reverse=True)
            return user_items[offset : offset + limit]

        query = f"user_id=eq.{user.id}&order=created_at.desc&limit={limit}&offset={offset}"
        if module_name:
            query += f"&module_name=eq.{module_name}"
        url = f"{self.supabase_url}/rest/v1/saved_scenarios?{query}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._get_headers(user))
            if resp.status_code == 200:
                return resp.json()
            logger.error("Failed to list scenarios: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to retrieve scenarios")

    async def get_scenario(self, user: AuthenticatedUser, scenario_id: str) -> dict[str, Any]:
        """Retrieve a specific scenario, enforcing ownership."""
        if self._test_mode:
            scenario = self._memory_scenarios.get(scenario_id)
            if not scenario or scenario["user_id"] != str(user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
            return scenario

        url = f"{self.supabase_url}/rest/v1/saved_scenarios?id=eq.{scenario_id}&user_id=eq.{user.id}&select=*"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._get_headers(user))
            if resp.status_code == 200:
                data = resp.json()
                if not data or len(data) == 0:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
                return data[0]
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to retrieve scenario")

    async def update_scenario(
        self,
        user: AuthenticatedUser,
        scenario_id: str,
        title: str | None = None,
        scenario_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update a scenario owned by the authenticated user."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if self._test_mode:
            scenario = self._memory_scenarios.get(scenario_id)
            if not scenario or scenario["user_id"] != str(user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
            if title is not None:
                scenario["title"] = title
            if scenario_data is not None:
                scenario["scenario_data"] = scenario_data
            scenario["updated_at"] = now_iso
            return scenario

        update_payload: dict[str, Any] = {"updated_at": now_iso}
        if title is not None:
            update_payload["title"] = title
        if scenario_data is not None:
            update_payload["scenario_data"] = scenario_data

        url = f"{self.supabase_url}/rest/v1/saved_scenarios?id=eq.{scenario_id}&user_id=eq.{user.id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(url, headers=self._get_headers(user), json=update_payload)
            if resp.status_code in (200, 204):
                data = resp.json() if resp.status_code == 200 else []
                if not data and resp.status_code == 200:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
                return data[0] if data else update_payload
            logger.error("Failed to update scenario: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to update scenario")

    async def delete_scenario(self, user: AuthenticatedUser, scenario_id: str) -> None:
        """Delete a scenario owned by the authenticated user."""
        if self._test_mode:
            scenario = self._memory_scenarios.get(scenario_id)
            if not scenario or scenario["user_id"] != str(user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
            del self._memory_scenarios[scenario_id]
            return

        url = f"{self.supabase_url}/rest/v1/saved_scenarios?id=eq.{scenario_id}&user_id=eq.{user.id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(url, headers=self._get_headers(user))
            if resp.status_code not in (200, 204):
                logger.error("Failed to delete scenario: %s %s", resp.status_code, resp.text)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to delete scenario")

    # =========================================================================
    # RESEARCH HISTORY
    # =========================================================================
    async def create_history_entry(
        self,
        user: AuthenticatedUser,
        module_name: str,
        summary: dict[str, Any],
        scenario_id: str | None = None,
    ) -> dict[str, Any]:
        """Record a concise research result in the user's history."""
        entry_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        record = {
            "id": entry_id,
            "user_id": str(user.id),
            "module_name": module_name,
            "scenario_id": scenario_id,
            "summary": summary,
            "created_at": now_iso,
        }

        if self._test_mode:
            self._memory_history[entry_id] = record
            return record

        url = f"{self.supabase_url}/rest/v1/research_history"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=self._get_headers(user), json=record)
            if resp.status_code in (200, 201):
                data = resp.json()
                return data[0] if isinstance(data, list) and data else record
            logger.error("Failed to insert history: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to record research history")

    async def list_history(
        self, user: AuthenticatedUser, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List research history entries owned by the authenticated user."""
        if self._test_mode:
            entries = [h for h in self._memory_history.values() if h["user_id"] == str(user.id)]
            entries.sort(key=lambda x: x["created_at"], reverse=True)
            return entries[offset : offset + limit]

        url = f"{self.supabase_url}/rest/v1/research_history?user_id=eq.{user.id}&order=created_at.desc&limit={limit}&offset={offset}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._get_headers(user))
            if resp.status_code == 200:
                return resp.json()
            logger.error("Failed to list history: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to retrieve research history")

    async def delete_history_entry(self, user: AuthenticatedUser, history_id: str) -> None:
        """Delete an individual research history entry owned by the user."""
        if self._test_mode:
            entry = self._memory_history.get(history_id)
            if not entry or entry["user_id"] != str(user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found")
            del self._memory_history[history_id]
            return

        url = f"{self.supabase_url}/rest/v1/research_history?id=eq.{history_id}&user_id=eq.{user.id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(url, headers=self._get_headers(user))
            if resp.status_code not in (200, 204):
                logger.error("Failed to delete history entry: %s %s", resp.status_code, resp.text)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to delete history entry")

    async def clear_history(self, user: AuthenticatedUser) -> None:
        """Clear all research history for the authenticated user."""
        if self._test_mode:
            to_delete = [k for k, v in self._memory_history.items() if v["user_id"] == str(user.id)]
            for k in to_delete:
                del self._memory_history[k]
            return

        url = f"{self.supabase_url}/rest/v1/research_history?user_id=eq.{user.id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(url, headers=self._get_headers(user))
            if resp.status_code not in (200, 204):
                logger.error("Failed to clear history: %s %s", resp.status_code, resp.text)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to clear research history")


# Singleton database gateway
db = SupabaseDbGateway()

