import os
import uuid
from typing import Literal, List

import xlsxwriter

from microledger import MassPaymentMicroLedger


class QugoRegistry:

    def __init__(
        self, payments: List[MassPaymentMicroLedger.Message],
        scenario: Literal['direct'] = 'direct'
    ):
        self._payments = payments
        self._scenario = scenario

    async def export_to_buffer(self) -> bytes:
        tmp_path = f'/tmp/{uuid.uuid4().hex}.xlsx'
        await self.export_to_file(tmp_path)
        try:
            with open(tmp_path, 'rb') as f:
                return f.read()
        finally:
            os.remove(tmp_path)

    async def export_to_file(self, path: str):
        workbook = xlsxwriter.Workbook(path)
        worksheet = workbook.add_worksheet(name='Реестр выплат')
        expenses = [
            ('ФИО (*)', 'Номер карты (*)', 'Сумма (*)', 'Комментарий')
        ]
        currency_format = workbook.add_format()
        currency_format.set_num_format('#,##0.00')
        text_format = workbook.add_format()
        text_format.set_num_format('@')

        for msg in self._payments:
            expenses.append(
                (
                    msg.customer.display_name,
                    msg.card.number,
                    msg.transaction.amount,
                    msg.transaction.description
                )
            )

        for row, tup in enumerate(expenses):
            name, card_number, amount, comment = tup
            worksheet.write(row, 0, name)
            worksheet.write(row, 3, comment)
            if row > 0:
                worksheet.write_string(row, 1, str(card_number), text_format)
                worksheet.write_number(row, 2, float(amount), currency_format)
            else:
                worksheet.write(row, 1, card_number)
                worksheet.write(row, 2, amount)

        workbook.close()
