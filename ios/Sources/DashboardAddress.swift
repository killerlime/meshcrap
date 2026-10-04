import Foundation

enum DashboardAddress {
    static func parse(_ text: String) -> URL? {
        guard let parts = URLComponents(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              parts.scheme?.lowercased() == "https", let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path.isEmpty || parts.path == "/",
              parts.port == nil || (1...65535).contains(parts.port!),
              let url = parts.url else { return nil }
        return url
    }
    static func sameOrigin(_ url: URL, _ base: URL) -> Bool {
        url.scheme?.lowercased() == "https" && url.user == nil && url.password == nil &&
        url.host?.lowercased() == base.host?.lowercased() && (url.port ?? 443) == (base.port ?? 443)
    }
}
