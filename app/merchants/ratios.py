import logging
from typing import Optional, List, Union, Tuple

from django.conf import settings as _settings
from pydantic import BaseModel, Field, computed_field

from cache import Cache
from ratios import (
    ForexEngine, BestChangeRatios, CoinMarketCapEngine
)
from context import context
from core import load_class, float_to_datetime
from .entities import Direction


class RatioEngineSettings(BaseModel):
    scope: str
    engines: List[str]
    enabled: Optional[bool] = True


class Amount(BaseModel):
    value: Optional[float] = 1000.0  # размер ордера
    base_cur: Optional[str] = 'USD'  # валюта, в которой производится расчет
    num: int = 5


class ForexSettings(RatioEngineSettings):
    scope: str = 'forex'
    engines: List[str] = ['ratios.ForexEngine']


class CEXSettings(RatioEngineSettings):
    scope: str = 'cex'
    engines: List[str] = [
        'ratios.HTXEngine', 
        #'ratios.GarantexEngine'
    ] 


class P2PRatioSettings(RatioEngineSettings):
    scope: str = 'p2p'
    amount: Optional[Amount] = Field(default_factory=Amount)
    # игнорировать записи с соотношением min,max amount val меньше значения
    ignore_ratio_minmax: Optional[float] = 0.9
    engines: List[str] = [
        'ratios.HTXP2P', 
        # 'ratios.GarantexP2P'
    ]
    pay_methods: Optional[List[str]] = ['CASHRUB', 'SBPRUB', 'SBERRUB']


class BestChangeSettings(RatioEngineSettings):
    scope: str = 'bestchange'
    low_pos: Optional[int] = 3
    high_pos: Optional[int] = 8
    engines: List[str] = ['ratios.BestChangeRatios']
    # является ли BC макс. возможным значением
    is_cutoff: Optional[bool] = False


class EngineVariable(BaseModel):
    id: str
    rate: float
    scope: str
    engine: str
    src: str
    dest: str
    src_method: str
    dest_method: str
    direction: Direction
    utc: Optional[float] = None

    @computed_field
    @property
    def give(self) -> float:
        return 1 if self.rate < 1 else self.rate

    @computed_field
    @property
    def get(self) -> float:
        return 1/self.rate if self.rate < 1 else 1


class FormattedUTC(BaseModel):
    ts: float
    s: Optional[str] = None


class P2PEngineVariable(EngineVariable):
    method: str = 'all'


class MerchantRatios:

    CACHE_KEY_RATIOS = 'ratios'
    METH_MARKET_CODE = 'market'

    class Settings(BaseModel):
        premium_percent: float = 1.0
        forex: ForexSettings = Field(default_factory=ForexSettings)
        cex: CEXSettings = Field(default_factory=CEXSettings)
        p2p: P2PRatioSettings = Field(default_factory=P2PRatioSettings)
        best_change: BestChangeSettings = Field(default_factory=BestChangeSettings)  # noqa

    class Ratio(BaseModel):
        rate: float
        min_amount: Optional[float] = None
        max_amount: Optional[float] = None
        src: Optional[str] = None
        dest: Optional[str] = None
        city: Optional[str] = None
        utc: Optional[FormattedUTC] = None

        @computed_field
        @property
        def give(self) -> float:
            return 1 if self.rate < 1 else self.rate

        @computed_field
        @property
        def get(self) -> float:
            return 1 / self.rate if self.rate < 1 else 1

    def __init__(self, uid: str = 'global', settings: Settings = None):
        self.uid = uid
        if settings is None:
            default_settings = (context.config.merchants or {}).get('default') or {}  # noqa
            self.settings = self.Settings.model_validate(default_settings)
        else:
            self.settings = settings
        self._cached_engines = {}
        self._cache = Cache(
            pool=_settings.REDIS_CONN_POOL, namespace=f'merchants::{uid}'
        )

    async def invalidate_cache(self):
        ks = await self._cache.keys()
        await self._cache.delete(ks)

    async def build_ratios(self, dirs: List[Direction], save_to_cache: bool = True) -> List[Union[EngineVariable, P2PEngineVariable]]:  # noqa
        result = []
        ratios_ids = set()

        def _extend_by_values(items: List[EngineVariable]):
            for item in items:
                if item.id in ratios_ids:
                    continue
                elif item is not None:
                    result.append(item)
                    ratios_ids.add(item.id)

        for direction in dirs:
            # BC
            bc_rates = await self._bestchange_rates(direction)
            _extend_by_values(bc_rates)
            # CEX
            cex_rates = await self._cex_rates(direction)
            _extend_by_values(cex_rates)
            # Forex
            forex_rates = await self._forex_rates(direction)
            _extend_by_values(forex_rates)
            # P2P
            p2p_rates = await self._p2p_rates(direction)
            _extend_by_values(p2p_rates)

        if save_to_cache:
            await self._cache.set(
                key=self.CACHE_KEY_RATIOS,
                value=[r.model_dump(mode='json') for r in result],
                ttl=context.config.cache_timeout_sec
            )
        return result

    async def engine_ratios(
        self,
        dirs: List[Direction] = None,
        cache_only: bool = False
    ) -> Optional[List[Union[EngineVariable, P2PEngineVariable]]]:  # noqa
        cached = await self._cache.get(key=self.CACHE_KEY_RATIOS)
        if cached:
            result = []
            for o in cached:
                if 'method' in o:
                    m = P2PEngineVariable.model_validate(o)
                else:
                    m = EngineVariable.model_validate(o)
                result.append(m)
            return result
        else:
            if cache_only:
                return None
            if dirs is None:
                raise RuntimeError('Dirs is empty')
            return await self.build_ratios(dirs)

    async def ratio(self, direction: Direction) -> Optional[Ratio]:
        if not direction.is_enabled:
            return None
        ratios = await self.engine_ratios()
        actual_ratios = self._filter_ratios(ratios, direction)
        if not actual_ratios:
            actual_ratios = await self.build_ratios(
                [direction], save_to_cache=False
            )
        if all(p.method.category == 'blockchain' for p in [direction.src, direction.dest]):  # noqa
            _, avg_cex, _, avg_bc = self._avg_ratios(actual_ratios)
            if avg_bc or avg_cex:
                avg = []
                if avg_cex:
                    avg_cex.rate *= (1+self.settings.premium_percent/100)
                    avg.append(avg_cex.rate)
                if avg_bc:
                    avg.append(avg_bc.rate)
                max_rate = max(*avg) if len(avg) > 1 else avg[0]
                ratio = self.Ratio(
                    rate=max_rate
                )
                if self.settings.best_change.is_cutoff and avg_bc:
                    ratio.rate = min(ratio.rate, avg_bc.rate)
                return self._fill_ratio(ratio, direction)
            else:
                return None

        if direction.src.cur.is_fiat and direction.dest.cur.is_fiat:
            # используем best-change в силу большого числа вариантов
            avg_forex, _, _, avg_bc = self._avg_ratios(actual_ratios)
            if avg_forex or avg_bc:
                avg = []
                if avg_forex:
                    avg_forex.rate *= (1 + self.settings.premium_percent / 100)
                    avg.append(avg_forex.rate)
                if avg_bc:
                    avg.append(avg_bc.rate)
                max_rate = max(*avg) if len(avg) > 1 else avg[0]
                ratio = self.Ratio(
                    rate=max_rate
                )
                if self.settings.best_change.is_cutoff and avg_bc:
                    ratio.rate = min(ratio.rate, avg_bc.rate)
                return self._fill_ratio(ratio, direction)
            else:
                return None
        else:
            # Фиат на крипту или обратно
            avg_forex, _, avg_p2p, avg_bc = self._avg_ratios(
                actual_ratios
            )
            if avg_forex or avg_p2p or avg_bc:
                avg = []
                for r in [avg_forex, avg_p2p, avg_bc]:
                    if r:
                        if r != avg_bc:
                            r.rate *= (1 + self.settings.premium_percent / 100)
                        avg.append(r.rate)
                max_rate = max(*avg) if len(avg) > 1 else avg[0]
                ratio = self.Ratio(
                    rate=max_rate
                )
                if self.settings.best_change.is_cutoff and avg_bc:
                    ratio.rate = min(ratio.rate, avg_bc.rate)
                return self._fill_ratio(ratio, direction)
            else:
                return None

    @classmethod
    def _filter_ratios(
        cls,
        ratios: List[Union[EngineVariable, P2PEngineVariable]],
        direction: Direction
    ) -> List[Union[EngineVariable, P2PEngineVariable]]:
        result = []
        for r in ratios:
            if r.src == direction.src.cur.symbol and r.dest == direction.dest.cur.symbol:
                success = True
                if r.src_method != cls.METH_MARKET_CODE and r.src_method != direction.src.code:
                    success = False
                if r.dest_method != cls.METH_MARKET_CODE and r.dest_method != direction.dest.code:
                    success = False
                if success is True:
                    result.append(r)
        return result

    @classmethod
    def _fill_ratio(cls, ratio: Ratio, direction: Direction):
        ratio.src = direction.src.code
        ratio.dest = direction.dest.code
        return ratio

    def _avg_ratios(
        self, ratios: List[Union[EngineVariable, P2PEngineVariable]]
    ) -> Tuple[Optional[Ratio], Optional[Ratio], Optional[Ratio], Optional[Ratio]]:
        """
        :return: avg values grouped by scope [forex, cex, p2p, best_change]
        """
        avg_forex, avg_cex, avg_p2p, avg_bc = None, None, None, None
        if not ratios:
            return avg_forex, avg_cex, avg_p2p, avg_bc
        first = ratios[0]
        assert all([r.src == first.src for r in ratios])
        assert all([r.dest == first.dest for r in ratios])

        forex_rates = [r for r in ratios if r.scope == 'forex']
        if forex_rates and self.settings.forex.enabled:
            avg_forex = self.Ratio(
                rate=sum([r.rate for r in forex_rates]) / len(forex_rates),
                utc=self._oldest_utc(forex_rates)
            )
        cex_rates = [r for r in ratios if r.scope == 'cex']
        if cex_rates and self.settings.cex.enabled:
            avg_cex = self.Ratio(
                rate=sum([r.rate for r in cex_rates]) / len(cex_rates),
                utc=self._oldest_utc(cex_rates)
            )
        p2p_rates = [r for r in ratios if r.scope == 'p2p']
        if p2p_rates and self.settings.p2p.enabled:
            avg_p2p = self.Ratio(
                rate=sum([r.rate for r in p2p_rates]) / len(p2p_rates),
                utc=self._oldest_utc(p2p_rates)
            )
        bc_rates = [r for r in ratios if r.scope == 'bestchange']
        if bc_rates and self.settings.best_change.enabled:
            avg_bc = self.Ratio(
                rate=sum([r.rate for r in bc_rates]) / len(bc_rates),
                utc=self._oldest_utc(bc_rates)
            )
        return avg_forex, avg_cex, avg_p2p, avg_bc

    @classmethod
    async def _token_price_usd(cls, symbol) -> Optional[float]:
        engine = CoinMarketCapEngine()
        ratio = await engine.ratio('USD', symbol)
        if ratio:
            return ratio.ratio
        else:
            return None

    @classmethod
    def _oldest_utc(cls, rates: List[EngineVariable]) -> Optional[FormattedUTC]:
        utcs = [i.utc for i in rates if i.utc]
        if utcs:
            ts = min(utcs)
            return FormattedUTC(
                ts=ts,
                s=str(float_to_datetime(ts))
            )
        else:
            return None

    def _load_engine(self, cls_name: str):
        if cls_name in self._cached_engines:
            return self._cached_engines[cls_name]
        else:
            cls = load_class(cls_name)
            engine = cls()
            self._cached_engines[cls_name] = engine
            return engine

    async def _forex_rates(self, direction: Direction) -> List[EngineVariable]:
        src_cur, dest_cur = direction.src.cur, direction.dest.cur
        forex_rates = []
        forex_utcs = []
        cls_name = ''
        if not self.settings.forex.enabled:
            return []
        for cls_name in self.settings.forex.engines:
            engine: ForexEngine = self._load_engine(cls_name)
            if src_cur.is_fiat != dest_cur.is_fiat:
                if not src_cur.is_fiat:
                    src_token_usd_price = await self._token_price_usd(src_cur.symbol)  # noqa
                    src_symbol, dest_symbol = 'USD', dest_cur.symbol
                    corr = 1 / src_token_usd_price
                else:
                    dest_token_usd_price = await self._token_price_usd(dest_cur.symbol)  # noqa
                    src_symbol, dest_symbol = src_cur.symbol, 'USD'
                    corr = 1 * dest_token_usd_price
                ratio = await engine.ratio(
                    base=dest_symbol, quote=src_symbol
                )
                ratio.ratio *= corr
            elif src_cur.is_fiat == dest_cur.is_fiat and dest_cur.is_fiat:
                ratio = await engine.ratio(
                    base=dest_cur.symbol, quote=src_cur.symbol
                )
            else:
                ratio = None
            if ratio is not None:
                forex_rates.append(ratio.ratio)
                if ratio.utc:
                    forex_utcs.append(ratio.utc)
        if forex_rates:
            avg_rate = sum(forex_rates) / len(forex_rates)
            oldest_utc = min(forex_utcs) if forex_utcs else None
            return [
                EngineVariable(
                    id=f'{src_cur.symbol}-{dest_cur.symbol}-{engine.__class__.__name__}'.lower(),  # noqa
                    rate=avg_rate,
                    scope=self.settings.forex.scope,
                    engine=cls_name,
                    src=direction.src.cur.symbol,
                    dest=direction.dest.cur.symbol,
                    direction=direction,
                    src_method=self.METH_MARKET_CODE,
                    dest_method=self.METH_MARKET_CODE,
                    utc=oldest_utc
                )
            ]
        else:
            return []

    async def _p2p_rates(self, direction: Direction) -> List[EngineVariable]:
        if not self.settings.p2p.enabled:
            return []
        src_cur, dest_cur = direction.src.cur, direction.dest.cur
        result = []
        if src_cur.is_fiat == dest_cur.is_fiat:
            return []
        else:
            for engine_cls_name in self.settings.p2p.engines:
                engine = self._load_engine(engine_cls_name)
                if src_cur.is_fiat:
                    fiat = src_cur.symbol
                    token = dest_cur.symbol
                else:
                    fiat = dest_cur.symbol
                    token = src_cur.symbol
                forex = ForexEngine()
                forex_ratio = await forex.ratio(
                    base=self.settings.p2p.amount.base_cur, quote=fiat
                )
                min_amount = self.settings.p2p.amount.value * forex_ratio.ratio
                orders = await engine.load_orders(token=token, fiat=fiat)
                if orders is None:
                    continue
                if src_cur.symbol == fiat:
                    side = orders.asks
                    reverse_price = False
                else:
                    side = orders.bids
                    reverse_price = True
                #
                if side:
                    filtered_orders = []
                    #
                    for order in side:
                        if order.max_amount < min_amount:
                            continue
                        if order.min_amount/order.max_amount > self.settings.p2p.ignore_ratio_minmax:  # noqa
                            continue
                        if self.settings.p2p.pay_methods is not None:
                            methods = set(order.bestchange_codes)
                            expected_methods = set(self.settings.p2p.pay_methods)  # noqa
                            if not expected_methods.intersection(methods):
                                continue
                        filtered_orders.append(order)
                    #
                    if not self.settings.p2p.pay_methods:
                        pay_methods = ['all']
                    else:
                        pay_methods = self.settings.p2p.pay_methods
                    for method in pay_methods:
                        orders_ = [o for o in filtered_orders if method == 'all' or method in o.bestchange_codes]  # noqa
                        orders_ = orders_[:self.settings.p2p.amount.num]
                        prices = [o.price for o in orders_]
                        utcs = [o.utc for o in orders_ if o.utc]
                        give_meth = direction.src.cur.symbol
                        get_meth = direction.dest.cur.symbol
                        if direction.src.cur.is_fiat:
                            give_meth = method
                        elif direction.dest.cur.is_fiat:
                            get_meth = method
                        if prices:
                            avg_price = sum(prices) / len(prices)
                            if reverse_price:
                                avg_price = 1/avg_price
                            id_ = f'{give_meth}-{get_meth}-{engine.__class__.__name__}'.lower()  # noqa
                            if direction.src.cur.is_fiat:
                                get_meth = self.METH_MARKET_CODE
                            elif direction.dest.cur.is_fiat:
                                give_meth = self.METH_MARKET_CODE
                            oldest_utc = min(utcs) if utcs else None
                            result.append(
                                P2PEngineVariable(
                                    id=id_,
                                    rate=avg_price,
                                    scope=self.settings.p2p.scope,
                                    engine=engine_cls_name,
                                    src=src_cur.symbol,
                                    dest=dest_cur.symbol,
                                    method=method,
                                    direction=direction,
                                    src_method=give_meth,
                                    dest_method=get_meth,
                                    utc=oldest_utc
                                )
                            )
            return result

    async def _bestchange_rates(self, direction: Direction) -> List[P2PEngineVariable]:  # noqa
        if not self.settings.best_change.enabled:
            return []
        src_meth, dest_meth = direction.src.code, direction.dest.code
        src_cur, dest_cur = direction.src.cur, direction.dest.cur
        result = []
        for engine_cls_name in self.settings.best_change.engines:
            engine: BestChangeRatios = self._load_engine(engine_cls_name)
            orders = await engine.load_orders(
                get=dest_cur.symbol, give=src_cur.symbol
            )
            side = [o for o in orders.asks if src_meth in o.bestchange_codes and dest_meth in o.bestchange_codes]  # noqa
            if self.settings.best_change.low_pos < len(side) and self.settings.best_change.high_pos < len(side):  # noqa
                __low_pos = self.settings.best_change.low_pos
                __high_pos = self.settings.best_change.high_pos
            else:
                __low_pos = 0
                __high_pos = len(side)
            filtered = side[__low_pos:__high_pos+1]
            if filtered:
                avg_price = sum([o.price for o in filtered]) / len(filtered)
                id_ = f'{direction.src.code}-{direction.dest.code}-{engine.__class__.__name__}'.lower()  # noqa
                utcs = [i.utc for i in filtered if i.utc]
                if utcs:
                    oldest_utc = min(utcs)
                else:
                    oldest_utc = None
                result.append(
                    P2PEngineVariable(
                        id=id_,
                        rate=avg_price,
                        scope=self.settings.best_change.scope,
                        engine=engine_cls_name,
                        src=src_cur.symbol,
                        dest=dest_cur.symbol,
                        method=src_meth if src_cur.is_fiat else dest_meth,
                        direction=direction,
                        src_method=direction.src.code,
                        dest_method=direction.dest.code,
                        utc=oldest_utc
                    )
                )
        return result

    async def _cex_rates(self, direction: Direction) -> List[EngineVariable]:
        if not self.settings.cex.enabled:
            return []
        src_cur, dest_cur = direction.src.cur, direction.dest.cur
        result = []
        for engine_cls_name in self.settings.cex.engines:
            engine = self._load_engine(engine_cls_name)
            ratio = await engine.ratio(
                base=src_cur.symbol, quote=dest_cur.symbol
            )
            if ratio:
                id_ = f'{direction.src.cur.symbol}-{direction.dest.cur.symbol}-{engine.__class__.__name__}'.lower()  # noqa
                result.append(
                    EngineVariable(
                        id=id_,
                        rate=ratio.ratio,
                        scope=self.settings.cex.scope,
                        engine=engine_cls_name,
                        src=src_cur.symbol,
                        dest=dest_cur.symbol,
                        direction=direction,
                        src_method=self.METH_MARKET_CODE,
                        dest_method=self.METH_MARKET_CODE,
                        utc=ratio.utc
                    )
                )
        return result
