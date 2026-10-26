import Foundation

/// Wisconsin Eats' side of the data updates (OTA-DATA.md): one places.json, checked with the loader launch uses.
extension DataLayout {
    static let app = DataLayout(kind: .single, bundled: Bundle.main.resourceURL!, head: "places") { folder in
        let (file, places) = try AppModel.read(folder.appending(path: "places.json"))
        return DataSummary(generated: file.generated, rows: ["places": file.places.count], places: places.count)
    }
}
