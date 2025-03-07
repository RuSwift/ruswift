from .base import ExchangeHttpRouter
from .kyc import KYCController, MTSKYCController
from .account import (
    AccountController, RegistrationController, ContactsVerifyController
)
from .ratios import EngineRateController, XMLEngineRateController
from .storage import StorageController
from .ledgers import LedgerController
from .directions import (
    DirectionController, CurrenciesController, PaymentController, 
    MethodCostController, MethodController
)
from .mass_payment import (
    MassPaymentController, ControlPanelMassPaymentController
)
from .orders import OrderController
from .autocomplete import BestChangeCodeController, ActiveCurrencyController


api_router = ExchangeHttpRouter('api')
api_router.register('kyc/mts', MTSKYCController)
api_router.register('kyc', KYCController)
api_router.register('accounts', AccountController)
api_router.register('register', RegistrationController)
api_router.register('contact-verify', ContactsVerifyController)
api_router.register('storage', StorageController)
api_router.register('ledgers', LedgerController)
api_router.register('mass-payments', MassPaymentController)
api_router.register(
    'control-panel/<merchant>/mass-payments',
    ControlPanelMassPaymentController
)
api_router.register('orders', OrderController)

rates_router = ExchangeHttpRouter('ratios')
rates_router.register('external', EngineRateController)
rates_router.register('external.xml', XMLEngineRateController)
api_router.append(rates_router)

exchange_router = ExchangeHttpRouter('exchange')
exchange_router.register('directions', DirectionController)
exchange_router.register('currencies', CurrenciesController)
exchange_router.register('costs', MethodCostController)
exchange_router.register('payments', PaymentController)
exchange_router.register('methods', MethodController)
api_router.append(exchange_router)

autocomplete_router = ExchangeHttpRouter('autocomplete')
autocomplete_router.register('bc-codes', BestChangeCodeController)
autocomplete_router.register('active-curs', ActiveCurrencyController)

api_router.append(autocomplete_router)
