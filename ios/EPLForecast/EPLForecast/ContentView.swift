import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationView {
            TableView()
                .navigationTitle("Premier League Forecast")
                .navigationBarTitleDisplayMode(.inline)
        }
    }
}

#Preview {
    ContentView()
}