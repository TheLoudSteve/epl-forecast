import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationStack {
            TableView()
                .navigationTitle("Premier League Forecast")
                .navigationBarTitleDisplayMode(.inline)
        }
    }
}

#Preview {
    ContentView()
}