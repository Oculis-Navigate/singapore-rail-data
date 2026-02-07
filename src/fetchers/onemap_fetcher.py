import os
import re
from .base_fetcher import BaseFetcher
from ..utils.logger import logger


class OneMapFetcher(BaseFetcher):
    def __init__(self):
        super().__init__()
        self.search_url = "https://www.onemap.gov.sg/api/common/elastic/search"
        self.nearby_url = "https://www.onemap.gov.sg/api/public/nearbysvc/getNearestMrtStops"
        self.api_key = os.getenv("ONEMAP_API_KEY")

    def search_onemap(self, query):
        params = {"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y"}
        try:
            data = self.get(self.search_url, params=params)
            return data.get("results", [])
        except Exception:
            return []

    def get_nearby_mrt(self, lat, lng):
        params = {"latitude": lat, "longitude": lng, "pagenum": 1}
        try:
            data = self.get(self.nearby_url, params=params)
            return data.get("results", [])
        except Exception:
            return []

    def fetch_all_mrt_stations(self):
        """Fetch all MRT stations from OneMap."""
        stations = {}
        line_prefixes = ["NS", "EW", "NE", "CC", "DT", "TE", "BP", "SW", "SE", "PW"]

        for prefix in line_prefixes:
            try:
                results = self.search_onemap(f"{prefix} MRT STATION")
                for result in results:
                    building = result.get("BUILDING", "").upper()
                    if "MRT STATION" in building and "EXIT" not in building:
                        codes = set(re.findall(r"([A-Z]{1,3}\d+)", building))
                        if codes:
                            name = re.sub(r"\(.*?\)", "", building).strip()
                            name = re.sub(r"\s+EXIT\s+[A-Z0-9]+", "", name).strip()

                            if name not in stations:
                                stations[name] = {
                                    "codes": sorted(list(codes)),
                                    "lat": float(result.get("LATITUDE", 0)),
                                    "lng": float(result.get("LONGITUDE", 0)),
                                }
            except Exception as e:
                logger.warning(f"Error searching for {prefix} stations: {e}")

        # Targeted searches for specific stations
        targeted_stations = ["PUNGGOL COAST", "SUNGEI BEDOK"]

        for station_query in targeted_stations:
            try:
                existing_names = [s.replace(" MRT STATION", "").replace(" LRT STATION", "") for s in stations.keys()]
                if station_query not in existing_names:
                    results = self.search_onemap(f"{station_query} MRT STATION")
                    for result in results:
                        building = result.get("BUILDING", "").upper()
                        if "MRT STATION" in building and "EXIT" not in building:
                            codes = set(re.findall(r"([A-Z]{1,3}\d+)", building))
                            if codes:
                                name = re.sub(r"\(.*?\)", "", building).strip()
                                name = re.sub(r"\s+EXIT\s+[A-Z0-9]+", "", name).strip()

                                if name not in stations:
                                    stations[name] = {
                                        "codes": sorted(list(codes)),
                                        "lat": float(result.get("LATITUDE", 0)),
                                        "lng": float(result.get("LONGITUDE", 0)),
                                    }
                                    logger.item(f"{name} ({', '.join(sorted(list(codes)))})")
            except Exception as e:
                logger.warning(f"Error searching for {station_query}: {e}")

        return stations

    def fetch_exits_for_station(self, station_name):
        """Fetch exit coordinates for a specific station from OneMap."""
        exits = []
        try:
            results = self.search_onemap(f"{station_name} EXIT")

            for result in results:
                building = result.get("BUILDING", "").upper()
                if station_name.upper() in building and "EXIT" in building:
                    exit_match = re.search(r"EXIT\s+([A-Z0-9]+)", building)
                    if exit_match:
                        exit_code = exit_match.group(1)
                        exits.append(
                            {
                                "exit_code": exit_code,
                                "lat": float(result.get("LATITUDE", 0)),
                                "lng": float(result.get("LONGITUDE", 0)),
                            }
                        )

            if not exits:
                for exit_num in range(1, 15):
                    results = self.search_onemap(f"{station_name} EXIT {exit_num}")
                    for result in results:
                        building = result.get("BUILDING", "").upper()
                        if station_name.upper() in building:
                            exits.append(
                                {
                                    "exit_code": str(exit_num),
                                    "lat": float(result.get("LATITUDE", 0)),
                                    "lng": float(result.get("LONGITUDE", 0)),
                                }
                            )
                            break

        except Exception as e:
            logger.warning(f"Error fetching exits for {station_name}: {e}")

        return exits
