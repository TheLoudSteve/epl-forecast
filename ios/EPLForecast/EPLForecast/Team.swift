import Foundation

struct Team: Codable, Identifiable, Equatable {
    let name: String
    let played: Int
    let won: Int
    let drawn: Int
    let lost: Int
    let goalsFor: Int
    let against: Int
    let goalDifference: Int
    let points: Int
    let pointsPerGame: Double
    let forecastedPoints: Double
    let currentPosition: Int
    let forecastedPosition: Int
    
    // Computed property for Identifiable
    var id: String { name }
    
    private enum CodingKeys: String, CodingKey {
        case name, played, won, drawn, lost
        case goalsFor = "for"
        case against
        case goalDifference = "goal_difference"
        case points
        case pointsPerGame = "points_per_game"
        case forecastedPoints = "forecasted_points"
        case currentPosition = "current_position"
        case forecastedPosition = "forecasted_position"
    }
}

struct APIResponse: Codable {
    let forecastTable: [Team]
    let metadata: Metadata
    
    private enum CodingKeys: String, CodingKey {
        case forecastTable = "forecast_table"
        case metadata
    }
}

struct Metadata: Codable {
    let lastUpdated: String
    let totalTeams: Int
    let apiVersion: String
    let description: String
    
    private enum CodingKeys: String, CodingKey {
        case lastUpdated = "last_updated"
        case totalTeams = "total_teams"
        case apiVersion = "api_version"
        case description
    }
}