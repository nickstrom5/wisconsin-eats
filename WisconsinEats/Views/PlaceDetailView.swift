import SwiftUI
import MapKit

struct PlaceDetailView: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    let place: Place

    @State private var mapItem: MKMapItem?
    @State private var lookingUp = false
    @State private var notOnAppleMaps = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header
                actions
                if let c = place.coordinate { mapSnippet(c) }
                if !place.tags.isEmpty || place.note != nil { classics }
                if place.isHonored || place.founded != nil { honors }
                if let i = place.inspection { inspections(i) }
                listing
            }
            .padding(16)
        }
        .background(Theme.surface)
        .navigationTitle(place.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button { model.toggleSaved(place) } label: {
                    Label(model.isSaved(place) ? "Saved" : "Save", systemImage: model.isSaved(place) ? "heart.fill" : "heart")
                }
                ShareLink(item: shareText) { Label("Share", systemImage: "square.and.arrow.up") }
            }
        }
        .mapItemDetailSheet(item: $mapItem)
        .alert("Not on Apple Maps", isPresented: $notOnAppleMaps) {
            Button("Open Apple Maps anyway") { AppleMaps.openInMaps(place) }
            Button("OK", role: .cancel) {}
        } message: {
            Text("Apple Maps doesn't have a listing for \(place.name) at this spot, so there are no ratings or hours to show here.")
        }
    }

    // MARK: sections

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text((place.city ?? "Wisconsin").uppercased())
                .font(.caption.weight(.bold)).tracking(1.2).foregroundStyle(Theme.green2)
            Text(place.name.uppercased())
                .font(Theme.display(38)).foregroundStyle(Theme.green)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            Text([place.fullAddress, place.cuisine].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(.subheadline).foregroundStyle(Theme.ink2)
                .textSelection(.enabled)
            if let here = model.screenshotLocation ?? location.location, let l = place.location {
                Text("\(here.milesText(to: l)) away").font(.subheadline).foregroundStyle(Theme.muted)
            }
            PlaceChips(place: place)
        }
    }

    private var actions: some View {
        VStack(spacing: 10) {
            Button {
                lookingUp = true
                Task {
                    let item = await AppleMaps.findItem(for: place)
                    lookingUp = false
                    if let item { mapItem = item } else { notOnAppleMaps = true }
                }
            } label: {
                HStack {
                    if lookingUp { ProgressView().tint(Theme.green) } else { Image(systemName: "star.bubble") }
                    Text("Ratings, hours & photos").fontWeight(.semibold)
                    Spacer()
                    Text("Apple Maps").font(.caption).foregroundStyle(Theme.green2)
                }
                .padding(14)
                .foregroundStyle(Theme.green)
                .background(RoundedRectangle(cornerRadius: 12).fill(Theme.gold))
            }
            .disabled(place.coordinate == nil || lookingUp)
            .accessibilityHint("Opens the Apple Maps place card with current ratings and hours")

            HStack(spacing: 10) {
                actionButton("Directions", "arrow.triangle.turn.up.right.diamond") { AppleMaps.openInMaps(place, directions: true) }
                if let phone = place.phone, let url = URL(string: "tel:\(phone.filter { $0.isNumber || $0 == "+" })") {
                    actionButton("Call", "phone") { UIApplication.shared.open(url) }
                }
                if let web = place.website {
                    actionButton("Website", "safari") { UIApplication.shared.open(web) }
                }
            }
        }
    }

    private func actionButton(_ title: String, _ icon: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon).font(.title3)
                Text(title).font(.caption.weight(.semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 56)
            .foregroundStyle(Theme.green)
            .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.rule2))
        }
    }

    private func mapSnippet(_ c: CLLocationCoordinate2D) -> some View {
        Map(initialPosition: .region(MKCoordinateRegion(center: c, latitudinalMeters: 900, longitudinalMeters: 900)), interactionModes: []) {
            Marker(place.name, systemImage: place.tags.contains(.fishFry) ? "fish.fill" : "fork.knife", coordinate: c).tint(Theme.green)
        }
        .frame(height: 170)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .onTapGesture { AppleMaps.openInMaps(place) }
        .accessibilityLabel("Map of \(place.name). Opens Apple Maps.")
    }

    private var classics: some View {
        section("Wisconsin classics") {
            VStack(alignment: .leading, spacing: 8) {
                if place.tags.contains(.fishFry) {
                    fact("Fish fry", [place.fryDays.map { "Served " + $0 }, place.fish.map { "Fish: " + $0 }, place.sides.map { "With " + $0 }].compactMap { $0 }.joined(separator: ". ").nonEmpty ?? "Serves a Friday fish fry.")
                }
                if place.tags.contains(.supperClub) {
                    fact("Supper club", place.handChecked ? "Calls itself a supper club, or is widely known as one." : "Has \u{201C}supper club\u{201D} in its name in the map listing.")
                }
                if place.tags.contains(.custard) { fact("Frozen custard", place.handChecked ? "Serves frozen custard." : "Listed as a frozen custard stand in the map listing.") }
                if place.tags.contains(.fishBoil) { fact("Fish boil", "Door County-style fish boil.") }
                if let note = place.note { Text(note).font(.subheadline).foregroundStyle(Theme.ink2) }
                Text(place.handChecked
                     ? "Hand-checked in Sep 2026 against the place's own site, menu or recent news. Days and menus change, so check before you go."
                     : "Not hand-checked yet, so it isn't in our supper club or custard guides. Check before you go.")
                    .font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    private var honors: some View {
        section("Honors & history") {
            VStack(alignment: .leading, spacing: 8) {
                if let icon = place.iconText { Text(icon).font(.subheadline).foregroundStyle(Theme.ink2) }
                ForEach(lines(place.jamesBeard, prefix: "James Beard: ") + lines(place.otherHonors, prefix: ""), id: \.self) { l in
                    Label(l, systemImage: "rosette").font(.subheadline).foregroundStyle(Theme.ink)
                }
                if let f = place.founded { fact("Open since", "\(f) (verified)") }
            }
        }
    }

    private func inspections(_ i: InspectionRecord) -> some View {
        section("Health inspections · Dane County, since Jan 2023") {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 12) {
                    GradeBadge(grade: i.g, size: 46)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Score \(i.sc ?? 0)/100").font(.headline).foregroundStyle(Theme.ink)
                        Text("Our grade, on a curve, from Public Health Madison & Dane County results. Not an official grade.")
                            .font(.caption).foregroundStyle(Theme.muted)
                    }
                }
                kv("Routine inspections", i.n.map(String.init))
                kv("Needed a re-inspection", i.re.map(String.init))
                kv("Violations per visit", i.vp.map { String(format: "%.1f", $0) })
                kv("Foodborne-illness risk items per visit", i.rf.map { String(format: "%.1f", $0) })
                kv("Visits with a pest item", i.pe.map(String.init))
                kv("Repeat violations", i.rp.map(String.init))
                if let su = i.su, su > 0 { kv("Immediate suspensions", String(su)) }
                if let ld = i.ld { kv("Last routine visit", ld + ((i.lr ?? 0) == 1 ? " · re-inspection needed" : "")) }
            }
        }
    }

    private var listing: some View {
        section("How we know it's here") {
            VStack(alignment: .leading, spacing: 8) {
                kv("Listed as", place.tier.label)
                if place.tier == .licensed { kv("License list", place.jurisdiction.listName) }
                if let lic = place.license { kv("License number", lic) }
                if place.chainCount >= 2 { kv("Locations in Wisconsin", place.chainCount.formatted()) }
                Text(listingNote).font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    private var listingNote: String {
        let checked = place.handChecked
        if place.source == "research" {
            return "On our hand-checked list, confirmed open in Sep 2026. The open map data didn't list it as a place to eat, so it's placed from its own map listing or street address."
        }
        switch place.tier {
        case .licensed:
            return place.source == "official"
                ? "From the \(place.jurisdiction.listName) active license list. The open map data didn't have it, so its location comes from the license record or its street address."
                : "Matched to an active license on the \(place.jurisdiction.listName) list."
        case .confirmed, .listing:
            let rate = model.matchRate(for: place)
            let base = place.tier == .confirmed
                ? "A high-confidence listing in Overture's open map data."
                : "A single listing in Overture's open map data, so it may be closed or misfiled."
            let measured = rate.map { " Checked against Milwaukee's and Dane County's license lists, listings like this matched a licensed business \($0) of the time." } ?? ""
            return base + measured + (checked ? " It's also on our hand-checked list, confirmed open in Sep 2026." : "")
        }
    }

    // MARK: helpers

    private var shareText: String {
        [place.name, place.fullAddress, "via Wisconsin Eats · wisconsineats.com"].filter { !$0.isEmpty }.joined(separator: "\n")
    }

    private func lines(_ s: String?, prefix: String) -> [String] {
        (s ?? "").components(separatedBy: "; ").filter { !$0.isEmpty }.map { prefix + $0 }
    }

    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased()).font(.caption.weight(.bold)).tracking(1).foregroundStyle(Theme.muted)
            Divider()
            content()
        }
    }

    private func fact(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
            Text(value).font(.subheadline).foregroundStyle(Theme.ink2)
        }
    }

    @ViewBuilder
    private func kv(_ k: String, _ v: String?) -> some View {
        if let v {
            HStack(alignment: .firstTextBaseline) {
                Text(k).font(.subheadline).foregroundStyle(Theme.ink2)
                Spacer(minLength: 12)
                Text(v).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink).multilineTextAlignment(.trailing)
            }
        }
    }
}

extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
