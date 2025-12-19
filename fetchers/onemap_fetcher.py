import os
from .base_fetcher import BaseFetcher

class OneMapFetcher(BaseFetcher):
    def __init__(self):
        super().__init__()
        self.search_url = "https://www.onemap.gov.sg/api/common/elastic/search"
        self.nearby_url = "https://www.onemap.gov.sg/api/public/nearbysvc/getNearestMrtStops"
        self.api_key = os.getenv("ONEMAP_API_KEY")

    def search_onemap(self, query):
        params = {'searchVal': query, 'returnGeom': 'Y', 'getAddrDetails': 'Y'}
        try:
            data = self.get(self.search_url, params=params)
            return data.get('results', [])
        except Exception:
            return []

    def get_nearby_mrt(self, lat, lng):
        params = {'latitude': lat, 'longitude': lng, 'pagenum': 1}
        try:
            data = self.get(self.nearby_url, params=params)
            return data.get('results', [])
        except Exception:
            return []
