import XCTest
@testable import EPLForecast

final class EPLForecastTests: XCTestCase {
    
    func testTeamDecoding() throws {
        let json = """
        {
            "name": "Arsenal",
            "played": 10,
            "won": 8,
            "drawn": 1,
            "lost": 1,
            "for": 20,
            "against": 5,
            "goal_difference": 15,
            "points": 25,
            "points_per_game": 2.5,
            "forecasted_points": 95.0,
            "current_position": 1,
            "forecasted_position": 1
        }
        """.data(using: .utf8)!
        
        let team = try JSONDecoder().decode(Team.self, from: json)
        
        XCTAssertEqual(team.name, "Arsenal")
        XCTAssertEqual(team.played, 10)
        XCTAssertEqual(team.points, 25)
        XCTAssertEqual(team.pointsPerGame, 2.5)
        XCTAssertEqual(team.forecastedPoints, 95.0)
        XCTAssertEqual(team.forecastedPosition, 1)
    }
    
    func testAPIResponseDecoding() throws {
        let json = """
        {
            "forecast_table": [
                {
                    "name": "Arsenal",
                    "played": 10,
                    "won": 8,
                    "drawn": 1,
                    "lost": 1,
                    "for": 20,
                    "against": 5,
                    "goal_difference": 15,
                    "points": 25,
                    "points_per_game": 2.5,
                    "forecasted_points": 95.0,
                    "current_position": 1,
                    "forecasted_position": 1
                }
            ],
            "metadata": {
                "last_updated": "2024-01-01T00:00:00Z",
                "total_teams": 1,
                "api_version": "1.0",
                "description": "Test"
            }
        }
        """.data(using: .utf8)!
        
        let response = try JSONDecoder().decode(APIResponse.self, from: json)
        
        XCTAssertEqual(response.forecastTable.count, 1)
        XCTAssertEqual(response.forecastTable[0].name, "Arsenal")
        XCTAssertEqual(response.metadata.totalTeams, 1)
        XCTAssertEqual(response.metadata.apiVersion, "1.0")
    }
    
    func testEPLServiceInitialization() {
        let service = EPLService()
        
        XCTAssertTrue(service.teams.isEmpty)
        XCTAssertFalse(service.isLoading)
        XCTAssertNil(service.errorMessage)
        XCTAssertNil(service.lastUpdated)
    }
}