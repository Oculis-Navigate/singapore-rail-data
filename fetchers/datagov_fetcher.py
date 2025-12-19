from .base_fetcher import BaseFetcher

class DataGovFetcher(BaseFetcher):
    def __init__(self):
        super().__init__()
        # The new v1 API endpoint for the MRT Exit dataset
        self.dataset_id = "d_b39d3a0871985372d7e1637193335da5"
        self.poll_url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{self.dataset_id}/poll-download"

    def fetch_all_exits(self):
        """
        1. Calls the poll-download endpoint to get the S3 URL.
        2. Downloads the GeoJSON from that URL.
        3. Flattens the GeoJSON features into a list of records.
        """
        try:
            print(f"Polling data.gov.sg for download URL...")
            poll_res = self.get(self.poll_url)
            
            # Extract the temporary S3 URL
            download_url = poll_res.get('data', {}).get('url')
            if not download_url:
                print("Error: Could not find download URL in poll response.")
                return []

            print(f"Downloading GeoJSON data...")
            geojson = self.get(download_url)
            
            # Standard GeoJSON has a 'features' list
            features = geojson.get('features', [])
            return self._flatten_geojson(features)

        except Exception as e:
            print(f"Error fetching from Data.gov.sg v1 API: {e}")
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
