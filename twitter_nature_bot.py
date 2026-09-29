[30.09.2026 00:38] Şevket: /paylas
[30.09.2026 00:38] Doğa Paylaşım Botu: ⏳ Komut alındı: /paylas
Çalıştırılıyor: twitter_nature_bot.py
[30.09.2026 00:38] Doğa Paylaşım Botu: ❌ **Hata oluştu (/paylas):**

📄 **Loglar:**
```
🔑 X oturumu kontrol ediliyor...
✅ Environment 'X_COOKIES_JSON' üzerinden oturum yüklendi.
⚠️️ Gemini tweet üretimi başarısız, Groq deneniyor: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model models/gemini-2.0-flash is no longer available. Please update your code to use models/gemini-3.8-flash for the latest features and improvements. We recommend you to use the Interactions API (https://ai.google.dev/gemini-api/docs/get-started).', 'status': 'NOT_FOUND'}}
⚠️ Groq tweet üretimi başarısız: Error code: 404 - {'error': {'message': 'The model `llama-3.3-70b-versatile` does not exist or you do not have access to it.', 'type': 'invalid_request_error', 'code': 'model_not_found'}}

⚠️ Hata/Uyarı Logları:
Direct use of automatic function calling (AFC) in Models.generate_content is not recommended. Instead, we recommend to use AFC in Chat.send_message. Similarly, direct use of AFC in Models.generate_content_stream is not recommended. Instead, we recommend to use AFC in Chat.send_message_stream.
Traceback (most recent call last):
  File "/opt/render/project/src/twitter_nature_bot.py", line 162, in <module>
    asyncio.run(post_daily_tweet())
    ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.14.3/lib/python3.14/asyncio/runners.py", line 204, in run
    return runner.run(main)
           ~~~~~~~~~~^^^^^^
  File "/opt/render/project/python/Python-3.14.3/lib/python3.14/asyncio/runners.py", line 127, in run
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/python/Python-3.14.3/lib/python3.14/asyncio/base_events.py", line 719, in run_until_complete
    return future.result()
           ~~~~~~~~~~~~~^^
  File "/opt/render/project/src/twitter_nature_bot.py", line 146, in post_daily_tweet
    tweet_text, ai_model = generate_ai_tweet()
                           ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/twitter_nature_bot.py", line 140, in generate_ai_tweet
    raise Exception("❌ Hiçbir Yapay Zeka servisi içerik üretemedi!")
Exception: ❌ Hiçbir Yapay Zeka servisi içerik üretemedi!
```
