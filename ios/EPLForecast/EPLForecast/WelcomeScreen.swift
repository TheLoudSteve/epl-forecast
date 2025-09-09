import SwiftUI

struct WelcomeScreen: View {
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [Color.blue.opacity(0.1), Color.green.opacity(0.1)]),
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                VStack(spacing: 40) {
                    Spacer()
                    
                    // Hero Section
                    VStack(spacing: 24) {
                        // App Icon/Logo
                        Image(systemName: "chart.line.uptrend.xyaxis")
                            .font(.system(size: 80, weight: .thin))
                            .foregroundStyle(
                                LinearGradient(
                                    gradient: Gradient(colors: [.blue, .green]),
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                        
                        VStack(spacing: 16) {
                            Text("English League Forecast")
                                .font(.title)
                                .fontWeight(.bold)
                                .multilineTextAlignment(.center)
                            
                            Text("Predict the Future of Football")
                                .font(.title2)
                                .fontWeight(.medium)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                    }
                    
                    // Value Proposition
                    VStack(spacing: 20) {
                        HStack(spacing: 16) {
                            Image(systemName: "crystal.ball")
                                .font(.title2)
                                .foregroundColor(.blue)
                                .frame(width: 30)
                            
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Smart Predictions")
                                    .font(.headline)
                                    .fontWeight(.semibold)
                                
                                Text("See where teams will finish based on current form")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                            
                            Spacer()
                        }
                        
                        HStack(spacing: 16) {
                            Image(systemName: "bell.badge")
                                .font(.title2)
                                .foregroundColor(.green)
                                .frame(width: 30)
                            
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Live Updates")
                                    .font(.headline)
                                    .fontWeight(.semibold)
                                
                                Text("Get notified when forecasts change")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                            
                            Spacer()
                        }
                        
                        HStack(spacing: 16) {
                            Image(systemName: "heart.fill")
                                .font(.title2)
                                .foregroundColor(.red)
                                .frame(width: 30)
                            
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Your Team")
                                    .font(.headline)
                                    .fontWeight(.semibold)
                                
                                Text("Personalized dashboard for your favorite team")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                            
                            Spacer()
                        }
                    }
                    .padding(.horizontal, 32)
                    
                    Spacer()
                }
            }
        }
    }
}

#Preview {
    WelcomeScreen()
}