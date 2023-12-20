#!/usr/bin/env swift
import Foundation
print()
if let path = ProcessInfo.processInfo.environment["PATH"] {
    path.components(separatedBy: ":").forEach { print("\t\($0)") }
}
print()