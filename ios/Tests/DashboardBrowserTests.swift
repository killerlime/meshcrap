import XCTest
import WebKit
@testable import Meshcrap

final class DashboardBrowserTests: XCTestCase {
    @MainActor func testForgetRemovesWebsiteSessionAndOldView() async {
        let browser = DashboardBrowser()
        let oldView = browser.web
        browser.base = DashboardAddress.parse("https://collector.example")!
        let cookie = HTTPCookie(properties: [
            .domain: "collector.example", .path: "/", .name: "test_session",
            .value: "synthetic-session", .secure: "TRUE", .expires: Date().addingTimeInterval(60)
        ])!
        let store = oldView.configuration.websiteDataStore
        let written = expectation(description: "Session cookie written")
        var cookieWritten = false
        store.httpCookieStore.setCookie(cookie) {
            cookieWritten = true; written.fulfill()
        }
        await fulfillment(of: [written], timeout: 10)
        guard cookieWritten else { return }

        let seeded = expectation(description: "Session cookie read before removal")
        var before: [HTTPCookie]?
        store.httpCookieStore.getAllCookies { cookies in before = cookies; seeded.fulfill() }
        await fulfillment(of: [seeded], timeout: 10)
        guard let before else { return }
        XCTAssertTrue(before.contains { $0.name == "test_session" && $0.domain == "collector.example" })

        let cleared = expectation(description: "Website data removal completed")
        let repeated = expectation(description: "Repeated removal shares the pending cleanup")
        var removalCompleted = false
        browser.forget { removalCompleted = true; cleared.fulfill() }
        browser.connect(DashboardAddress.parse("https://other.example")!)
        XCTAssertNil(browser.base, "A reconnect must not recreate the session during cleanup")
        browser.forget { repeated.fulfill() }
        // Each stage yields the main actor and has its own unchanged timeout.
        await fulfillment(of: [cleared, repeated], timeout: 10)
        guard removalCompleted else { return }
        XCTAssertNil(browser.base)
        XCTAssertFalse(browser.loading)
        XCTAssertFalse(browser.canGoBack)
        XCTAssertNil(browser.error)
        XCTAssertFalse(browser.web === oldView)

        let checked = expectation(description: "Session cookie read after removal")
        var after: [HTTPCookie]?
        store.httpCookieStore.getAllCookies { cookies in after = cookies; checked.fulfill() }
        await fulfillment(of: [checked], timeout: 10)
        guard let after else { return }
        XCTAssertFalse(after.contains { $0.name == "test_session" && $0.domain == "collector.example" })
    }
}
