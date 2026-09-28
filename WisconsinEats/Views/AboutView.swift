import SwiftUI

struct AboutView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text("WISCONSIN EATS").font(Theme.display(30)).foregroundStyle(Theme.green)
                    Text("A free guide to every restaurant in Wisconsin, with hand-checked lists of Friday fish fries, supper clubs and custard stands. No account, no ads, no tracking.")
                        .font(.subheadline).foregroundStyle(Theme.ink2)
                }
                .padding(.vertical, 4)
            }
            Section("How the lists are built") {
                Text("Fish fries, supper clubs, custard stands and icons are hand-checked: each was confirmed open in September 2026 on its own website, menu or recent news, with the address checked.")
                Text("Everything else comes from Overture Maps' open place data, the City of Milwaukee's active food and tavern licenses, and Public Health Madison & Dane County's licensed establishments. Map listings are kept only when they proved reliable: checked against Milwaukee's and Dane County's license lists, high-confidence listings matched a licensed business \(rate("meta_high")) of the time.")
                Text("Inspection grades are ours, graded on a curve from Dane County's routine inspections since January 2023. They're not official grades, and other counties don't publish inspections in bulk.")
                Text("Ratings, reviews, hours and photos are Apple Maps' own, shown live in Apple's place card. This app doesn't store or rank by them.")
            }
            .font(.subheadline).foregroundStyle(Theme.ink2)
            Section("Sources and licenses") {
                source("Overture Maps Foundation", "Places (CDLA Permissive 2.0), boundaries and water (ODbL). © OpenStreetMap contributors, Overture Maps Foundation.", "https://overturemaps.org")
                source("City of Milwaukee Open Data", "Active food dealer and tavern licenses.", "https://data.milwaukee.gov")
                source("Public Health Madison & Dane County", "Licensed establishments, inspections and violation records.", "https://www.publichealthmdc.com")
                source("James Beard Foundation", "Award, finalist and semifinalist history.", "https://www.jamesbeard.org/awards/search-past-awards")
                source("Apple Maps", "Live ratings, hours and photos in each place card.", nil)
            }
            Section("Privacy") {
                Text("The app collects nothing. Your location, if you allow it, only sorts lists by distance on this device. Saved places stay on this device.")
                    .font(.subheadline).foregroundStyle(Theme.ink2)
                Link("Privacy policy", destination: Links.privacy)
                Link("Terms", destination: Links.terms)
            }
            Section {
                Text("Not affiliated with any team, restaurant, chain or government agency. Data as of \(model.generated). Places open and close; check before you go.")
                    .font(.footnote).foregroundStyle(Theme.muted)
                Link("Report a missing or closed place", destination: Links.correctionEmail)
                Text("Version \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0")").font(.footnote).foregroundStyle(Theme.muted)
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
