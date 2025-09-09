import SwiftUI

struct ForecastExplanationScreen: View {
    
    @State private var showPrediction = false
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [Color.purple.opacity(0.1), Color.blue.opacity(0.1)]),
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                VStack(spacing: 32) {
                    // Header
                    VStack(spacing: 16) {
                        Image(systemName: "arrow.left.arrow.right")
                            .font(.system(size: 60, weight: .thin))
                            .foregroundStyle(
                                LinearGradient(
                                    gradient: Gradient(colors: [.purple, .blue]),
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                        
                        Text("How It Works")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .multilineTextAlignment(.center)
                        
                        Text("Go beyond current standings")
                            .font(.title3)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 40)
                    
                    Spacer()
                    
                    // Comparison Visual
                    VStack(spacing: 24) {
                        // Current vs Predicted Toggle
                        HStack {
                            Text(showPrediction ? "Final Prediction" : "Current Table")
                                .font(.headline)
                                .fontWeight(.semibold)
                            
                            Spacer()
                            
                            Button(action: {
                                withAnimation(.easeInOut(duration: 0.5)) {
                                    showPrediction.toggle()
                                }
                            }) {
                                HStack(spacing: 8) {
                                    Text(showPrediction ? "Show Current" : "Show Prediction")
                                    Image(systemName: "arrow.triangle.2.circlepath")
                                }
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundColor(.blue)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(Color.blue.opacity(0.1))
                                .cornerRadius(8)
                            }
                        }
                        
                        // Table View
                        VStack(spacing: 2) {
                            ForEach(0..<5, id: \.self) { index in
                                let (position, team, points, isHighlighted) = getTableData(index: index, showPrediction: showPrediction)
                                
                                HStack {
                                    // Position
                                    Text("\(position)")
                                        .font(.system(size: 16, weight: .bold, design: .monospaced))
                                        .foregroundColor(isHighlighted ? .blue : .primary)
                                        .frame(width: 24, alignment: .leading)
                                    
                                    // Team Name
                                    Text(team)
                                        .font(.system(size: 16, weight: isHighlighted ? .semibold : .medium))
                                        .foregroundColor(isHighlighted ? .blue : .primary)
                                    
                                    Spacer()
                                    
                                    // Points
                                    Text("\(points)")
                                        .font(.system(size: 16, weight: .bold, design: .monospaced))
                                        .foregroundColor(isHighlighted ? .blue : .secondary)
                                        .frame(width: 32, alignment: .trailing)
                                }
                                .padding(.horizontal, 16)
                                .padding(.vertical, 12)
                                .background(
                                    RoundedRectangle(cornerRadius: 8)
                                        .fill(isHighlighted ? Color.blue.opacity(0.1) : Color.clear)
                                )
                                .animation(.easeInOut(duration: 0.3), value: showPrediction)
                            }
                        }
                        .padding(16)
                        .background(
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Color(.systemBackground))
                                .shadow(radius: 2)
                        )
                        
                        // Explanation Text
                        VStack(spacing: 8) {
                            if showPrediction {
                                Text("Our algorithm analyzes:")
                                    .font(.headline)
                                    .fontWeight(.semibold)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Image(systemName: "chart.line.uptrend.xyaxis")
                                            .foregroundColor(.blue)
                                            .frame(width: 20)
                                        Text("Current form and points per game")
                                    }
                                    
                                    HStack {
                                        Image(systemName: "calendar")
                                            .foregroundColor(.blue)
                                            .frame(width: 20)
                                        Text("Remaining fixtures and difficulty")
                                    }
                                    
                                    HStack {
                                        Image(systemName: "brain.head.profile")
                                            .foregroundColor(.blue)
                                            .frame(width: 20)
                                        Text("Historical performance patterns")
                                    }
                                }
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            } else {
                                Text("Current league table")
                                    .font(.headline)
                                    .fontWeight(.semibold)
                                
                                Text("Shows where teams are right now, but not where they're heading")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                            }
                        }
                        .multilineTextAlignment(.center)
                        .animation(.easeInOut(duration: 0.3), value: showPrediction)
                    }
                    .padding(.horizontal, 24)
                    
                    Spacer()
                }
            }
        }
        .onAppear {
            // Auto-animate to show prediction after a delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                withAnimation(.easeInOut(duration: 0.5)) {
                    showPrediction = true
                }
            }
        }
    }
    
    private func getTableData(index: Int, showPrediction: Bool) -> (Int, String, Int, Bool) {
        if showPrediction {
            // Predicted final table
            switch index {
            case 0: return (1, "Millfield Rangers", 89, true)
            case 1: return (2, "Cromwell City", 87, true)
            case 2: return (3, "Thornbury FC", 82, false)
            case 3: return (4, "Redwood City", 68, true)
            case 4: return (5, "Whitmore United", 65, false)
            default: return (1, "", 0, false)
            }
        } else {
            // Current table
            switch index {
            case 0: return (1, "Cromwell City", 63, true)
            case 1: return (2, "Millfield Rangers", 61, true)
            case 2: return (3, "Thornbury FC", 59, false)
            case 3: return (4, "Whitmore United", 47, false)
            case 4: return (5, "Redwood City", 44, true)
            default: return (1, "", 0, false)
            }
        }
    }
}

#Preview {
    ForecastExplanationScreen()
}