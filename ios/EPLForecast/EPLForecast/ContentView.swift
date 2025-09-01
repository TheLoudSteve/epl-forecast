import SwiftUI

struct ContentView: View {
    @StateObject private var userSettings = UserSettings.shared
    @State private var showingSettings = false
    
    var body: some View {
        NavigationStack {
            TableView()
                .navigationTitle("Premier League Forecast")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button(action: {
                            showingSettings = true
                        }) {
                            Image(systemName: "gearshape.fill")
                        }
                    }
                }
        }
        .sheet(isPresented: $showingSettings) {
            SettingsView()
        }
        .fullScreenCover(isPresented: .constant(userSettings.showOnboarding)) {
            FavoriteTeamSelectionView(isOnboarding: true)
        }
    }
}

#Preview {
    ContentView()
}