import uuid
import requests
import random

from binaries import DATA_URL_JPG, DATA_URL_PDF, DATA_URI_XLS, DATA_URI_DOCX


def fill_mass_payments():
    pdf_uid = 'pdf'
    jpg_uid = 'jpg'
    docx_uid = 'docx'
    xls_uid = 'xls'
    resp = requests.post(
        'http://localhost/api/control-panel/did:web:ruswift.ru:koan/mass-payments/attachments',
        json=[
            {
                'uid': pdf_uid,
                'name': 'TestDocument.pdf',
                'data': DATA_URL_PDF
            },
            {
                'uid': jpg_uid,
                'name': 'TestImage.jpeg',
                'data': DATA_URL_JPG
            },
            {
                'uid': docx_uid,
                'name': 'TestDoc.docx',
                'data': DATA_URI_DOCX
            },
            {
                'uid': xls_uid,
                'name': 'TestSheet.xlsx',
                'data': DATA_URI_XLS
            }
        ],
        headers={
            'Token': 'root'
        }
    )
    assert resp.status_code == 200
    url = 'http://localhost/api/mass-payments'
    headers = {
        'Content-type': 'application/json',
        'Token': 'BCHoRV2Di5XTAyaluMBSgLat8MGbhavQ'
    }
    amounts = [10000.0, 20000.0, 30000.0, 140000.0, 35000.0, 55000.0]
    identities = [
        'petr@ivanov.ru', 'semen@slepakov.ru', 'ivan@zuev.ru',
        'slavik@gmail.com', 'roman@fedorov.ru'
    ]
    error_uid = None
    success_uid = None
    only_attachment_uid = None
    for n in range(5):
        i = n
        create = requests.post(
            url,
            json=
                {
                    'uid': f'id-{n}',
                    'transaction': {
                        'order_id': f'000{i}',
                        'description': f'Test description X-{i}',
                        'amount': random.choice(amounts),
                        'currency': 'RUB'
                    },
                    'customer': {
                        'identifier': random.choice(identities),
                        'display_name': 'Ivan Sidorov',
                        'email': random.choice(identities),
                    },
                    'card': {
                        'number': '22001112200005555',
                        'expiration_date': '10/30'
                    }
                }

            ,
            headers=headers
        )
        assert create.status_code == 200
        if error_uid is None and i > 1:
            error_uid = create.json()['uid']
        if success_uid is None and i > 2:
            success_uid = create.json()['uid']
        if only_attachment_uid is None and i > 3:
            only_attachment_uid = create.json()['uid']

    status = requests.post(
        url='http://localhost/api/control-panel/did:web:ruswift.ru:koan/mass-payments/status',
        json=[
            {
                'uid': error_uid,
                'status': 'error',
                'message': 'Some error message !'
            },
            {
                'uid': success_uid,
                'status': 'success',
                'payload': {
                    'attachments': [
                        {'uid': pdf_uid}, {'uid': jpg_uid}
                    ]
                }
            },
            {
                'uid': only_attachment_uid,
                'status': 'attachment',
                'payload': {
                    'attachments': [
                        {'uid': docx_uid}, {'uid': xls_uid}
                    ]
                }
            }
            #
        ],
        headers={
            'Token': 'root'
        }
    )
    assert status.status_code == 200, status.status_code


if __name__ == '__main__':
    fill_mass_payments()
