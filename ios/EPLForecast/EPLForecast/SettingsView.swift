import SwiftUI
import NewRelic
import UserNotifications

struct SettingsView: View {
    @ObservedObject private var userSettings = UserSettings.shared
    @StateObject private var eplService = EPLService()
    @Environment(\.dismiss) private var dismiss
    @State private var showingTeamSelection = false
    @State private var isTestingNotification = false
    @State private var testNotificationResult: String?
    @State private var showingTestResult = false
    @State private var notificationPermissionStatus: UNAuthorizationStatus = .notDetermined
    @State private var showingPermissionAlert = false
    
    var body: some View {
        NavigationView {
            List {
                Section("Favorite Team") {
                    if let favoriteTeam = userSettings.favoriteTeam {
                        HStack {
                            AsyncImage(url: URL(string: teamLogoURL(for: favoriteTeam))) { image in
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fit)
                            } placeholder: {
                                Image(systemName: teamIcon(for: favoriteTeam))
                                    .foregroundColor(teamColorForName(favoriteTeam))
                            }
                            .frame(width: 24, height: 24)
                            
                            Text(favoriteTeam)
                            
                            Spacer()
                            
                            if let team = eplService.teams.first(where: { $0.name == favoriteTeam }) {
                                VStack(alignment: .trailing, spacing: 2) {
                                    Text("#\(team.forecastedPosition)")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    Text("\(String(format: "%.0f", team.forecastedPoints)) pts")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture {
                            showingTeamSelection = true
                        }
                    } else {
                        Button("Choose Favorite Team") {
                            showingTeamSelection = true
                        }
                    }
                }
                
                Section("Notifications") {
                    // Permission status indicator
                    if notificationPermissionStatus == .denied {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.orange)
                                Text("Notifications Disabled")
                                    .fontWeight(.medium)
                                Spacer()
                            }
                            
                            Text("Go to Settings → Notifications → EPL Forecast to enable push notifications.")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            
                            Button("Open Settings") {
                                if let settingsUrl = URL(string: UIApplication.openSettingsURLString) {
                                    UIApplication.shared.open(settingsUrl)
                                }
                            }
                            .foregroundColor(.blue)
                        }
                        .padding(.vertical, 4)
                    }
                    
                    // Master notification toggle
                    HStack {
                        Text("Enable Notifications")
                        Spacer()
                        Toggle("", isOn: $userSettings.notificationsEnabled)
                            .disabled(notificationPermissionStatus == .denied)
                    }
                    
                    if userSettings.notificationsEnabled {
                        // Notification timing
                        VStack(alignment: .leading, spacing: 8) {
                            Text("When to Notify")
                                .font(.subheadline)
                                .fontWeight(.medium)
                            
                            ForEach(NotificationTiming.allCases, id: \.self) { timing in
                                HStack {
                                    Button(action: {
                                        userSettings.notificationTiming = timing
                                    }) {
                                        HStack {
                                            Image(systemName: userSettings.notificationTiming == timing ? "checkmark.circle.fill" : "circle")
                                                .foregroundColor(userSettings.notificationTiming == timing ? .blue : .gray)
                                            
                                            VStack(alignment: .leading, spacing: 2) {
                                                Text(timing.displayName)
                                                    .foregroundColor(.primary)
                                                Text(timing.description)
                                                    .font(.caption)
                                                    .foregroundColor(.secondary)
                                            }
                                        }
                                    }
                                    .buttonStyle(PlainButtonStyle())
                                    
                                    Spacer()
                                }
                            }
                        }
                        .padding(.vertical, 4)
                        
                        // Notification sensitivity
                        VStack(alignment: .leading, spacing: 8) {
                            Text("What to Notify")
                                .font(.subheadline)
                                .fontWeight(.medium)
                            
                            ForEach(NotificationSensitivity.allCases, id: \.self) { sensitivity in
                                HStack {
                                    Button(action: {
                                        userSettings.notificationSensitivity = sensitivity
                                    }) {
                                        HStack {
                                            Image(systemName: userSettings.notificationSensitivity == sensitivity ? "checkmark.circle.fill" : "circle")
                                                .foregroundColor(userSettings.notificationSensitivity == sensitivity ? .blue : .gray)
                                            
                                            VStack(alignment: .leading, spacing: 2) {
                                                Text(sensitivity.displayName)
                                                    .foregroundColor(.primary)
                                                Text(sensitivity.description)
                                                    .font(.caption)
                                                    .foregroundColor(.secondary)
                                            }
                                        }
                                    }
                                    .buttonStyle(PlainButtonStyle())
                                    
                                    Spacer()
                                }
                            }
                        }
                        .padding(.vertical, 4)
                        
                        // Test notification button
                        Button(action: {
                            isTestingNotification = true
                            testNotificationResult = nil
                            
                            eplService.sendTestNotification { result in
                                isTestingNotification = false
                                
                                switch result {
                                case .success(let message):
                                    testNotificationResult = message
                                    showingTestResult = true
                                case .failure(let error):
                                    testNotificationResult = "Failed to send test notification: \(error.localizedDescription)"
                                    showingTestResult = true
                                }
                            }
                        }) {
                            HStack {
                                if isTestingNotification {
                                    ProgressView()
                                        .scaleEffect(0.8)
                                        .padding(.trailing, 8)
                                }
                                Text(isTestingNotification ? "Sending..." : "Send Test Notification")
                            }
                        }
                        .disabled(isTestingNotification)
                    } else {
                        Text("Enable notifications to receive updates about your team's forecast position changes.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .padding(.vertical, 4)
                    }
                }
                
                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Text("Build")
                        Spacer()
                        Text(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1")
                            .foregroundColor(.secondary)
                    }
                }
                
                Section {
                    Text("Data updates every 2 minutes during live matches and twice daily otherwise. Forecasts are based on current points per game projected to a full 38-game season.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
        .sheet(isPresented: $showingTeamSelection) {
            FavoriteTeamSelectionView(isOnboarding: false)
        }
        .alert("Test Notification", isPresented: $showingTestResult) {
            Button("OK") {
                testNotificationResult = nil
            }
        } message: {
            Text(testNotificationResult ?? "")
        }
        .onAppear {
            // Track settings view appearance
            NewRelic.recordCustomEvent("SettingsViewAppeared", attributes: [
                "hasFavoriteTeam": userSettings.favoriteTeam != nil
            ])
            
            // Check notification permission status
            checkNotificationPermissions()
        }
    }
    
    private func teamColorForName(_ teamName: String) -> Color {
        // Create a temporary team object to get color
        let dummyTeam = Team(
            name: teamName,
            played: 0, won: 0, drawn: 0, lost: 0, goalsFor: 0, against: 0,
            goalDifference: 0, points: 0, pointsPerGame: 0, forecastedPoints: 0,
            currentPosition: 0, forecastedPosition: 0
        )
        return dummyTeam.primaryColor
    }
    
    private func checkNotificationPermissions() {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                self.notificationPermissionStatus = settings.authorizationStatus
                
                // Track permission status
                NewRelic.recordCustomEvent("NotificationPermissionChecked", attributes: [
                    "status": settings.authorizationStatus.rawValue,
                    "alertSetting": settings.alertSetting.rawValue,
                    "soundSetting": settings.soundSetting.rawValue
                ])
            }
        }
    }
}

#Preview {
    SettingsView()
}