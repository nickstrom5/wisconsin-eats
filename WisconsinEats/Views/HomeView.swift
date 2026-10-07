import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    /// iPad's split view: keep the navigation bar, because in portrait it holds the only sidebar button.
    /// (The size class can't tell: a split-view column reports compact.)
    var inSplitView = false
    @State private var lastRandom: String?
    private let columns = [GridItem(.adaptive(minimum: 158), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                if isFriday { fridayCard }
                Button { model.openGuide(.all) } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").foregroundStyle(Theme.green)
                        Text("Search by name, town or street").foregroundStyle(Theme.muted)
                        Spacer()
                    }
                    .font(.subheadline)
                    .padding(14)
                    .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.green, lineWidth: 2))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Search every restaurant")
                if model.filters.activeCount > 0 { filtersOn }
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach([Guide.fishFry, .supperClubs, .custard, .icons, .oldest, .inspections, .nearMe, .all]) { g in
                        Button { model.openGuide(g) } label: { GuideCard(guide: g, count: model.count(g)) }
                            .buttonStyle(.plain)
                    }
                }
                surpriseButton
                Text("Ratings, hours and photos come live from Apple Maps on each place. Lists are built from open map data, Milwaukee and Dane County license records and hand-checked research. See About for sources.")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
            .padding(16)
        }
        .background(Theme.surface)
        .navigationTitle("")
        // iPhone: the big header is the title, so no bar
        .toolbar(inSplitView ? .automatic : .hidden, for: .navigationBar)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Rectangle().fill(Theme.gold).frame(width: 44, height: 5).clipShape(Capsule())
            Text("WISCONSIN\nEATS")
                .displayFont(52)
                .foregroundStyle(Theme.green)
                .lineSpacing(-6)
                .accessibilityAddTraits(.isHeader)
            Text("Fish fry & supper club guide")
                .font(.headline).foregroundStyle(Theme.ink)
            Text("Every Friday fish fry, supper club and custard stand we could verify, plus \(model.restaurantCount.formatted()) restaurants in \(model.towns.count.formatted()) towns.")
                .font(.subheadline).foregroundStyle(Theme.ink2)
        }
        .padding(.top, 8)
    }

    /// Filters stick between launches, so say so here: a forgotten town filter made the counts look nearly empty.
    private var filtersOn: some View {
        HStack(spacing: 10) {
            Image(systemName: "line.3.horizontal.decrease.circle.fill").foregroundStyle(Theme.green).accessibilityHidden(true)
            Text(model.filters.activeCount == 1 ? "A filter is on, so the counts below are filtered." : "\(model.filters.activeCount) filters are on, so the counts below are filtered.")
                .font(.footnote).foregroundStyle(Theme.ink2)
            Spacer(minLength: 4)
            Button("Clear") { model.filters = Filters() }.font(.footnote.weight(.semibold))
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 12).fill(Theme.surface2))
    }

    private var isFriday: Bool { Calendar.current.component(.weekday, from: .now) == 6 }

    private var fridayCard: some View {
        Button { model.openGuide(.fishFry) } label: {
            HStack(spacing: 12) {
                Image(systemName: "fish.fill").font(.title2).foregroundStyle(Theme.green).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("It's Friday").displayFont(24).foregroundStyle(Theme.green)
                    Text("Find a fish fry near you").font(.subheadline).foregroundStyle(Theme.ink)
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(Theme.green).accessibilityHidden(true)
            }
            .padding(14)
            .background(RoundedRectangle(cornerRadius: 14).fill(Theme.gold))
        }
        .buttonStyle(.plain)
    }

    private var surpriseButton: some View {
        Button {
            if let p = model.randomPick(from: .supperClubs, excluding: lastRandom) {
                lastRandom = p.id
                model.guidesPath.append(.place(p))
                model.selectedPlace = p
            }
        } label: {
            Label("Surprise me with a supper club", systemImage: "dice")
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity).padding(12)
                .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.rule2))
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.ink)
    }
}

struct GuideCard: View {
    let guide: Guide
    let count: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: guide.systemImage).font(.title3).foregroundStyle(Theme.green)
                    .frame(width: 36, height: 36).background(Circle().fill(isWisconsin ? Theme.goldSoft : Theme.surface2))
                    .accessibilityHidden(true)
                Spacer()
                if guide != .nearMe && guide != .all {   // "All" would just repeat the total in the header
                    // text styles, not displayFont: cards must scale all the way with Dynamic Type
                    Text(count.formatted()).font(.title3.weight(.black).width(.compressed)).foregroundStyle(Theme.green).monospacedDigit()
                }
            }
            Text(guide.title).font(.title3.weight(.heavy).width(.compressed)).foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)   // wraps at large text sizes instead of shrinking
            Text(guide.subtitle).font(.caption).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 150, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.surface))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(isWisconsin ? Color(hex: 0xD9A21A) : Theme.rule))
        .accessibilityElement(children: .combine)
        .accessibilityHint(guide == .nearMe ? "" : "\(count) places")
    }

    private var isWisconsin: Bool { [.fishFry, .supperClubs, .custard].contains(guide) }
}
