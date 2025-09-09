import SwiftUI
import NewRelic

struct FavoriteTeamSelectionView: View {
    @StateObject private var eplService = EPLService()
    @ObservedObject private var userSettings = UserSettings.shared
    @State private var selectedTeam: String?
    @Environment(\.dismiss) private var dismiss
    
    let isOnboarding: Bool
    
    init(isOnboarding: Bool = true) {
        self.isOnboarding = isOnboarding
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                if isOnboarding {
                    VStack(spacing: 12) {
                        Image(systemName: "heart.fill")
                            .font(.system(size: 60))
                            .foregroundColor(.red)
                        
                        Text("Choose Your Team")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                        
                        Text("Select your favorite Premier League team to highlight them in the table")
                            .font(.body)
                            .multilineTextAlignment(.center)
                            .foregroundColor(.secondary)
                            .padding(.horizontal)
                    }
                    .padding(.top, 20)
                }
                
                if eplService.isLoading {
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.2)
                        Text("Loading teams...")
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let errorMessage = eplService.errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        
                        Text("Error loading teams")
                            .font(.headline)
                        
                        Text(errorMessage)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        
                        Button("Try Again") {
                            eplService.refreshData()
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding()
                } else {
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(eplService.teams.sorted(by: { $0.name < $1.name })) { team in
                                TeamSelectionRow(
                                    team: team,
                                    isSelected: selectedTeam == team.name
                                ) {
                                    selectedTeam = team.name
                                    
                                    // Track team selection
                                    NewRelic.recordCustomEvent("FavoriteTeamSelected", attributes: [
                                        "teamName": team.name,
                                        "isOnboarding": isOnboarding,
                                        "currentPosition": team.forecastedPosition
                                    ])
                                }
                            }
                        }
                        .padding(.horizontal)
                    }
                    
                    if selectedTeam != nil {
                        Button(action: saveSelection) {
                            Text(isOnboarding ? "Continue" : "Save")
                                .font(.headline)
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .cornerRadius(12)
                        }
                        .padding(.horizontal)
                        .padding(.bottom)
                    }
                }
            }
            .navigationTitle(isOnboarding ? "Welcome" : "Choose Team")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if !isOnboarding {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Cancel") {
                            dismiss()
                        }
                    }
                }
            }
        }
        .onAppear {
            selectedTeam = userSettings.favoriteTeam
            
            // Track onboarding view appearance
            NewRelic.recordCustomEvent("FavoriteTeamSelectionAppeared", attributes: [
                "isOnboarding": isOnboarding,
                "hasExistingFavorite": userSettings.favoriteTeam != nil
            ])
        }
    }
    
    private func saveSelection() {
        guard let selectedTeam = selectedTeam else { return }
        
        userSettings.setFavoriteTeam(selectedTeam)
        
        // Track successful selection
        NewRelic.recordCustomEvent("FavoriteTeamSaved", attributes: [
            "teamName": selectedTeam,
            "isOnboarding": isOnboarding
        ])
        
        if !isOnboarding {
            dismiss()
        }
    }
}

struct TeamSelectionRow: View {
    let team: Team
    let isSelected: Bool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(team.name)
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                    
                    HStack {
                        Text("Position: \(team.forecastedPosition)")
                        Spacer()
                        Text("\(String(format: "%.0f", team.forecastedPoints)) pts")
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
                
                Spacer()
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.blue)
                        .font(.title2)
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? team.backgroundColor : Color(.systemBackground))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(isSelected ? team.primaryColor : Color(.systemGray5), lineWidth: isSelected ? 2 : 1)
                    )
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

#Preview {
    FavoriteTeamSelectionView(isOnboarding: true)
}

#Preview("Settings") {
    FavoriteTeamSelectionView(isOnboarding: false)
}