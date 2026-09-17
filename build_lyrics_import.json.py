import json
import os
import re
import time
import urllib.parse
import bs4
import cloudscraper
import pandas as pd

# Base URL du Wiki Fandom NOPLP
BASE_URL = "https://n-oubliez-pas-les-paroles.fandom.com"

# Pages d'index listant toutes les chansons avec les slugs exacts
INDEX_URLS = [
    "https://n-oubliez-pas-les-paroles.fandom.com/fr/wiki/Liste_des_chansons_existantes_(de_la_lettre_A_%C3%A0_la_lettre_M)",
    "https://n-oubliez-pas-les-paroles.fandom.com/fr/wiki/Liste_des_chansons_existantes_(de_la_lettre_N_%C3%A0_la_lettre_Z)",
]

# Initialisation du scraper anti-Cloudflare
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


# 1. Extraction de tous les liens de chansons depuis les pages d'index
def get_all_song_urls() -> list[str]:
    song_urls = []
    print("--- Récupération des liens depuis les index ---")

    for index_url in INDEX_URLS:
        try:
            res = scraper.get(index_url, timeout=15)
            res.raise_for_status()
            soup = bs4.BeautifulSoup(res.content, "html.parser")
            content = soup.find("div", class_="mw-parser-output")

            if not content:
                continue

            for a in content.find_all("a", href=True):
                href = a["href"]
                # Filtre les liens internes vers les pages de chansons
                if href.startswith("/fr/wiki/") and ":" not in href:
                    full_url = urllib.parse.urljoin(BASE_URL, href)
                    if full_url not in song_urls and not full_url.endswith(
                        ("Liste_des_chansons_(A-M)", "Liste_des_chansons_(N-Z)")
                    ):
                        song_urls.append(full_url)
        except Exception as e:
            print(f"Erreur lors du chargement de l'index {index_url}: {e}")

    print(f"Total de chansons trouvées : {len(song_urls)}")
    return song_urls


# 2. Scraper d'une page de chanson individuelle
def parse_song_page(url: str) -> dict | None:
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200:
            return None

        soup = bs4.BeautifulSoup(res.content, "html.parser")
        content = soup.find("div", class_="mw-parser-output")
        if not content:
            return None

        track_id = url.split("/")[-1]

        # Titre
        title_tag = soup.find("h1", id="firstHeading")
        title = (
            title_tag.text.strip()
            if title_tag
            else track_id.replace("_", " ")
        )

        # Interprète
        artist_display = None
        text_nodes = content.get_text("\n").split("\n")
        for line in text_nodes:
            if "Interprète" in line and ":" in line:
                artist_display = line.split(":", 1)[1].strip()
                break

        # Paroles
        paroles_heading = soup.find("span", id="Paroles")
        lyrics_lines = []

        if paroles_heading:
            parent_h = paroles_heading.find_parent(["h2", "h3"])
            if parent_h:
                for elem in parent_h.find_next_siblings():
                    if elem.name in ["h2", "h3"]:
                        break
                    if elem.name == "p":
                        text = elem.get_text(strip=True)
                        if text and not text.startswith("Légende"):
                            lyrics_lines.append(text)

        lyrics = "\n".join(lyrics_lines) if lyrics_lines else None

        if not lyrics:
            return None

        return {
            "id": track_id,
            "title": title,
            "artist_display": artist_display or "Artiste Inconnu",
            "lyrics": lyrics,
            "language": "fr",
            "genre": None,
        }

    except Exception as e:
        print(f"Erreur sur {url}: {e}")
        return None


# 3. Adaptation au format d'importation
def build_dataframe(extracted_songs: list[dict]) -> pd.DataFrame:
    records = []
    for item in extracted_songs:
        records.append(
            {
                "track_id": item["id"],
                "track_name": item["title"],
                "artist_name": item["artist_display"],
                "lyrics": item["lyrics"],
                "language": item["language"],
                "genre": item["genre"],
            }
        )
    return pd.DataFrame(records)


# --- Exécution principale ---
if __name__ == "__main__":
    urls = get_all_song_urls()
    extracted_data = []

    print("\n--- Scraping des chansons en cours ---")
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] Scraping: {url.split('/')[-1]}...")
        song_dict = parse_song_page(url)

        if song_dict:
            extracted_data.append(song_dict)

        # Pause pour éviter la surcharge
        time.sleep(0.3)

    # Conversion en DataFrame
    df_catalog = build_dataframe(extracted_data)

    print("\n--- Aperçu du résultat ---")
    print(df_catalog.head())
    print(f"\nNombre total de chansons récupérées avec paroles : {len(df_catalog)}")

    # Sauvegarde
    os.makedirs("data", exist_ok=True)
    output_json = "data/lyrics_import.json"

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)

    print(f"\nFichier sauvegardé avec succès dans : {output_json}")