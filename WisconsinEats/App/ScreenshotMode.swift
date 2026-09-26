import Foundation
import CoreLocation
import UIKit

/// `-screenshot <name>` opens one screen with fixed state for App Store screenshots (scripts/capture-screenshots.sh).
/// Names: home, fishfry, supper, detail, map, inspections, icons, saved, about.
enum ScreenshotMode {
    static var name: String? {
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screenshot"), i + 1 < args.count else { return nil }
        return args[i + 1]
    }
    static var isActive: Bool { name != nil }

    @MainActor
    static func apply(to model: AppModel) {
        guard let name, model.isLoaded else { return }
        model.filters = Filters()
        // downtown Milwaukee, so "nearest" lists have distances without a permission prompt
        model.screenshotLocation = CLLocation(latitude: 43.0389, longitude: -87.9065)
        let pick = { (n: String) in model.places.first { $0.name == n } }
        for n in ["The Del-Bar", "Kopp's Frozen Custard", "Solly's Grille", "Three Brothers"] {
            if let p = pick(n), !model.isSaved(p) { model.toggleSaved(p) }
        }
        let open = { (g: Guide) in model.tab = .guides; model.selectedGuide = g; model.guidesPath = [.guide(g)] }
        switch name {
        case "fishfry": open(.fishFry)
        case "supper": open(.supperClubs)
        case "icons": open(.icons)
        case "inspections": open(.inspections)
        case "detail":
            open(.supperClubs)
            if let p = pick("The Del-Bar") ?? model.places.first { model.selectedPlace = p; model.guidesPath.append(.place(p)) }
        case "map": model.tab = .map
        case "saved": model.tab = .saved
        case "about": model.tab = .about
        default: model.tab = .guides; model.selectedGuide = nil
        }
        // iPad shows the place column next to every list, so give each shot a place instead of "Pick a place".
        guard UIDevice.current.userInterfaceIdiom == .pad, model.selectedPlace == nil else { return }
        let place: Place? = switch name {
        case "supper": pick("Five O'Clock Steakhouse")
        case "icons": pick("Solly's Grille")
        case "saved": pick("Kopp's Frozen Custard")
        case "inspections": model.list(.inspections, sort: .cleanest, search: "", here: nil).first
        case "about": nil
        case "map": pick("The Del-Bar")
        default: pick("Lakefront Brewery") ?? pick("The Del-Bar")
        }
        model.selectedPlace = place
    }
}
