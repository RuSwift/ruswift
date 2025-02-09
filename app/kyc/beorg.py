import json
from typing import List, Any, Dict, Literal
from urllib.parse import urljoin

from aiohttp import ClientSession

from entities import KYCPhoto, VerifiedDocument
from .base import BaseKYCProvider


class BeOrgKYCProvider(BaseKYCProvider):

    provider_id = 'beorg.ru'

    class KYCSettings(BaseKYCProvider.KYCSettings):
        project_id: str
        machine_uid: str
        token: str
        base_url: str = 'https://api.beorg.ru'

    async def verify(self, photos: List[KYCPhoto]) -> VerifiedDocument:
        if len(photos) != 2:
            raise ValueError('Expected document and selfie photos both')
        resp1 = await self._make_request(
            path='api/bescan/add_document',
            data={
                "project_id": self.settings.project_id,
                "images": [photo.image.decode() for photo in photos],
                "token": self.settings.token,
                "machine_uid": self.settings.machine_uid

            }
        )
        document_id = resp1['document_id']
        resp2 = await self._make_request(
            path=f'api/document/result/{document_id}',
            data={
                "token": self.settings.token
            },
            method='GET'
        )
        return resp2

    async def _make_request(
        self, path: str, data: Dict, method: Literal['GET', 'POST'] = 'POST'
    ) -> Any:
        url = urljoin(self.settings.base_url, path)
        async with ClientSession() as cli:
            if method == 'POST':
                coro = cli.post
                kwargs = {'json': data}
            else:
                coro = cli.get
                kwargs = {'params': data}
            resp = await coro(
                url,
                allow_redirects=True,
                **kwargs
            )
            if resp.ok:
                raw = await resp.text()
                return json.loads(raw)
            else:
                err_msg = await resp.text()
                raise RuntimeError(err_msg)
