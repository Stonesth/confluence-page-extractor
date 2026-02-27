# Confluence Page Extractor — Étapes de réalisation

## Contraintes à respecter
- **Pas d'API Confluence** : tout se fait via scraping navigateur (Selenium).
- Respecter les droits d'accès de l'utilisateur connecté dans le navigateur.
- Les dépendances sont installées depuis Artifactory :
  ```
  pip install --index-url "https://artifactory.insim.biz/artifactory/nn-py-pypi-org-cache/" <package>
  ```

## Existant déjà en place
- `ConfluencePageExtractor.py` ouvre déjà le navigateur Chrome et navigue vers une page Confluence cible.
- Le dossier `Tools/` contient déjà des utilitaires de connexion et de pilotage navigateur (`tools_v000.py`).
- La suite doit donc se concentrer sur : extraction du contenu, découverte récursive des sous-pages, et export structuré.
- `scraper.py` est en place et déjà branché dans `ConfluencePageExtractor.py`.
- Export actuel déjà généré : `output/metadata.json`, `output/content.html` (stylé), `output/content_raw.html`.

---

## Étape 1 — Initialisation du projet

- [x] Créer le repository GitHub `Stonesth/confluence-page-extractor`.
- [ ] Structurer le projet :
  ```
  ConfluencePageExtractor/
    README.md
    STEPS.md
    requirements.txt
    config/
      settings.py          # URL Confluence, timeouts, chemins output
    src/
      __init__.py
      browser.py           # Gestion du navigateur Selenium
      scraper.py           # Extraction du contenu d'une page
      crawler.py           # Parcours récursif des sous-pages
      exporter.py          # Sauvegarde structurée sur disque
      utils.py             # Fonctions utilitaires (slugify, logging…)
    main.py                # Point d'entrée CLI
    Tools/                 # Clone de https://github.com/Stonesth/Tools.git
  ```
- [ ] Créer le `requirements.txt` :
  ```
  selenium
  chromedriver_py
  keyboard
  ```
- [X] Créer le virtual environment et installer les dépendances :
  ```
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install --index-url "https://artifactory.insim.biz/artifactory/nn-py-pypi-org-cache/" -r requirements.txt
  ```
- [X] Cloner le projet Tools :
  ```
  git clone https://github.com/Stonesth/Tools.git
  ```

---

## Étape 2 — Module navigateur (`src/browser.py`)

**Objectif** : ouvrir et piloter un navigateur Chrome/Edge via Selenium.

- [x] Initialiser le WebDriver (Chrome) via `Tools.tools_v000.openBrowserChrome()`.
- [x] Naviguer vers une URL Confluence cible (déjà fait dans `ConfluencePageExtractor.py`).
- [ ] Attendre que l'utilisateur soit authentifié (détection d'un élément post-login, ou pause manuelle).
- [ ] Fournir des méthodes utilitaires :
  - `open_page(url)` — naviguer vers une URL et attendre le chargement complet.
  - `get_page_source()` — retourner le HTML rendu.
  - `close()` — fermer le navigateur proprement.
- [ ] Gérer les sessions expirées (détection de la page de login → alerte / reconnexion).

---

## Étape 3 — Extraction du contenu (`src/scraper.py`)

**Objectif** : extraire les données utiles d'une page Confluence ouverte dans le navigateur.

- [x] Extraire le **titre** de la page (`#title-text`, `h1`, ou sélecteur Confluence adapté).
- [x] Extraire le **contenu principal** (zone `#main-content` ou équivalent).
  - Version HTML brute.
  - Version texte nettoyée (optionnel).
- [x] Extraire les **métadonnées** visibles :
  - URL courante.
  - Space (breadcrumb ou sidebar).
  - Date de dernière modification (si affichée).
  - Auteur (si affiché).
- [x] Retourner un dictionnaire structuré :
  ```python
  {
      "title": "...",
      "url": "...",
      "space": "...",
      "last_updated": "...",
      "author": "...",
      "content_html": "...",
      "content_text": "...",
      "head_styles": "..."
  }
  ```

- [x] Générer un HTML de sortie plus lisible en conservant les styles de la page (head CSS + fallback local).

---

## Étape 4 — Crawler récursif des sous-pages (`src/crawler.py`)

**Objectif** : à partir d'une page racine, découvrir et parcourir toutes les sous-pages.

- [x] Détecter les **liens vers les sous-pages** (prototype) :
  - Depuis la sidebar / arbre de navigation Confluence.
  - Depuis la section "Sous-pages" (child pages) dans le corps de la page.
  - Filtrer pour ne garder que les liens internes Confluence (même domaine, même space).
- [x] Construire un **arbre de pages** (relation parent → enfants).
- [x] Parcourir récursivement chaque sous-page :
  - Ouvrir la page via `browser.open_page(url)`.
  - Extraire le contenu via `scraper.extract(driver)`.
  - Détecter les sous-pages de cette page → récursion.
- [x] Éviter les **boucles** : maintenir un ensemble d'URLs déjà visitées.
- [x] Gérer la profondeur maximale (optionnel, configurable).

Note : implémenté dans `crawler.py` avec `crawl_and_save(...)` et intégré dans `ConfluencePageExtractor.py` (actuellement `max_depth=1`).

---

## Étape 5 — Export structuré sur disque (`src/exporter.py`)

**Objectif** : sauvegarder chaque page et ses enfants dans une arborescence locale.

- [ ] Pour chaque page extraite, créer un dossier nommé `<slug-du-titre>/` :
  ```
  output/
    Home/
      metadata.json
      content.html
      children/
        Guide/
          metadata.json
          content.html
        FAQ/
          metadata.json
          content.html
  ```
- [x] Écrire `metadata.json` avec les infos extraites (titre, URL, space, date, auteur).
- [x] Écrire `content.html` avec le contenu HTML de la page (version stylée lisible).
- [x] Écrire `content_raw.html` avec le contenu HTML brut extrait.
- [ ] (Optionnel) Écrire `content.txt` ou `content.md` avec le contenu nettoyé.
- [ ] Générer un fichier `index.json` à la racine d'output :
  ```json
  {
      "extracted_at": "2026-02-27T10:00:00",
      "root_url": "https://...",
      "total_pages": 42,
      "pages": [
          { "title": "Home", "url": "...", "path": "output/Home/", "children_count": 2 },
          ...
      ]
  }
  ```

---

## Étape 6 — Point d'entrée CLI (`main.py`)

**Objectif** : permettre le lancement en ligne de commande.

- [ ] Accepter les arguments :
  - `--url` : URL de la page racine Confluence.
  - `--output` : dossier de sortie (défaut : `output/`).
  - `--depth` : profondeur maximale (défaut : illimité).
  - `--browser` : choix du navigateur (`chrome`, `edge`).
- [ ] Orchestrer le flux :
  1. Initialiser le navigateur.
  2. Ouvrir la page racine.
  3. Lancer le crawler récursif.
  4. Exporter les résultats.
  5. Afficher un résumé (nombre de pages, erreurs).
  6. Fermer le navigateur.

---

## Étape 7 — Résilience et logging (`src/utils.py`)

- [ ] Configurer un logger (console + fichier `extractor.log`).
- [ ] Journaliser chaque page : visitée, extraite, ignorée, en erreur.
- [ ] Implémenter un mécanisme de retry en cas d'erreur de chargement.
- [ ] Gérer les timeouts (page qui ne charge pas → skip + log).
- [ ] Gérer la détection de session expirée (redirection vers login).

---

## Étape 8 — Tests et validation

- [x] Tester `scraper.py` sur une page Confluence connue.
- [ ] Tester `crawler.py` sur une page avec 2-3 niveaux de sous-pages.
- [ ] Valider la structure de sortie (`output/`, `index.json`).
- [ ] Vérifier la gestion des erreurs (page inexistante, timeout, boucle).

---

## Blocage courant

- L'exécution échoue selon l'environnement actif si `selenium` n'est pas installé dans le venv utilisé (`ModuleNotFoundError: selenium`).
- Action à stabiliser : activer le bon venv puis installer via Artifactory avant exécution.

---

## Résumé du flux d'exécution

```
[Utilisateur]
     │
     ▼
  main.py --url <URL> --output output/
     │
     ▼
  browser.py  →  Ouvre le navigateur, navigue vers l'URL
     │
     ▼
  crawler.py  →  Détecte les sous-pages, parcourt récursivement
     │                │
     │                ▼
     │          scraper.py  →  Extrait titre, contenu, métadonnées
     │
     ▼
  exporter.py  →  Sauvegarde dans output/ (metadata.json + content.html)
     │
     ▼
  index.json  →  Index global de toutes les pages extraites
```
