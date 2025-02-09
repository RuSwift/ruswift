import asyncio
import logging
from random import shuffle

from django.conf import settings
from django.core.management.base import BaseCommand

from cache import Cache
from ratios import (
    BestChangeRatios, HTXEngine, ForexEngine, CoinMarketCapEngine,
    GarantexEngine, GarantexP2P, HTXP2P
)
from api.kyc import MTSKYCController
from context import Context, context
from reposiroty import ExchangeConfigRepository
from merchants import MerchantRatios, load_directions


class Command(BaseCommand):

    """Run foreground tasks"""

    DEF_TIMEOUT = 60
    COINMARKETCAP_TIMEOUT = 60*5

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            help="Repeat timeout is [secs]"
        )

    def handle(self, *args, **options):
        if options.get('timeout'):
            timeout = int(options['timeout'])
        else:
            timeout = self.DEF_TIMEOUT
        asyncio.run(
            self.run(
                timeout=timeout
            )
        )

    async def run(self, timeout: int):
        cache = Cache(
            pool=settings.REDIS_CONN_POOL, namespace='exchange:cron'
        )
        cache_key = 'repeats'
        while True:
            is_set = await cache.get(key=cache_key)
            if not is_set:
                logging.debug('****** CRON ******')
                kyc_tsk = asyncio.create_task(self._refresh_kyc_records_cyclic())
                try:
                    await self._refresh_ratios(cache)
                    await cache.set(
                        key=cache_key,
                        value={'flag': 'ok'},
                        ttl=timeout
                    )
                    logging.debug('******  ******')
                finally:
                    kyc_tsk.cancel()
            await asyncio.sleep(timeout)

    async def _refresh_ratios(self, cache: Cache):
        routines = [
            self._refresh_forex_ratios(),
            self._refresh_htx_ratios(),
            self._refresh_coinmarketcap_ratios(cache),
            self._refresh_garantex_ratios(),
            self._refresh_bestchange_ratios()
        ]
        shuffle(routines)
        cfg = await ExchangeConfigRepository.get()
        with Context.create_context(config=cfg):
            try:
                for coro in routines:
                    await coro
            except Exception as e:
                logging.exception('EXC')
            await self._refresh_merchant_ratios()

    @classmethod
    async def _refresh_forex_ratios(cls):
        logging.critical('Refresh Forex ratios')
        engine = ForexEngine(refresh_cache=True)
        await engine.market()
        logging.critical('Successfully forex ratios was refreshed')

    @classmethod
    async def _refresh_htx_ratios(cls):
        logging.critical('Refresh Htx ratios')
        engine = HTXEngine(refresh_cache=True)
        await engine.market()
        logging.critical('Successfully htx ratios was refreshed')
        p2p = HTXP2P(refresh_cache=True)
        await p2p.load_config()
        directions = load_directions(context.config)
        cached_paths = set()
        for direction in directions:
            if direction.src.cur.is_fiat != direction.dest.cur.is_fiat:
                if direction.src.cur.is_fiat:
                    fiat = direction.src.cur.symbol
                    token = direction.dest.cur.symbol
                else:
                    token = direction.src.cur.symbol
                    fiat = direction.dest.cur.symbol
                path = f'{fiat}:{token}'
                if path not in cached_paths:
                    cached_paths.add(path)
                    logging.critical(f'> P2P htx refresh token: {token} fiat: {fiat}')  # noqa
                    await p2p.load_orders(token, fiat)
                    logging.critical('> ok!')
        logging.critical('Successfully HTX ratios was refreshed')

    @classmethod
    async def _refresh_coinmarketcap_ratios(cls, cache: Cache):
        key = 'coinmarketcap'
        logging.critical('Refresh CoinMarketCap ratios')
        throttled = await cache.get(key=key)
        if throttled:
            logging.critical('CoinMarketCap wait for timeout: throttling')
            return
        else:
            engine = CoinMarketCapEngine(refresh_cache=True)
            await engine.market()
            await cache.set(
                key=key,
                value={'flag': 'on'},
                ttl=cls.COINMARKETCAP_TIMEOUT
            )
            logging.critical('Successfully CoinMarketCap ratios was refreshed')

    @classmethod
    async def _refresh_garantex_ratios(cls):
        logging.critical('Refresh Garantex CEX ratios')
        engine = GarantexEngine(refresh_cache=True)
        await engine.auth()
        await engine.market()
        logging.critical('Refresh Garantex P2P ratios')
        p2p = GarantexP2P(refresh_cache=True)
        await p2p.auth()
        await p2p.load_orders(token='RUB', fiat='RUB')
        logging.critical('Successfully Garantex ratios was refreshed')

    @classmethod
    async def _refresh_bestchange_ratios(cls):
        logging.critical('Refresh BestChange ratios')
        exchange_cfg = await ExchangeConfigRepository.get()

        engine = BestChangeRatios(refresh_cache=True)
        rates, currencies, exchangers, cities = await engine.load_from_server()
        await engine.save_to_cache(rates, currencies, exchangers, cities)

        directions = load_directions(context.config)
        cached_paths = set()
        for direction in directions:
            give = direction.src.cur.symbol
            get = direction.dest.cur.symbol
            path = f'{give}:{get}'
            if path not in cached_paths:
                cached_paths.add(path)
                logging.critical(f'> bestchange refresh give: {give} get: {get}')  # noqa
                await engine.load_orders(give=give, get=get)
                logging.critical('> ok!')

        logging.critical('Successfully BestChange ratios was refreshed')

    @classmethod
    async def _refresh_merchant_ratios(cls):
        logging.critical('Refresh Merchant ratios')
        directions = load_directions(context.config)
        engine = MerchantRatios()
        await engine.build_ratios(directions)
        logging.critical('Successfully Merchant ratios was refreshed')

    @classmethod
    async def _refresh_kyc_records(cls):
        logging.critical('Refresh KYC records')
        await MTSKYCController.update_final_tasks(delay=0.1)
        logging.critical('Successfully refresh KYC records')

    @classmethod
    async def _refresh_kyc_records_cyclic(cls):
        while True:
            await cls._refresh_kyc_records()
            await asyncio.sleep(5)
