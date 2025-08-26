// swift-tools-version: 5.9
// This Package.swift file is for managing dependencies via Swift Package Manager

import PackageDescription

let package = Package(
    name: "EPLForecast",
    platforms: [
        .iOS(.v15)
    ],
    dependencies: [
        // New Relic iOS Agent
        .package(url: "https://github.com/newrelic/newrelic-ios-agent-spm", from: "7.0.0")
    ],
    targets: [
        .target(
            name: "EPLForecast",
            dependencies: [
                .product(name: "NewRelic", package: "newrelic-ios-agent-spm")
            ]
        )
    ]
)