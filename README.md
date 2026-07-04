<div align="center">
  <h1>Disney Comics Watcher</h1>
  <p><strong>The Ultimate Automated Tracker for Disney Magazines & Comic Books in France & the US</strong></p>

  [![Python](https://img.shields.io/badge/Python-3.12+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
  [![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Active-success.svg?logo=github-actions)](https://github.com/features/actions)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
  [![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)](#-contributing)
</div>

<hr/>

**Disney Comics Watcher** is an open-source, automated bot designed to monitor new releases of Disney magazines (Picsou Magazine, Le Journal de Mickey, Super Picsou Géant, Fantomiald) and comic books (Glénat albums, Don Rosa, Carl Barks) in France and the US.

It seamlessly tracks publication dates and automatically sends real-time notifications to a dedicated Telegram channel for every new issue or announcement. Perfect for collectors, Inducks contributors, and Disney comics fans!

### 📱 Join our Telegram Channel

Stay updated with all the latest Disney comics releases directly on your phone!
👉 **[Join the Disney Comics Watcher Telegram Channel here](https://t.me/infobddisney)**

---

## 🎯 Features & Notifications

- **New kiosk magazine issues** — Complete with cover image, issue number, retail price, and publication dates.
- **Glénat album announcements** — Notifies you when an upcoming comic book appears as "to be published" in the official catalog.
- **Glénat album releases** — Alerts you on the exact day the publication date is reached in bookstores.
- **Gemini AI integration** — Automatically analyzes magazine covers to detect featured characters and extract the main story titles!
- **Inducks pre-indexing** — Automatically generates `.dbi` skeleton files (`fr.dbi` and `us.dbi`) for seamless contributions to the [Inducks database](https://inducks.org/). It also automatically cleans up these files by removing issues once they are indexed and available in the Inducks database.
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
- Adding support for other countries (Germany, Italy, Brazil...)
- Improving the Telegram message formatting
- Enhancing the Gemini AI character detection
- Adding new comic book publishers

---

<div align="center">
  <i>Built with ❤️ for the Disney Comics community and Inducks contributors.</i>
</div>
