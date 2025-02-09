import logging
from typing import Optional, List, Union

from entities import Account
from reposiroty import AccountRepository
from api.auth import LoginAuth, TokenAuth, ApiTokenAuth


AnyCredential = Union[
    LoginAuth.LoginCredential,
    TokenAuth.TokenCredential,
    ApiTokenAuth.ApiCredential
]


async def create_account(
    uid: str, credentials: List[AnyCredential], **kwargs
) -> Account:

    account: Optional[Account] = await AccountRepository.get(uid=uid)
    if account:
        raise RuntimeError(f'Account [{uid}] already exists!')
    account = Account(
        uid=uid,
        **kwargs
    )
    actual: Account = await AccountRepository.update_or_create(e=account, uid=uid)
    for cred in credentials:
        for auth in [LoginAuth, TokenAuth, ApiTokenAuth]:
            if isinstance(cred, auth.Schema):
                await auth.register(
                    account=uid,
                    payload=cred.model_dump(mode='json')
                )
                logging.critical(
                    f'Superuser [{uid}] with cred {cred} '
                    f'was successfully created'
                )
                break
    return actual


async def create_superuser(
    uid: str, credentials: List[AnyCredential]
) -> Account:
    return await create_account(
        uid,
        credentials=credentials,
        is_active=True,
        permissions=[Account.Permission.ROOT]
    )
