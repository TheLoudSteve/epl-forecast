import SwiftUI
import NewRelic

struct OnboardingFlowView: View {
    @ObservedObject private var userSettings = UserSettings.shared
    @Environment(\.dismiss) private var dismiss
    @State private var currentPage = 0
    @State private var selectedTeam: String? = nil
    
    private let totalPages = 5
    
    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 0) {
                // Consistent Top Navigation Bar for all screens
                OnboardingTopNavigationView(
                    currentPage: currentPage,
                    totalPages: totalPages,
                    onBack: currentPage > 0 ? { previousPage() } : nil,
                    onContinue: currentPage < totalPages - 1 ? { nextPage() } : { completeOnboarding() },
                    canContinue: true,
                    isFirstScreen: currentPage == 0,
                    isLastScreen: currentPage == totalPages - 1
                )
            
            // Content Area
            TabView(selection: $currentPage) {
                // Page 0: Welcome
                WelcomeScreen()
                    .tag(0)
                
                // Page 1: Forecast Explanation
                ForecastExplanationScreen()
                    .tag(1)
                
                // Page 2: Features Overview
                FeaturesScreen()
                    .tag(2)
                
                // Page 3: Team Selection
                TeamSelectionScreen(selectedTeam: $selectedTeam)
                    .tag(3)
                
                // Page 4: Completion
                CompletionScreen(
                    selectedTeam: selectedTeam ?? "your team",
                    onFinish: { completeOnboarding() }
                )
                .tag(4)
            }
            .tabViewStyle(PageTabViewStyle(indexDisplayMode: .never))
            }
        }
        .onAppear {
            // Track onboarding start
            NewRelic.recordCustomEvent("OnboardingStarted", attributes: [
                "startTime": Date().timeIntervalSince1970,
                "totalPages": totalPages
            ])
        }
    }
    
    private func nextPage() {
        withAnimation(.easeInOut(duration: 0.3)) {
            if currentPage < totalPages - 1 {
                currentPage += 1
            }
        }
        
        // Track page progression
        NewRelic.recordCustomEvent("OnboardingPageProgression", attributes: [
            "fromPage": currentPage - 1,
            "toPage": currentPage,
            "direction": "forward"
        ])
    }
    
    private func previousPage() {
        withAnimation(.easeInOut(duration: 0.3)) {
            if currentPage > 0 {
                currentPage -= 1
            }
        }
        
        // Track page regression
        NewRelic.recordCustomEvent("OnboardingPageProgression", attributes: [
            "fromPage": currentPage + 1,
            "toPage": currentPage,
            "direction": "back"
        ])
    }
    
    private func skipOnboarding() {
        // Track onboarding skip
        NewRelic.recordCustomEvent("OnboardingSkipped", attributes: [
            "skipAtPage": currentPage,
            "totalPages": totalPages
        ])
        
        // Mark as completed but don't set favorite team
        userSettings.hasLaunchedBefore = true
        dismiss()
    }
    
    private func completeOnboarding() {
        // Set favorite team if selected
        if let team = selectedTeam {
            userSettings.favoriteTeam = team
        }
        
        // Mark onboarding as completed
        userSettings.hasLaunchedBefore = true
        
        // Track onboarding completion
        NewRelic.recordCustomEvent("OnboardingCompleted", attributes: [
            "completionTime": Date().timeIntervalSince1970,
            "selectedTeam": selectedTeam ?? "none",
            "totalPages": totalPages
        ])
        
        dismiss()
    }
}

struct OnboardingTopNavigationView: View {
    let currentPage: Int
    let totalPages: Int
    let onBack: (() -> Void)?
    let onContinue: () -> Void
    let canContinue: Bool
    let isFirstScreen: Bool
    let isLastScreen: Bool
    
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                // Back Button
                if let onBack = onBack {
                    Button(action: onBack) {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left")
                                .font(.system(size: 16, weight: .medium))
                            Text("Back")
                                .font(.system(size: 16, weight: .medium))
                        }
                        .foregroundColor(.blue)
                    }
                } else {
                    // Empty space to maintain layout
                    HStack(spacing: 4) {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 16, weight: .medium))
                        Text("Back")
                            .font(.system(size: 16, weight: .medium))
                    }
                    .foregroundColor(.clear)
                }
                
                Spacer()
                
                // Progress Dots
                HStack(spacing: 6) {
                    ForEach(0..<totalPages, id: \.self) { index in
                        Circle()
                            .fill(index == currentPage ? Color.blue : Color.gray.opacity(0.3))
                            .frame(width: 8, height: 8)
                            .animation(.easeInOut(duration: 0.3), value: currentPage)
                    }
                }
                
                Spacer()
                
                // Continue Button
                Button(action: onContinue) {
                    Text(isLastScreen ? "Finish" : "Continue")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(canContinue ? .blue : .blue.opacity(0.5))
                }
                .disabled(!canContinue)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
            .padding(.top, 8) // Extra padding from safe area
            
            Divider()
        }
        .background(Color(.systemBackground))
    }
}


#Preview {
    OnboardingFlowView()
}