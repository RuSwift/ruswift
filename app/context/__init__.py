import weakref
from typing import Optional
from contextvars import ContextVar
from contextlib import contextmanager

from entities import Account, ExchangeConfig, Session


class Context:

    user: Optional[Account]
    session: Optional[Session]
    config: ExchangeConfig
    _proxy = ContextVar('context', default=None)

    def __getattr__(self, item):
        o = self.__class__._proxy.get()
        if not o:
            raise ValueError('Context is empty')
        return o.__getattribute__(item)  # noqa

    @classmethod
    @contextmanager
    def create_context(
        cls, config: ExchangeConfig,
        user: Account = None, session: Session = None
    ):
        inst = Context()
        inst.config = config
        inst.user = user
        inst.session = session
        token = cls._proxy.set(weakref.proxy(inst))
        try:
            yield inst
        finally:
            cls._proxy.reset(token)


context: Context = Context()
