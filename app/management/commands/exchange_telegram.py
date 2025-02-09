import asyncio
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from core.telegram import TelegramBot


class Command(BaseCommand):

    """Telegram Bot"""
    __settings = settings.TG_BOT

    def add_arguments(self, parser):
        parser.add_argument(
            "--command",
            type=str,
            help="Telegram bot command",
            default='get_updates'
        )

    def handle(self, *args, **options):
        command = options['command']
        asyncio.run(self.run(command))

    async def run(self, command):
        bot = TelegramBot(token=settings.TG_BOT.token)
        if command == 'get_updates':
            ok, res = await bot.get_updates(clear=True)
            print(json.dumps(res, indent=True, sort_keys=True))\
