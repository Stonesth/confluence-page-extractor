# Confluence Page Extractor

python -m venv venv
.\venv\Scripts\Activate.ps1
python .\start_pbi.py

Need to import the folowing project into this one

git clone https://github.com/Stonesth/Tools.git

# import 
pip install selenium
pip install chromedriver_py
pip install keyboard


https://artifactory.insim.biz/artifactory/python/



python -m pip install --index-url "https://artifactory.insim.biz/artifactory/python/simple" selenium
python -m pip install --index-url "https://artifactory.insim.biz/artifactory/nn-npm-remote-cache/" selenium
python -m pip install --index-url "https://artifactory.insim.biz/artifactory/nn-py-pypi-org-cache/" selenium
pip install --index-url "https://artifactory.insim.biz/artifactory/nn-py-pypi-org-cache/" --upgrade pip
python -m pip index versions pip --index-url https://artifactory.insim.biz/artifactory/nn-py-pypi-org-cache/

## Objectif
Créer un outil Python capable de :
- extraire une page Confluence ;
- détecter et extraire toutes ses sous-pages (récursif) ;
- stocker les données de manière structurée dans un dossier local.

## Logique du projet

### 1) Point d’entrée
- L’utilisateur fournit un identifiant de page racine (ou URL Confluence).
- L’outil ouvre un navigateur automatisé (Selenium) et utilise une session authentifiée Confluence.

### 2) Récupération de la page
- Lire les métadonnées visibles dans la page : `title`, `url`, `space` (si disponible), `last updated` (si disponible).
- Récupérer le contenu rendu (DOM HTML) + éventuellement une version texte nettoyée.

### 3) Parcours des sous-pages (récursif)
- Pour chaque page, détecter les liens vers les sous-pages depuis la navigation Confluence (sidebar, arbre de pages, section enfants, liens internes).
- Si des sous-pages existent :
  - répéter le processus pour chaque enfant ;
  - conserver la relation parent/enfant.

### 4) Stockage local structuré
- Créer une arborescence miroir du contenu Confluence :
  - un dossier par page ;
  - un fichier `metadata.json` ;
  - un fichier `content.html` (et optionnellement `content.md` ou `content.txt`).
- Exemple de structure :

```text
output/
  123456-Home/
    metadata.json
    content.html
    children/
      123457-Guide/
        metadata.json
        content.html
      123458-FAQ/
        metadata.json
        content.html
```

### 5) Résilience et qualité
- Gérer le chargement dynamique des pages (attentes explicites, retries, scrolling si nécessaire).
- Gérer les sessions expirées (reconnexion navigateur) et les erreurs de navigation.
- Journaliser les pages récupérées, ignorées, et en erreur.
- Générer un index global (`index.json`) avec l’ensemble des pages extraites.

## Étape en cours
- Création du repository GitHub dans `Stonesth`.

## Prochaines étapes (implémentation)
1. Initialiser le projet Python (`src/`, `requirements.txt`, `config`).
2. Implémenter le module navigateur (Selenium + Chrome/Firefox driver).
3. Implémenter le crawler récursif des sous-pages via le DOM.
4. Implémenter l’export structuré sur disque.
5. Ajouter tests unitaires et mode CLI.

## Contraintes
- Pas d’API Confluence : extraction uniquement via scraping navigateur.
- Respecter les droits d’accès de l’utilisateur connecté.
