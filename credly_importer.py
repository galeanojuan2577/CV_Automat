import logging
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger("credly")

CREDLY_API = "https://www.credly.com/users/{username}/badges.json"


def fetch_credly_badges(username="", max_badges=50):
    url = CREDLY_API.format(username=username)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        badges_data = data.get("data", [])
    except Exception as e:
        logger.error("Error fetching Credly badges: %s", e)
        return []

    badges = []
    for b in badges_data:
        if len(badges) >= max_badges:
            break
        try:
            name = b.get("badge_template", {}).get("name", "")
            issuer_entity = b.get("issuer", {}).get("entities", [{}])[0].get("entity", {})
            issuer = issuer_entity.get("name", "")
            date_str = b.get("issued_at_date", "")
            badge_url = f"https://www.credly.com/badges/{b.get('id', '')}"
            badges.append({
                "name": name,
                "issuer": issuer,
                "date": date_str,
                "url": badge_url,
            })
        except Exception as e:
            logger.warning("Error parsing badge: %s", e)
            continue

    badges.sort(key=lambda x: x["date"], reverse=True)
    return badges
