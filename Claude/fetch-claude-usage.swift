#!/usr/bin/env swift

import Foundation
import Security

func readFromKeychain(service: String, account: String) -> String? {
    let query: [CFString: Any] = [
        kSecClass:       kSecClassGenericPassword,
        kSecAttrService: service,
        kSecAttrAccount: account,
        kSecReturnData:  true,
        kSecMatchLimit:  kSecMatchLimitOne,
    ]
    var result: AnyObject?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    guard status == errSecSuccess,
          let data = result as? Data,
          let value = String(data: data, encoding: .utf8) else { return nil }
    return value.trimmingCharacters(in: .whitespacesAndNewlines)
}

func fetchUsageData(sessionKey: String, orgId: String) async throws -> (utilization: Int, resetsAt: String?) {
    guard !orgId.contains(".."), !orgId.contains("/") else {
        throw NSError(domain: "ClaudeAPI", code: 5, userInfo: [NSLocalizedDescriptionKey: "Invalid organization ID"])
    }
    guard let url = URL(string: "https://claude.ai/api/organizations/\(orgId)/usage") else {
        throw NSError(domain: "ClaudeAPI", code: 0, userInfo: [NSLocalizedDescriptionKey: "Invalid URL"])
    }
    var request = URLRequest(url: url)
    request.setValue("sessionKey=\(sessionKey)", forHTTPHeaderField: "Cookie")
    request.setValue("application/json", forHTTPHeaderField: "Accept")
    request.httpMethod = "GET"

    let (data, response) = try await URLSession.shared.data(for: request)
    guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
        throw NSError(domain: "ClaudeAPI", code: 3, userInfo: [NSLocalizedDescriptionKey: "Failed to fetch usage"])
    }
    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
       let fiveHour = json["five_hour"] as? [String: Any],
       let utilization = fiveHour["utilization"] as? Int {
        let resetsAt = fiveHour["resets_at"] as? String
        return (utilization, resetsAt)
    }
    throw NSError(domain: "ClaudeAPI", code: 4, userInfo: [NSLocalizedDescriptionKey: "Invalid response format"])
}

Task {
    guard let sessionKey = readFromKeychain(service: "claude-usage", account: "session-key") else {
        print("ERROR:NO_SESSION_KEY")
        exit(1)
    }
    guard let orgId = readFromKeychain(service: "claude-usage", account: "org-id") else {
        print("ERROR:NO_ORG_CONFIGURED")
        exit(1)
    }
    do {
        let (utilization, resetsAt) = try await fetchUsageData(sessionKey: sessionKey, orgId: orgId)
        print("\(utilization)|\(resetsAt ?? "")")
        exit(0)
    } catch {
        print("ERROR:\(error.localizedDescription)")
        exit(1)
    }
}

RunLoop.main.run()
