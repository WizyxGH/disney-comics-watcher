<div align="center">
  <h1>Disney Comics Watcher</h1>
  <p><strong>The ultimate automated tracker for Disney comic books around the world</strong></p>

  [![Python](https://img.shields.io/badge/Python-3.12+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
  [![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Active-success.svg?logo=github-actions)](https://github.com/features/actions)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
  [![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)](#-contributing)
</div>

<hr/>

**Disney Comics Watcher** is an open-source, automated bot designed to monitor new releases of Disney magazines and comic books in France, the US, Germany, Greece, Italy, Brazil, Egypt, and 9 Eastern European countries (Bulgaria, Croatia, Estonia, Latvia, Lithuania, Poland, Czech Republic, Serbia, Slovenia).

> ⭐️ **If you like this project, please consider giving it a star on GitHub! It helps a lot!** ⭐️


It seamlessly tracks publication dates and automatically sends real-time notifications to a dedicated Telegram channel for every new issue or announcement. Perfect for collectors, Inducks contributors, and Disney comics fans!

### 📱 Join our Telegram Channel

Stay updated with all the latest Disney comics releases directly on your phone!
👉 **[Join the Disney Comics Watcher Telegram Channel here](https://t.me/infobddisney)**

---

## 🎯 Features & Notifications

- **Global Coverage** — Tracks releases from publishers in France, USA, Germany, Greece, Italy, Brazil, Egypt, and Croatia!
- **New magazine issues** — Complete with cover image, issue number, retail price, and publication dates.
- **Comic book announcements** — Notifies you when an upcoming comic book appears as "to be published" in official catalogs.
- **Release day alerts** — Alerts you on the exact day the publication date is reached in bookstores.
- **Gemini AI integration** — Automatically analyzes magazine covers to detect featured characters and extract the main story titles!
- **Inducks pre-indexing** — Automatically generates `.dbi` skeleton files for all monitored countries for seamless contributions to the [Inducks database](https://inducks.org/). It also automatically cleans up these files by removing issues once they are indexed.
- **Local cover archive** — Automatically downloads and saves high-quality cover images to a local `covers/` folder.

---

## 📡 Monitored Sources & Publishers

| Source | What it covers |
|---|---|
| [direct-editeurs.fr](https://direct-editeurs.fr) | Active kiosk magazines (Picsou, Mickey, Fantomiald, Donald…) |
| [catalogueproduits.mlp.fr](https://catalogueproduits.mlp.fr) | Complementary kiosk issues missing from Direct Éditeurs (Picsou Soir, Destin de Picsou…) |
| [glenat.com](https://www.glenat.com/livres-glenat-disney/) | Disney comic books and graphic novels by Glénat (Picsou, Mickey, Don Rosa, Romano Scarpa…) |
| [marvel.com](https://www.marvel.com/) | US Disney comic books published by Marvel (Uncle Scrooge...) |
| [fantagraphics.com](https://www.fantagraphics.com/) | US Disney comic books published by Fantagraphics |
| [egmont-shop.de](https://www.egmont-shop.de/) | German Disney comic books and magazines published by Egmont Ehapa |
| [lustiges-taschenbuch.de](https://www.lustiges-taschenbuch.de/) | Story data enricher for German LTB series |
| [kathimerini.gr](https://www.kathimerini.gr/k/disney/) | Greek Disney comic books and magazines published by Kathimerini |
| [panini.it](https://www.panini.it/) | Italian Disney comic books and magazines published by Panini Comics (Topolino, Paperinik...) |
| [panini.com.br](https://panini.com.br/) | Brazilian Disney comic books and magazines published by Panini Brasil (Mickey, Tio Patinhas...) |
| [nahdetmisrbookstore.com](https://nahdetmisrbookstore.com/) | Egyptian Disney comic books and magazines published by Nahdet Misr (Miki, Super Miki...) |
| Eastern European publishers | Prepared architecture for Bulgaria (bg), Croatia (hr), Estonia (ee), Latvia (lv), Lithuania (lt), Poland (pl), Czech Republic (cz), Serbia (rs), Slovenia (si) |

---

## 🚀 Installation & Setup

Want to run your own instance of the Watcher? Follow these simple steps:

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
   TELEGRAM_THREAD_ID_BG=your_test_thread_id_bg
   TELEGRAM_THREAD_ID_HR=your_test_thread_id_hr
   TELEGRAM_THREAD_ID_EE=your_test_thread_id_ee
   TELEGRAM_THREAD_ID_LV=your_test_thread_id_lv
   TELEGRAM_THREAD_ID_LT=your_test_thread_id_lt
   TELEGRAM_THREAD_ID_PL=your_test_thread_id_pl
   TELEGRAM_THREAD_ID_CZ=your_test_thread_id_cz
   TELEGRAM_THREAD_ID_RS=your_test_thread_id_rs
   TELEGRAM_THREAD_ID_SI=your_test_thread_id_si
   # Optional: Add GEMINI_API_KEY for AI cover analysis
   ```
3. Run the test suite:
   ```powershell
   python tests/test_telegram_notif.py
   ```

---

## 🤝 Contributing

We would absolutely love your help to make **Disney Comics Watcher** even better! 

Whether you want to add support for a new country, improve the Gemini AI prompts, fix bugs, or refine the Inducks `.dbi` generator, all contributions are highly appreciated!

### How to contribute:
1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open a Pull Request** 🚀

### Ideas for future contributions:
- Adding support for other countries (Netherlands, Spain, Scandinavia...)
- Improving the Telegram message formatting
- Enhancing the Gemini AI character detection
- Adding new comic book publishers

---

<div align="center">
  <i>Built with ❤️ for the Disney Comics community and Inducks contributors.</i>
</div>
