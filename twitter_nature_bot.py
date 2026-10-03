import asyncio
import json
import os
import random
import re
import sys
import time
import requests

# --- TWIKIT KEY_BYTE DÜZELTME YAMASI v2 ---
try:
    import base64
    import twikit.x_client_transaction.transaction as tx

    _INDICES_RE = re.compile(r'\(\w\[(\d{1,2})\],\s*16\)')
    _ONDEMAND_URL_RE = re.compile(
        r'https://abs\.twimg\.com/responsive-web/client-web/ondemand\.s\.[a-zA-Z0-9]+\.js'
    )
    _ONDEMAND_HASH_RE = re.compile(r'''['"]ondemand\.s['"]\s*:\s*['"](\w+)['"]''')

    async def _patched_get_indices(self, home_page_response, session, headers):
        page = str(home_page_response)
        if len(page) < 1000 and getattr(self, "home_page_response", None) is not None:
            page = str(self.home_page_response)

        m = _ONDEMAND_URL_RE.search(page)
        if m:
            js_url = m.group(0)
        else:
            h = _ONDEMAND_HASH_RE.search(page)
            if not h:
                raise Exception("ondemand.s dosyası sayfada bulunamadı")
            js_url = f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{h.group(1)}a.js"

        resp = await session.request(method="GET", url=js_url, headers=headers)
        nums = [int(x) for x in _INDICES_RE.findall(str(resp.text))]
        if len(nums) < 2:
            raise Exception("KEY_BYTE indeksleri ondemand dosyasında bulunamadı")
        return nums[0], nums[1:]

    tx.ClientTransaction.get_indices = _patched_get_indices
    
