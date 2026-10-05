import SwiftUI

struct AboutView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text("WISCONSIN EATS").displayFont(30).foregroundStyle(Theme.green)
                    Text("A free guide to \(model.restaurantCount.formatted()) Wisconsin restaurants, with hand-checked lists of Friday fish fries, supper clubs and custard stands. No account, no ads, no tracking.")
                        .font(.subheadline).foregroundStyle(Theme.ink2)
                    Text("Wisconsin Eats (\u{201C}WI Eats\u{201D}) is an independent app by Nicholas Soderstrom. It is not affiliated with, endorsed by or operated by the City of Milwaukee, Public Health Madison & Dane County, the James Beard Foundation, Apple, or any restaurant, team or chain.")
                        .font(.footnote).foregroundStyle(Theme.muted)
                }
                .padding(.vertical, 4)
            }
            Section("How the lists are built") {
                Text("Fish fries, supper clubs, custard stands and icons are hand-checked: each was checked in September 2026 against a 2025 or 2026 source (the place's own website or menu, local news, or its Travel Wisconsin listing), with the address checked.")
                Text("The rest come from Overture Maps' open place data, the City of Milwaukee's active food and tavern licenses, and Public Health Madison & Dane County's licensed establishments. Map listings are kept only when they proved reliable: checked against Milwaukee's and Dane County's license lists, high-confidence listings matched a licensed business \(rate("meta_high")) of the time. Website links are checked, and any that no longer belong to the place are left out.")
                Text("Inspection grades are ours, graded on a curve from Dane County's routine inspections since January 2023. They are our summary, not official grades, and other counties don't publish inspections in bulk.")
                Text("Ratings, reviews, hours and photos are Apple Maps' own, shown live in Apple's place card. This app doesn't store or rank by them.")
            }
            .font(.subheadline).foregroundStyle(Theme.ink2)
            Section("Sources") {
                source("Overture Maps Foundation", "Restaurant listings and websites outside the Milwaukee and Dane County license lists come from Overture Maps Foundation places data (overturemaps.org), release 2026-09-23.0, filtered and reformatted for this app.\n• Data from Meta, Microsoft, DAC and BrightQuery. Available under CDLA Permissive 2.0.\n• Data from Foursquare. Copyright 2024 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0. Foursquare data was transformed to the Overture schema; this app further filtered and reformatted it. See the NOTICE below.\n• Data from AllThePlaces. Available under CC0 1.0.", "https://overturemaps.org")
                source("City of Milwaukee Open Data", "Active food dealer and tavern licenses (data.milwaukee.gov), modified for use in this app. The City of Milwaukee makes no warranty as to the data's accuracy, completeness or timeliness and does not endorse this app.", "https://data.milwaukee.gov")
                source("Public Health Madison & Dane County", "Licensed establishments and routine inspection results, modified for use in this app. Public Health Madison & Dane County makes no warranty as to the data's accuracy, completeness or timeliness and does not endorse this app.", "https://www.publichealthmdc.com")
                source("Honors", "James Beard Foundation awards, finalists, semifinalists and America's Classics, and the other honors shown, are reported as facts and checked by hand against public announcements. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Other names belong to their owners.", "https://www.jamesbeard.org/awards/search-past-awards")
                source("Maps", "Maps, place cards and directions by Apple Maps.", nil)
            }
            Section("Licenses") {
                NavigationLink("Community Data License Agreement – Permissive 2.0") { LicenseText(file: "CDLA-Permissive-2.0", title: "CDLA Permissive 2.0") }
                NavigationLink("Apache License 2.0") { LicenseText(file: "Apache-2.0", title: "Apache License 2.0") }
                NavigationLink("Foursquare OS Places NOTICE") { LicenseText(file: "Foursquare-NOTICE", title: "Foursquare NOTICE") }
            }
            Section("Privacy") {
                Text("The app collects nothing. Your location, if you allow it, only sorts lists by distance and shows where you are on the map, on this device. Saved places stay on this device.")
                    .font(.subheadline).foregroundStyle(Theme.ink2)
                Link("Privacy policy", destination: Links.privacy)
                Link("Terms of use", destination: Links.terms)
            }
            Section("Help") {
                Link("Report a missing or closed place", destination: Links.correctionEmail)
                Link("Email \(Links.supportEmail)", destination: URL(string: "mailto:\(Links.supportEmail)")!)
                Link("Website: wisconsin.eatsranked.com", destination: Links.site)
                Text("Data as of \(model.generated). Places open and close; check before you go. Version \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0")")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
        }
        .navigationTitle("About")
        .tint(Theme.green)
    }

    private func rate(_ group: String) -> String {
        let v = ["mke", "dane"].compactMap { model.calibration[$0]?[group]?.official }
        guard let lo = v.min(), let hi = v.max() else { return "most" }
        let a = Int((lo * 100).rounded()), b = Int((hi * 100).rounded())
        return a == b ? "\(a)%" : "\(a)–\(b)%"
    }

    @ViewBuilder
    private func source(_ name: String, _ detail: String, _ url: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            if let url, let u = URL(string: url) { Link(name, destination: u).font(.subheadline.weight(.semibold)) }
            else { Text(name).font(.subheadline.weight(.semibold)) }
            Text(detail).font(.caption).foregroundStyle(Theme.muted)
        }
    }
}

/// A bundled license text (Resources/Licenses), reflowed rather than shown as raw 80-column lines.
struct LicenseText: View {
    let file: String
    let title: String

    var body: some View {
        ScrollView {
            Text(text).font(.footnote).foregroundStyle(Theme.ink).textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading).padding()
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }

    private var text: String {
        guard let url = Bundle.main.url(forResource: file, withExtension: "txt"),
              let raw = try? String(contentsOf: url, encoding: .utf8) else { return "License text missing." }
        // join hard-wrapped lines into paragraphs; keep blank lines and list items as breaks
        var out: [String] = []
        for para in raw.components(separatedBy: "\n\n") {
            let lines = para.components(separatedBy: "\n").map { $0.trimmingCharacters(in: .whitespaces) }
            var joined = ""
            for l in lines where !l.isEmpty {
                let startsItem = l.hasPrefix("–") || l.hasPrefix("-") || l.range(of: #"^\(?[a-z0-9]{1,3}[.)]\s"#, options: .regularExpression) != nil
                joined += joined.isEmpty ? l : (startsItem ? "\n" + l : " " + l)
            }
            if !joined.isEmpty { out.append(joined) }
        }
        return out.joined(separator: "\n\n")
    }
}
