from .base_fetcher import BaseFetcher
from utils.logger import logger


class DataGovFetcher(BaseFetcher):
    def __init__(self):
        super().__init__()
        self.dataset_id = "d_b39d3a0871985372d7e1637193335da5"
        self.poll_url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{self.dataset_id}/poll-download"

    def fetch_all_exits(self):
        """Fetch exit data from Data.gov.sg API."""
        try:
            logger.info("Polling data.gov.sg for download URL...")
            poll_res = self.get(self.poll_url)

            download_url = poll_res.get("data", {}).get("url")
            if not download_url:
                logger.error("Could not find download URL in poll response")
                return []

            logger.info("Downloading GeoJSON data...")
            geojson = self.get(download_url)

            features = geojson.get("features", [])
            records = self._flatten_geojson(features)
            return records

        except Exception as e:
            logger.error(f"Failed to fetch from Data.gov.sg: {e}")
            return []

    def _flatten_geojson(self, features):
        """
        Converts GeoJSON Feature objects into a flat list of dicts.
        GeoJSON coordinates are [Longitude, Latitude].
        """
        records = []
        for feature in features:
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            coords = geom.get('coordinates', [0, 0])
            
            # Map the GeoJSON structure back to a simple flat dict
            records.append({
                "STATION_NA": props.get('STATION_NA'),
                "EXIT_CODE": props.get('EXIT_CODE'),
                # GeoJSON is [Lng, Lat], we store it as Lat, Lng for our processor
                "LATITUDE": coords[1],
                "LONGITUDE": coords[0]
            })
        return records
