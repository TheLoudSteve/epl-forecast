import SwiftUI

struct ContentView: View {
    @StateObject private var userSettings = UserSettings.shared
    @State private var showingSettings = false
    @State private var shouldResetScroll = false
    
    var body: some View {
        NavigationStack {
            TableView(shouldResetScroll: $shouldResetScroll)
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
        .onChange(of: showingSettings) { _, isShowing in
            if !isShowing {
                // Settings sheet was just dismissed
                shouldResetScroll = true
            }
        }
        .fullScreenCover(isPresented: .constant(userSettings.showOnboarding)) {
            FavoriteTeamSelectionView(isOnboarding: true)
        }
    }
}

#Preview {
    ContentView()
}