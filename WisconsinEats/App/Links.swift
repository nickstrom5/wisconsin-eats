import Foundation

/// The app's web pages and support address, in one place.
/// The site is GitHub Pages at wisconsin.eatsranked.com (builds 1–2 used the github.io address, which GitHub forwards here).
enum Links {
    static let site = URL(string: "https://wisconsin.eatsranked.com/")!
    static let privacy = URL(string: "https://wisconsin.eatsranked.com/privacy.html")!
    static let terms = URL(string: "https://wisconsin.eatsranked.com/terms.html")!
    static let supportEmail = "nick@eatsranked.com"   // one contact for every Eats Ranked state (Nick, 2026-10-12)

    static var correctionEmail: URL {
        URL(string: "mailto:\(supportEmail)?subject=Wisconsin%20Eats%20correction")!
    }
}
