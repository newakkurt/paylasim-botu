"""Telegram komutları: /yardim, /etkilesim, /paylas  (pyTelegramBotAPI / telebot için)

Bu modül SÜREKLİ ÇALIŞAN bota (Render) eklenir. GitHub Actions komut dinleyemez,
çünkü iş bitince kapanır; komutlara ancak 7/24 açık bir süreç cevap verebilir.

Kullanım, mevcut bot dosyanda `bot = telebot.TeleBot(...)` satırından sonra:

    from bot_commands import register_handlers
    register_handlers(bot)

Notlar:
- Komutlar sadece TELEGRAM_CHAT_ID'deki sohbetten kabul edilir (başkası /paylas ile hesabına tweet attıramaz).
- Botunda "her mesajı yakalayan" genel bir handler varsa, register_handlers(bot) çağrısını ONDAN ÖNCE yap.
- Botunda zaten /paylas varsa ve onu korumak istersen: register_handlers(bot, include_paylas=False)
- Render'da bu dosya ile twitter_nature_bot.py aynı klasörde olmalı.
"""
import os
import threading

import twitter_nature_bot as nb


def _command_of(message) -> str:
    """'/Etkileşim@botadi arg' -> 'etkileşim'. Komut değilse boş döner."""
    text = (getattr(message, "text", None) or "").strip()
    if not text.startswith("/"):
        return ""
    return text.split()[0].split("@")[0][1:].lower()


def register_handlers(bot, include_paylas: bool = True):
    allowed_chat = str(os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    def is_allowed(message) -> bool:
        return bool(allowed_chat) and str(message.chat.id) == allowed_chat

    @bot.message_handler(func=lambda m: _command_of(m) in ("yardim", "yardım"))
    def _help(message):
        if not is_allowed(message):
            return
        nb.send_telegram_help()

    @bot.message_handler(func=lambda m: _command_of(m) in ("etkilesim", "etkileşim"))
    def _engage(message):
        if not is_allowed(message):
            return
        threading.Thread(target=nb.send_interaction_reminder, daemon=True).start()

    if include_paylas:

        @bot.message_handler(func=lambda m: _command_of(m) in ("paylas", "paylaş"))
        def _paylas(message):
            if not is_allowed(message):
                return
            bot.reply_to(message, "⏳ Tweet hazırlanıyor, Buffer'a ekleniyor...")

            def work():
                try:
                    # Başarı/hata bildirimini run_job kendisi Telegram'a yollar.
                    # Etkileşim hatırlatması arka planda 16 dk sonra gider (uyutmaz).
                    nb.run_job(wait=False, background_reminder=True)
                except Exception as e:
                    bot.send_message(message.chat.id, f"❌ Beklenmeyen hata: {type(e).__name__}: {str(e)[:200]}")

            threading.Thread(target=work, daemon=True).start()
