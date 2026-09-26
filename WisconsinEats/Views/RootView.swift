import SwiftUI
import CoreLocation

struct RootView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        Group {
            if let error = model.loadError {
                ContentUnavailableView("Couldn't open the list", systemImage: "exclamationmark.triangle", description: Text(error))
            } else if !model.isLoaded {
                ProgressView("Loading Wisconsin's restaurants…").tint(Theme.green).foregroundStyle(Theme.muted)
            } else if sizeClass == .regular {
                SplitRoot()
            } else {
                TabRoot()
            }
        }
        .background(Theme.surface)
    }
}

/// iPhone: tabs, each with its own navigation stack.
struct TabRoot: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        TabView(selection: $model.tab) {
            NavigationStack(path: $model.guidesPath) {
                HomeView()
                    .navigationDestination(for: AppModel.Route.self) { route in
                        switch route {
                        case .guide(let g): GuideListView(guide: g)
                        case .place(let p): PlaceDetailView(place: p)
                        }
                    }
            }
                .tabItem { Label("Guides", systemImage: "list.bullet.rectangle") }.tag(AppModel.Tab.guides)
            NavigationStack { MapScreen() }
                .tabItem { Label("Map", systemImage: "map") }.tag(AppModel.Tab.map)
            NavigationStack { SavedView() }
                .tabItem { Label("Saved", systemImage: "heart") }.tag(AppModel.Tab.saved)
            NavigationStack { AboutView() }
                .tabItem { Label("About", systemImage: "info.circle") }.tag(AppModel.Tab.about)
        }
    }
}

/// iPad: guides in the sidebar, the list in the middle, the place on the right.
struct SplitRoot: View {
    @Environment(AppModel.self) private var model
    @State private var sidebar: SidebarItem? = .guide(.fishFry)
    // App Store shots show all three columns; people get the system default and the sidebar button
    @State private var columns: NavigationSplitViewVisibility = ScreenshotMode.isActive ? .all : .automatic

    enum SidebarItem: Hashable { case guide(Guide), map, saved, about }

    var body: some View {
        @Bindable var model = model
        NavigationSplitView(columnVisibility: $columns) {
            List(selection: $sidebar) {
                Section {
                    ForEach(Guide.allCases) { g in
                        Label(g.title, systemImage: g.systemImage).tag(SidebarItem.guide(g))
                    }
                } header: { Text("Guides") }
                Section {
                    Label("Map", systemImage: "map").tag(SidebarItem.map)
                    Label("Saved", systemImage: "heart").tag(SidebarItem.saved)
                    Label("About", systemImage: "info.circle").tag(SidebarItem.about)
                }
            }
            .navigationTitle("Wisconsin Eats")
        } content: {
            switch sidebar {
            case .guide(let g): GuideListView(guide: g, selection: $model.selectedPlace)
            case .map: MapScreen(selection: $model.selectedPlace)
            case .saved: SavedView(selection: $model.selectedPlace)
            case .about: AboutView()
            case nil: HomeView()
            }
        } detail: {
            if let p = model.selectedPlace {
                NavigationStack { PlaceDetailView(place: p) }.id(p.id)
            } else {
                ContentUnavailableView("Pick a place", systemImage: "fork.knife", description: Text("Choose a fish fry, supper club or restaurant to see its details."))
            }
        }
        .tint(Theme.green)
        .onAppear { show(model.tab); if ScreenshotMode.name == "home" { sidebar = nil } }
        .onChange(of: model.tab) { _, t in show(t) }
        .onChange(of: model.selectedGuide) { _, g in if let g { sidebar = .guide(g) } }
    }

    private func show(_ tab: AppModel.Tab) {
        switch tab {
        case .map: sidebar = .map
        case .saved: sidebar = .saved
        case .about: sidebar = .about
        case .guides: if let g = model.selectedGuide { sidebar = .guide(g) }
        }
    }
}
