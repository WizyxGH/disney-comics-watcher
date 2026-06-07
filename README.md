# Disney Comics Watcher

Surveille automatiquement les nouvelles sorties de magazines et BD Disney en France, et envoie une notification dans un canal Telegram à chaque nouveau numéro.

## Sources surveillées

| Source | Ce qu'elle couvre |
|---|---|
| [direct-editeurs.fr](https://direct-editeurs.fr) | Magazines actifs (Picsou, Mickey, Fantomiald…) |
| [catalogueproduits.mlp.fr](https://catalogueproduits.mlp.fr) | Complémentaire : titres absents de DE (Picsou Soir, Destin de Picsou…) |
| [glenat.com/livres-glenat-disney](https://www.glenat.com/livres-glenat-disney/) | Albums BD Disney (Picsou, Mickey, Don Rosa, Scarpa…) |

## Types de notifications

- 🦆 / 💰 / 🐭 … **Nouveau numéro de magazine** — avec cover, numéro, prix et dates
- 📢 **Annonce Glénat** — quand un album apparaît « à paraître » dans le catalogue
- 📚 **Sortie Glénat** — quand la date de parution est atteinte

## Installation

### 1. Créer le bot Telegram

1. Ouvre Telegram → cherche **@BotFather**
2. Envoie `/newbot`, suis les instructions
3. Copie le **token** (ex: `123456:ABC-DEF...`)

### 2. Créer le canal d'annonce

1. Crée un canal Telegram (public recommandé)
2. Ajoute le bot comme **administrateur** avec la permission "Poster des messages"
3. Note l'username du canal (ex: `@DisneyComicsWatcher`)

### 3. Créer le repo GitHub

1. Crée un nouveau repo GitHub (public ou privé)
2. Pousse ce code sur la branche `main`

### 4. Ajouter les secrets GitHub

Dans ton repo → **Settings → Secrets and variables → Actions → New repository secret** :

| Nom du secret | Valeur |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Le token obtenu via @BotFather |
| `TELEGRAM_CHAT_ID_FR` | L'username du canal (ex: `@DisneyComicsWatcher`) |

### 5. Activer GitHub Actions

Va dans l'onglet **Actions** de ton repo. Si désactivé, clique sur
*"I understand my workflows, go ahead and enable them"*.

### 6. Test manuel

**Actions → Disney Comics Watcher 🦆 → Run workflow**

Le premier run initialise le state silencieusement (aucun flood).
Les runs suivants notifient uniquement les nouveaux numéros.

## Comment ça marche

1. Le script tourne **toutes les heures** (à la minute 0) via GitHub Actions
2. Il interroge Direct Éditeurs et MLP pour découvrir tous les magazines Disney actifs
3. Il compare avec le dernier numéro connu (stocké dans `state.json` sur la branche `datas`)
4. Pour chaque nouveau numéro → notification Telegram avec cover, prix et dates
5. En parallèle, il surveille les albums Glénat (annonces + sorties)
6. Le `state.json` est commité sur la branche `datas` (le code reste propre sur `main`)
7. À chaque nouvelle parution détectée, un **squelette de pré-index Inducks** (format `.dbi`) est ajouté au fichier local `fr.dbi` à la racine du projet.

## Pré-index Inducks (`fr.dbi`)

À chaque nouvelle parution notifiée, le script génère automatiquement un fichier de pré-index au format [Inducks Bolderbast DBI](https://inducks.org/bolderbast/xh7111_DBIReader.html) et l'ajoute par concaténation (mode *append*) dans le fichier `fr.dbi` à la racine.

### Ce que contient le fichier

Chaque squelette d'index généré contient :

- Une **ligne d'en-tête `h3`** correctement formatée (positions fixes selon la spec Bolderbast) avec :
  - Le code Inducks de la parution (ex: `fr/PM  580` ou `->` si le code dépasse 12 caractères comme pour `fr/JM 3858-59`)
  - La date de parution `[issdate:YYYY-MM-DD]`
  - Le prix `[price:X.XX EUR]`
  - Pour les albums Glénat : le titre du livre, le nombre de pages `[pages:XX]`, les dimensions `[size:...]`, le traducteur `[isstrans:...]` et l'EAN `[EAN:...]` (si disponibles)
  - `[inx:-]` indiquant que l'index est à compléter
- Une **ligne d'entrée pré-remplie pour la couverture** (pages = `1`, brokpg = vide, pagel = `c`)
- Un **gabarit commenté** (lignes `^^`) expliquant le format des lignes d'entrée (couverture, histoires) pour aider l'indexeur

### Exemple de fichier généré (magazine)

```
^^ Pre-index genere automatiquement par DisneyComicsWatcher
^^ Source : magazine
^^ A completer et soumettre sur https://inducks.org/bolderbast/
fr/PM  580   h3 [issdate:2026-06-10] [price:6.50 EUR] [inx:-]
fr/PM  580a ?              1 c                      

^^ -- Entrees a completer ci-dessous --
...
```

### Comment l'utiliser

1. Récupère le fichier `fr.dbi` à la racine du projet (disponible dans les artefacts de run de la GitHub Action).
2. Complète la ligne de couverture et les entrées avec les histoires du numéro (storycode, pages, crédits…).
3. Soumets le contenu correspondant à ton index sur [Inducks Bolderbast](https://inducks.org/bolderbast/).

### Codes Inducks pré-configurés

Les publications dont le code Inducks est connu (configuré dans `OVERRIDES`) génèrent directement le bon code (ex: `fr/PM`, `fr/JM`, `fr/CF`). Pour les autres, un code provisoire `fr/TODO_<codif>` est utilisé — à corriger avant soumission.

Pour les albums Glénat, les séries connues sont automatiquement reconnues :

| Série | Code Inducks |
|---|---|
| La Grande Histoire de Picsou (Don Rosa) | `fr/GHP` |
| Les Âges d'or de Disney | `fr/AOD` |

## Personnaliser un magazine

Pour ajouter un emoji ou un nom dédié à un magazine découvert automatiquement,
ajoute son `codif` dans `OVERRIDES` dans `check_magazines.py` :

```python
OVERRIDES = {
    "12345": {"name": "Mon Magazine", "emoji": "📰"},
    ...
}
```

Le codif est visible dans l'URL sur direct-editeurs.fr.

## Ajouter un nouveau pays (future extension)

1. Crée un nouveau canal Telegram pour le pays
2. Ajoute un secret `TELEGRAM_CHAT_ID_XX` (ex: `TELEGRAM_CHAT_ID_DE` pour l'Allemagne)
3. Duplique le job dans `watcher.yml` avec `TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID_XX }}`
4. Adapte les sources et mots-clés pour le nouveau pays
