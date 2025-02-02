from entities import ExchangeConfig, Identity, Ledger


def configure_mass_payments_ledger(
    cfg: ExchangeConfig, owner: Identity, ledger: Ledger = None
) -> Ledger:
    if not ledger:
        ledger = Ledger(
            id=f'{owner.did.root}:payments',
            tags=['payments']
        )
    if 'payments' not in ledger.tags:
        ledger.tags.append('payments')
    owners = ledger.participants.get('owner') or []
    if owner.did.root not in owners:
        owners.append(owner.did.root)
        ledger.participants['owner'] = owners
    processors = ledger.participants.get('processing') or []
    if cfg.identity.did.root not in processors:
        processors.append(cfg.identity.did.root)
        ledger.participants['processing'] = processors
    return ledger