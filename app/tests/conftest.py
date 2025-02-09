import asyncio
import os.path

import pytest
from pydantic import BaseModel, Extra
from pydantic_yaml import parse_yaml_file_as

from entities import ExchangeConfig, Account


class AnyCfg(BaseModel, extra=Extra.allow):
    ...


@pytest.fixture
def redis_dsn() -> str:
    return 'redis://default:password@redis'


@pytest.fixture
def exchange_config() -> ExchangeConfig:
    path, section = '/app/exchange/tests/files/init.example.yml', 'exchange'
    if not os.path.isfile(path):
        raise RuntimeError(f'path "{path}" not exists')
    settings = parse_yaml_file_as(AnyCfg, path)
    if section:
        values = getattr(settings, section)
    else:
        values = settings
    cfg = ExchangeConfig.model_validate(values)
    return cfg


@pytest.fixture
def user() -> Account:
    return Account(
        uid='test',
        icon='https://x.com/icon.png',
        first_name='John',
        last_name='Don'
    )


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
