import Foundation

/// The app's web pages and support address, in one place.
/// The site is GitHub Pages at wisconsin.eatsranked.com (builds 1–2 used the github.io address, which GitHub forwards here).
enum Links {
    static let site = URL(string: "https://wisconsin.eatsranked.com/")!
    static let privacy = URL(string: "https://wisconsin.eatsranked.com/privacy.html")!
    static let terms = URL(string: "https://wisconsin.eatsranked.com/terms.html")!
    /// The app's data updates: scripts/publish_app_data.py writes docs/data/app/ (OTA-DATA.md).
    static let appData = URL(string: site.absoluteString + "data/app/")!
    static let supportEmail = "nick@eatsranked.com"   // one contact for every Eats Ranked state (Nick, 2026-10-12)

    static var correctionEmail: URL {
        URL(string: "mailto:\(supportEmail)?subject=Wisconsin%20Eats%20correction")!
    }

    // MARK: Share

    /// The web app. It opens a place's panel from the hash, explore/#p=<id> (readHash in scripts/explore.js), using the app's ids.
    static let explore = URL(string: site.absoluteString + "explore/")!

    /// What Share sends: the place's own page in the web app, never an Apple Maps or Google link (Apple Maps has its own button).
    /// The id is escaped the way the page's encodeURIComponent would escape it. A place the web app leaves out
    /// gets the web app's front page instead of a link that opens nothing.
    static func share(_ place: Place) -> URL {
        guard onWeb(place), let id = place.id.addingPercentEncoding(withAllowedCharacters: uriComponent),
              let url = URL(string: explore.absoluteString + "#p=" + id) else { return explore }
        return url
    }

    /// The text that goes with the link: the place, its town and the app. No street address, which Messages turns into a Maps link.
    static func shareMessage(_ place: Place) -> String {
        [place.name, place.city ?? ""].filter { !$0.isEmpty }.joined(separator: ", ") + ", on Wisconsin Eats"
    }

    /// Whether the web app lists the place: make-site.py's rows_web (restaurants, plus the venues that are hand-checked icons).
    static func onWeb(_ place: Place) -> Bool { !place.isVenue || (place.iconicPoints != nil && place.handChecked) }

    /// What encodeURIComponent leaves as is.
    private static let uriComponent = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.!~*'()")
}
