# NOPLP Révision

Application web locale d'entraînement pour *N'oubliez pas les paroles* (NOPLP) :
exercices karaoké à trous (mode "trous" ou mode "coupure", comme à la TV),
suivi des scores et révision ciblée des mots les plus souvent ratés.

Prototype pour usage personnel, à lancer en local (Flask + SQLite, sans
authentification).

## ⚠️ À propos des paroles

**Cette application ne contient, ne récupère et ne génère aucune parole de
chanson.** Le répertoire (`data/catalog.json`, 2949 chansons) a été
constitué à partir du wiki fan *N'oubliez pas les paroles* et ne contient que
des métadonnées : titre, artiste(s), regroupement (comédie musicale, film...),
crédits "avec"/"chanté par", et indicateurs "même chanson" (présentée 10 fois
ou plus, probable reprise, ère des 100 000 €). La colonne `lyrics` de la base
de données reste vide tant que **tu** n'y ajoutes rien.

Les paroles de chansons sont protégées par le droit d'auteur : à toi de les
saisir depuis des sources dont tu as le droit de te servir (tes propres
notes, un service sous licence auquel tu es abonné, etc.), via l'écran
Admin ou via `import_lyrics.py`. Aucune fonctionnalité de scraping/récupération
automatique de paroles n'est fournie ni prévue.

## Installation

```bash
cd noplp_app
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Premier lancement

```bash
# 1. Initialise la base et charge le catalogue (titres/artistes uniquement)
python3 seed_catalog.py

# 2. Lance le serveur
python3 app.py
```

Ouvre ensuite http://127.0.0.1:5000 dans ton navigateur.

`seed_catalog.py` peut être relancé sans risque à tout moment (par exemple
après une mise à jour de `data/catalog.json`) : il met à jour le catalogue
par identifiant et ne touche jamais à la table `lyrics`.

## Ajouter des paroles

Deux méthodes, à combiner comme tu veux :

### 1. Manuellement, depuis l'appli

Va sur `/admin`, cherche une chanson, colle le texte (une ligne de couplet
par ligne de texte) et enregistre. Tu peux ensuite directement tester
l'exercice depuis cet écran.

### 2. En bulk, avec ton propre script + `import_lyrics.py`

`import_lyrics.py` lit un fichier JSON que **tu** fournis (assemblé par tes
soins, par exemple avec ton propre script qui interroge une source dont tu as
les droits) et l'importe dans la base. Format attendu — voir
`data/lyrics_import_example.json` pour un exemple complet avec du texte
factice :

```json
[
  {
    "song_id": "sardou-michel-les-lacs-du-connemara",
    "wiki_target": "Les lacs du Connemara",
    "lyrics": "Ligne 1...\nLigne 2...\n...",
    "source_note": "Saisi à la main depuis mon cahier de révision"
  }
]
```

- `song_id` (recommandé) : identifiant exact tel que généré dans
  `data/catalog.json`.
- `wiki_target` : à défaut, correspondance par le titre original de la page
  wiki (utile si tu ne connais pas l'id généré).
- Priorité de correspondance : `song_id` d'abord, puis `wiki_target`.

```bash
python3 import_lyrics.py data/lyrics_import_example.json --dry-run   # aperçu, n'écrit rien
python3 import_lyrics.py data/mes_paroles.json                       # import réel
```

Les entrées sans correspondance sont listées en fin d'exécution, sans qu'aucune
tentative de "deviner" la bonne chanson ne soit faite.

## Modes d'exercice

- **Coupure** (mode principal, fidèle à l'émission) : le texte s'affiche
  normalement jusqu'à une ligne choisie au hasard, s'arrête brutalement au
  milieu de cette ligne, et il faut taper la suite (fin de la ligne + la
  ligne suivante en entier).
- **Trous** : des mots sont effacés un peu partout dans le texte, soit tous
  les *N* mots ("every_n"), soit uniquement les mots longs et peu fréquents
  ("keywords").

La correction est insensible aux accents/majuscules par défaut (une case
"Accents stricts" permet d'exiger une orthographe exacte).

## Suivi des scores et révision des erreurs

- Chaque exercice terminé crée une session (`/api/stats` en donne un résumé :
  score moyen, chansons les plus jouées, mots les plus ratés).
- Chaque mot manqué est comptabilisé par position exacte dans la chanson
  (`error_bank`), de façon stable d'une session à l'autre même si le mode ou
  les paramètres changent.
- L'écran **Révision des erreurs** (`/review`) construit un petit quiz avec
  les mots les plus souvent ratés, tous morceaux confondus, chacun affiché
  avec un peu de contexte. La correction se fait entièrement côté serveur :
  le mot attendu n'est jamais envoyé au navigateur avant validation.

## Structure du projet

```
noplp_app/
├── app.py              # Flask : routes pages + API JSON
├── blanking.py         # génération des trous / coupures, correction
├── db.py               # connexion SQLite + initialisation du schéma
├── schema.sql           # schéma SQL complet (voir commentaires inline)
├── seed_catalog.py     # charge data/catalog.json -> tables artists/songs
├── import_lyrics.py    # CLI d'import de paroles depuis un JSON fourni par toi
├── requirements.txt
├── data/
│   ├── catalog.json                 # métadonnées scrapées (2949 chansons, sans paroles)
│   ├── lyrics_import_example.json   # exemple factice pour import_lyrics.py
│   └── noplp.db                     # créée au premier lancement
├── templates/           # pages HTML (Jinja)
└── static/              # CSS + JS (vanilla, pas de framework)
```

## Schéma de données

Voir `schema.sql` pour le détail commenté. Résumé :

- `artists` / `songs` : catalogue (métadonnées uniquement, jamais de paroles).
- `lyrics` : paroles saisies par l'utilisateur, une ligne par chanson,
  totalement séparée du catalogue pour que reseeder celui-ci ne les efface
  jamais.
- `sessions` : un essai d'exercice (une chanson, un mode, des paramètres).
- `blank_attempts` : le détail par mot d'une session.
- `error_bank` : compteur glissant par (chanson, position de mot), utilisé
  pour prioriser la révision.

## Limitations connues de ce prototype

- Usage mono-utilisateur, sans authentification (prévu pour un usage
  strictement personnel, en local).
- Les exercices actifs sont gardés en mémoire (`ACTIVE_EXERCISES`) : ils sont
  perdus si le serveur redémarre en cours d'exercice (sans conséquence, il
  suffit de relancer).
- Le serveur de développement Flask (`app.run(debug=True)`) est utilisé
  volontairement : ce projet n'est pas prévu pour être exposé sur un réseau
  public.
