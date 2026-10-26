import SwiftUI
import CoreSpotlight

@main
struct WisconsinEatsApp: App {
    @Environment(\.scenePhase) private var scenePhase
    @State private var model = AppModel()
    @State private var location = LocationService()
    @State private var updater = DataUpdater()

    init() {
        // Large titles in the same compressed black type as the home header.
        let green = UIColor(Theme.green)
        UINavigationBar.appearance().largeTitleTextAttributes = [
            .font: UIFont.systemFont(ofSize: 36, weight: .black, width: .compressed), .foregroundColor: green,
        ]
        UINavigationBar.appearance().titleTextAttributes = [
            .font: UIFont.systemFont(ofSize: 19, weight: .heavy, width: .compressed), .foregroundColor: green,
        ]
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .environment(location)
                .environment(updater)
                .tint(Theme.green)
                .task {
                    await AppData.prepare()
                    await model.load()
                    ScreenshotMode.apply(to: model)
                    if model.isLoaded { updater.checkIfDue(placesInUse: model.places.count) }
                    if model.isLoaded && !ScreenshotMode.isActive {
                        // after the first screen is up: building ~600 index items shouldn't compete with launch
                        try? await Task.sleep(for: .seconds(3))
                        SpotlightIndexer.indexIfNeeded(model.places, generated: model.generated)
                    }
                }
                .onContinueUserActivity(CSSearchableItemActionType) { activity in
                    guard let id = activity.userInfo?[CSSearchableItemActivityIdentifier] as? String else { return }
                    Task {
                        await model.load()
                        if let p = model.place(id: id) { model.tab = .guides; model.selectedPlace = p; model.guidesPath = [.place(p)] }
                    }
                }
        }
        .onChange(of: scenePhase) { _, phase in updater.phaseChanged(to: phase, placesInUse: model.isLoaded ? model.places.count : nil) }
    }
}
