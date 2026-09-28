import Foundation

/// The app's web pages and support address, in one place.
/// The site is GitHub Pages at the project address. When a domain is added later (a state subdomain such as
/// wisconsin.<hub domain>), GitHub forwards these github.io links to it, so shipped builds keep working.
enum Links {
    static let site = URL(string: "https://nickstrom5.github.io/wisconsin-eats/")!
    static let privacy = URL(string: "https://nickstrom5.github.io/wisconsin-eats/privacy.html")!
    static let terms = URL(string: "https://nickstrom5.github.io/wisconsin-eats/terms.html")!
    static let supportEmail = "work-with-nick@gmail.com"

    static var correctionEmail: URL {
        URL(string: "mailto:\(supportEmail)?subject=Wisconsin%20Eats%20correction")!
    }
}
