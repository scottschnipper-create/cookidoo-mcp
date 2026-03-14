# Discovering the Cookidoo Search API Endpoint

## Status: TODO

This document will be filled after a playwright-mcp session to capture the search HTTP request.

## Steps to discover

1. Open a playwright-mcp session and navigate to cookidoo.thermomix.com (or the locale equivalent).
2. Open DevTools → Network tab, filter by XHR/Fetch.
3. Log in with Cookidoo credentials.
4. Perform a recipe search (e.g. "pasta").
5. Capture the request:
   - Full URL (including query params)
   - Request headers (especially `Authorization`)
   - Response structure
6. Fill in the sections below.

## Discovered Endpoint

```
METHOD: GET (expected)
URL: TODO
Query params: TODO  (e.g. query=pasta&limit=10&offset=0)
```

## Response structure

```json
TODO
```

## Implementation note

Once the endpoint is known, add a `search_recipes` tool to `server.py`:

```python
@mcp.tool()
async def search_recipes(query: str, max_results: int = 10) -> list[dict]:
    """Search Cookidoo recipes by name, ingredient, or cuisine."""
    api = await _client.api()
    # direct aiohttp call reusing api._api_headers and api.api_endpoint
    ...
```
