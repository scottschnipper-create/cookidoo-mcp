"""FastMCP server with all Cookidoo tools."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from cookidoo_mcp.client import CookidooClient

load_dotenv()

mcp = FastMCP("cookidoo", dependencies=["cookidoo-api", "python-dotenv", "aiohttp"])

_client = CookidooClient.get()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize(value: str) -> str:
    """Strip control characters to prevent prompt injection via untrusted recipe data."""
    return re.sub(r"[\x00-\x1f\x7f]", "", value)


def _search_locale(language: str) -> str:
    """Extract the bare language code used in the search path (e.g. 'en-US' → 'en')."""
    return language.split("-")[0].lower()


def _pick_image(assets: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Extract (thumbnail, image) from descriptiveAssets list."""
    for asset in assets:
        url = asset.get("square") or asset.get("landscape") or asset.get("portrait")
        if url:
            return url, url
    return None, None


def _parse_date(date_str: str | None) -> date:
    if not date_str:
        return date.today()
    return datetime.fromisoformat(date_str).date()


# ---------------------------------------------------------------------------
# Priority 1 — Recipe Search
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_recipes(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Search Cookidoo recipes by name, ingredient, or cuisine.

    Args:
        query: Free-text search term (e.g. "pasta tomato", "chicken curry", "gluten free cake").
        max_results: Maximum number of results to return (default 10, max 50).
    """
    api = await _client.api()

    lang = _search_locale(api.localization.language)
    url = api.api_endpoint / f"search/{lang}"

    headers = dict(api._api_headers)
    if api._auth_data:
        headers["Cookie"] = f"v-token={api._auth_data.access_token}"

    page_size = min(max(1, max_results), 50)
    params = {"query": query, "pageSize": str(page_size), "page": "1"}

    async with api._session.get(url, headers=headers, params=params) as r:
        r.raise_for_status()
        data = await r.json()

    raw_recipes = data.get("data") or data.get("recipes") or []
    base_url = api.localization.url.rsplit("/foundation/", 1)[0]

    results = []
    for item in raw_recipes[:max_results]:
        recipe_id = item.get("id", "")
        name = _sanitize(item.get("title") or item.get("name") or "")
        assets = item.get("descriptiveAssets") or []
        thumbnail, image = _pick_image(assets)
        total_time = item.get("totalTime") or item.get("total_time")
        recipe_url = f"{base_url}/recipes/recipe/{lang}/{recipe_id}"
        results.append({
            "id": recipe_id,
            "name": name,
            "url": recipe_url,
            "total_time_seconds": total_time,
            "thumbnail": thumbnail,
        })

    return results


# ---------------------------------------------------------------------------
# Priority 2 — Recipe Details & Shopping List
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_recipe_details(recipe_id: str) -> dict[str, Any]:
    """Get full details for a recipe: ingredients, timing, nutrition, categories, difficulty.

    Args:
        recipe_id: The Cookidoo recipe ID (e.g. "r907001").
    """
    api = await _client.api()
    details = await api.get_recipe_details(recipe_id)
    return {
        "id": details.id,
        "name": _sanitize(details.name),
        "url": details.url,
        "difficulty": details.difficulty,
        "active_time_seconds": details.active_time,
        "total_time_seconds": details.total_time,
        "serving_size": details.serving_size,
        "thumbnail": details.thumbnail,
        "notes": [_sanitize(n) for n in details.notes],
        "utensils": [_sanitize(u) for u in details.utensils],
        "categories": [
            {"id": c.id, "name": _sanitize(c.name), "notes": _sanitize(c.notes)}
            for c in details.categories
        ],
        "collections": [
            {"id": c.id, "name": _sanitize(c.name), "total_recipes": c.total_recipes}
            for c in details.collections
        ],
        "ingredients": [
            {
                "id": i.id,
                "name": _sanitize(i.name),
                "description": _sanitize(i.description),
            }
            for i in details.ingredients
        ],
        "nutrition_groups": [
            {
                "name": _sanitize(ng.name),
                "entries": [
                    {
                        "quantity": rn.quantity,
                        "unit": _sanitize(rn.unit_notation),
                        "nutritions": [
                            {
                                "type": _sanitize(n.type),
                                "number": n.number,
                                "unit": _sanitize(n.unittype),
                            }
                            for n in rn.nutritions
                        ],
                    }
                    for rn in ng.recipe_nutritions
                ],
            }
            for ng in details.nutrition_groups
        ],
    }


@mcp.tool()
async def get_shopping_list() -> list[dict[str, Any]]:
    """Get the current shopping list — all ingredient items with quantities and ownership status."""
    api = await _client.api()
    items = await api.get_ingredient_items()
    return [
        {
            "id": item.id,
            "name": _sanitize(item.name),
            "description": _sanitize(item.description),
            "is_owned": item.is_owned,
        }
        for item in items
    ]


@mcp.tool()
async def add_to_shopping_list(recipe_ids: list[str]) -> list[dict[str, Any]]:
    """Add recipe ingredients to the shopping list.

    Args:
        recipe_ids: List of Cookidoo recipe IDs whose ingredients to add.
    """
    api = await _client.api()
    items = await api.add_ingredient_items_for_recipes(recipe_ids)
    return [
        {
            "id": item.id,
            "name": _sanitize(item.name),
            "description": _sanitize(item.description),
            "is_owned": item.is_owned,
        }
        for item in items
    ]


@mcp.tool()
async def remove_from_shopping_list(recipe_ids: list[str]) -> list[dict[str, Any]]:
    """Remove recipe ingredients from the shopping list.

    Args:
        recipe_ids: List of Cookidoo recipe IDs whose ingredients to remove.
    """
    api = await _client.api()
    items = await api.remove_ingredient_items_for_recipes(recipe_ids)
    return [
        {
            "id": item.id,
            "name": _sanitize(item.name),
            "description": _sanitize(item.description),
            "is_owned": item.is_owned,
        }
        for item in items
    ]


@mcp.tool()
async def clear_shopping_list() -> dict[str, str]:
    """Wipe the entire shopping list (removes all ingredient items)."""
    api = await _client.api()
    await api.clear_shopping_list()
    return {"status": "ok", "message": "Shopping list cleared."}


# ---------------------------------------------------------------------------
# Priority 3 — Meal Calendar
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_calendar_week(date: str = "") -> list[dict[str, Any]]:
    """View the meal plan for the week containing the given date.

    Args:
        date: ISO date string (e.g. "2025-03-15"). Defaults to today.
    """
    api = await _client.api()
    target = _parse_date(date or None)
    days = await api.get_recipes_in_calendar_week(target)
    return [
        {
            "id": day.id,
            "title": _sanitize(day.title),
            "recipes": [
                {
                    "id": r.id,
                    "name": _sanitize(r.name),
                    "url": r.url,
                    "total_time_seconds": r.total_time,
                    "thumbnail": r.thumbnail,
                }
                for r in day.recipes
            ],
        }
        for day in days
    ]


@mcp.tool()
async def add_to_calendar(recipe_ids: list[str], date: str) -> dict[str, Any]:
    """Schedule recipes for a specific day in the meal calendar.

    Args:
        recipe_ids: List of Cookidoo recipe IDs to add.
        date: ISO date string for the target day (e.g. "2025-03-15").
    """
    api = await _client.api()
    target = _parse_date(date)
    day = await api.add_recipes_to_calendar(target, recipe_ids)
    return {
        "id": day.id,
        "title": _sanitize(day.title),
        "recipes": [
            {
                "id": r.id,
                "name": _sanitize(r.name),
                "url": r.url,
                "total_time_seconds": r.total_time,
                "thumbnail": r.thumbnail,
            }
            for r in day.recipes
        ],
    }


@mcp.tool()
async def remove_from_calendar(recipe_id: str, date: str) -> dict[str, Any]:
    """Remove a recipe from a specific day in the meal calendar.

    Args:
        recipe_id: The Cookidoo recipe ID to remove.
        date: ISO date string for the target day (e.g. "2025-03-15").
    """
    api = await _client.api()
    target = _parse_date(date)
    day = await api.remove_recipe_from_calendar(target, recipe_id)
    return {
        "id": day.id,
        "title": _sanitize(day.title),
        "recipes": [
            {
                "id": r.id,
                "name": _sanitize(r.name),
                "url": r.url,
                "total_time_seconds": r.total_time,
                "thumbnail": r.thumbnail,
            }
            for r in day.recipes
        ],
    }
