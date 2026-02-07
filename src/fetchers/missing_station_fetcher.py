from .base_fetcher import BaseFetcher
from ..utils.logger import logger


class MissingStationFetcher(BaseFetcher):
    """Fetches station data from OneMap for stations missing from Data.gov.sg."""

    def __init__(self, onemap_fetcher):
        super().__init__()
        self.onemap = onemap_fetcher

    def find_missing_stations(self, datagov_records):
        """Identify stations in OneMap that are missing from Data.gov.sg."""
        logger.info("Scanning OneMap for missing stations...")

        onemap_stations = self.onemap.fetch_all_mrt_stations()

        datagov_stations = set()
        for record in datagov_records:
            name = record.get("STATION_NA", "").upper()
            name = name.replace(" LRT STATION", " MRT STATION")
            datagov_stations.add(name)

        missing = []
        for station_name, station_data in onemap_stations.items():
            found = False
            station_base = station_name.replace(" MRT STATION", "").replace(" LRT STATION", "")
            for dg_name in datagov_stations:
                if station_base in dg_name or dg_name in station_name:
                    found = True
                    break

            if not found:
                missing.append(
                    {
                        "name": station_name,
                        "codes": station_data["codes"],
                        "lat": station_data["lat"],
                        "lng": station_data["lng"],
                    }
                )

        if missing:
            logger.info(f"Found {len(missing)} stations missing from Data.gov.sg:")
            for station in missing:
                logger.item(f"{station['name']} ({', '.join(station['codes'])})")

        return missing

    def fetch_missing_stations(self, missing_stations_list):
        """Fetch exit data for missing stations from OneMap."""
        records = []

        for i, station in enumerate(missing_stations_list, 1):
            station_name = station["name"]
            codes = station["codes"]

            logger.progress(i, len(missing_stations_list), f"Fetching {station_name}")

            exits = self.onemap.fetch_exits_for_station(station_name)

            if exits:
                for exit_data in exits:
                    records.append(
                        {
                            "STATION_NA": station_name,
                            "EXIT_CODE": exit_data["exit_code"],
                            "LATITUDE": exit_data["lat"],
                            "LONGITUDE": exit_data["lng"],
                        }
                    )
            else:
                logger.warning(f"No exits found for {station_name}, using station center")
                for code in codes:
                    records.append(
                        {
                            "STATION_NA": station_name,
                            "EXIT_CODE": "A",
                            "LATITUDE": station["lat"],
                            "LONGITUDE": station["lng"],
                        }
                    )

        return records

    def augment_datagov_data(self, datagov_records):
        """Find missing stations and fetch them from OneMap."""
        missing = self.find_missing_stations(datagov_records)

        if missing:
            additional_records = self.fetch_missing_stations(missing)
            logger.success(f"Added {len(additional_records)} exit records from OneMap")
            return datagov_records + additional_records

        return datagov_records
