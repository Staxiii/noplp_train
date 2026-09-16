import json
import pandas as pd


def load_and_adapt_catalog(json_path: str) -> pd.DataFrame:
    """
    Charge le fichier catalog.json et adapte sa structure aux spécifications
    du dictionnaire de données Anamusique.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. Extraction et transformation des entrées
    records = []
    for item in data:
        # Renommage des identifiants et titres
        track_id = item.get('id')
        track_name = item.get('title')

        # Concaténation propre des artistes (Main + Featured / Performed By)
        artist_main = item.get('artist_display') or item.get('artist_raw') or ""
        featured = item.get('featured_artists')
        performed_by = item.get('performed_by')

        artists = [artist_main]
        if featured:
            artists.append(f"feat. {featured}")
        if performed_by and performed_by != artist_main:
            artists.append(f"({performed_by})")

        artist_name = " ".join(filter(None, artists)).strip()

        # Gestion des paroles manquantes (null)
        lyrics = item.get('lyrics')

        # Champs optionnels ou à compléter par la suite
        language = item.get('language')  # 'fr' ou 'en'
        genre = item.get('genre')  # Label cible pour le modèle

        records.append({
            'track_id': track_id,
            'track_name': track_name,
            'artist_name': artist_name,
            'lyrics': lyrics,
            'language': language,
            'genre': genre
        })

    # 2. Conversion en DataFrame Pandas
    df = pd.DataFrame(records)

    return df


def fetch_missing_lyrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fonction stub / placeholder pour compléter les paroles nulles
    via l'API Genius, Musixmatch ou un fichier CSV/paroles externe.
    """
    # Exemple de gestion défensive : isoler les lignes où lyrics est non nul
    # df_clean = df.dropna(subset=['lyrics'])

    print(f"Total morceaux dans le catalogue: {len(df)}")
    print(f"Morceaux sans paroles (lyrics == null): {df['lyrics'].isna().sum()}")

    return df


# --- Exemple d'utilisation ---
if __name__ == "__main__":
    # Chargement
    df_catalog = load_and_adapt_catalog("catalog.json")

    # Vérification du dictionnaire de données
    print("Aperçu du DataFrame adapté :")
    print(df_catalog.head())

    # Inspection de la présence des paroles
    df_catalog = fetch_missing_lyrics(df_catalog)