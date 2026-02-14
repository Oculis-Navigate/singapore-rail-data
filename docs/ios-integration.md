# iOS Integration Guide

## Data Format

The JSON file follows the existing FinalOutput schema with added version metadata.

## URL Pattern

```
https://github.com/{USER}/{REPO}/releases/download/{VERSION}/stage3_final.json
```

Example:
```
https://github.com/yourname/mrt-data/releases/download/20240214/stage3_final.json
```

## Swift Models

```swift
struct StationData: Codable {
    let metadata: Metadata
    let stations: [Station]
}

struct Metadata: Codable {
    let dataVersion: String  // "2024-02-14"
    let dataVersionIso: String  // "20240214"
    let checksumSha256: String
    let stationCount: Int
    
    enum CodingKeys: String, CodingKey {
        case dataVersion = "data_version"
        case dataVersionIso = "data_version_iso"
        case checksumSha256 = "checksum_sha256"
        case stationCount = "station_count"
    }
}

struct Station: Codable {
    let officialName: String
    let mrtCodes: [String]
    let exits: [Exit]
    
    enum CodingKeys: String, CodingKey {
        case officialName = "official_name"
        case mrtCodes = "mrt_codes"
        case exits
    }
}

struct Exit: Codable {
    let exitCode: String
    let lat: Double
    let lng: Double
    let platforms: [Platform]?
    let accessibility: [String]?
    let busStops: [BusStop]?
    let nearbyLandmarks: [String]?
    
    enum CodingKeys: String, CodingKey {
        case exitCode = "exit_code"
        case lat
        case lng
        case platforms
        case accessibility
        case busStops = "bus_stops"
        case nearbyLandmarks = "nearby_landmarks"
    }
}

struct Platform: Codable {
    let platformCode: String
    let towardsCode: String?
    let lineCode: String
    
    enum CodingKeys: String, CodingKey {
        case platformCode = "platform_code"
        case towardsCode = "towards_code"
        case lineCode = "line_code"
    }
}

struct BusStop: Codable {
    let code: String
    let services: [String]
}
```

## Update Detection

```swift
func checkForUpdates() async throws -> Bool {
    // Get latest release version
    let manifestURL = URL(string: "https://api.github.com/repos/YOUR_USER/mrt-data/releases/latest")!
    
    let (data, _) = try await URLSession.shared.data(from: manifestURL)
    let release = try JSONDecoder().decode(GitHubRelease.self, from: data)
    
    // Compare with bundled version
    let remoteVersion = release.tagName  // "20240214"
    let bundledVersion = UserDefaults.standard.string(forKey: "dataVersion") ?? "0"
    
    return remoteVersion > bundledVersion
}

struct GitHubRelease: Codable {
    let tagName: String
    
    enum CodingKeys: String, CodingKey {
        case tagName = "tag_name"
    }
}
```

## Loading Data

```swift
// From app bundle
if let url = Bundle.main.url(forResource: "stage3_final", withExtension: "json") {
    let data = try Data(contentsOf: url)
    let stations = try JSONDecoder().decode(StationData.self, from: data)
}

// From remote (after update)
let remoteURL = URL(string: "https://github.com/USER/REPO/releases/download/20240214/stage3_final.json")!
let (data, _) = try await URLSession.shared.data(from: remoteURL)
let stations = try JSONDecoder().decode(StationData.self, from: data)
```

## Checksum Validation

```swift
func validateChecksum(for data: StationData) -> Bool {
    // Reconstruct JSON without checksum field
    var json = try JSONSerialization.jsonObject(with: encodedData) as! [String: Any]
    var metadata = json["metadata"] as! [String: Any]
    metadata.removeValue(forKey: "checksum_sha256")
    json["metadata"] = metadata
    
    // Sort keys and serialize
    let jsonData = try JSONSerialization.data(
        withJSONObject: json,
        options: [.sortedKeys, .withoutEscapingSlashes]
    )
    
    // Calculate SHA256
    let calculated = jsonData.sha256().hexString()
    
    return calculated == data.metadata.checksumSha256
}
```

## Caching Strategy

```swift
class DataManager {
    static let shared = DataManager()
    
    private let cacheKey = "cachedStationData"
    private let versionKey = "dataVersion"
    
    func loadCachedData() -> StationData? {
        guard let data = UserDefaults.standard.data(forKey: cacheKey) else {
            return nil
        }
        return try? JSONDecoder().decode(StationData.self, from: data)
    }
    
    func cacheData(_ data: StationData) {
        if let encoded = try? JSONEncoder().encode(data) {
            UserDefaults.standard.set(encoded, forKey: cacheKey)
            UserDefaults.standard.set(data.metadata.dataVersionIso, forKey: versionKey)
        }
    }
}
```

## Example Usage

```swift
class StationService {
    private let baseURL = "https://github.com/YOUR_USER/mrt-data/releases/download"
    
    func fetchLatestData() async throws -> StationData {
        // Check for updates
        let hasUpdate = try await checkForUpdates()
        
        if hasUpdate {
            // Download new data
            let latestVersion = try await getLatestVersion()
            let url = URL(string: "\(baseURL)/\(latestVersion)/stage3_final.json")!
            
            let (data, _) = try await URLSession.shared.data(from: url)
            let stationData = try JSONDecoder().decode(StationData.self, from: data)
            
            // Validate and cache
            if validateChecksum(for: stationData) {
                DataManager.shared.cacheData(stationData)
                return stationData
            } else {
                throw DataError.checksumMismatch
            }
        } else {
            // Return cached data
            guard let cached = DataManager.shared.loadCachedData() else {
                throw DataError.noCachedData
            }
            return cached
        }
    }
    
    private func getLatestVersion() async throws -> String {
        let url = URL(string: "https://api.github.com/repos/YOUR_USER/mrt-data/releases/latest")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let release = try JSONDecoder().decode(GitHubRelease.self, from: data)
        return release.tagName
    }
}

enum DataError: Error {
    case checksumMismatch
    case noCachedData
}
```

## Data Size

The JSON file is approximately 650KB, making it suitable for mobile distribution. The file includes:

- All MRT/LRT stations (187 stations)
- Exit information with coordinates
- Nearby bus stops
- Landmarks and accessibility features
- Complete metadata with versioning

## Rate Limits

GitHub Releases have generous bandwidth limits:
- No limits for public repositories
- Sufficient for iOS apps with thousands of users
- CDN-backed for fast global distribution
