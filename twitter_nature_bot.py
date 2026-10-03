import asyncio
import json
import os
import random
import re
import sys
import time
import requests

# --- TWIKIT KEY_BYTE DÜZELTME YAMASI (MONKEY PATCH) ---
try:
    import twikit.x_client_transaction.transaction as tx

    _orig_get_indices = tx.ClientTransaction.get_indices

    async def _patched_get_indices(self, response_text, *args, **kwargs):
        try:
            return await _orig_get_indices(self, response_text, *args, **kwargs)
        except Exception:
            text_str = str(response_text)  # BeautifulSoup -> str
            row_index_match = re.search(r'\((\d+)\)', text_str)
            key_bytes_match = re.search(r'\[([\d,\s]+)\]', text_str)
            if row_index_match and key_bytes_match:
                row_index = int(row_index_match.group(1))
                key_bytes = [int(x.strip()) for x in key_bytes_match.group(1).split(',') if x.strip()]
                return row_index, key_bytes
            raise

    tx.ClientTransaction.get_indices = _patched_get_indices

    tx.ON_DEMAND_FILE_REGEX = re.compile(
        r'https://abs\.twimg\.com/responsive-web/client-web/ondemand\.s\.[a-z0-9]+a\.js'
    )
except Exception as e:
    print(f"⚠️ Twikit patch uygulanamadı: {e}")
# ------------------------------------------------------

from twikit import Client
from google import genai
from google.genai import types
from groq import Groq
