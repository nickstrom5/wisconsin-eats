import SwiftUI
import CoreSpotlight

@main
struct WisconsinEatsApp: App {
    @State private var model = AppModel()
    @State private var location = LocationService()

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
                .tint(Theme.green)
                .task {
                    await model.load()
                    ScreenshotMode.apply(to: model)
                    if model.isLoaded && !ScreenshotMode.isActive {
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
    }
}
