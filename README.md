<div align="center">
  <h1>Disney Comics Watcher</h1>
  <p><strong>The ultimate automated tracker for Disney comic books around the world</strong></p>

  [![Python](https://img.shields.io/badge/Python-3.12+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
  [![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Active-success.svg?logo=github-actions)](https://github.com/features/actions)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
  [![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)](#-contributing)
</div>

<hr/>

**Disney Comics Watcher** is an open-source, automated platform designed to monitor new releases and announcements of Disney magazines and comic books across **27 countries worldwide** (France, USA, Germany, Italy, Brazil, Mexico, Turkey, Greece, Spain, Netherlands, United Kingdom, Denmark, Norway, Sweden, Finland, Iceland, Egypt, Poland, Czech Republic, Bulgaria, Croatia, Estonia, Latvia, Lithuania, Serbia, Slovenia, and China).

It combines real-time notification dispatch (Telegram, Discord), automated Inducks `.dbi` skeleton generation, and an interactive **web agenda** application.

> ⭐️ **If you like this project, please consider giving it a star on GitHub! It helps a lot!** ⭐️

---

## 🎯 Features

- **Worldwide Coverage (27 Countries)** — Monitors publishers across Europe, North & South America, the Middle East, and Asia.
- **Interactive Web Agenda** — Clean, responsive web app with monthly calendar and chronological list views, instant search, country filtering, cover previews, and dark/light themes.
- **New Magazine Issues & Announcements** — Extracts cover art, issue numbers, retail prices, barcodes (EAN), and precise publication dates.
- **Multi-Platform Notifications** — Real-time alerts dispatched to Telegram channels/topics and Discord servers with country-role pings.
- **Inducks Pre-Indexing** — Automatically generates and maintains `.dbi` skeleton files for seamless integration into the [Inducks database](https://inducks.org/), with automatic cleanup when issues get indexed.
- **Gemini AI Integration** — Analyzes magazine covers to extract character appearances and featured story titles.
- **Local & Remote Cover Archive** — Automatically downloads and archives high-quality cover images.

---

## 📡 Monitored Countries & Publishers

| Country | Code | Publisher / Source | What it covers |
|---|:---:|---|---|
| 🇫🇷 France | `fr` | Direct Éditeurs, MLP, Glénat | Kiosk magazines (*Picsou*, *Mickey*, *Fantomiald*) and Glénat albums |
| 🇺🇸 United States | `us` | Marvel, Fantagraphics, Dynamite | US comic book series, collections, and omnibuses |
| 🇩🇪 Germany | `de` | Egmont Ehapa, Lustiges Taschenbuch | *Micky Maus*, *LTB*, and German albums |
| 🇮🇹 Italy | `it` | Panini Comics Italia | *Topolino*, *Paperinik*, and special Panini editions |
| 🇧🇷 Brazil | `br` | Panini Brasil | Brazilian editions (*Tio Patinhas*, *Pato Donald*, *Mickey*) |
| 🇲🇽 Mexico | `mx` | Panini Comics México | Mexican releases (*Pato Donald*, *Mickey*, *Colección Clásicos*) |
| 🇹🇷 Turkey | `tr` | Beta Kids (D&R) | Turkish graphic novels (*Disney En Güzel Maceralar*) |
| 🇬🇷 Greece | `gr` | Kathimerini | Greek weekly & monthly Disney magazines (*Komix*, *Miky Maous*) |
| 🇪🇸 Spain | `es` | Panini España | Spanish Disney publications and albums |
| 🇳🇱 Netherlands | `nl` | DPG Media (Donald Duck Shop) | *Donald Duck Weekblad*, pocket books, and specials |
| 🇬🇧 United Kingdom | `uk` | Panini / Titan / Hachette UK | UK Disney magazines and graphic novel collections |
| 🇩🇰 Denmark | `dk` | Egmont Publishing / Andeby | Danish Disney releases (*Anders And & Co.*) |
| 🇳🇴 Norway | `no` | Egmont Kids Media / Donald | Norwegian releases (*Donald Duck & Co*) |
| 🇸🇪 Sweden | `se` | Story House Egmont / Kalle Anka | Swedish releases (*Kalle Anka & C:o*) |
| 🇫🇮 Finland | `fi` | Sanoma (Aku Ankka API) | Finnish issues (*Aku Ankka*, taskukirjat) |
| 🇮🇸 Iceland | `is` | Edda Útgáfa | Icelandic pocket books (*Andrés Önd Syrpa*) |
| 🇪🇬 Egypt | `eg` | Nahdet Misr | Egyptian Arabic magazines (*Miki*, *Super Miki*) |
| 🇵🇱 Poland | `pl` | Egmont Polska | Polish releases (*Kaczor Donald*, *Gigant Poleca*) |
| 🇨🇿 Czech Republic | `cz` | Egmont CZ | Czech pocket books and magazines (*Kačer Donald*) |
| 🇧🇬 Bulgaria | `bg` | Egmont Bulgaria | Bulgarian Disney issues (*Мики Маус*) |
| 🇭🇷 Croatia | `hr` | Egmont d.o.o. | Croatian Disney releases |
| 🇪🇪 Estonia | `ee` | Egmont Estonia | Estonian magazines (*Miki Hiir*) |
| 🇱🇻 Latvia | `lv` | Egmont Latvija | Latvian issues (*Miks Pele*) |
| 🇱🇹 Lithuania | `lt` | Egmont Lietuva | Lithuanian issues (*Antulis Donaldas*) |
| 🇷🇸 Serbia | `rs` | Egmont Serbia | Serbian Disney releases |
| 🇸🇮 Slovenia | `si` | Egmont Slovenia | Slovenian Disney releases |
| 🇨🇳 China | `cn` | DRP / Disney China | Chinese translations and local editions |

---

## 🌐 Web Agenda Application

The project features a lightweight, standalone responsive web app located in `web/`:

- **Monthly Calendar Grid** — Displays all issues day by day with real-time badges and day inspection.
- **Chronological List View** — Browse upcoming and recently released issues in order.
- **Dynamic Filters** — Filter by country (simple clean dropdown menu) and release status (*All*, *Upcoming*, *Released*).
- **Fast Search** — Real-time filter across titles, publishers, series names, and EAN numbers.
- **Light & Dark Themes** — Automatic system preference detection with manual toggle.
- **Mobile Responsive** — Optimized for both desktop displays and mobile touch devices.

### Launching the Web App locally:

```bash
# 1. Export fresh releases data (merges local DBI issues + live scraper catalogs)
python export_agenda.py web/data/releases.json

# 2. Start a local HTTP server
python -m http.server 8000 --directory web
```
Then navigate to `http://localhost:8000` in your browser.

---

## 🚀 Installation & Setup

Want to run your own instance of the Watcher? Follow these simple steps:

### 0. Choose your notification backend

The Watcher can post to **Discord**, **Telegram**, or both. Set `NOTIFY_BACKENDS`
to `telegram` (default), `discord`, or `discord,telegram`.

**Discord setup** (webhook-based, no bot to invite):
1. In your server, open **Channel settings → Integrations → Webhooks → New Webhook**
   on your announcements channel and copy the URL into `DISCORD_WEBHOOK_URL`.
2. Do the same on a private staff channel for the generated DBI skeletons →
   `DISCORD_ADMIN_WEBHOOK_URL`.
3. Every announcement pings the role of the country it belongs to. Enable
   **Developer Mode** (User Settings → Advanced), right-click each country role
   → **Copy Role ID**, and list them in `DISCORD_ROLE_IDS`:
   ```
   DISCORD_ROLE_IDS=fr:123456789012345678,us:234567890123456789,it:345678901234567890
   ```
   Countries with no role listed simply get no mention. A single
   `DISCORD_ROLE_ID_XX` variable (e.g. `DISCORD_ROLE_ID_FR`) overrides the list
   for that country.

Discord webhooks cannot send interactive buttons, so the source and Inducks
buttons are rendered as inline links at the bottom of each embed.

### 1. Create the Telegram Bot
1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the instructions to create your bot
3. Copy the **token** (e.g., `123456:ABC-DEF...`)

### 2. Create the Announcement Channel
1. Create a Telegram channel (public recommended)
2. Add your new bot as an **administrator** with "Post Messages" permission
3. Note the channel's username (e.g., `@MyDisneyComics`)

### 3. Deploy via GitHub Actions
1. Fork or clone this repository
2. Go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `TELEGRAM_BOT_TOKEN`: The token obtained via @BotFather
   - `TELEGRAM_CHAT_ID_FR`: The channel's username (e.g., `@MyDisneyComics`) for French releases
   - `TELEGRAM_CHAT_ID_US`: The channel's username (e.g., `@MyDisneyComicsUS`) for US releases
   - `TELEGRAM_THREAD_ID_DE`: The thread ID for German releases (if using topics)
   - `TELEGRAM_THREAD_ID_GR`: The thread ID for Greek releases (if using topics)
   - `TELEGRAM_THREAD_ID_IT`: The thread ID for Italian releases (if using topics)
   - `TELEGRAM_THREAD_ID_BR`: The thread ID for Brazilian releases (if using topics)
   - `TELEGRAM_THREAD_ID_EG`: The thread ID for Egyptian releases (if using topics)
   - `TELEGRAM_THREAD_ID_BG`, `_HR`, `_EE`, `_LV`, `_LT`, `_PL`, `_CZ`, `_RS`, `_SI`: Thread IDs for Eastern European releases

   For Discord, add instead: `DISCORD_WEBHOOK_URL`, `DISCORD_ADMIN_WEBHOOK_URL`
   and `DISCORD_ROLE_IDS` (see step 0), plus a `NOTIFY_BACKENDS` repository
   *variable* set to `discord` (or `discord,telegram` to run both during a transition).
3. Go to the **Actions** tab and enable workflows. The bot will now run hourly automatically!

---

## 💻 Local Development & Testing

You can easily run the monitoring script locally without configuring global system variables.

1. Clone the repository and install dependencies:
   ```bash
   pip install requests beautifulsoup4
   ```
2. Create a `.env` file at the root of the project:
   ```env
   TELEGRAM_BOT_TOKEN=your_test_token
   TELEGRAM_CHAT_ID_FR=your_test_chat_id_fr
   TELEGRAM_CHAT_ID_US=your_test_chat_id_us
   TELEGRAM_THREAD_ID_DE=your_test_thread_id_de
   TELEGRAM_THREAD_ID_GR=your_test_thread_id_gr
   TELEGRAM_THREAD_ID_IT=your_test_thread_id_it
   TELEGRAM_THREAD_ID_BR=your_test_thread_id_br
   TELEGRAM_THREAD_ID_EG=your_test_thread_id_eg
   TELEGRAM_THREAD_ID_MX=your_test_thread_id_mx
   TELEGRAM_THREAD_ID_TR=your_test_thread_id_tr
   TELEGRAM_THREAD_ID_BG=your_test_thread_id_bg
   TELEGRAM_THREAD_ID_HR=your_test_thread_id_hr
   TELEGRAM_THREAD_ID_EE=your_test_thread_id_ee
   TELEGRAM_THREAD_ID_LV=your_test_thread_id_lv
   TELEGRAM_THREAD_ID_LT=your_test_thread_id_lt
   TELEGRAM_THREAD_ID_PL=your_test_thread_id_pl
   TELEGRAM_THREAD_ID_CZ=your_test_thread_id_cz
   TELEGRAM_THREAD_ID_RS=your_test_thread_id_rs
   TELEGRAM_THREAD_ID_SI=your_test_thread_id_si
   TELEGRAM_THREAD_ID_DK=your_test_thread_id_dk
   TELEGRAM_THREAD_ID_NO=your_test_thread_id_no
   TELEGRAM_THREAD_ID_SE=your_test_thread_id_se
   TELEGRAM_THREAD_ID_FI=your_test_thread_id_fi
   TELEGRAM_THREAD_ID_IS=your_test_thread_id_is
   TELEGRAM_THREAD_ID_NL=your_test_thread_id_nl
   TELEGRAM_THREAD_ID_UK=your_test_thread_id_uk
   TELEGRAM_THREAD_ID_ES=your_test_thread_id_es
   # Optional: Add GEMINI_API_KEY for AI cover analysis
   ```
3. Run the regression tests:
   ```powershell
   python -m unittest discover -s tests/regression -v
   ```

---

## 🤝 Contributing

We would absolutely love your help to make **Disney Comics Watcher** even better! 

Whether you want to add support for a new country, improve the Gemini AI prompts, fix bugs, refine the Inducks `.dbi` generator, or enhance the web agenda, all contributions are highly appreciated!

### How to contribute:
1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open a Pull Request** 🚀

### Ideas for future contributions:
- Adding support for additional publishers and countries
- Enriching story metadata and variant cover detection
- Improving the web agenda UX and offline caching (PWA)

---

<div align="center">
  <i>Built with ❤️ for the Disney Comics community and Inducks contributors.</i>
</div>
