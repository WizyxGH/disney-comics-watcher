# Disney Comics Watcher 🦆

Surveille automatiquement les nouvelles sorties de magazines et BD Disney en France, et envoie une notification dans un canal Telegram à chaque nouveau numéro.

## Sources surveillées

| Source | Ce qu'elle couvre |
|---|---|
| [direct-editeurs.fr](https://direct-editeurs.fr) | Magazines actifs (Picsou, Mickey, Fantomiald…) |
| [catalogueproduits.mlp.fr](https://catalogueproduits.mlp.fr) | Complémentaire : titres absents de DE (Picsou Soir, Destin de Picsou…) |
| [glenat.com/livres-glenat-disney](https://www.glenat.com/livres-glenat-disney/) | Albums BD Disney (Picsou, Mickey, Don Rosa, Scarpa…) |

## Types de notifications

- 🦆 / 💰 / 🐭 … **Nouveau numéro de magazine** — avec cover, numéro, prix, dates et lien Inducks
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
4. Pour chaque nouveau numéro → notification Telegram avec cover, prix, dates et lien Inducks
5. En parallèle, il surveille les albums Glénat (annonces + sorties)
6. **Fenêtre calme** : aucune notification entre 23h et 7h (heure Paris)
7. Le `state.json` est commité sur la branche `datas` (le code reste propre sur `main`)

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
