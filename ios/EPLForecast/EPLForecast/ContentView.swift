import SwiftUI

struct ContentView: View {
    @StateObject private var eplService = EPLService()
    
    var body: some View {
        TableView(eplService: eplService)
    }
}

#Preview {
    ContentView()
}