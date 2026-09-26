import SwiftUI
import MapKit

struct MapScreen: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    var selection: Binding<Place?>? = nil

    @State private var layer: Layer = .fishFry
    @State private var pushed: Place?

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
        let places = model.places.filter { layer.guide.includes($0) && model.filters.allows($0) && $0.coordinate != nil }
        ZStack(alignment: .top) {
            ClusteredMap(places: places, showsUser: location.location != nil) { p in
                if let selection { selection.wrappedValue = p } else { pushed = p }
            }
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
                Text("\(places.count.formatted()) places · tap a pin, then its name").font(.caption).foregroundStyle(Theme.ink2)
                    .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(.thinMaterial))
            }
            .padding(.top, 8)
        }
        .navigationTitle("Map")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(item: $pushed) { PlaceDetailView(place: $0) }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { location.request() } label: { Label("My location", systemImage: "location") }
            }
        }
    }
}

/// MKMapView with clustering: SwiftUI's Map can't cluster thousands of pins.
struct ClusteredMap: UIViewRepresentable {
    let places: [Place]
    let showsUser: Bool
    let onSelect: (Place) -> Void

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.pointOfInterestFilter = .excludingAll
        map.register(PlaceMarker.self, forAnnotationViewWithReuseIdentifier: PlaceMarker.id)
        map.register(ClusterMarker.self, forAnnotationViewWithReuseIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier)
        map.setRegion(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 44.65, longitude: -89.75),
                                         span: MKCoordinateSpan(latitudeDelta: 5.3, longitudeDelta: 6.6)), animated: false)
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        context.coordinator.onSelect = onSelect
        map.showsUserLocation = showsUser
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
                map.showAnnotations(cluster.memberAnnotations, animated: true)
                map.deselectAnnotation(cluster, animated: false)
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
