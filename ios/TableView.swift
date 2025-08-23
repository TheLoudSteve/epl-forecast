import SwiftUI

struct TableView: View {
    @StateObject private var eplService = EPLService()
    
    var body: some View {
        VStack {
            if eplService.isLoading {
                ProgressView("Loading forecast...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let errorMessage = eplService.errorMessage {
                VStack(spacing: 20) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    
                    Text("Error")
                        .font(.headline)
                    
                    Text(errorMessage)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    
                    Button("Retry") {
                        eplService.refreshData()
                    }
                    .buttonStyle(.bordered)
                }
                .padding()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List {
                    if let lastUpdated = eplService.lastUpdated {
                        Section {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Last Updated")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                Text(lastUpdated)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    
                    Section {
                        ForEach(eplService.teams) { team in
                            TeamRowView(team: team)
                        }
                    } header: {
                        Text("Forecasted Final Table (38 Games)")
                            .font(.headline)
                    }
                }
                .refreshable {
                    eplService.refreshData()
                }
            }
        }
    }
}

struct TeamRowView: View {
    let team: Team
    
    var body: some View {
        HStack {
            Text("\(team.forecastedPosition)")
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(.primary)
                .frame(width: 30, alignment: .leading)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(team.name)
                    .font(.body)
                    .fontWeight(.medium)
                
                HStack(spacing: 12) {
                    Label("\(team.played)", systemImage: "gamecontroller.fill")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Label("\(String(format: "%.1f", team.pointsPerGame)) PPG", systemImage: "chart.line.uptrend.xyaxis")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(String(format: "%.0f", team.forecastedPoints))")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(.primary)
                
                Text("pts")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

#Preview {
    NavigationView {
        TableView()
            .navigationTitle("EPL Forecast")
    }
}