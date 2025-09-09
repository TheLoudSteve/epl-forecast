import SwiftUI

struct TeamSelectionScreen: View {
    @Binding var selectedTeam: String?
    
    @StateObject private var eplService = EPLService()
    @State private var tempSelectedTeam: String? = nil
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [Color.red.opacity(0.1), Color.orange.opacity(0.1)]),
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                VStack(spacing: 32) {
                    // Header
                    VStack(spacing: 16) {
                        Image(systemName: "heart.circle")
                            .font(.system(size: 60, weight: .thin))
                            .foregroundStyle(
                                LinearGradient(
                                    gradient: Gradient(colors: [.red, .orange]),
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                        
                        Text("Choose Your Team")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .multilineTextAlignment(.center)
                        
                        Text("Get personalized forecasts and notifications")
                            .font(.title3)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 40)
                    
                    // Team List
                    ScrollView {
                        LazyVStack(spacing: 4) {
                            if eplService.teams.isEmpty {
                                VStack(spacing: 16) {
                                    ProgressView()
                                        .scaleEffect(1.2)
                                    Text("Loading teams...")
                                        .foregroundColor(.secondary)
                                }
                                .frame(height: 200)
                            } else {
                                ForEach(eplService.teams, id: \.id) { team in
                                    OnboardingTeamRow(
                                        team: team,
                                        isSelected: tempSelectedTeam == team.name
                                    ) {
                                        tempSelectedTeam = team.name
                                        selectedTeam = team.name
                                    }
                                }
                            }
                        }
                        .padding(.horizontal, 24)
                    }
                    .frame(maxHeight: 300)
                    
                    Spacer()
                }
            }
        }
        .onAppear {
            eplService.refreshData()
        }
    }
}

struct OnboardingTeamRow: View {
    let team: Team
    let isSelected: Bool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(team.name)
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                        .multilineTextAlignment(.leading)
                    
                    Text("Predicted #\(team.forecastedPosition) • \(String(format: "%.0f", team.forecastedPoints)) pts")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.red)
                } else {
                    Circle()
                        .stroke(Color.gray.opacity(0.3), lineWidth: 2)
                        .frame(width: 24, height: 24)
                }
            }
            .padding(.vertical, 12)
            .padding(.horizontal, 16)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(isSelected ? team.primaryColor.opacity(0.1) : Color.clear)
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

#Preview {
    TeamSelectionScreen(selectedTeam: .constant(nil))
}