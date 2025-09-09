import SwiftUI

struct CompletionScreen: View {
    let selectedTeam: String
    let onFinish: () -> Void
    
    @State private var showCheckmark = false
    @State private var showContent = false
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [Color.green.opacity(0.1), Color.blue.opacity(0.1)]),
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                VStack(spacing: 40) {
                    Spacer()
                    
                    // Success Animation
                    ZStack {
                        if showCheckmark {
                            Circle()
                                .fill(Color.green.opacity(0.1))
                                .frame(width: 120, height: 120)
                                .scaleEffect(showContent ? 1.0 : 0.5)
                                .animation(.easeOut(duration: 0.6), value: showContent)
                            
                            Image(systemName: "checkmark")
                                .font(.system(size: 60, weight: .bold))
                                .foregroundColor(.green)
                                .scaleEffect(showContent ? 1.0 : 0.1)
                                .animation(.spring(response: 0.6, dampingFraction: 0.6).delay(0.2), value: showContent)
                        }
                    }
                    
                    // Success Content
                    if showContent {
                        VStack(spacing: 24) {
                            VStack(spacing: 16) {
                                Text("You're All Set!")
                                    .font(.largeTitle)
                                    .fontWeight(.bold)
                                    .multilineTextAlignment(.center)
                                
                                if selectedTeam != "your team" {
                                    Text("Welcome to your personalized \(selectedTeam) forecast")
                                        .font(.title3)
                                        .foregroundColor(.secondary)
                                        .multilineTextAlignment(.center)
                                } else {
                                    Text("You can always choose your favorite team later in settings")
                                        .font(.title3)
                                        .foregroundColor(.secondary)
                                        .multilineTextAlignment(.center)
                                }
                            }
                            
                            // Features Summary
                            VStack(spacing: 16) {
                                FeatureSummaryRow(
                                    icon: "chart.line.uptrend.xyaxis",
                                    title: "Smart Forecasts",
                                    description: "See predicted final positions",
                                    color: .blue
                                )
                                
                                FeatureSummaryRow(
                                    icon: "bell.badge",
                                    title: "Live Updates",
                                    description: "Get notified of forecast changes",
                                    color: .green
                                )
                                
                                if selectedTeam != "your team" {
                                    FeatureSummaryRow(
                                        icon: "heart.fill",
                                        title: "Personal Dashboard",
                                        description: "Track \(selectedTeam)'s journey",
                                        color: .red
                                    )
                                } else {
                                    FeatureSummaryRow(
                                        icon: "apps.iphone",
                                        title: "Home Screen Widget",
                                        description: "Quick access to forecasts",
                                        color: .purple
                                    )
                                }
                            }
                            .padding(.horizontal, 32)
                        }
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                    }
                    
                    // Finish Button - integrated into content
                    if showContent {
                        VStack(spacing: 16) {
                            Spacer()
                            
                            Button(action: onFinish) {
                                HStack {
                                    Text("Start Forecasting")
                                        .fontWeight(.semibold)
                                    Image(systemName: "arrow.right")
                                        .font(.system(size: 14, weight: .semibold))
                                }
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .frame(height: 50)
                                .background(
                                    LinearGradient(
                                        gradient: Gradient(colors: [.green, .blue]),
                                        startPoint: .leading,
                                        endPoint: .trailing
                                    )
                                )
                                .cornerRadius(25)
                            }
                            .padding(.horizontal, 32)
                            
                            Spacer()
                        }
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                    } else {
                        Spacer()
                    }
                }
            }
        }
        .onAppear {
            // Start animations
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                withAnimation {
                    showCheckmark = true
                }
            }
            
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                withAnimation(.easeOut(duration: 0.8)) {
                    showContent = true
                }
            }
        }
    }
}

struct FeatureSummaryRow: View {
    let icon: String
    let title: String
    let description: String
    let color: Color
    
    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
                .frame(width: 30)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Text(description)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    CompletionScreen(
        selectedTeam: "Arsenal",
        onFinish: { print("Finish") }
    )
}