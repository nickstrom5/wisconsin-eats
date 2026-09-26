import Foundation
import CoreLocation

// MARK: - The bundled data file (Resources/places.json), written by pipeline/wisconsin.py with WI_APP=1

struct DataFile: Decodable {
    let generated: String
    let cities: [String]
    let cuisines: [String]
    let brands: [String]
    let sources: [String]
    let count_restaurants: Int
    let calibration: [String: [String: CalibrationGroup]]
    let places: [PlaceRecord]
}

struct CalibrationGroup: Decodable, Hashable {
    let n: Int
    let official: Double
}

struct InspectionRecord: Decodable, Hashable {
    let g: String          // our letter grade (on a curve), not an official one
    let sc: Int?           // 0-100 score
    let n: Int?            // routine inspections since Jan 2023
    let re: Int?           // visits that needed a re-inspection
    let vp: Double?        // violations per visit
    let rf: Double?        // foodborne-illness risk items per visit
    let pe: Int?           // visits with a pest item
    let rp: Int?           // repeat violations
    let su: Int?           // immediate suspensions
    let ld: String?        // last routine visit
    let lr: Int?           // 1 if the last visit needed a re-inspection
}

struct PlaceRecord: Decodable {
    let id: String
    let n: String
    let c: Int?
    let cu: Int
    let t: Int
    let s: Int
    let a: String?
    let z: String?
    let la: Double?
    let lo: Double?
    let b: Int?
    let ch: Int?
    let j: Int?
    let v: Int?
    let bar: Int?
    let g: Int?
    let hc: Int?
    let h: Int?
    let ip: Double?
    let icon: String?
    let jbf: String?
    let hon: String?
    let f: Int?
    let fish: String?
    let days: String?
    let sides: String?
    let note: String?
    let w: String?
    let ph: String?
    let lic: String?
    let inspection: InspectionRecord?

    enum CodingKeys: String, CodingKey {
        case id, n, c, cu, t, s, a, z, la, lo, b, ch, j, v, bar, g, hc, h, ip, icon, jbf, hon, f, fish, days, sides, note, w, ph, lic
        case inspection = "in"
    }
}

// MARK: - The model the views use

struct PlaceTags: OptionSet, Hashable {
    let rawValue: Int
    static let supperClub = PlaceTags(rawValue: 1)
    static let fishFry = PlaceTags(rawValue: 2)
    static let cheeseCurds = PlaceTags(rawValue: 4)
    static let custard = PlaceTags(rawValue: 8)
    static let fishBoil = PlaceTags(rawValue: 16)
}

/// How a place got on the list. The share that matched a licensed business comes from calibration.json.
enum Tier: Int, Comparable {
    case listing = 0        // one map listing
    case confirmed = 1      // a high-confidence Meta listing, or a hand-checked place
    case licensed = 2       // on the City of Milwaukee or Dane County license list

    static func < (a: Tier, b: Tier) -> Bool { a.rawValue < b.rawValue }

    var label: String {
        switch self {
        case .licensed: "Licensed"
        case .confirmed: "Confirmed listing"
        case .listing: "Listing only"
        }
    }
}

enum Jurisdiction: Int {
    case none = 0, milwaukee = 1, dane = 2
    var listName: String {
        switch self {
        case .milwaukee: "City of Milwaukee"
        case .dane: "Public Health Madison & Dane County"
        case .none: ""
        }
    }
}

struct Place: Identifiable, Hashable {
    let id: String
    let name: String
    let address: String?
    let city: String?
    let zip: String?
    let coordinate: CLLocationCoordinate2D?
    let cuisine: String
    let brand: String?
    let chainCount: Int
    let tier: Tier
    let jurisdiction: Jurisdiction
    let source: String
    let isVenue: Bool
    let isBar: Bool
    let tags: PlaceTags
    /// On our hand-checked list (data/curated.json or data/research/app): confirmed open with a 2025–26 source.
    let handChecked: Bool
    let honorFlags: Int
    let iconicPoints: Double?
    let iconText: String?
    let jamesBeard: String?
    let otherHonors: String?
    let founded: Int?
    let fish: String?
    let fryDays: String?
    let sides: String?
    let note: String?
    let website: URL?
    let phone: String?
    let license: String?
    let inspection: InspectionRecord?
    /// normalized text for search: name, town, zip, cuisine, brand, then the address with street words abbreviated
    let searchText: String
    let nameText: String

    static func == (a: Place, b: Place) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }

    var isHonored: Bool { honorFlags != 0 }
    var isChain: Bool { chainCount >= 5 }
    var hasJamesBeard: Bool { honorFlags & 0b1111 != 0 }
    var jamesBeardLabel: String? {
        if honorFlags & 1 != 0 { return "America's Classic" }
        if honorFlags & 2 != 0 { return "James Beard winner" }
        if honorFlags & 4 != 0 { return "James Beard finalist" }
        if honorFlags & 8 != 0 { return "James Beard semifinalist" }
        return nil
    }
    var townLine: String { [city, cuisine].compactMap { $0 }.joined(separator: " · ") }
    var fullAddress: String {
        [address, [city, zip].compactMap { $0 }.joined(separator: " ")].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ", ")
    }
    var location: CLLocation? { coordinate.map { CLLocation(latitude: $0.latitude, longitude: $0.longitude) } }

    init(_ r: PlaceRecord, file: DataFile) {
        let city = r.c.flatMap { $0 < file.cities.count ? file.cities[$0] : nil }
        let cuisine = r.cu < file.cuisines.count ? file.cuisines[r.cu] : "American & Other"
        let brand = r.b.flatMap { $0 < file.brands.count ? file.brands[$0] : nil }
        id = r.id
        name = r.n
        address = r.a
        self.city = city
        zip = r.z
        if let la = r.la, let lo = r.lo { coordinate = CLLocationCoordinate2D(latitude: la, longitude: lo) } else { coordinate = nil }
        self.cuisine = cuisine
        self.brand = brand
        chainCount = r.ch ?? 1
        tier = Tier(rawValue: r.t) ?? .listing
        jurisdiction = Jurisdiction(rawValue: r.j ?? 0) ?? .none
        source = r.s < file.sources.count ? file.sources[r.s] : "meta"
        isVenue = r.v == 1
        isBar = r.bar == 1
        tags = PlaceTags(rawValue: r.g ?? 0)
        handChecked = r.hc == 1
        honorFlags = r.h ?? 0
        iconicPoints = r.ip
        iconText = r.icon
        jamesBeard = r.jbf
        otherHonors = r.hon
        founded = r.f
        fish = r.fish
        fryDays = r.days
        sides = r.sides
        note = r.note
        website = r.w.flatMap { URL(string: $0.hasPrefix("http") ? $0 : "https://" + $0) }
        phone = r.ph
        license = r.lic
        inspection = r.inspection
        // the fish a fry serves is searchable too: "perch green bay"
        searchText = " " + Search.normalize([r.n, city, r.z, cuisine, brand, r.fish].compactMap { $0 }.joined(separator: " ")) + " " + Search.normalizeAddress(r.a ?? "") + " "
        nameText = " " + Search.normalize([r.n, brand].compactMap { $0 }.joined(separator: " ")) + " "
    }
}
