# Confluence Page Extractor

## Objectif
Créer un outil Python capable de :
- extraire une page Confluence ;
- détecter et extraire toutes ses sous-pages (récursif) ;
- stocker les données de manière structurée dans un dossier local.

## Logique du projet

### 1) Point d’entrée
- L’utilisateur fournit un identifiant de page racine (ou URL Confluence).
- L’outil se connecte à l’API Confluence avec un token.

### 2) Récupération de la page
- Lire les métadonnées de la page : `id`, `title`, `space`, `version`, `updatedAt`, `author`.
- Récupérer le contenu principal (HTML / stockage Confluence) + éventuellement une version texte nettoyée.

### 3) Parcours des sous-pages (récursif)
- Pour chaque page, appeler l’endpoint des enfants.
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
- Gérer la pagination de l’API.
- Gérer les limites de taux (retry avec backoff).
- Journaliser les pages récupérées, ignorées, et en erreur.
- Générer un index global (`index.json`) avec l’ensemble des pages extraites.

## Étape en cours
- Création du repository GitHub dans `Stonesth`.

## Prochaines étapes (implémentation)
1. Initialiser le projet Python (`src/`, `requirements.txt`, `config`).
2. Implémenter le client Confluence API.
3. Implémenter le crawler récursif.
4. Implémenter l’export structuré sur disque.
5. Ajouter tests unitaires et mode CLI.
