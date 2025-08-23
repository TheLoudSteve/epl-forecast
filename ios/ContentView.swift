import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationView {
            TableView()
                .navigationTitle("EPL Forecast")
        }
    }
}

#Preview {
    ContentView()
}