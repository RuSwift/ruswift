import logging
import os.path
import asyncio
from typing import Optional

from django.core.management.base import BaseCommand

from entities import Account
from reposiroty import AccountRepository
from reposiroty.utils import (
    create_superuser, LoginAuth, AnyCredential
)
from api.auth import LoginAuth


class Command(BaseCommand):

    """Create Superuser With Login+Password"""

    def add_arguments(self, parser):
        parser.add_argument(
            "login",
            type=str,
            help="Superuser login"
        )
        parser.add_argument(
            "password",
            type=str,
            help="Superuser Password"
        )

    def handle(self, *args, **options):
        asyncio.run(
            self.run(options['login'], options['password'])
        )

    async def run(self, login: str, password: str):
        uid = f'management:{login}'
        await create_superuser(
            uid=uid,
            credentials=[
                LoginAuth.LoginCredential(
                    login=login,
                    password=password
                )
            ]
        )
