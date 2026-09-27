import XCTest

/// Taps through every screen and control a reviewer is likely to touch, on iPhone (tabs) and iPad (split view).
/// Pass = nothing crashes and each screen shows what it should. Slow (network place cards, map tiles), so CI runs
/// only the unit tests; run this before every App Store submission:
/// xcodebuild test -scheme WisconsinEats -only-testing:WisconsinEatsUITests -destination 'id=<sim>'
final class SmokeUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        // the location prompt can appear on Near Me or the Nearest sort; answer it like a first-time user would
        addUIInterruptionMonitor(withDescription: "Location") { alert in
            for b in ["Allow While Using App", "Allow Once", "Don’t Allow", "Don't Allow"] where alert.buttons[b].exists {
                alert.buttons[b].tap(); return true
            }
            return false
        }
        app.launch()
    }

    private func button(containing text: String) -> XCUIElement {
        app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", text)).firstMatch
    }

    private func text(containing text: String) -> XCUIElement {
        app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", text)).firstMatch
    }

    private func waitFor(_ e: XCUIElement, _ seconds: TimeInterval = 10, _ what: String) {
        XCTAssertTrue(e.waitForExistence(timeout: seconds), "missing: \(what)")
    }

    private func scrollTo(_ e: XCUIElement, max: Int = 8) {
        var n = 0
        while !e.isHittable && n < max { app.swipeUp(); n += 1 }
    }

    private var isPad: Bool { UIDevice.current.userInterfaceIdiom == .pad }

    /// Place detail: Apple Maps card (or the "not on Apple Maps" fallback), save, share.
    private func exerciseDetail(named name: String) {
        waitFor(text(containing: name), 10, "detail for \(name)")
        let card = button(containing: "Ratings, hours")
        waitFor(card, 5, "Apple Maps button")
        card.tap()
        // either Apple's place card sheet or our fallback alert
        let fallback = app.alerts["Not on Apple Maps"]
        let deadline = Date().addingTimeInterval(15)
        var opened = false
        while Date() < deadline && !opened {
            if fallback.exists { fallback.buttons["OK"].tap(); opened = true; break }
            let close = app.buttons.matching(NSPredicate(format: "label ==[c] 'Close' OR identifier ==[c] 'Close'")).firstMatch
            if close.exists && close.isHittable { close.tap(); opened = true; break }
            Thread.sleep(forTimeInterval: 0.5)
        }
        if !opened { app.swipeDown(velocity: .fast) }   // dismiss the sheet if its close button isn't labelled
        XCTAssertEqual(app.state, .runningForeground)
        let save = app.buttons["Save"]
        if save.waitForExistence(timeout: 3) {
            save.tap()
            // on iPad Apple's card is a centered sheet that a tap outside dismisses; that first tap may only close it
            if !app.buttons["Saved"].waitForExistence(timeout: 2) && app.buttons["Save"].exists { app.buttons["Save"].tap() }
            waitFor(app.buttons["Saved"], 3, "heart turns to Saved")
        }
        let share = app.buttons["Share"]
        if share.exists {
            share.tap()
            Thread.sleep(forTimeInterval: 1.5)
            let close = app.buttons.matching(NSPredicate(format: "label ==[c] 'Close' OR label ==[c] 'Cancel'")).firstMatch
            if close.exists { close.tap() } else { app.swipeDown(velocity: .fast) }
        }
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// A clean start for each section, so one screen's navigation state can't strand the next (also proves saved places persist).
    private func fresh() {
        app.terminate()
        app.launch()
        waitFor(text(containing: "Fish fry & supper club guide"), 15, "home header")
    }

    func testTourEveryScreen() throws {
        if isPad { try padTour(); return }
        waitFor(text(containing: "Fish fry & supper club guide"), 15, "home header")

        // Friday Fish Fry: sort, filters, search
        button(containing: "Friday Fish Fry").tap()
        waitFor(app.navigationBars["Friday Fish Fry"], 5, "fish fry list")
        waitFor(text(containing: "places ·"), 5, "list count header")
        app.buttons["Sort"].tap()
        waitFor(app.buttons["Oldest first"], 3, "sort menu"); app.buttons["Oldest first"].tap()
        waitFor(text(containing: "Oldest first"), 3, "sorted header")
        app.buttons["Filters"].tap()
        waitFor(app.navigationBars["Filters"], 3, "filters sheet")
        // tap the switch itself (its right edge); a tap on the middle of a Toggle row lands on the label
        let hide = app.switches.matching(NSPredicate(format: "label CONTAINS 'Hide chains'")).firstMatch
        waitFor(hide, 3, "hide-chains toggle")
        hide.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        XCTAssertEqual(hide.value as? String, "1", "toggle switched on")
        app.buttons["Done"].tap()
        waitFor(text(containing: "1 filter on"), 3, "active-filter row")
        button(containing: "Clear").tap()
        XCTAssertFalse(text(containing: "filter on").waitForExistence(timeout: 1), "filters cleared")
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown() }
        waitFor(search, 3, "search field"); search.tap(); search.typeText("perch")
        waitFor(text(containing: "places ·"), 3, "search results header")

        // the full directory → a known place → Apple Maps card, save, share
        fresh()
        button(containing: "Search every restaurant").tap()
        let search2 = app.searchFields.firstMatch
        waitFor(search2, 5, "directory search"); search2.tap(); search2.typeText("del-bar")
        let delbar = button(containing: "The Del-Bar")
        waitFor(delbar, 5, "Del-Bar in results"); delbar.tap()
        exerciseDetail(named: "THE DEL-BAR")

        // every other guide opens with a list
        for g in ["Supper Clubs", "Frozen Custard", "Wisconsin Icons", "Oldest Places", "Inspections", "Near Me", "All Restaurants"] {
            fresh()
            let card = button(containing: g)
            scrollTo(card)
            card.tap()
            if g == "Near Me" { app.swipeDown() }   // any interaction lets the monitor answer the location prompt (a tap could open a row)
            waitFor(app.navigationBars[g], 5, "\(g) list")
            if g != "Near Me" { waitFor(text(containing: "places ·"), 5, "\(g) count header") }
        }

        // surprise me
        fresh()
        let surprise = button(containing: "Surprise me")
        scrollTo(surprise); surprise.tap()
        waitFor(button(containing: "Ratings, hours"), 5, "a random supper club")

        // Map: every layer
        fresh()
        app.tabBars.buttons["Map"].tap()
        for l in ["Supper clubs", "Custard", "Icons", "Everything", "Fish fry"] {
            let chip = app.buttons[l]
            waitFor(chip, 5, "map layer \(l)")
            if !chip.isHittable { app.scrollViews.firstMatch.swipeLeft() }
            if !chip.isHittable { app.scrollViews.firstMatch.swipeRight(); app.scrollViews.firstMatch.swipeRight() }
            chip.tap()
            // statewide, Everything asks you to zoom in instead of drawing 16,000 pins
            waitFor(text(containing: l == "Everything" ? "Zoom in to a town" : "tap a pin"), 5, "map hint for \(l)")
        }

        // Saved: the Del-Bar saved earlier survived relaunches; remove it
        app.tabBars.buttons["Saved"].tap()
        let saved = button(containing: "The Del-Bar")
        waitFor(saved, 5, "saved place")
        saved.swipeLeft()
        if app.buttons["Remove"].waitForExistence(timeout: 2) { app.buttons["Remove"].tap() }

        // About
        app.tabBars.buttons["About"].tap()
        waitFor(text(containing: "WISCONSIN EATS"), 5, "about header")
        let privacy = app.buttons["Privacy policy"].exists ? app.buttons["Privacy policy"] : app.links["Privacy policy"]
        scrollTo(privacy)
        XCTAssertTrue(privacy.exists, "privacy link")
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// iPad sidebar row. The rows themselves carry no label; the name is a text inside the "Sidebar" list.
    private func sidebarItem(_ name: String) -> XCUIElement {
        app.collectionViews["Sidebar"].staticTexts[name]
    }

    private func padTour() throws {
        // the list must be visible at launch, in portrait, without touching the sidebar button
        waitFor(text(containing: "places ·"), 15, "a list at launch in portrait")
        XCUIDevice.shared.orientation = .landscapeLeft     // all three columns
        Thread.sleep(forTimeInterval: 1.5)
        for g in ["Supper Clubs", "Frozen Custard", "Wisconsin Icons", "Inspections", "Oldest Places", "All Restaurants", "Friday Fish Fry"] {
            let item = sidebarItem(g)
            waitFor(item, 5, "sidebar \(g)"); item.tap()
            waitFor(app.navigationBars[g], 5, "\(g) list")
        }
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown() }
        waitFor(search, 5, "search"); search.tap(); search.typeText("lakefront")
        let row = button(containing: "Lakefront Brewery")
        waitFor(row, 5, "Lakefront in results"); row.tap()
        exerciseDetail(named: "LAKEFRONT BREWERY")
        for s in ["Map", "Saved", "About"] {
            let item = sidebarItem(s)
            waitFor(item, 5, "sidebar \(s)"); item.tap()
        }
        waitFor(text(containing: "WISCONSIN EATS"), 5, "about header")
        XCUIDevice.shared.orientation = .portrait
        Thread.sleep(forTimeInterval: 1.5)
        XCTAssertEqual(app.state, .runningForeground)
    }

    func testEverythingLayerFillsInWhenZoomed() {
        if isPad {
            XCUIDevice.shared.orientation = .landscapeLeft
            waitFor(sidebarItem("Map"), 15, "sidebar Map"); sidebarItem("Map").tap()
        } else {
            waitFor(text(containing: "Fish fry & supper club guide"), 15, "home header")
            app.tabBars.buttons["Map"].tap()
        }
        let chip = app.buttons["Everything"]
        waitFor(chip, 5, "Everything chip")
        if !chip.isHittable { app.scrollViews.firstMatch.swipeLeft() }
        chip.tap()
        waitFor(text(containing: "Zoom in to a town"), 5, "zoom hint statewide")
        let map = app.maps.firstMatch
        for _ in 0..<6 { map.doubleTap(); Thread.sleep(forTimeInterval: 0.8) }
        waitFor(text(containing: "places here"), 10, "restaurants appear once zoomed in")
        XCTAssertEqual(app.state, .runningForeground)
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// "My location" moves the map to you at town level, which also fills in the Everything layer.
    func testMyLocationCentersTheMap() {
        if isPad {
            XCUIDevice.shared.orientation = .landscapeLeft
            waitFor(sidebarItem("Map"), 15, "sidebar Map"); sidebarItem("Map").tap()
        } else {
            waitFor(text(containing: "Fish fry & supper club guide"), 15, "home header")
            app.tabBars.buttons["Map"].tap()
        }
        let chip = app.buttons["Everything"]
        waitFor(chip, 5, "Everything chip")
        if !chip.isHittable { app.scrollViews.firstMatch.swipeLeft() }
        chip.tap()
        waitFor(text(containing: "Zoom in to a town"), 5, "zoom hint statewide")
        app.buttons["My location"].tap()
        chip.tap()    // an interaction, so the monitor can answer the permission prompt if it appears
        waitFor(text(containing: "places here"), 15, "map moved to the simulated location and filled in")
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    func testLaunchIsQuick() {
        // the 3.8 MB bundle decodes off the main thread; the home screen should be up well within a few seconds
        app.terminate()
        let start = Date()
        app.launch()
        let ready = isPad ? app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'places ·' OR label CONTAINS 'Fish fry & supper club guide'")).firstMatch
                          : text(containing: "Fish fry & supper club guide")
        XCTAssertTrue(ready.waitForExistence(timeout: 8), "home didn't appear")
        let secs = Date().timeIntervalSince(start)
        print("launch to home: \(String(format: "%.2f", secs)) s")
        XCTAssertLessThan(secs, 6)
    }
}
