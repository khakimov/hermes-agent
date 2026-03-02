"""
Google Places tool.

Uses the Google Places API (New) for place search, details, and nearby search.
Requires GOOGLE_PLACES_API_KEY environment variable.

API docs: https://developers.google.com/maps/documentation/places/web-service
"""

import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Places API (New) endpoints
_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
_DETAILS_URL = "https://places.googleapis.com/v1/places"  # /{place_id}

# Fields to request (controls billing — only request what we need)
_DEFAULT_FIELDS = [
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.rating",
    "places.userRatingCount",
    "places.types",
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.currentOpeningHours",
    "places.priceLevel",
    "places.editorialSummary",
    "places.location",
]

_DETAIL_FIELDS = [
    "id",
    "displayName",
    "formattedAddress",
    "rating",
    "userRatingCount",
    "types",
    "websiteUri",
    "nationalPhoneNumber",
    "internationalPhoneNumber",
    "currentOpeningHours",
    "regularOpeningHours",
    "priceLevel",
    "editorialSummary",
    "reviews",
    "location",
    "googleMapsUri",
]


def check_google_places_api_key() -> bool:
    return bool(os.getenv("GOOGLE_PLACES_API_KEY"))


def _format_place(place: dict) -> dict:
    """Extract a clean summary from a Places API (New) place object."""
    result = {}
    if dn := place.get("displayName"):
        result["name"] = dn.get("text", "")
    result["place_id"] = place.get("id", "")
    result["address"] = place.get("formattedAddress", "")
    if rating := place.get("rating"):
        result["rating"] = rating
    if count := place.get("userRatingCount"):
        result["rating_count"] = count
    if types := place.get("types"):
        result["types"] = types
    if website := place.get("websiteUri"):
        result["website"] = website
    if phone := place.get("nationalPhoneNumber"):
        result["phone"] = phone
    if price := place.get("priceLevel"):
        result["price_level"] = price
    if summary := place.get("editorialSummary"):
        result["summary"] = summary.get("text", "")
    if loc := place.get("location"):
        result["location"] = {"lat": loc.get("latitude"), "lng": loc.get("longitude")}
    if maps_uri := place.get("googleMapsUri"):
        result["google_maps_url"] = maps_uri
    return result


def google_places_tool(
    action: str = "search",
    query: str = "",
    place_id: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius: int = 1000,
    type: Optional[str] = None,
    max_results: int = 10,
) -> str:
    """Search for places, get place details, or find nearby places."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return json.dumps({"error": "GOOGLE_PLACES_API_KEY not set"})

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            if action == "details":
                if not place_id:
                    return json.dumps({"error": "place_id is required for details action"})
                headers["X-Goog-FieldMask"] = ",".join(_DETAIL_FIELDS)
                resp = client.get(f"{_DETAILS_URL}/{place_id}", headers=headers)
                resp.raise_for_status()
                place = resp.json()
                return json.dumps({"place": _format_place(place)}, ensure_ascii=False)

            elif action == "nearby":
                if latitude is None or longitude is None:
                    return json.dumps({"error": "latitude and longitude are required for nearby action"})
                headers["X-Goog-FieldMask"] = ",".join(_DEFAULT_FIELDS)
                payload = {
                    "locationRestriction": {
                        "circle": {
                            "center": {"latitude": latitude, "longitude": longitude},
                            "radius": min(radius, 50000),
                        }
                    },
                    "maxResultCount": min(max_results, 20),
                }
                if type:
                    payload["includedTypes"] = [type]
                resp = client.post(_NEARBY_SEARCH_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                places = [_format_place(p) for p in data.get("places", [])]
                return json.dumps({"results": places, "count": len(places)}, ensure_ascii=False)

            else:  # text search (default)
                if not query:
                    return json.dumps({"error": "query is required for search action"})
                headers["X-Goog-FieldMask"] = ",".join(_DEFAULT_FIELDS)
                payload = {
                    "textQuery": query,
                    "maxResultCount": min(max_results, 20),
                }
                if type:
                    payload["includedType"] = type
                if latitude is not None and longitude is not None:
                    payload["locationBias"] = {
                        "circle": {
                            "center": {"latitude": latitude, "longitude": longitude},
                            "radius": min(radius, 50000),
                        }
                    }
                resp = client.post(_TEXT_SEARCH_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                places = [_format_place(p) for p in data.get("places", [])]
                return json.dumps({
                    "query": query,
                    "results": places,
                    "count": len(places),
                }, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Google Places API error: {e.response.status_code} - {e.response.text[:300]}"})
    except Exception as e:
        return json.dumps({"error": f"Google Places API request failed: {e}"})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
from tools.registry import registry

GOOGLE_PLACES_SCHEMA = {
    "name": "google_places",
    "description": (
        "Search for places, get place details, or find nearby places using Google Places API. "
        "Actions: 'search' (text search), 'nearby' (lat/lng radius search), 'details' (get full info by place_id). "
        "Returns name, address, rating, phone, website, opening hours, price level, and more."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "nearby", "details"],
                "description": "Action to perform: 'search' for text search, 'nearby' for radius search around coordinates, 'details' for full place info",
                "default": "search",
            },
            "query": {
                "type": "string",
                "description": "Search query (required for 'search' action). E.g. 'pizza near Times Square' or 'best coffee shops in Portland'",
            },
            "place_id": {
                "type": "string",
                "description": "Google Place ID (required for 'details' action). Obtained from search/nearby results.",
            },
            "latitude": {
                "type": "number",
                "description": "Latitude for location bias (search) or center point (nearby)",
            },
            "longitude": {
                "type": "number",
                "description": "Longitude for location bias (search) or center point (nearby)",
            },
            "radius": {
                "type": "integer",
                "description": "Search radius in meters (max 50000, default 1000). Used with nearby and as location bias for search.",
                "default": 1000,
            },
            "type": {
                "type": "string",
                "description": "Place type filter (e.g. 'restaurant', 'cafe', 'hotel', 'gas_station', 'pharmacy')",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (1-20, default 10)",
                "default": 10,
            },
        },
        "required": [],
    },
}

registry.register(
    name="google_places",
    toolset="web",
    schema=GOOGLE_PLACES_SCHEMA,
    handler=lambda args, **kw: google_places_tool(
        action=args.get("action", "search"),
        query=args.get("query", ""),
        place_id=args.get("place_id", ""),
        latitude=args.get("latitude"),
        longitude=args.get("longitude"),
        radius=args.get("radius", 1000),
        type=args.get("type"),
        max_results=args.get("max_results", 10),
    ),
    check_fn=check_google_places_api_key,
    requires_env=["GOOGLE_PLACES_API_KEY"],
)
