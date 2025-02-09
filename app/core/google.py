import httplib2
from asgiref.sync import sync_to_async
from googleapiclient import discovery


class GoogleSpreadSheet:

    _discovery_url = 'https://sheets.googleapis.com/$discovery/rest?version=v4'

    def __init__(self, api_key: str, spread_sheet_id: str):
        self.__api_key = api_key
        self.__spread_sheet_id = spread_sheet_id

    async def read(self, range_name: str = 'Markets!A2:E') -> list:
        result = await sync_to_async(
            self.sync_read, thread_sensitive=True
        )(range_name=range_name)
        return result

    def sync_read(self, range_name: str = 'Markets!A2:E') -> list:

        service = discovery.build(
            'sheets',
            'v4',
            http=httplib2.Http(),
            discoveryServiceUrl=self._discovery_url,
            developerKey=self.__api_key)

        result = service.spreadsheets().values().get(
            spreadsheetId=self.__spread_sheet_id,
            range=range_name
        ).execute()
        values = result.get('values', [])
        return values
