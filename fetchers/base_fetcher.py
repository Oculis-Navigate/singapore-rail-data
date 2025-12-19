import requests

class BaseFetcher:
    def get(self, url, params=None, headers=None):
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
