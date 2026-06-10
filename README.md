# Disney Comics Watcher

Automatically monitors new releases of Disney magazines and comic books in France, and sends a notification to a Telegram channel for every new issue.

## Monitored Sources

| Source | What it covers |
|---|---|
| [direct-editeurs.fr](https://direct-editeurs.fr) | Active magazines (Picsou, Mickey, Fantomiald…) |
| [catalogueproduits.mlp.fr](https://catalogueproduits.mlp.fr) | Complementary: issues missing from DE (Picsou Soir, Destin de Picsou…) |
| [glenat.com/livres-glenat-disney](https://www.glenat.com/livres-glenat-disney/) | Disney comic books/graphic novels (Picsou, Mickey, Don Rosa, Scarpa…) |

## Notification Types

- 🦆 / 💰 / 🐭 … **New magazine issue** — with cover, issue number, price, and dates
- 📢 **Glénat announcement** — when a book appears as "to be published" in the catalog
- 📚 **Glénat release** — when the publication date is reached

## Installation

### 1. Create the Telegram Bot

1. Open Telegram → search for **@BotFather**
2. Send `/newbot` and follow the instructions
3. Copy the **token** (e.g., `123456:ABC-DEF...`)

### 2. Create the Announcement Channel

1. Create a Telegram channel (public recommended)
2. Add the bot as an **administrator** with "Post Messages" permission
3. Note the channel's username (e.g., `@DisneyComicsWatcher`)

### 3. Create the GitHub Repository

1. Create a new GitHub repository (public or private)
2. Push this code to the `main` branch

### 4. Add GitHub Secrets

In your repository → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | The token obtained via @BotFather |
| `TELEGRAM_CHAT_ID_FR` | The channel's username (e.g., `@DisneyComicsWatcher`) |

### 5. Enable GitHub Actions

Go to the **Actions** tab of your repository. If disabled, click on
*"I understand my workflows, go ahead and enable them"*.

### 6. Manual Test

**Actions → Disney Comics Watcher → Run workflow**

The first run initializes the state silently (no flooding).
Subsequent runs will only notify you of new issues.

### 7. Development and Local Testing

You can run the monitoring script and its tests on your machine without configuring global system variables.
To do this, simply create a `.env` file at the root of the project (this file is already configured in `.gitignore`):

```env
TELEGRAM_BOT_TOKEN=your_test_token
TELEGRAM_CHAT_ID_FR=your_test_chat_id
```

Then run the test suite with:
```powershell
python test_telegram_notif.py
```

## How It Works

1. The script runs **hourly** (at minute 0) via GitHub Actions.
2. It queries Direct Éditeurs and MLP to discover all active Disney magazines.
3. It compares them with the last known issue (stored in `state.json` on the `datas` branch).
4. For each new issue → Telegram notification with cover, price, and dates.
5. In parallel, it monitors Glénat albums (announcements + releases).
6. `state.json` is committed to the `datas` branch (keeping the code clean on `main`).
7. For each detected new release, an **Inducks pre-index skeleton** (in `.dbi` format) is appended to the local `fr.dbi` file at the project root.

## Inducks Pre-index (`fr.dbi`)

For every new notified release, the script automatically generates a pre-index skeleton in the [Inducks Bolderbast DBI format](https://inducks.org/bolderbast/xh7111_DBIReader.html) and appends it to the `fr.dbi` file at the root.

### What the File Contains

Each generated skeleton index contains:

- A properly formatted **`h3` header line** (fixed positions according to the Bolderbast spec) with:
  - The publication's Inducks code (e.g., `fr/PM  580` or `->` if the code exceeds 12 characters, such as `fr/JM 3858-59`)
  - The publication date `[issdate:YYYY-MM-DD]`
  - The price `[price:X.XX EUR]`
  - For Glénat albums: book title, page count `[pages:XX]`, size `[size:...]`, translator name `[isstrans:...]`, and EAN `[EAN:...]` (if available)
  - `[inx:-]` indicating the index needs to be completed
- A **pre-filled entry line for the cover** (pages = `1`, brokpg = empty, pagel = `c`)

### Example of a Generated File (magazine)

```
^^ Pre-index genere automatiquement par DisneyComicsWatcher
^^ Source : magazine
PM  580      h3 [issdate:2026-06-10] [price:6.50 EUR] [inx:-]
PM  580a    ?              1 c                      
```

### How to Use It

1. Retrieve the `fr.dbi` file at the project root (available in the run artifacts of the GitHub Action).
2. Complete the cover line and add entries for the issue's stories (storycode, pages, credits…).
3. Submit the completed index on [Inducks Bolderbast](https://inducks.org/bolderbast/).

### Pre-configured Inducks Codes

Publications with known Inducks codes (configured in `OVERRIDES`) directly generate the correct code (e.g., `fr/PM`, `fr/JM`, `fr/CF`). For others, a temporary code `fr/TODO_<codif>` is used — to be corrected before submission.

For Glénat albums, known series are automatically recognized:

| Series | Inducks Code |
|---|---|
| La Grande Histoire de Picsou (Don Rosa) | `fr/GHP` |
| Les Âges d'or de Disney | `fr/AOD` |

## Customizing a Magazine

To add an emoji or a dedicated name for an automatically discovered magazine, add its `codif` to `OVERRIDES` in `check_magazines.py`:

```python
OVERRIDES = {
    "13159": {"name": "Picsou Magazine", "inducks": ("PM", 5)},
    ...
}
```

The codif is visible in the URL on direct-editeurs.fr.

## Adding a New Country (future extension)

1. Create a new Telegram channel for the country.
2. Add a secret `TELEGRAM_CHAT_ID_XX` (e.g., `TELEGRAM_CHAT_ID_DE` for Germany).
3. Duplicate the job in `watcher.yml` with `TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID_XX }}`.
4. Adapt the sources and keywords for the new country.
