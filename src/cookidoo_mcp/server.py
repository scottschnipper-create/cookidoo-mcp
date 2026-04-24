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
# Recipe Search
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
# Recipe Details
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_recipe_details(recipe_id: str) -> dict[str, Any]:
    """Get full details for a recipe: ingredients, steps, timing, nutrition, categories, difficulty.

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
            {"id": c.id, "name": _sanitize(c.name)}
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


# ---------------------------------------------------------------------------
# Shopping List — Recipe Ingredients
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_shopping_list() -> dict[str, Any]:
    """Get the full shopping list — recipe ingredients and additional freeform items, with ownership status."""
    api = await _client.api()
    ingredients = await api.get_ingredient_items()
    additional = await api.get_additional_items()
    return {
        "ingredients": [
            {
                "id": item.id,
                "name": _sanitize(item.name),
                "description": _sanitize(item.description),
                "is_owned": item.is_owned,
            }
            for item in ingredients
        ],
        "additional_items": [
            {
                "id": item.id,
                "name": _sanitize(item.name),
                "is_owned": item.is_owned,
            }
            for item in additional
        ],
    }


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
    """Wipe the entire shopping list (removes all ingredient items and additional items)."""
    api = await _client.api()
    await api.clear_shopping_list()
    return {"status": "ok", "message": "Shopping list cleared."}


# ---------------------------------------------------------------------------
# Shopping List — Additional (Freeform) Items
# ---------------------------------------------------------------------------

@mcp.tool()
async def add_additional_items(item_names: list[str]) -> list[dict[str, Any]]:
    """Add freeform items to the shopping list (not linked to any recipe).

    Use this for non-recipe items like "paper towels", "wine", "bin bags", etc.

    Args:
        item_names: List of item names to add.
    """
    api = await _client.api()
    items = await api.add_additional_items(item_names)
    return [
        {
            "id": item.id,
            "name": _sanitize(item.name),
            "is_owned": item.is_owned,
        }
        for item in items
    ]


@mcp.tool()
async def remove_additional_items(item_ids: list[str]) -> dict[str, str]:
    """Remove freeform items from the shopping list by their IDs.

    Args:
        item_ids: List of additional item IDs to remove.
    """
    api = await _client.api()
    await api.remove_additional_items(item_ids)
    return {"status": "ok", "message": f"Removed {len(item_ids)} additional item(s)."}


# ---------------------------------------------------------------------------
# Shopping List — Check Off / Mark Owned
# ---------------------------------------------------------------------------

@mcp.tool()
async def mark_ingredients_owned(ingredient_ids: list[str], owned: bool = True) -> list[dict[str, Any]]:
    """Mark recipe ingredient items as owned (already have them) or not owned.

    Use this to check off items you already have at home before ordering groceries.

    Args:
        ingredient_ids: List of ingredient item IDs to update.
        owned: True to mark as owned/checked-off, False to uncheck.
    """
    api = await _client.api()
    # Build stub items with the target ownership
    from cookidoo_api.types import CookidooIngredientItem
    stubs = [
        CookidooIngredientItem(id=iid, name="", description="", is_owned=owned)
        for iid in ingredient_ids
    ]
    items = await api.edit_ingredient_items_ownership(stubs)
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
async def mark_additional_items_owned(item_ids: list[str], owned: bool = True) -> list[dict[str, Any]]:
    """Mark freeform additional items as owned (already have them) or not owned.

    Args:
        item_ids: List of additional item IDs to update.
        owned: True to mark as owned/checked-off, False to uncheck.
    """
    api = await _client.api()
    from cookidoo_api.types import CookidooAdditionalItem
    stubs = [
        CookidooAdditionalItem(id=iid, name="", is_owned=owned)
        for iid in item_ids
    ]
    items = await api.edit_additional_items_ownership(stubs)
    return [
        {
            "id": item.id,
            "name": _sanitize(item.name),
            "is_owned": item.is_owned,
        }
        for item in items
    ]


# ---------------------------------------------------------------------------
# Shopping List — Which Recipes Feed the List
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_shopping_list_recipes() -> list[dict[str, Any]]:
    """Get the list of recipes currently contributing ingredients to the shopping list."""
    api = await _client.api()
    recipes = await api.get_shopping_list_recipes()
    return [
        {
            "id": r.id,
            "name": _sanitize(r.name),
            "url": r.url,
            "thumbnail": r.thumbnail,
            "ingredients": [
                {
                    "id": i.id,
                    "name": _sanitize(i.name),
                    "description": _sanitize(i.description),
                }
                for i in r.ingredients
            ],
        }
        for r in recipes
    ]


# ---------------------------------------------------------------------------
# Meal Calendar
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_calendar_week(date: str = "") -> list[dict[str, Any]]:
    """View the meal plan for the week containing the given date.

    Args:
        date: ISO date string (e.g. "2026-04-14"). Defaults to today.
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
        date: ISO date string for the target day (e.g. "2026-04-14").
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
        date: ISO date string for the target day (e.g. "2026-04-14").
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


# ---------------------------------------------------------------------------
# Custom Recipe Creation
# ---------------------------------------------------------------------------

@mcp.tool()
async def create_custom_recipe(
    name: str,
    ingredients: list[str],
    instructions: list[str],
    serving_size: int = 4,
    active_time_minutes: int = 0,
    total_time_minutes: int = 0,
) -> dict[str, Any]:
    """Create a brand-new custom recipe on Cookidoo.

    The recipe will appear in the user's "My Created Recipes" and can be added
    to the meal calendar, shopping list, and synced to the TM6.

    For Thermomix recipes, include machine commands in instructions, e.g.:
    "Add onions to mixing bowl. Chop 5 sec/speed 5."
    "Cook 10 min/100°C/speed 1."

    Args:
        name: Recipe name.
        ingredients: List of ingredient strings, e.g. ["500 g chicken breast", "2 tbsp olive oil"].
        instructions: List of step-by-step instructions.
        serving_size: Number of servings (default 4).
        active_time_minutes: Hands-on time in minutes (0 = not specified).
        total_time_minutes: Total time including cooking in minutes (0 = not specified).
    """
    api = await _client.api()
    lang = api.localization.language

    # Step 1: Create an empty custom recipe
    create_url = api.api_endpoint / f"created-recipes/{lang}"
    headers = dict(api._api_headers)
    if api._auth_data:
        headers["Authorization"] = f"Bearer {api._auth_data.access_token}"
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"

    async with api._session.post(
        create_url,
        headers=headers,
        json={"recipeName": name},
    ) as r:
        r.raise_for_status()
        created = await r.json()

    recipe_id = created.get("recipeId") or created.get("id")

    # Step 2: Patch with full recipe body
    patch_url = api.api_endpoint / f"created-recipes/{lang}/{recipe_id}"

    body: dict[str, Any] = {
        "recipeName": name,
        "ingredients": [{"type": "INGREDIENT", "text": ing} for ing in ingredients],
        "instructions": [{"type": "STEP", "text": step} for step in instructions],
        "tools": ["TM6"],
        "servingSize": serving_size,
    }
    if active_time_minutes > 0:
        body["activeTime"] = active_time_minutes * 60
    if total_time_minutes > 0:
        body["totalTime"] = total_time_minutes * 60

    async with api._session.patch(
        patch_url,
        headers=headers,
        json=body,
    ) as r:
        r.raise_for_status()
        patched = await r.json()

    content = patched.get("recipeContent", {})
    return {
        "id": recipe_id,
        "name": _sanitize(content.get("name", name)),
        "serving_size": content.get("yield", {}).get("value", serving_size),
        "ingredients": [_sanitize(i.get("text", "")) for i in content.get("ingredients", [])],
        "instructions": [_sanitize(s.get("text", "")) for s in content.get("instructions", [])],
        "tools": content.get("tools", ["TM6"]),
        "status": "created",
    }


@mcp.tool()
async def clone_recipe(recipe_id: str, serving_size: int = 4) -> dict[str, Any]:
    """Clone an existing Cookidoo recipe as your own custom recipe (editable copy).

    Useful for modifying ingredients, adjusting servings, or adapting an official recipe.

    Args:
        recipe_id: The Cookidoo recipe ID to clone (e.g. "r907001").
        serving_size: Desired serving size for the cloned recipe.
    """
    api = await _client.api()
    custom = await api.add_custom_recipe_from(recipe_id, serving_size)
    return {
        "id": custom.id,
        "name": _sanitize(custom.name),
        "url": custom.url,
        "serving_size": custom.serving_size,
        "ingredients": [_sanitize(i) for i in custom.ingredients],
        "instructions": [_sanitize(s) for s in custom.instructions],
        "tools": custom.tools,
        "status": "cloned",
    }


@mcp.tool()
async def delete_custom_recipe(custom_recipe_id: str) -> dict[str, str]:
    """Delete a custom recipe you created.

    Args:
        custom_recipe_id: The custom recipe ID to delete.
    """
    api = await _client.api()
    await api.remove_custom_recipe(custom_recipe_id)
    return {"status": "ok", "message": f"Custom recipe {custom_recipe_id} deleted."}


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_collections() -> dict[str, Any]:
    """Get all recipe collections (both your custom collections and Cookidoo managed ones)."""
    api = await _client.api()
    custom = await api.get_custom_collections()
    managed = await api.get_managed_collections()
    return {
        "custom_collections": [
            {"id": c.id, "name": _sanitize(c.name)}
            for c in custom
        ],
        "managed_collections": [
            {"id": c.id, "name": _sanitize(c.name)}
            for c in managed
        ],
    }


@mcp.tool()
async def create_collection(name: str) -> dict[str, Any]:
    """Create a new custom recipe collection.

    Args:
        name: Name for the collection (e.g. "Weeknight Dinners", "Kids Favourites").
    """
    api = await _client.api()
    collection = await api.add_custom_collection(name)
    return {
        "id": collection.id,
        "name": _sanitize(collection.name),
    }


@mcp.tool()
async def add_recipes_to_collection(collection_id: str, recipe_ids: list[str]) -> dict[str, Any]:
    """Add recipes to an existing custom collection.

    Args:
        collection_id: The collection ID to add recipes to.
        recipe_ids: List of recipe IDs to add.
    """
    api = await _client.api()
    collection = await api.add_recipes_to_custom_collection(collection_id, recipe_ids)
    return {
        "id": collection.id,
        "name": _sanitize(collection.name),
    }


# ---------------------------------------------------------------------------
# Account Info
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_account_info() -> dict[str, Any]:
    """Get Cookidoo account info: username, subscription status, and profile details."""
    api = await _client.api()
    user = await api.get_user_info()
    sub = await api.get_active_subscription()
    result: dict[str, Any] = {
        "username": _sanitize(user.username),
        "picture": user.picture,
    }
    if sub:
        result["subscription"] = {
            "active": True,
            "type": sub.type if hasattr(sub, "type") else "unknown",
        }
    return result


# ---------------------------------------------------------------------------
# Grocery Ordering Helper
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_grocery_order_link() -> dict[str, str]:
    """Get the URL to order shopping list ingredients from Waitrose or Ocado.

    Opens the Cookidoo online ingredient ordering page where you can select
    Waitrose or Ocado as your retailer and checkout.
    """
    return {
        "order_url": "https://cookidoo.co.uk/foundation/en-GB/shopping-list",
        "instructions": (
            "Open this URL in your browser → click 'Order Ingredients' → "
            "select Waitrose or Ocado → Northfork will match ingredients to products → "
            "complete checkout on the retailer's site."
        ),
        "supported_retailers": "Waitrose, Ocado",
    }
