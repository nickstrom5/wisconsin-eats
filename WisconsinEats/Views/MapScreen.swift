import SwiftUI
import MapKit

struct MapScreen: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    var selection: Binding<Place?>? = nil

    @State private var layer: Layer = .fishFry
    @State private var pushed: Place?
    @State private var region: MKCoordinateRegion?
    /// "My location": where to move the map (a new object each tap, so a second tap re-centers after panning away)
    @State private var centerOn: CLLocation?
    @State private var centerWhenFound = false
    @State private var notice: String?
    @State private var askSettings = false
    /// places at the same spot (a food hall, a shared building) that clustering can never pull apart
    @State private var stacked: [Place] = []

    /// All 16,000+ restaurants at once kept the map busy for a minute and more in QA, so the Everything layer fills in
    /// only once you zoom to about town size (this many degrees of latitude on screen), and only for what's in view.
    private static let everythingSpan = 0.3

    enum Layer: String, CaseIterable, Identifiable {
        case fishFry = "Fish fry", supper = "Supper clubs", custard = "Custard", icons = "Icons", all = "Everything"
        var id: String { rawValue }
        var guide: Guide {
            switch self {
            case .fishFry: .fishFry
            case .supper: .supperClubs
            case .custard: .custard
            case .icons: .icons
            case .all: .all
            }
        }
    }

    var body: some View {
        let layerPlaces = model.places.filter { layer.guide.includes($0) && model.filters.allows($0) && $0.coordinate != nil }
        let zoomedOut = layer == .all && (region?.span.latitudeDelta ?? .infinity) > Self.everythingSpan
        let places = layer != .all ? layerPlaces : zoomedOut ? [] : layerPlaces.filter(inView)
        ZStack(alignment: .top) {
            ClusteredMap(places: places, showsUser: location.location != nil, center: centerOn, onRegion: { region = $0 },
                         onStack: { stacked = $0 }) { p in open(p) }
            .ignoresSafeArea(edges: .bottom)
            VStack(spacing: 6) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(Layer.allCases) { l in
                            Button { layer = l } label: {
                                Text(l.rawValue).font(.subheadline.weight(.semibold))
                                    .padding(.horizontal, 12).padding(.vertical, 8)
                                    .foregroundStyle(layer == l ? .white : Theme.green)
                                    .background(Capsule().fill(layer == l ? Theme.green : Theme.surface))
                                    .overlay(Capsule().strokeBorder(Theme.rule2, lineWidth: layer == l ? 0 : 1))
                            }
                            .accessibilityAddTraits(layer == l ? .isSelected : [])
                        }
                    }
                    .padding(.horizontal, 12)
                }
                Text(notice ?? (zoomedOut ? "Zoom in to a town to see all \(layerPlaces.count.formatted()) places"
                               : "\(places.count.formatted()) \(layer == .all ? "places here" : "places") · tap a pin, then its name"))
                    .font(.caption).foregroundStyle(Theme.ink2)
                    .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(.thinMaterial))
            }
            .padding(.top, 8)
        }
        .navigationTitle("Map")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(item: $pushed) { PlaceDetailView(place: $0) }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    if location.isDenied {
                        askSettings = true
                    } else {
                        // a fix from launch may be miles out of date, so always ask for a fresh one; a very recent fix moves the map now
                        if let here = location.location, here.timestamp.timeIntervalSinceNow > -60 { center(on: here) }
                        centerWhenFound = true
                        location.request()
                    }
                } label: { Label("My location", systemImage: "location") }
            }
        }
        .onChange(of: location.location) { _, here in
            guard centerWhenFound, let here else { return }
            centerWhenFound = false
            center(on: here)
        }
        .onChange(of: location.failed) { _, failed in
            guard failed && centerWhenFound else { return }
            centerWhenFound = false
            // the map already moved to a fix from the last minute or so; only say so when there was nothing to go on
            if (location.location?.timestamp.timeIntervalSinceNow ?? -.infinity) < -90 {
                flash("Couldn't find your location. Check that Location Services is on.")
            }
        }
        .onChange(of: location.status) { _, _ in
            if location.isDenied { centerWhenFound = false }   // they said no; don't jump the map if they allow it later
        }
        .confirmationDialog("Places here", isPresented: Binding(get: { !stacked.isEmpty }, set: { if !$0 { stacked = [] } })) {
            ForEach(stacked) { p in Button(p.name) { open(p) } }
        } message: {
            Text("These places share one spot on the map.")
        }
        .alert("Location is off", isPresented: $askSettings) {
            Button("Open Settings") { LocationService.openSettings() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Turn on location for Wisconsin Eats in Settings to center the map on you. It stays on your device.")
        }
    }
}

extension MapScreen {
    private func open(_ p: Place) {
        if let selection { selection.wrappedValue = p } else { pushed = p }
    }

    /// Town-level zoom on the reader, unless they're outside Wisconsin: then the map stays on the state and says why.
    private func center(on here: CLLocation) {
        if location.isOutsideWisconsin {
            flash("You're outside Wisconsin, so the map stays on the state.")
        } else {
            centerOn = CLLocation(latitude: here.coordinate.latitude, longitude: here.coordinate.longitude)
        }
    }

    private func flash(_ text: String) {
        notice = text
        Task { try? await Task.sleep(for: .seconds(5)); if notice == text { notice = nil } }
    }

    /// On screen, with half a screen of margin so panning doesn't show empty edges.
    private func inView(_ p: Place) -> Bool {
        guard let r = region, let c = p.coordinate else { return false }
        return abs(c.latitude - r.center.latitude) <= r.span.latitudeDelta && abs(c.longitude - r.center.longitude) <= r.span.longitudeDelta
    }
}

/// MKMapView with clustering: SwiftUI's Map can't cluster thousands of pins.
struct ClusteredMap: UIViewRepresentable {
    let places: [Place]
    let showsUser: Bool
    /// move the map here (town-level zoom) whenever a new location object arrives
    var center: CLLocation? = nil
    var onRegion: (MKCoordinateRegion) -> Void = { _ in }
    var onStack: ([Place]) -> Void = { _ in }
    let onSelect: (Place) -> Void

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.pointOfInterestFilter = .excludingAll
        map.register(PlaceMarker.self, forAnnotationViewWithReuseIdentifier: PlaceMarker.id)
        map.register(ClusterMarker.self, forAnnotationViewWithReuseIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier)
        map.setRegion(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 44.65, longitude: -89.75),
                                         span: MKCoordinateSpan(latitudeDelta: 5.3, longitudeDelta: 6.6)), animated: false)
        let start = map.region
        DispatchQueue.main.async { onRegion(start) }
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        context.coordinator.onSelect = onSelect
        context.coordinator.onRegion = onRegion
        context.coordinator.onStack = onStack
        map.showsUserLocation = showsUser
        if let c = center, c !== context.coordinator.centered {
            context.coordinator.centered = c
            map.setRegion(MKCoordinateRegion(center: c.coordinate, span: MKCoordinateSpan(latitudeDelta: 0.15, longitudeDelta: 0.15)),
                          animated: !UIAccessibility.isReduceMotionEnabled)
        }
        let want = Set(places.map(\.id))
        let have = map.annotations.compactMap { $0 as? PlaceAnnotation }
        let haveIds = Set(have.map(\.place.id))
        guard want != haveIds else { return }
        map.removeAnnotations(have.filter { !want.contains($0.place.id) })
        map.addAnnotations(places.filter { !haveIds.contains($0.id) }.map(PlaceAnnotation.init))
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, MKMapViewDelegate {
        var onSelect: ((Place) -> Void)?
        var onRegion: ((MKCoordinateRegion) -> Void)?
        var onStack: (([Place]) -> Void)?
        var centered: CLLocation?

        func mapView(_ map: MKMapView, regionDidChangeAnimated animated: Bool) {
            let r = map.region
            DispatchQueue.main.async { self.onRegion?(r) }   // not during a SwiftUI view update
        }

        func mapView(_ map: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if annotation is MKUserLocation { return nil }
            if annotation is MKClusterAnnotation { return nil }   // the registered ClusterMarker
            return map.dequeueReusableAnnotationView(withIdentifier: PlaceMarker.id, for: annotation)
        }

        func mapView(_ map: MKMapView, annotationView view: MKAnnotationView, calloutAccessoryControlTapped control: UIControl) {
            if let a = view.annotation as? PlaceAnnotation { onSelect?(a.place) }
        }

        func mapView(_ map: MKMapView, didSelect annotation: MKAnnotation) {
            if let cluster = annotation as? MKClusterAnnotation {
                map.deselectAnnotation(cluster, animated: false)
                let members = cluster.memberAnnotations.compactMap { $0 as? PlaceAnnotation }
                let lats = members.map(\.coordinate.latitude), lons = members.map(\.coordinate.longitude)
                // within ~20 m of each other: zooming in can never split them, so offer a list
                if let a = lats.min(), let b = lats.max(), let c = lons.min(), let d = lons.max(), b - a < 0.0002, d - c < 0.0003 {
                    onStack?(members.map(\.place).sorted { $0.name < $1.name })
                } else {
                    map.showAnnotations(cluster.memberAnnotations, animated: !UIAccessibility.isReduceMotionEnabled)
                }
            }
        }
    }
}

final class PlaceAnnotation: NSObject, MKAnnotation {
    let place: Place
    let coordinate: CLLocationCoordinate2D
    var title: String? { place.name }
    var subtitle: String? { place.townLine }
    init(_ p: Place) { place = p; coordinate = p.coordinate! }
}

final class PlaceMarker: MKMarkerAnnotationView {
    static let id = "place"
    override var annotation: MKAnnotation? { didSet { configure() } }

    private func configure() {
        clusteringIdentifier = "places"
        canShowCallout = true
        let info = UIButton(type: .detailDisclosure)
        info.accessibilityLabel = "Details"
        rightCalloutAccessoryView = info
        guard let p = (annotation as? PlaceAnnotation)?.place else { return }
        let classic = p.tags.contains(.fishFry) || p.tags.contains(.supperClub) || p.tags.contains(.custard)
        markerTintColor = UIColor(classic ? Theme.gold : Theme.green)
        glyphTintColor = UIColor(classic ? Theme.green : .white)
        glyphImage = UIImage(systemName: p.tags.contains(.fishFry) ? "fish.fill" : p.tags.contains(.supperClub) ? "wineglass.fill"
                             : p.tags.contains(.custard) ? "birthday.cake.fill" : "fork.knife")
        displayPriority = p.isHonored || classic ? .defaultHigh : .defaultLow
    }
}

final class ClusterMarker: MKMarkerAnnotationView {
    override var annotation: MKAnnotation? {
        didSet {
            markerTintColor = UIColor(Theme.green)
            glyphText = (annotation as? MKClusterAnnotation).map { "\($0.memberAnnotations.count)" }
            displayPriority = .defaultHigh
        }
    }
}
