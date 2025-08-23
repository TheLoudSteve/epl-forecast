import SwiftUI

struct TableView: View {
    @StateObject private var eplService = EPLService()
    
    var body: some View {
        VStack {
            if eplService.isLoading {
                VStack(spacing: 20) {
                    ProgressView()
                        .scaleEffect(1.2)
                        .tint(.blue)
                    
                    VStack(spacing: 8) {
                        Text("Loading EPL Forecast")
                            .font(.headline)
                        
                        Text("Getting latest Premier League data...")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
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
                .accessibilityLabel("Position \(team.forecastedPosition)")
            
            VStack(alignment: .leading, spacing: 2) {
                Text(team.name)
                    .font(.body)
                    .fontWeight(.medium)
                
                HStack(spacing: 8) {
                    AsyncImage(url: URL(string: teamLogoURL(for: team.name))) { image in
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                    } placeholder: {
                        Image(systemName: teamIcon(for: team.name))
                            .foregroundColor(teamColor(for: team.name))
                    }
                    .frame(width: 16, height: 16)
                    
                    Text("\(team.played) GP | \(team.points) PTS | \(String(format: "%.1f", team.pointsPerGame)) PPG")
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
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(team.name), position \(team.forecastedPosition), forecasted \(String(format: "%.0f", team.forecastedPoints)) points, played \(team.played) games, \(String(format: "%.1f", team.pointsPerGame)) points per game")
    }
}

func teamLogoURL(for teamName: String) -> String {
    let normalizedName = teamName.lowercased().trimmingCharacters(in: .whitespaces)
    print("Looking for logo for team: '\(teamName)' (normalized: '\(normalizedName)')")
    
    switch normalizedName {
    case let name where name.contains("arsenal"):
        return "https://resources.premierleague.com/premierleague/badges/50/t3.png"
    case let name where name.contains("chelsea"):
        return "https://resources.premierleague.com/premierleague/badges/50/t8.png"
    case let name where name.contains("liverpool"):
        return "https://resources.premierleague.com/premierleague/badges/50/t14.png"
    case let name where name.contains("manchester city"):
        return "https://resources.premierleague.com/premierleague/badges/50/t43.png"
    case let name where name.contains("manchester united"):
        return "https://resources.premierleague.com/premierleague/badges/50/t1.png"
    case let name where name.contains("tottenham"):
        return "https://resources.premierleague.com/premierleague/badges/50/t6.png"
    case let name where name.contains("newcastle"):
        return "https://resources.premierleague.com/premierleague/badges/50/t4.png"
    case let name where name.contains("brighton"):
        return "https://resources.premierleague.com/premierleague/badges/50/t36.png"
    case let name where name.contains("aston villa"):
        return "https://resources.premierleague.com/premierleague/badges/50/t7.png"
    case let name where name.contains("west ham"):
        return "https://resources.premierleague.com/premierleague/badges/50/t21.png"
    case let name where name.contains("crystal palace"):
        return "https://resources.premierleague.com/premierleague/badges/50/t31.png"
    case let name where name.contains("wolves"):
        return "https://resources.premierleague.com/premierleague/badges/50/t39.png"
    case let name where name.contains("fulham"):
        return "https://resources.premierleague.com/premierleague/badges/50/t54.png"
    case let name where name.contains("brentford"):
        return "https://resources.premierleague.com/premierleague/badges/50/t94.png"
    case let name where name.contains("nottingham"):
        return "https://resources.premierleague.com/premierleague/badges/50/t17.png"
    case let name where name.contains("everton"):
        return "https://resources.premierleague.com/premierleague/badges/50/t11.png"
    case let name where name.contains("bournemouth"):
        return "https://resources.premierleague.com/premierleague/badges/50/t91.png"
    case let name where name.contains("luton"):
        return "https://resources.premierleague.com/premierleague/badges/50/t102.png"
    case let name where name.contains("burnley"):
        return "https://resources.premierleague.com/premierleague/badges/50/t90.png"
    case let name where name.contains("sheffield"):
        return "https://resources.premierleague.com/premierleague/badges/50/t49.png"
    case let name where name.contains("leicester"):
        return "https://resources.premierleague.com/premierleague/badges/50/t13.png"
    case let name where name.contains("leeds"):
        return "https://resources.premierleague.com/premierleague/badges/50/t2.png"
    case let name where name.contains("southampton"):
        return "https://resources.premierleague.com/premierleague/badges/50/t20.png"
    default:
        print("No logo found for team: '\(teamName)'")
        return ""
    }
}

func teamIcon(for teamName: String) -> String {
    switch teamName.lowercased() {
    case let name where name.contains("arsenal"):
        return "shield.fill"
    case let name where name.contains("chelsea"):
        return "crown.fill"
    case let name where name.contains("liverpool"):
        return "heart.fill"
    case let name where name.contains("manchester city"):
        return "star.fill"
    case let name where name.contains("manchester united"):
        return "flame.fill"
    case let name where name.contains("tottenham"):
        return "bolt.fill"
    case let name where name.contains("newcastle"):
        return "n.circle.fill"
    case let name where name.contains("brighton"):
        return "sun.max.fill"
    case let name where name.contains("aston villa"):
        return "leaf.fill"
    case let name where name.contains("west ham"):
        return "hammer.fill"
    case let name where name.contains("crystal palace"):
        return "diamond.fill"
    case let name where name.contains("wolves"):
        return "pawprint.fill"
    case let name where name.contains("fulham"):
        return "house.fill"
    case let name where name.contains("brentford"):
        return "hexagon.fill"
    case let name where name.contains("nottingham"):
        return "tree.fill"
    case let name where name.contains("everton"):
        return "building.columns.fill"
    case let name where name.contains("bournemouth"):
        return "circle.fill"
    case let name where name.contains("luton"):
        return "h.circle.fill"
    case let name where name.contains("burnley"):
        return "flame"
    case let name where name.contains("sheffield"):
        return "scissors"
    default:
        return "soccerball"
    }
}

func teamColor(for teamName: String) -> Color {
    switch teamName.lowercased() {
    case let name where name.contains("arsenal"):
        return .red
    case let name where name.contains("chelsea"):
        return .blue
    case let name where name.contains("liverpool"):
        return .red
    case let name where name.contains("manchester city"):
        return .cyan
    case let name where name.contains("manchester united"):
        return .red
    case let name where name.contains("tottenham"):
        return .blue
    case let name where name.contains("newcastle"):
        return .black
    case let name where name.contains("brighton"):
        return .blue
    case let name where name.contains("aston villa"):
        return .purple
    case let name where name.contains("west ham"):
        return .purple
    case let name where name.contains("crystal palace"):
        return .blue
    case let name where name.contains("wolves"):
        return .orange
    case let name where name.contains("fulham"):
        return .black
    case let name where name.contains("brentford"):
        return .red
    case let name where name.contains("nottingham"):
        return .red
    case let name where name.contains("everton"):
        return .blue
    case let name where name.contains("bournemouth"):
        return .red
    case let name where name.contains("luton"):
        return .orange
    case let name where name.contains("burnley"):
        return .purple
    case let name where name.contains("sheffield"):
        return .red
    default:
        return .primary
    }
}

#Preview {
    NavigationView {
        TableView()
            .navigationTitle("EPL Forecast")
    }
}