name: X Advanced Bot Run

on:
  schedule:
    - cron: "0 9,15,21 * * *" # Günde 3 kez uygun saatlerde
  workflow_dispatch:

jobs:
  run-follow-bot:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests selenium webdriver-manager

      - name: Run X Advanced Bot
        run: python x_advanced_bot.py
        env:
          X_AUTH_TOKEN: ${{ secrets.X_AUTH_TOKEN }}
          X_CT0: ${{ secrets.X_CT0 }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}