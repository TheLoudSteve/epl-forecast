import SwiftUI

struct TableView: View {
    @ObservedObject var eplService: EPLService
    
    var body: some View {
        NavigationView {
            VStack {
                if eplService.isLoading {
                    VStack {
                        ProgressView()
                        Text("Loading forecast...")
                            .padding(.top)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let errorMessage = eplService.errorMessage {
                    VStack {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text("Error")
                            .font(.headline)
                            .padding(.top)
                        Text(errorMessage)
                            .multilineTextAlignment(.center)
                            .padding()
                        Button("Retry") {
                            eplService.refreshData()
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    VStack {
                        if let lastUpdated = eplService.lastUpdated {
                            Text("Last updated: \(lastUpdated)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .padding(.horizontal)
                        }
                        
                        List {
                            ForEach(eplService.teams) { team in
                                TeamRowView(team: team)
                            }
                        }
                        .refreshable {
                            eplService.refreshData()
                        }
                    }
                }
            }
            .navigationTitle("EPL Forecast")
            .navigationBarTitleDisplayMode(.large)
        }
    }
}

struct TeamRowView: View {
    let team: Team
    
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                HStack {
                    Text("\(team.forecastedPosition)")
                        .font(.headline)
                        .foregroundColor(.primary)
                        .frame(width: 30, alignment: .leading)
                    
                    Text(team.name)
                        .font(.headline)
                        .lineLimit(1)
                }
                
                HStack {
                    Text("Current: \(team.currentPosition)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Spacer()
                    
                    Text("\(team.played) played")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            VStack(alignment: .trailing) {
                Text("\(team.forecastedPoints, specifier: "%.1f")")
                    .font(.headline)
                    .foregroundColor(.primary)
                
                Text("\(team.pointsPerGame, specifier: "%.2f") ppg")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    TableView(eplService: EPLService())
}