import XCTest
import CoreLocation
@testable import WisconsinEats

@MainActor
final class WisconsinEatsTests: XCTestCase {

    /// A tiny data file with the same shape as Resources/places.json.
    private func sampleModel() async throws -> AppModel {
        let json = """
        {"v":1,"generated":"2026-09-26","cities":["Milwaukee","Madison","Fond du Lac","St. Germain","Green Bay"],"cuisines":["Bar & Pub","Frozen Custard","Supper Club","Seafood","Burgers"],
         "brands":["Culver's"],"tags":["supper","fishfry","curds","custard","boil"],"sources":["official","meta","AllThePlaces","DAC","research"],
         "count":8,"count_restaurants":7,
         "calibration":{"mke":{"meta_high":{"n":1126,"official":0.79},"meta_mid":{"n":269,"official":0.375}},"dane":{"meta_high":{"n":1119,"official":0.75},"meta_mid":{"n":192,"official":0.479}}},
         "places":[
          {"id":"a","n":"Kopp's Frozen Custard","c":0,"cu":1,"t":1,"s":1,"hc":1,"a":"7631 W Layton Ave","z":"53220","la":42.959,"lo":-88.008,"g":8,"f":1950},
          {"id":"b","n":"The Del-Bar","c":2,"cu":2,"t":1,"s":1,"hc":1,"a":"800 Wisconsin Dells Pkwy","la":43.61,"lo":-89.79,"g":3,"h":16,"ip":81,"icon":"Supper club since 1943.","f":1943},
          {"id":"c","n":"Culver's","c":0,"cu":4,"t":1,"s":2,"b":0,"ch":157,"la":43.05,"lo":-87.95,"g":8},
          {"id":"d","n":"Sobelman's Pub & Grill","c":0,"cu":0,"t":2,"s":0,"hc":1,"a":"1900 W St Paul Ave","la":43.035,"lo":-87.935,"j":1,"g":2,"fish":"cod, perch","days":"Friday"},
          {"id":"e","n":"Kwik Trip","c":1,"cu":4,"t":1,"s":1,"v":1,"la":43.07,"lo":-89.4},
          {"id":"f","n":"Thunderbird Bar & Grill","c":3,"cu":0,"t":0,"s":1,"a":"520 Hwy 70","la":45.91,"lo":-89.48},
          {"id":"h","n":"Lakeview Supper Club","c":1,"cu":2,"t":0,"s":1,"a":"1 Lake Rd","la":43.2,"lo":-89.2,"g":1},
          {"id":"g","n":"Stadium View Bar","c":4,"cu":0,"t":2,"s":0,"a":"1963 Holmgren Way","la":44.5,"lo":-88.06,"j":2,
           "in":{"g":"B","sc":70,"n":3,"re":0,"vp":2.0,"rf":0.5,"pe":0,"rp":1}}
         ]}
        """
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("places-test.json")
        try json.data(using: .utf8)!.write(to: url)
        let model = AppModel(defaults: UserDefaults(suiteName: "test-\(UUID().uuidString)")!)
        await model.load(from: url)
        XCTAssertTrue(model.isLoaded, model.loadError ?? "")
        return model
    }

    func testDecodesAndHidesNonRestaurantsByDefault() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.places.count, 8)
        let all = m.list(.all, sort: .name, search: "", here: nil)
        XCTAssertFalse(all.contains { $0.name == "Kwik Trip" }, "gas-station counters are hidden unless asked for")
        m.filters.includeNonRestaurants = true
        XCTAssertTrue(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Kwik Trip" })
    }

    func testGuides() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(Set(m.list(.fishFry, sort: .name, search: "", here: nil).map(\.id)), ["b", "d"])
        XCTAssertEqual(m.list(.supperClubs, sort: .name, search: "", here: nil).map(\.id), ["b"],
                       "a listing merely named \u{201C}supper club\u{201D} stays out of the checked guide")
        XCTAssertTrue(m.list(.all, sort: .name, search: "lakeview", here: nil).map(\.id) == ["h"], "but it's still in the directory")
        // custard stands, not the chains
        XCTAssertEqual(m.list(.custard, sort: .name, search: "", here: nil).map(\.id), ["a"])
        XCTAssertEqual(m.list(.oldest, sort: .oldest, search: "", here: nil).map(\.id), ["b", "a"])
        XCTAssertEqual(m.list(.nearMe, sort: .nearest, search: "", here: nil), [], "near me needs a location")
    }

    func testNearestSort() async throws {
        let m = try await sampleModel()
        let milwaukee = CLLocation(latitude: 43.0389, longitude: -87.9065)
        let near = m.list(.nearMe, sort: .nearest, search: "", here: milwaukee)
        XCTAssertEqual(near.first?.id, "d", "Sobelman's is closest to downtown Milwaukee")
        XCTAssertEqual(near.last?.id, "f", "St. Germain is farthest")
    }

    func testSearchWordStartsApostrophesAndStreets() async throws {
        let m = try await sampleModel()
        func ids(_ q: String) -> [String] { m.list(.all, sort: .name, search: q, here: nil).map(\.id) }
        XCTAssertEqual(ids("kopp"), ["a"])
        XCTAssertEqual(ids("kopps"), ["a"])
        XCTAssertTrue(ids("opp").isEmpty, "matches the start of words only")
        XCTAssertEqual(ids("st paul ave"), ["d"])
        XCTAssertEqual(ids("west layton avenue"), ["a"], "north/west/avenue match the abbreviated address")
        XCTAssertEqual(ids("saint germain"), ["f"])
        XCTAssertEqual(ids("st germain"), ["f"])
    }

    func testSearchTownsAndDishes() async throws {
        let m = try await sampleModel()
        func ids(_ q: String) -> [String] { m.list(.all, sort: .name, search: q, here: nil).map(\.id) }
        XCTAssertEqual(Set(ids("milwaukee fish fry")), ["d"])
        XCTAssertEqual(ids("perch milwaukee"), ["d"], "the fish a fry serves is searchable")
        XCTAssertEqual(Set(ids("fond du lac")), ["b"])
        XCTAssertEqual(Set(ids("supper club")), ["b", "h"], "the directory search finds supper clubs by name too")
        // "green bay" is a town, but "holmgren way" is a street
        XCTAssertEqual(ids("green bay"), ["g"])
        XCTAssertEqual(ids("holmgren way"), ["g"])
    }

    func testFiltersAndSavedPlaces() async throws {
        let m = try await sampleModel()
        m.filters.hideChains = true
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Culver's" })
        m.filters = Filters(confirmedOnly: true)
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.id == "f" }, "single listings drop out")
        m.filters = Filters(town: "Milwaukee")
        XCTAssertEqual(Set(m.list(.all, sort: .name, search: "", here: nil).map(\.id)), ["a", "c", "d"])
        let p = m.place(id: "b")!
        m.toggleSaved(p)
        XCTAssertEqual(m.savedPlaces.map(\.id), ["b"])
        m.toggleSaved(p)
        XCTAssertTrue(m.savedPlaces.isEmpty)
    }

    func testInspectionsAndMatchRates() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.list(.inspections, sort: .cleanest, search: "", here: nil).map(\.id), ["g"])
        XCTAssertEqual(m.matchRate(for: m.place(id: "a")!), "75–79%")
        XCTAssertNil(m.matchRate(for: m.place(id: "d")!), "licensed places don't cite a listing rate")
        XCTAssertEqual(m.place(id: "d")!.tier, .licensed)
    }

    /// The real bundled file decodes and holds the guides the app promises.
    func testBundledData() async throws {
        let m = AppModel(defaults: UserDefaults(suiteName: "bundle-\(UUID().uuidString)")!)
        await m.load()
        XCTAssertTrue(m.isLoaded, m.loadError ?? "")
        XCTAssertGreaterThan(m.restaurantCount, 10_000)
        XCTAssertGreaterThan(m.count(.supperClubs), 100)
        XCTAssertGreaterThan(m.count(.icons), 100)
        XCTAssertGreaterThan(m.count(.inspections), 500)
        XCTAssertEqual(Set(m.places.map(\.id)).count, m.places.count, "ids are unique")
        XCTAssertTrue(m.places.contains { $0.name == "Solly's Grille" && $0.jamesBeardLabel == "America's Classic" })
    }
}
