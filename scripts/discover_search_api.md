# Cookidoo Search API Endpoint

## Status: Implemented ✓

Discovered from the open PR #141 in `miaucl/cookidoo-api` (reverse-engineering the mobile API).

## Endpoint

```
GET https://{country_code}.tmmobile.vorwerk-digital.com/search/{lang}
```

- `country_code`: two-letter country code (e.g. `us`, `de`, `pl`, `gb`; UK → `gb`, international → `xp`)
- `lang`: bare language code, first segment of the BCP-47 tag (e.g. `en` from `en-US`, `pl` from `pl`, `de` from `de-DE`)

## Query parameters

| Key | Type | Notes |
|-----|------|-------|
| `query` | string | Free-text search term |
| `pageSize` | int string | Results per page |
| `page` | int string | 1-based page number |
| `difficulty` | string | `easy`, `medium`, `hard` |
| `totalTime` | int string | Max total time in seconds |
| `preparationTime` | int string | Max prep time in seconds |
| `categories` | comma-separated | Category IDs |
| `tags` | comma-separated | Tag IDs |
| `tmv` | comma-separated | `TM5`, `TM6`, `TM7`, `TM31` |

## Headers

```
Accept: application/json
Authorization: Bearer {access_token}
Cookie: v-token={access_token}
```

## Response structure

```json
{
  "data": [
    {
      "id": "r123456",
      "title": "Chicken Soup",
      "descriptiveAssets": [
        { "square": "https://…/square.jpg", "landscape": "https://…/landscape.jpg" }
      ],
      "totalTime": 1800
    }
  ],
  "total": 42
}
```

Fallback: `{ "recipes": [...], "total": 42 }` (both shapes handled).
