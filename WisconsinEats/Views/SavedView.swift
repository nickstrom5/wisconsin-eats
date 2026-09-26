import SwiftUI

struct SavedView: View {
    @Environment(AppModel.self) private var model
    var selection: Binding<Place?>? = nil
    @State private var pushed: Place?

    var body: some View {
        let places = model.savedPlaces
        List {
            if places.isEmpty {
                ContentUnavailableView("Nothing saved yet", systemImage: "heart",
                                       description: Text("Tap the heart on a fish fry or supper club to keep it here for Friday."))
            }
            ForEach(places) { p in
                Button {
                    if let selection { selection.wrappedValue = p } else { pushed = p }
                } label: { PlaceRow(place: p) }
                .swipeActions { Button("Remove", role: .destructive) { model.toggleSaved(p) } }
            }
        }
        .listStyle(.plain)
        .navigationTitle("Saved")
        .navigationDestination(item: $pushed) { PlaceDetailView(place: $0) }
    }
}
