import aiohttp
from typing import Any
from contextlib import asynccontextmanager


class TelegramBot:

    def __init__(self, token: str):
        self.__token = token
        self.__url = f"https://api.telegram.org/bot{token}/"

    async def get_updates(self, clear: bool = False) -> (bool, list):
        ok, res = await self._call('getUpdates')
        if ok and clear:
            if len(res) > 0:
                max_update_id = 0
                for i in res:
                    max_update_id = max(i['update_id'], max_update_id)
                await self._call(
                    'getUpdates', params={'offset': max_update_id+1}
                )
        return ok, res

    async def send_message(self, text: str, chat_id: str, **kwargs) -> (bool, Any):  # noqa
        params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'MarkdownV2'
        }
        params |= kwargs
        ok, res = await self._call('sendMessage', params)
        return ok, res

    @classmethod
    def _allocate_session(cls) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(headers={"Accept": "application/json"})

    async def _call(self, method_name: str, params: dict = None) -> (bool, Any):  # noqa
        async with self._allocate_session() as session:
            url = self.__url + method_name
            response = await session.post(url, json=params)
            data = await response.json() or {}
            if response.status == 200 and data.get('ok') is True:
                return True, data.get('result')
            else:
                return False, data.get("description", "")
