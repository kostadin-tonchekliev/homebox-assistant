# HomeBox Telegram Helper

A Telegram bot that checks your [HomeBox](https://homebox.software/en/) inventory.

## Requirements

- Python 3.11+
- A running HomeBox instance
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

1. Clone or copy this project and create a virtual environment:
  ```bash
   python3.11 -m venv venv
   source venv/bin/activate   # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
  ```
2. Copy the example env file and fill in your values:
  ```bash
   cp .env.example .env
   # Edit .env with HOMEBOX_BASE_URL, HOMEBOX_USERNAME, HOMEBOX_PASSWORD, and TELEGRAM_BOT_TOKEN
  ```
3. Run the bot:
  ```bash
   python3 main.py
  ```
   The bot will start polling; send it a message in Telegram to test.

## Commands

| Command      | Description                          |
| ----------- | ------------------------------------ |
| `/help`     | Show usage and supported features.   |
| `/locations`| List all locations from HomeBox (with item counts). |

## Usage

### Check if you have specific items

Ask whether you have a list of items. The bot replies with what’s available (name, location, quantity) and what’s not.

- **With a list:**
  ```
  Do I have the following:
  - M3x10 screws
  - M3x15 screws
  - ESP32C3
  ```
- **Comma-separated:**
  ```
  Do I have: M3x10, M3x15, ESP32C3
  ```

### List items in a location

Ask what you have in a given location (e.g. Hardware, Microcontrollers). The bot checks that the location exists and replies with in-stock items and quantities.

Examples:
- `What do I have under Hardware`
- `What do I have in Microcontrollers`
- `List items in Hardware`
- `Items under Sensors`

If the location name doesn’t match any of your HomeBox locations, the bot will say so and suggest using `/locations` to see available names.

### Other

- Messages that don’t match a supported intent (e.g. “Hello”) get a short “Command not supported” reply with a list of what is supported.
- Availability is based on HomeBox search: an item is “available” if there is at least one matching, non-archived item with quantity > 0.

## Project structure

```
homebox-helper/
├── main.py                 # Entry point: python3 main.py
├── src/
│   ├── core/               # Helpers
│   │   ├── config.py       # Env: HOMEBOX_*, TELEGRAM_BOT_TOKEN
│   │   └── parser.py       # Message parsing (intents, item list, location)
│   ├── homebox/            # HomeBox API
│   │   └── client.py       # API client (items, locations, auth)
│   └── bot/                # Telegram bot
│       ├── handlers.py     # /help, /locations, inventory & location queries
│       └── run.py          # Bot setup and run_polling
├── requirements.txt
└── .env
```

## License

Use and modify as you like for your workshop.