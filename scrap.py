import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --------------------------
# Google Sheets Setup
# --------------------------
SHEET_NAME = "Sid_Was_Here"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

with open("/etc/secrets/google_creds.json") as f:
    creds_dict = json.load(f)
    
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# --------------------------
# Scraper Config
# --------------------------
BASE_URL = "https://sidwashere.com/long-term-rentals/"
headers = {"User-Agent": "Mozilla/5.0"}

# --------------------------
# Helper Functions
# --------------------------
def extract_number(text):
    match = re.search(r"\d+(?:\.\d+)?", text)
    return match.group(0) if match else "N/A"

def extract_numeric_value(text):
    clean_text = re.sub(r"[^\d]", "", text)
    return clean_text if clean_text else "N/A"

def extract_availability(text):
    if not text:
        return "Now"
    text = text.strip()
    if "Available Now" in text or text.strip().lower() == "now":
        return "Now"
    match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", text)
    return match.group(1) if match else "Now"

# --------------------------
# Main Scraper
# --------------------------
print("🔍 Fetching listings page...")
resp = requests.get(BASE_URL, headers=headers)
soup = BeautifulSoup(resp.text, "html.parser")
listings = soup.select(".all-listings .listing-item")
print(f"Found {len(listings)} listings.\n")

properties = []

for i, listing in enumerate(listings, 1):
    link_tag = listing.select_one("a")
    property_url = urljoin(BASE_URL, link_tag['href']) if link_tag else None

    title = listing.select_one(".lstng_ttl")
    address = listing.select_one(".address")
    price = listing.select_one(".rent-price")
    beds = listing.select_one(".beds")
    baths = listing.select_one(".baths")
    area = listing.select_one(".area")
    avail = listing.select_one(".lstng-avail")

    rental_terms = []
    pet_policy = "No policy"

    # Get details from property page
    if property_url:
        detail_resp = requests.get(property_url, headers=headers)
        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
        section = detail_soup.select_one('.listing-sec')
        if section:
            for block in section.select(".extra-half"):
                heading = block.select_one("h4")
                items = block.select("ul li")
                texts = [item.get_text(strip=True) for item in items]
                if heading:
                    label = heading.get_text(strip=True).lower()
                    if "rental" in label:
                        rental_terms = [line for line in texts if not re.search(r"available", line, re.IGNORECASE)]
                    elif "pet" in label:
                        pet_policy = "; ".join(texts)

    # Extract lid for Apply Link
    lid_match = re.search(r"lid=([a-f0-9\-]+)", property_url or "")
    lid = lid_match.group(1) if lid_match else None
    apply_link = f"https://remaxaccent.appfolio.com/apply/{lid}/start?source=Website" if lid else ""

    prop_data = {
        "Title": title.get_text(strip=True) if title else "N/A",
        "Address": address.get_text(strip=True) if address else "N/A",
        "Price": extract_numeric_value(price.get_text(strip=True)) if price else "N/A",
        "Bedrooms": extract_number(beds.get_text(strip=True)) if beds else "N/A",
        "Bathrooms": extract_number(baths.get_text(strip=True)) if baths else "N/A",
        "Area": extract_numeric_value(area.get_text(strip=True)) if area else "N/A",
        "Available": extract_availability(avail.get_text(strip=True) if avail else ""),
        "Rental Terms": rental_terms,
        "Pet Policy": pet_policy,
        "Property Link": property_url,
        "Apply Link": apply_link,
    }
    properties.append(prop_data)
    print(f"✅ Scraped {i}: {prop_data['Title']}")

# --------------------------
# Upload to Google Sheets
# --------------------------
print("\n📤 Uploading to Google Sheets...")
sheet.clear()
header = [
    "Title", "Address", "Rent", "Beds", "Baths", "Area",
    "Available From", "Rental Terms", "Pet Policy", "Property Link", "Apply Link"
]
rows = []
for p in properties:
    rows.append([
        p["Title"],
        p["Address"],
        p["Price"],
        p["Bedrooms"],
        p["Bathrooms"],
        p["Area"],
        p["Available"],
        "; ".join(p["Rental Terms"]),
        p["Pet Policy"],
        p["Property Link"],
        p["Apply Link"],
    ])
sheet.update('A1', [header] + rows)
print("🎉 Done! Google Sheet updated successfully.")




