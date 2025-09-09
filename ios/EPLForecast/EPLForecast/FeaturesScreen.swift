import SwiftUI

struct FeaturesScreen: View {
    
    @State private var currentFeature = 0
    private let features = ["widget", "notifications", "insights"]
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [Color.orange.opacity(0.1), Color.red.opacity(0.1)]),
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                VStack(spacing: 32) {
                    // Header
                    VStack(spacing: 16) {
                        Image(systemName: "sparkles")
                            .font(.system(size: 60, weight: .thin))
                            .foregroundStyle(
                                LinearGradient(
                                    gradient: Gradient(colors: [.orange, .red]),
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                        
                        Text("Powerful Features")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .multilineTextAlignment(.center)
                        
                        Text("Everything you need to stay ahead")
                            .font(.title3)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 40)
                    
                    // Feature Showcase
                    TabView(selection: $currentFeature) {
                        // Widget Feature
                        WidgetFeatureView()
                            .tag(0)
                        
                        // Notifications Feature
                        NotificationFeatureView()
                            .tag(1)
                        
                        // Insights Feature
                        InsightsFeatureView()
                            .tag(2)
                    }
                    .tabViewStyle(PageTabViewStyle(indexDisplayMode: .never))
                    .frame(height: 400)
                    
                    // Feature Indicators
                    HStack(spacing: 8) {
                        ForEach(0..<features.count, id: \.self) { index in
                            Circle()
                                .fill(index == currentFeature ? Color.orange : Color.gray.opacity(0.3))
                                .frame(width: 8, height: 8)
                                .animation(.easeInOut(duration: 0.3), value: currentFeature)
                        }
                    }
                    
                    Spacer()
                }
            }
        }
    }
}

struct WidgetFeatureView: View {
    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 12) {
                Image(systemName: "apps.iphone")
                    .font(.system(size: 40))
                    .foregroundColor(.blue)
                
                Text("Home Screen Widget")
                    .font(.title2)
                    .fontWeight(.bold)
            }
            
            // Mock Widget Preview
            VStack(spacing: 8) {
                HStack {
                    Text("League")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Spacer()
                    Image(systemName: "soccerball")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(spacing: 4) {
                    Text("#3")
                        .font(.system(size: 32, weight: .bold, design: .rounded))
                        .foregroundColor(.red)
                    
                    Text("Millfield Rangers")
                        .font(.headline)
                        .fontWeight(.semibold)
                        .foregroundColor(.red)
                    
                    Text("68 pts")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    HStack {
                        Circle()
                            .fill(Color.blue)
                            .frame(width: 6, height: 6)
                        Text("Champions League")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Spacer()
                    }
                }
                
                Spacer()
            }
            .padding(12)
            .frame(width: 140, height: 140)
            .background(Color(.systemBackground))
            .cornerRadius(12)
            .shadow(radius: 3)
            
            Text("See your team's forecast position right on your home screen")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.horizontal, 32)
    }
}

struct NotificationFeatureView: View {
    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 12) {
                Image(systemName: "bell.badge")
                    .font(.system(size: 40))
                    .foregroundColor(.green)
                
                Text("Smart Notifications")
                    .font(.title2)
                    .fontWeight(.bold)
            }
            
            // Mock Notification
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 12) {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.title3)
                        .foregroundColor(.green)
                        .frame(width: 30, height: 30)
                        .background(Color.green.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("English League Forecast")
                            .font(.caption)
                            .fontWeight(.semibold)
                        
                        Text("Millfield Rangers' forecast position improved!")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    
                    Spacer()
                    
                    Text("now")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                
                Text("Your team moved up to 2nd place in our predictions after their recent form improvement.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .padding(16)
            .background(Color(.systemBackground))
            .cornerRadius(12)
            .shadow(radius: 3)
            
            Text("Get instant alerts when your team's forecast changes significantly")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.horizontal, 32)
    }
}

struct InsightsFeatureView: View {
    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 12) {
                Image(systemName: "chart.bar.fill")
                    .font(.system(size: 40))
                    .foregroundColor(.purple)
                
                Text("Personal Insights")
                    .font(.title2)
                    .fontWeight(.bold)
            }
            
            // Mock Insights Panel
            VStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Circle()
                            .fill(Color.red)
                            .frame(width: 8, height: 8)
                        Text("Millfield Rangers")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(.red)
                        Spacer()
                        Text("#3")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.red)
                    }
                    
                    Divider()
                    
                    VStack(spacing: 6) {
                        HStack {
                            Text("Recent Form")
                            Spacer()
                            Text("2.1 PPG")
                                .fontWeight(.semibold)
                                .foregroundColor(.green)
                        }
                        .font(.subheadline)
                        
                        HStack {
                            Text("Forecast Change")
                            Spacer()
                            HStack(spacing: 4) {
                                Image(systemName: "arrow.up")
                                    .font(.caption)
                                    .foregroundColor(.green)
                                Text("↑1")
                                    .fontWeight(.semibold)
                                    .foregroundColor(.green)
                            }
                        }
                        .font(.subheadline)
                        
                        HStack {
                            Text("Final Prediction")
                            Spacer()
                            Text("68.5 pts")
                                .fontWeight(.semibold)
                        }
                        .font(.subheadline)
                    }
                }
                .padding(16)
                .background(Color(.systemBackground))
                .cornerRadius(12)
                .shadow(radius: 2)
            }
            
            Text("Deep insights and analytics personalized for your favorite team")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.horizontal, 32)
    }
}

#Preview {
    FeaturesScreen()
}