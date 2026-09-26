import Foundation
import CoreLocation

/// The lists the app is built around. Each is a filter plus an order; none uses ratings (the app only publishes data it may).
enum Guide: String, CaseIterable, Identifiable, Hashable {
    case fishFry, supperClubs, custard, icons, oldest, inspections, nearMe, all

    var id: String { rawValue }

    var title: String {
        switch self {
        case .fishFry: "Friday Fish Fry"
        case .supperClubs: "Supper Clubs"
        case .custard: "Frozen Custard"
        case .icons: "Wisconsin Icons"
        case .oldest: "Oldest Places"
        case .inspections: "Inspections"
        case .nearMe: "Near Me"
        case .all: "All Restaurants"
        }
    }

    var subtitle: String {
        switch self {
        case .fishFry: "Hand-checked Friday fish fries, with the fish they serve"
        case .supperClubs: "Relish trays, old fashioneds and prime rib, statewide"
        case .custard: "Local custard stands, not the chains"
        case .icons: "James Beard honorees and long-running institutions"
        case .oldest: "Verified founding years, oldest first"
        case .inspections: "Dane County health inspections, cleanest and worst"
        case .nearMe: "Everything around you, closest first"
        case .all: "Every restaurant, café, tavern and bakery"
        }
    }

    var systemImage: String {
        switch self {
        case .fishFry: "fish"
        case .supperClubs: "wineglass"
        case .custard: "birthday.cake"
        case .icons: "star.circle"
        case .oldest: "clock.arrow.circlepath"
        case .inspections: "checkmark.seal"
        case .nearMe: "location"
        case .all: "fork.knife"
        }
    }

    /// Guides whose order is a ranking worth numbering.
    var isRanked: Bool { [.icons, .oldest, .inspections].contains(self) }

    var sortOptions: [SortOrder] {
        switch self {
        case .fishFry, .supperClubs, .custard: [.featured, .nearest, .oldest, .name]
        case .icons: [.iconic, .oldest, .nearest]
        case .oldest: [.oldest]
        case .inspections: [.cleanest, .worst]
        case .nearMe: [.nearest]
        case .all: [.name, .nearest]
        }
    }

    var defaultSort: SortOrder { sortOptions[0] }

    func includes(_ p: Place) -> Bool {
        switch self {
        // the Wisconsin guides promise "checked open", so only hand-checked places; a map listing named "… Supper Club" isn't enough
        case .fishFry: p.handChecked && p.tags.contains(.fishFry)
        case .supperClubs: p.handChecked && p.tags.contains(.supperClub)
        case .custard: p.handChecked && p.tags.contains(.custard) && !p.isChain       // Culver's and Freddy's have their own apps
        case .icons: p.iconicPoints != nil
        case .oldest: p.founded != nil
        case .inspections: (p.inspection?.n ?? 0) >= 2
        case .nearMe, .all: true
        }
    }
}

enum SortOrder: String, CaseIterable, Identifiable {
    case featured, nearest, oldest, name, iconic, cleanest, worst
    var id: String { rawValue }
    var label: String {
        switch self {
        case .featured: "Featured first"
        case .nearest: "Nearest"
        case .oldest: "Oldest first"
        case .name: "A to Z"
        case .iconic: "Most iconic"
        case .cleanest: "Cleanest"
        case .worst: "Worst inspections"
        }
    }
}

/// Filters shared by every list. Search text lives with each list.
struct Filters: Equatable, Codable {
    var town: String?
    var cuisine: String?
    var hideChains = false
    var confirmedOnly = false
    var includeNonRestaurants = false

    var activeCount: Int {
        [town != nil, cuisine != nil, hideChains, confirmedOnly, includeNonRestaurants].filter { $0 }.count
    }

    func allows(_ p: Place) -> Bool {
        if !includeNonRestaurants && p.isVenue { return false }
        if let town, p.city != town { return false }
        if let cuisine, p.cuisine != cuisine { return false }
        if hideChains && p.isChain { return false }
        if confirmedOnly && p.tier == .listing { return false }
        return true
    }
}

enum Ranking {
    static func sort(_ places: [Place], by order: SortOrder, from here: CLLocation?) -> [Place] {
        func name(_ a: Place, _ b: Place) -> Bool { a.name.localizedCaseInsensitiveCompare(b.name) == .orderedAscending }
        func dist(_ p: Place) -> Double { (here != nil ? p.location?.distance(from: here!) : nil) ?? .greatestFiniteMagnitude }
        switch order {
        case .nearest where here != nil:
            return places.sorted { dist($0) != dist($1) ? dist($0) < dist($1) : name($0, $1) }
        case .featured, .nearest:
            // honored places first, then verified founding year, then name
            return places.sorted {
                let a = $0.iconicPoints ?? -1, b = $1.iconicPoints ?? -1
                if a != b { return a > b }
                let fa = $0.founded ?? 9999, fb = $1.founded ?? 9999
                return fa != fb ? fa < fb : name($0, $1)
            }
        case .oldest:
            return places.sorted { ($0.founded ?? 9999, $0.name) < ($1.founded ?? 9999, $1.name) }
        case .name:
            return places.sorted(by: name)
        case .iconic:
            return places.sorted { ($0.iconicPoints ?? -1) != ($1.iconicPoints ?? -1) ? ($0.iconicPoints ?? -1) > ($1.iconicPoints ?? -1) : name($0, $1) }
        case .cleanest, .worst:
            let sign: Int = order == .cleanest ? -1 : 1
            return places.sorted {
                let a = $0.inspection?.sc ?? 50, b = $1.inspection?.sc ?? 50
                if a != b { return sign < 0 ? a > b : a < b }
                let ra = $0.inspection?.re ?? 0, rb = $1.inspection?.re ?? 0
                if ra != rb { return sign < 0 ? ra < rb : ra > rb }
                return name($0, $1)
            }
        }
    }
}
