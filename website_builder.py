#!/usr/bin/env python3
"""
AI Website Builder
==================
Finds local businesses without websites using Google Places API,
then generates a premium HTML website for each one using Claude AI.

Usage:
    python website_builder.py --niche plumber --city "Phoenix AZ" --leads 5

Requirements:
    GOOGLE_PLACES_API_KEY and ANTHROPIC_API_KEY env vars (or prompted at start)
"""

import os
import re
import csv
import time
import json
import argparse
import textwrap
from pathlib import Path
from datetime import datetime

import requests
import anthropic


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

GOOGLE_PLACES_BASE = "https://maps.googleapis.com/maps/api/place"
SLEEP_BETWEEN_CALLS = 0.5   # seconds — keeps us under rate limits
MAX_REVIEWS_TO_FETCH = 5    # Google Places returns up to 5 reviews per place


# ─────────────────────────────────────────────────────────────────────────────
# API KEY SETUP
# ─────────────────────────────────────────────────────────────────────────────

def get_api_keys() -> tuple[str, str]:
    """
    Returns (google_key, anthropic_key).
    Reads from environment variables first; prompts the user if not set.
    """
    google_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not google_key:
        print("\n🔑  Google Places API key not found in environment.")
        print("    Get one at: https://console.cloud.google.com/apis/library/places-backend.googleapis.com")
        google_key = input("    Paste your Google Places API key: ").strip()

    if not anthropic_key:
        print("\n🔑  Anthropic API key not found in environment.")
        print("    Get one at: https://console.anthropic.com/")
        anthropic_key = input("    Paste your Anthropic API key: ").strip()

    if not google_key or not anthropic_key:
        raise ValueError("Both API keys are required to run the website builder.")

    return google_key, anthropic_key


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE PLACES API HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def search_places(niche: str, city: str, google_key: str, max_results: int = 20) -> list[dict]:
    """
    Uses the Places Text Search API to find businesses matching niche + city.
    Returns a list of raw place dicts (trimmed to max_results).
    """
    query = f"{niche} in {city}"
    print(f"\n🔍  Searching Google Places for: '{query}'")

    results = []
    next_page_token = None

    while len(results) < max_results:
        params = {
            "query": query,
            "key": google_key,
            "type": "establishment",
        }
        if next_page_token:
            params["pagetoken"] = next_page_token
            # Google requires a short delay before using a page token
            time.sleep(2)

        try:
            resp = requests.get(f"{GOOGLE_PLACES_BASE}/textsearch/json", params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"  ⚠️  Google Places search error: {e}")
            break

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            print(f"  ⚠️  Google Places API status: {data.get('status')} — {data.get('error_message', '')}")
            break

        page_results = data.get("results", [])
        results.extend(page_results)

        next_page_token = data.get("next_page_token")
        if not next_page_token or len(results) >= max_results:
            break

        time.sleep(SLEEP_BETWEEN_CALLS)

    print(f"  ✅  Found {len(results)} places total.")
    return results[:max_results]


def get_place_details(place_id: str, google_key: str) -> dict:
    """
    Fetches full details for a place (phone, website, address, reviews, rating).
    Returns the 'result' dict from Google Places Details API.
    """
    fields = "name,formatted_phone_number,formatted_address,website,rating,user_ratings_total,reviews,opening_hours"
    params = {
        "place_id": place_id,
        "fields": fields,
        "key": google_key,
    }
    try:
        resp = requests.get(f"{GOOGLE_PLACES_BASE}/details/json", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "OK":
            return data.get("result", {})
        else:
            print(f"    ⚠️  Details API status: {data.get('status')}")
            return {}
    except requests.RequestException as e:
        print(f"    ⚠️  Details fetch error: {e}")
        return {}


def filter_no_website(places: list[dict], google_key: str, num_leads: int) -> list[dict]:
    """
    Iterates through places, fetching full details for each.
    Returns up to num_leads places that have NO website listed.
    """
    leads = []
    print(f"\n🕵️   Filtering for businesses without websites (target: {num_leads} leads)...\n")

    for place in places:
        if len(leads) >= num_leads:
            break

        place_id = place.get("place_id", "")
        name = place.get("name", "Unknown")
        print(f"  Checking: {name} ...", end=" ", flush=True)

        details = get_place_details(place_id, google_key)
        time.sleep(SLEEP_BETWEEN_CALLS)

        # Skip businesses that already have a website
        if details.get("website"):
            print("has website, skipping.")
            continue

        # Must have a phone number to be a useful lead
        if not details.get("formatted_phone_number"):
            print("no phone, skipping.")
            continue

        # Merge top-level place data with details
        merged = {**place, **details, "place_id": place_id}
        leads.append(merged)
        print(f"✅  NO WEBSITE — added as lead #{len(leads)}")

    print(f"\n  Found {len(leads)} qualified leads.")
    return leads


# ─────────────────────────────────────────────────────────────────────────────
# REVIEW FORMATTING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def stars_html(rating: float, size: str = "small") -> str:
    """Returns HTML for a star rating display (filled / half / empty stars)."""
    full_stars = int(rating)
    has_half = (rating - full_stars) >= 0.5
    empty_stars = 5 - full_stars - (1 if has_half else 0)

    size_class = "w-4 h-4" if size == "small" else "w-6 h-6"
    html_parts = []

    for _ in range(full_stars):
        html_parts.append(
            f'<svg class="{size_class} text-gold-400" fill="currentColor" viewBox="0 0 20 20">'
            f'<path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>'
            f'</svg>'
        )
    if has_half:
        html_parts.append(
            f'<svg class="{size_class} text-gold-400" fill="currentColor" viewBox="0 0 20 20">'
            f'<defs><linearGradient id="half"><stop offset="50%" stop-color="currentColor"/>'
            f'<stop offset="50%" stop-color="#334155"/></linearGradient></defs>'
            f'<path fill="url(#half)" d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>'
            f'</svg>'
        )
    for _ in range(empty_stars):
        html_parts.append(
            f'<svg class="{size_class} text-slate-600" fill="currentColor" viewBox="0 0 20 20">'
            f'<path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>'
            f'</svg>'
        )
    return "\n".join(html_parts)


def build_review_cards(reviews: list[dict]) -> str:
    """Converts a list of Google review dicts into HTML review cards."""
    if not reviews:
        return '<p class="text-slate-500 col-span-3 text-center">No reviews available yet.</p>'

    cards = []
    for review in reviews[:MAX_REVIEWS_TO_FETCH]:
        reviewer = review.get("author_name", "Anonymous")
        rating = review.get("rating", 5)
        text = review.get("text", "")
        # Truncate very long reviews
        if len(text) > 280:
            text = text[:277] + "..."
        # Escape HTML special chars
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        reviewer_safe = reviewer.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Get reviewer initials for avatar
        parts = reviewer.split()
        initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

        card = f"""
        <div class="bg-navy-900 border border-white/5 rounded-2xl p-6 card-hover flex flex-col gap-4">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-gold-500/20 border border-gold-500/30 rounded-full flex items-center justify-center flex-shrink-0">
              <span class="text-gold-400 font-bold text-sm">{initials}</span>
            </div>
            <div>
              <p class="text-white font-semibold text-sm">{reviewer_safe}</p>
              <div class="flex gap-0.5 mt-0.5">
                {stars_html(rating, "small")}
              </div>
            </div>
          </div>
          <p class="text-slate-400 text-sm leading-relaxed flex-1">"{text}"</p>
        </div>"""
        cards.append(card)

    return "\n".join(cards)


# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE AI — WEBSITE CONTENT GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_website_content(business: dict, niche: str, city: str, client: anthropic.Anthropic) -> dict:
    """
    Calls Claude claude-3-haiku to generate customized copy for the business website.
    Returns a dict with: tagline, about_paragraphs, services (list of {title, desc, icon_svg})
    """
    name = business.get("name", "Local Business")
    address = business.get("formatted_address", city)
    phone = business.get("formatted_phone_number", "")
    rating = business.get("rating", 4.5)
    review_count = business.get("user_ratings_total", 0)

    # Pull up to 3 reviews for context
    reviews = business.get("reviews", [])[:3]
    reviews_text = "\n".join([
        f"- {r.get('author_name', 'Customer')}: {r.get('text', '')[:200]}"
        for r in reviews
    ]) or "No reviews available."

    prompt = f"""You are a premium web copywriter. Generate website content for this local business.

Business Details:
- Name: {name}
- Type: {niche}
- Location: {address}
- Phone: {phone}
- Google Rating: {rating}/5 ({review_count} reviews)

Recent customer reviews:
{reviews_text}

Generate a JSON object (and ONLY the JSON, no markdown fences) with exactly this structure:
{{
  "tagline": "A compelling 1-sentence tagline under 15 words. Professional, confident, local-focused.",
  "about_paragraph_1": "First about paragraph, 2-3 sentences. Mention the city, experience, and commitment to quality. Warm and professional.",
  "about_paragraph_2": "Second about paragraph, 2-3 sentences. Focus on reliability, fast response, and satisfaction guarantee.",
  "services": [
    {{"title": "Service 1 Name", "description": "Short 1-sentence description of this {niche} service.", "emoji": "🔧"}},
    {{"title": "Service 2 Name", "description": "Short 1-sentence description.", "emoji": "🚿"}},
    {{"title": "Service 3 Name", "description": "Short 1-sentence description.", "emoji": "🛠️"}},
    {{"title": "Service 4 Name", "description": "Short 1-sentence description.", "emoji": "💧"}},
    {{"title": "Service 5 Name", "description": "Short 1-sentence description.", "emoji": "🔩"}},
    {{"title": "Service 6 Name", "description": "Short 1-sentence description.", "emoji": "⚡"}}
  ]
}}

Rules:
- Keep all copy professional and trust-building
- Services must be realistic for a {niche} business
- Do NOT include any markdown, code blocks, or explanation — pure JSON only"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()

        # Strip any accidental markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        content = json.loads(raw)
        return content

    except (json.JSONDecodeError, IndexError, KeyError) as e:
        print(f"    ⚠️  Claude response parse error: {e}. Using default content.")
        return _default_content(name, niche, city)
    except anthropic.APIError as e:
        print(f"    ⚠️  Claude API error: {e}. Using default content.")
        return _default_content(name, niche, city)


def _default_content(name: str, niche: str, city: str) -> dict:
    """Fallback content when Claude call fails."""
    return {
        "tagline": f"Professional {niche} services you can trust in {city}.",
        "about_paragraph_1": f"{name} has been proudly serving the {city} community with expert {niche} solutions. Our licensed team delivers fast, reliable service with attention to detail.",
        "about_paragraph_2": "We stand behind every job with a satisfaction guarantee. Whether it's an emergency or a planned project, we show up on time and get it done right.",
        "services": [
            {"title": "Emergency Service", "description": "24/7 rapid response for urgent issues.", "emoji": "🚨"},
            {"title": "Repairs", "description": "Fast, lasting repairs done correctly the first time.", "emoji": "🔧"},
            {"title": "Installations", "description": "Professional installation of all fixtures and systems.", "emoji": "🛠️"},
            {"title": "Inspections", "description": "Thorough inspections to catch problems early.", "emoji": "🔍"},
            {"title": "Maintenance", "description": "Scheduled maintenance to keep everything running smoothly.", "emoji": "⚙️"},
            {"title": "Free Estimates", "description": "Honest, transparent pricing with no hidden fees.", "emoji": "📋"},
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML SITE ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def build_service_cards(services: list[dict]) -> str:
    """Converts a list of service dicts into HTML service cards."""
    cards = []
    for svc in services:
        title = svc.get("title", "Service")
        desc = svc.get("description", "")
        emoji = svc.get("emoji", "🔧")
        title_safe = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        desc_safe = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        card = f"""
        <div class="bg-navy-900 border border-white/5 rounded-2xl p-6 card-hover group">
          <div class="w-12 h-12 bg-gold-500/10 border border-gold-500/20 rounded-xl flex items-center justify-center mb-4 text-2xl group-hover:bg-gold-500/20 transition-colors">
            {emoji}
          </div>
          <h3 class="text-white font-bold text-lg mb-2">{title_safe}</h3>
          <p class="text-slate-400 text-sm leading-relaxed">{desc_safe}</p>
        </div>"""
        cards.append(card)

    return "\n".join(cards)


def build_about_paragraphs(content: dict) -> str:
    """Returns HTML <p> tags for about section paragraphs."""
    p1 = content.get("about_paragraph_1", "")
    p2 = content.get("about_paragraph_2", "")
    p1 = p1.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    p2 = p2.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<p>{p1}</p>\n<p class='mt-4'>{p2}</p>"


def sanitize_filename(name: str) -> str:
    """Converts a business name to a safe filename slug."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:80]  # cap at 80 chars


def assemble_html(business: dict, content: dict, city: str) -> str:
    """
    Loads the base template and substitutes all placeholders with real data.
    Returns the complete HTML string.
    """
    template_path = Path("templates/base_template.html")
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}. Run from project root.")

    html = template_path.read_text(encoding="utf-8")

    name = business.get("name", "Local Business")
    phone_raw = business.get("formatted_phone_number", "")
    # Strip formatting for tel: links
    phone_link = re.sub(r"[^\d+]", "", phone_raw) if phone_raw else ""
    address = business.get("formatted_address", city)
    rating = business.get("rating", 4.8)
    review_count = business.get("user_ratings_total", 0)
    reviews = business.get("reviews", [])

    # Estimate "years in business" — we don't have real data, so generate a believable number
    # based on review count (more reviews ≈ older business)
    if review_count > 200:
        years_exp = "15"
    elif review_count > 100:
        years_exp = "10"
    elif review_count > 50:
        years_exp = "7"
    else:
        years_exp = "5"

    tagline = content.get("tagline", f"Professional {city} service you can trust.")
    tagline_safe = tagline.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    service_cards_html = build_service_cards(content.get("services", []))
    review_cards_html = build_review_cards(reviews)
    about_html = build_about_paragraphs(content)

    replacements = {
        "{{BUSINESS_NAME}}": name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
        "{{PHONE_RAW}}": phone_link,
        "{{PHONE_DISPLAY}}": phone_raw or "Call Us",
        "{{ADDRESS}}": address.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
        "{{CITY}}": city.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
        "{{RATING}}": str(rating),
        "{{REVIEW_COUNT}}": str(review_count),
        "{{TAGLINE}}": tagline_safe,
        "{{YEARS_EXP}}": years_exp,
        "{{YEAR}}": str(datetime.now().year),
        "{{SERVICE_CARDS}}": service_cards_html,
        "{{REVIEW_CARDS}}": review_cards_html,
        "{{ABOUT_PARAGRAPHS}}": about_html,
        "{{STAR_RATING_HTML}}": stars_html(rating, "small"),
        "{{STAR_RATING_HTML_LARGE}}": stars_html(rating, "large"),
    }

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return html


def save_website(html: str, business_name: str) -> Path:
    """Saves the HTML string to output/<business_slug>.html. Returns the path."""
    slug = sanitize_filename(business_name)
    if not slug:
        slug = f"business_{int(time.time())}"
    output_path = OUTPUT_DIR / f"{slug}.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# CSV OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def save_csv(leads_data: list[dict], niche: str, city: str) -> Path:
    """
    Saves a CSV file with all lead info + path to generated website.
    Returns the path to the CSV.
    """
    city_slug = sanitize_filename(city)
    niche_slug = sanitize_filename(niche)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUTPUT_DIR / f"leads_{niche_slug}_{city_slug}_{timestamp}.csv"

    fieldnames = ["business_name", "phone", "address", "email", "website_path", "rating", "review_count", "place_id"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads_data:
            writer.writerow({
                "business_name": lead.get("name", ""),
                "phone": lead.get("formatted_phone_number", ""),
                "address": lead.get("formatted_address", ""),
                "email": lead.get("email", ""),          # rarely available via Places API
                "website_path": str(lead.get("html_path", "")),
                "rating": lead.get("rating", ""),
                "review_count": lead.get("user_ratings_total", ""),
                "place_id": lead.get("place_id", ""),
            })

    return csv_path


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def run(niche: str, city: str, num_leads: int):
    """
    Full pipeline:
      1. Get API keys
      2. Search Google Places for niche + city
      3. Filter to businesses with no website
      4. For each lead: fetch reviews, generate AI copy, build HTML, save file
      5. Write output CSV
    """
    print("\n" + "=" * 60)
    print("  🏗️   AI Website Builder")
    print(f"  Niche: {niche} | City: {city} | Target leads: {num_leads}")
    print("=" * 60)

    # ── Step 1: API keys ──────────────────────────────────────────
    google_key, anthropic_key = get_api_keys()
    claude_client = anthropic.Anthropic(api_key=anthropic_key)

    # ── Step 2: Search Places ─────────────────────────────────────
    # Fetch more results than we need so we can filter for no-website leads
    search_pool = max(num_leads * 4, 20)
    raw_places = search_places(niche, city, google_key, max_results=search_pool)

    if not raw_places:
        print("\n❌  No places found. Try a different niche or city.")
        return

    # ── Step 3: Filter to no-website leads ───────────────────────
    leads = filter_no_website(raw_places, google_key, num_leads)

    if not leads:
        print("\n❌  No businesses without websites found. Try a broader search.")
        return

    # ── Step 4: Generate sites ────────────────────────────────────
    print(f"\n🤖  Generating AI websites for {len(leads)} leads...\n")
    processed = []

    for i, business in enumerate(leads, 1):
        name = business.get("name", f"Business {i}")
        print(f"  [{i}/{len(leads)}] Building site for: {name}")

        try:
            # Generate AI copy
            print(f"    → Calling Claude for website copy...", end=" ", flush=True)
            content = generate_website_content(business, niche, city, claude_client)
            print("done.")
            time.sleep(SLEEP_BETWEEN_CALLS)

            # Assemble HTML from template + AI content
            html = assemble_html(business, content, city)

            # Save HTML file
            html_path = save_website(html, name)
            business["html_path"] = html_path
            print(f"    → Saved: {html_path}")

            processed.append(business)

        except FileNotFoundError as e:
            print(f"\n  ❌  {e}")
            raise
        except Exception as e:
            print(f"\n    ⚠️  Skipping {name} due to error: {e}")
            continue

        time.sleep(SLEEP_BETWEEN_CALLS)

    if not processed:
        print("\n❌  No websites were successfully generated.")
        return

    # ── Step 5: Save CSV ──────────────────────────────────────────
    csv_path = save_csv(processed, niche, city)

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  ✅  Done! Generated {len(processed)} websites.")
    print(f"  📁  HTML files: {OUTPUT_DIR}/")
    print(f"  📊  CSV leads:  {csv_path}")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Open any HTML file in your browser to preview the site")
    print("  2. Use the CSV to reach out to each business")
    print("  3. Offer to host the site for them (easy upsell!)\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Website Builder — finds local businesses without websites and generates premium HTML sites.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          python website_builder.py --niche plumber --city "Phoenix AZ" --leads 5
          python website_builder.py --niche "electrician" --city "Austin TX" --leads 10
          python website_builder.py --niche "landscaper" --city "Miami FL" --leads 3

        API Keys (set as environment variables to skip prompts):
          export GOOGLE_PLACES_API_KEY=your_key_here
          export ANTHROPIC_API_KEY=your_key_here
        """)
    )
    parser.add_argument(
        "--niche",
        required=True,
        help='Business type to search for (e.g. "plumber", "electrician", "roofer")',
    )
    parser.add_argument(
        "--city",
        required=True,
        help='City and state to search in (e.g. "Phoenix AZ", "Austin TX")',
    )
    parser.add_argument(
        "--leads",
        type=int,
        default=5,
        help="Number of no-website businesses to find and build sites for (default: 5)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(niche=args.niche, city=args.city, num_leads=args.leads)
