import os.path
import asyncio

from django.core.management.base import BaseCommand

from reposiroty import ExchangeConfigRepository
from merchants import update_merchants_config


class Command(BaseCommand):

    """Init exchange from YAML"""

    DEF_TIMEOUT = 60

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            type=str,
            help="YAML file with exchange config"
        )
        parser.add_argument(
            "--section",
            type=str,
            help="YAML section"
        )

    def handle(self, *args, **options):
        path = options['path']
        section = options['section']
        asyncio.run(
            self.run(path, section)
        )

    async def run(self, path: str, section: str = None):
        if not os.path.isfile(path):
            raise RuntimeError(f'File {path} does not exists!')
        await ExchangeConfigRepository.init_from_yaml(path, section)
        cfg = await ExchangeConfigRepository.get()
        await update_merchants_config(cfg)
        print('=========== CONFIG ============')
        print(cfg.model_dump_json(indent=2))
