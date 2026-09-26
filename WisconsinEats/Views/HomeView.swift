import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    @State private var lastRandom: String?
    private let columns = [GridItem(.adaptive(minimum: 158), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                if isFriday { fridayCard }
                NavigationLink(value: AppModel.Route.guide(.all)) {
                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").foregroundStyle(Theme.green)
                        Text("Search by name, town or street").foregroundStyle(Theme.muted).lineLimit(1)
                        Spacer()
                    }
                    .font(.subheadline)
                    .padding(14)
                    .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.green, lineWidth: 2))
                }
                .accessibilityLabel("Search every restaurant")
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach([Guide.fishFry, .supperClubs, .custard, .icons, .oldest, .inspections, .nearMe, .all]) { g in
                        NavigationLink(value: AppModel.Route.guide(g)) { GuideCard(guide: g, count: model.count(g)) }
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
        .toolbar(.hidden, for: .navigationBar)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Rectangle().fill(Theme.gold).frame(width: 44, height: 5).clipShape(Capsule())
            Text("WISCONSIN\nEATS")
                .font(Theme.display(52))
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

    private var isFriday: Bool { Calendar.current.component(.weekday, from: .now) == 6 }

    private var fridayCard: some View {
        NavigationLink(value: AppModel.Route.guide(.fishFry)) {
            HStack(spacing: 12) {
                Image(systemName: "fish.fill").font(.title2).foregroundStyle(Theme.green)
                VStack(alignment: .leading, spacing: 2) {
                    Text("It's Friday").font(Theme.display(24)).foregroundStyle(Theme.green)
                    Text("Find a fish fry near you").font(.subheadline).foregroundStyle(Theme.ink)
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(Theme.green)
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
                Spacer()
                if guide != .nearMe {
                    Text(count.formatted()).font(Theme.display(22)).foregroundStyle(Theme.green).monospacedDigit()
                }
            }
            Text(guide.title).font(Theme.display(22, weight: .heavy)).foregroundStyle(Theme.ink).lineLimit(1).minimumScaleFactor(0.8)
            Text(guide.subtitle).font(.caption).foregroundStyle(Theme.muted).lineLimit(3).fixedSize(horizontal: false, vertical: true)
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
