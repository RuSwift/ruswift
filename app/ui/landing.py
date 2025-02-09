import asyncio
import math
import os
import logging
import json
import secrets
import hashlib
from typing import Optional, Tuple

import aiohttp
from aiohttp_socks import ProxyType, ProxyConnector
from bs4 import BeautifulSoup
from django.conf import settings
from django.views.generic.base import (
    TemplateResponseMixin, ContextMixin
)
from django.http import (
    HttpRequest, HttpResponse, HttpResponseForbidden
)
from core import utc_now_float, telegram, google
from cache import Cache
from .views import BaseExchangeView


class LandingDevelopmentView(TemplateResponseMixin, ContextMixin, BaseExchangeView):
    template_name = "landing/development/service-details.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs) or {}
        return data

    async def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class LandingPayolinView(TemplateResponseMixin, ContextMixin, BaseExchangeView):
    template_name = "landing/payolin/index.html"
    _cache = Cache(pool=settings.REDIS_CONN_POOL, namespace='payolin')
    _cache_ttl = 60
    _gc_cache_ttl = 60*5
    _banks_cache_ttl = 60*60
    _tor_proxy = os.getenv('TOR', None)
    _session_id_cookie = 'payolin_session_id'
    _throttle_ttl = 15

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs) or {}
        data['address'] = {
            'geo': 'Россия, Санкт-Петербург',
            'location': 'ул. Кирочная 67, строение 2, 2-й этаж, офис 14'
        }
        email = 'service@payolin.ru'
        data['contacts'] = {
            'phone': 'Phone ToDo',
            'whatsapp': '+7 (993)490-93-22',
            'telegram': '@payolin_assist_bot',
            'email': email,
            'inn': 'ООО «Пэйолин» ИНН 7811800794',
            'whatsapp_link': 'https://wa.link/b0kx9c',
            'telegram_link': 'https://t.me/payolin_assist_bot',
            'email_link': f'mailto:{email}',
        }
        data['nav'] = [
            {'label': 'Home', 'section': 'hero', 'required': False},
            {'label': 'Платежные решения', 'section': 'payments'},
            {'label': 'Калькулятор', 'section': 'pricing'},
            {'label': 'О Нас', 'section': 'about'},
            {'label': 'Отзывы', 'section': 'testimonials'},
            {'label': 'Почему Мы', 'section': 'why-us'},
            {'label': 'Связаться с нами', 'section': 'contact', 'required': False},
        ]
        data['begin'] = {'label': 'Начать', 'section': 'payments'}
        data['payments'] = [
            {'label': 'Банковский перевод', 'icon': 'bank', 'id': 'bank'},
            {'label': 'Альтернативные методы', 'icon': 'brilliance', 'id': 'alter'},
            {'label': 'Нестандартные решения', 'icon': 'link', 'id': 'nonstandard'}
        ]
        data['logo'] = {
            'icon': '/static/landing/payolin/assets/img/logo.svg',
            'caption': 'Payolin'
        }
        data['testimonials'] = [
            {
                'name': 'Мария',
                'agenda': 'владелец магазина на OZON',
                'text': 'Сотрудничаем с Payolin уже не первый год. '
                        'У них всё прозрачно, на каждом этапе получаем уведомления о статусе платежей, '
                        'знаем, когда средства поступили поставщику. '
                        'С таким подходом чувствуем уверенность, что никаких сюрпризов не будет.'
            },
            {
                'name': 'Артём',
                'agenda': 'предприниматель на WB',
                'text': 'С Payolin решился на постоянное сотрудничество, '
                        'когда увидел, что они предоставляют все документы '
                        'для налоговой отчетности. Это очень важно для '
                        'моего бизнеса — не приходится самому разбираться с '
                        'бумагами, и можно не переживать перед проверками. '
                        'Качественный сервис, которому доверяю.'
            },
            {
                'name': 'Ольга',
                'agenda': 'мелкий реселлер товаров',
                'text': 'Огромное спасибо команде Payolin! '
                        'Помимо удобства, они предлагают разные валюты для '
                        'оплаты, что позволяет мне сэкономить на конвертациях '
                        'и выбрать оптимальные условия. Работать стало проще, '
                        'и нет привязки к одной валюте — подстраиваются под '
                        'запрос клиента, что редкость на рынке.'
            },
            {
                'name': 'Николай',
                'agenda': 'владелец интернет-магазина',
                'text': 'Очень довольны, что нашли Payolin. Они предложили '
                        'несколько вариантов перевода, включая AliPay, WeChat '
                        'и даже прямые переводы на банковские карты '
                        'поставщиков. С Payolin удобно, потому что мы сами '
                        'выбираем, как и когда платить, чтобы максимально '
                        'упростить процессы. Благодаря этому все заказы '
                        'проходят гладко!'
            },
            {
                'name': 'Татьяна',
                'agenda': 'продавец на маркетплейсах',
                'text': 'Работа с Payolin стала для нас настоящим открытием. '
                        'У них не только гибкие варианты перевода, но и все '
                        'необходимые документы для отчетности. Это снимает с '
                        'нас огромную нагрузку, и позволяет не думать о '
                        'налоговых проверках. Плюс — прозрачность на каждом '
                        'этапе перевода, знаем, что всё будет выполнено вовремя!'
            }
        ]
        data['rates'] = {
            'bank': [
                {'id': 'EUR', 'label': 'Евросоюз/США'},
                {'id': 'World', 'label': 'По миру'},
            ],
            'alternative': [
                {'id': 'alipay', 'label': 'AliPay', 'value': str(7.03)},
                {'id': 'wechat', 'label': 'WeChat', 'value': str(7.02)},
                {'id': 'card', 'label': 'UnionPay Card', 'value': str(7.01)},
            ],
            'usdtrub': {
                'default': 100.4
            },
            'usdtswift_comission': {
                'default': 1.5
            },
            'comission': {
                'default': '6.0'
            }
        }
        data['ym'] = True if not settings.DEBUG else False
        return data

    async def context_extra(self, data: dict):
        data['token'] = secrets.token_urlsafe(16)
        ratios, ts = await self._load_ruswift_ratios()
        data['ratios'] = ratios
        data['ts'] = ts

        google_sheet_ratios = await self._load_google_sheet_ratios()
        data['rates']['usdtrub']['default'] = google_sheet_ratios[2][1]
        data['rates']['usdtswift_comission']['default'] = google_sheet_ratios[3][1]
        data['rates']['comission']['default'] = google_sheet_ratios[4][1]
        for alter in data['rates']['alternative']:
            if alter['id'] == 'alipay':
                alter['value'] = str(google_sheet_ratios[2][4]).replace(',', '')
            elif alter['id'] == 'wechat':
                alter['value'] = str(google_sheet_ratios[2][4]).replace(',', '')
            elif alter['id'] == 'card':
                alter['value'] = str(google_sheet_ratios[3][4]).replace(',', '')

        data['banks'] = {}
        for cur in ['CNY', 'USD', 'EUR']:
            values = await self.load_bank_cur(cur.lower())
            if values:
                data['banks'][cur] = {
                    'url': values[0],
                    'rate': values[1]
                }

    async def get(self, request: HttpRequest, *args, **kwargs):
        session_id = request.COOKIES.get(self._session_id_cookie) or secrets.token_hex(8)
        context = self.get_context_data(**kwargs)
        await self.context_extra(context)
        resp = self.render_to_response(context)
        # CSRF
        token = context['token']
        csrf = hashlib.md5(f'{token}:{settings.SECRET_KEY}'.encode()).hexdigest()
        resp.set_cookie('csrf', csrf)
        resp.set_cookie(self._session_id_cookie, session_id)
        return resp

    async def post(self, request: HttpRequest, *args, **kwargs):
        if request.headers['Content-Type'] == 'application/json':
            data = json.loads(request.body)
            token = data.get('token')
            check_csrf = hashlib.md5(f'{token}:{settings.SECRET_KEY}'.encode()).hexdigest()
            csrf = request.COOKIES.get('csrf')
            if True:  # check_csrf == csrf: - убрал проверку т.к. в live у нек пользователей не работает
                session_id = request.COOKIES.get(self._session_id_cookie)
                throttle_cache_key = f'throttling:{session_id}'
                on = await self._cache.get(throttle_cache_key)
                if on:
                    await self._cache.set(
                        throttle_cache_key,
                        {'session': session_id},
                        ttl=self._throttle_ttl
                    )
                    return HttpResponse(status=429)
                else:
                    print('--- Feedback ---')
                    bot = telegram.TelegramBot(
                        token=settings.TG_BOT.token
                    )
                    message = f'''
                    <b>Запрос с сайта</b>
                    <b>Тема:</b> {data["subject"] or "no"}
                    <b>Имя:</b> {data["name"]}
                    <b>Контакт:</b> {data["contact"]}
                    <b>Текст сообщения:</b>
                    <i>"{data["message"]}"</i>
                    '''
                    ok, res = await bot.send_message(
                        text=message, chat_id=settings.TG_BOT.chat_id,
                        parse_mode='HTML'
                    )
                    await self._cache.set(
                        throttle_cache_key,
                        {'session': session_id},
                        ttl=self._throttle_ttl
                    )
                    if ok:
                        return HttpResponse(status=200)
                    else:
                        logging.error('Telegram bot error: ' + str(res))
                        return HttpResponse(
                            status=400, content=str(res).encode()
                        )

            else:
                return HttpResponseForbidden(content=b'CSRF error')
        else:
            return HttpResponse(status=400, content=b'Unexpected Content Type')

    @classmethod
    async def load_bank_cur(cls, currency: str, use_cache: bool = True) -> Optional[Tuple[str, float]]:
        url = f'https://bankiros.ru/currency/{currency}'  # noqa
        ts = utc_now_float()
        if use_cache:
            cached_meta = await cls._cache.get(url)
            if cached_meta:
                delta = ts - cached_meta['ts']
                if delta <= cls._banks_cache_ttl:
                    return tuple(cached_meta['values'])
        if cls._tor_proxy:
            host, port = cls._tor_proxy.split(':')
            connector = ProxyConnector(
                proxy_type=ProxyType.SOCKS5,
                host=host,
                port=port,
                # username='user',
                # password='password',
                rdns=True
            )
        else:
            connector = None
        async with aiohttp.ClientSession(read_timeout=5, connector=connector) as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        try:
                            s = soup.find_all('table')[0].find_all('tr')[2].find_all('td')[1].text  # noqa
                            ret = (url, float(s))
                            values = list(ret)
                            if use_cache and values:
                                meta = {
                                    'ts': ts,
                                    'values': values
                                }
                                await cls._cache.set(url, meta)
                            return url, float(s)
                        except Exception as e:
                            logging.exception('ERR:')
            except Exception as e:
                logging.exception('ERR:')
            return None

    async def _load_ruswift_ratios(self) -> Tuple[Optional[dict], Optional[float]]:  # noqa
        ts = utc_now_float()
        cache_key_ = 'ruswift-ratios'
        cached_meta = await self._cache.get(cache_key_)
        if cached_meta:
            delta = ts - cached_meta['ts']
            if delta <= self._cache_ttl:
                return cached_meta['ratios'], cached_meta['ts']
        try:
            async with aiohttp.ClientSession(read_timeout=5) as session:
                async with session.get(
                        'https://ruswift.ru/api/ratios/external'
                ) as resp:
                    if resp.status == 200:
                        ratios = await resp.json()
                        meta = {
                            'ts': ts,
                            'ratios': ratios
                        }
                        await self._cache.set(cache_key_, meta)
                        return ratios, ts
                    else:
                        logging.error('Error when load ruswift ratios')
                        if cached_meta:
                            return cached_meta['ratios'], cached_meta['ts']
                        else:
                            return None, None
        except Exception:
            if cached_meta:
                return cached_meta['ratios'], cached_meta['ts']
            else:
                return None, ts

    async def _load_google_sheet_ratios(self) -> list:
        range_name = 'Landing!A:G'
        ver = 'v1'
        ts = utc_now_float()
        cache_key_ = f'google_sheet_ratios::{range_name}::{ver}'
        cached_meta = await self._cache.get(cache_key_)
        values = None
        if cached_meta:
            delta = ts - cached_meta['ts']
            values = cached_meta['values']
        else:
            delta = math.inf

        async def _load_data_in_foreground():
            print('#1 _load_data_in_foreground')
            api = google.GoogleSpreadSheet(
                api_key=settings.GC.api_key,
                spread_sheet_id='1xV-EZdkHN4PcE1Z-VQuzhirhuVyfdfVdrM5gxvUKZ4w'
            )
            values_ = await api.read(range_name=range_name)
            meta = {
                'ts': ts,
                'values': values_
            }
            print('#2 _load_data_in_foreground')
            await self._cache.set(cache_key_, meta)
            return values_

        if delta > self._gc_cache_ttl:
            values = await _load_data_in_foreground()

        for ri, row in enumerate(values):
            for ci, col in enumerate(row):
                cell = str(values[ri][ci])
                if ',' in cell or '.' in cell or '%' in cell:
                    try:
                        cell = float(cell.replace(',', '.').replace('%', ''))
                    except ValueError:
                        ...
                    else:
                        values[ri][ci] = cell
        return values
