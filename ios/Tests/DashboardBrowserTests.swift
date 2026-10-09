import XCTest
import WebKit
@testable import Meshcrap

final class DashboardBrowserTests: XCTestCase {
    @MainActor func testForgetRemovesWebsiteSessionAndOldView() {
        let done = expectation(description: "Website data removed")
        let browser = DashboardBrowser()
        let oldView = browser.web
        browser.base = DashboardAddress.parse("https://collector.example")!
        let cookie = HTTPCookie(properties: [
            .domain: "collector.example", .path: "/", .name: "test_session",
            .value: "synthetic-session", .secure: "TRUE", .expires: Date().addingTimeInterval(60)
        ])!
        let store = oldView.configuration.websiteDataStore
        store.httpCookieStore.setCookie(cookie) {
            browser.forget {
                XCTAssertNil(browser.base)
                XCTAssertFalse(browser.loading)
                XCTAssertFalse(browser.canGoBack)
                XCTAssertNil(browser.error)
                XCTAssertFalse(browser.web === oldView)
                store.httpCookieStore.getAllCookies { cookies in
                    XCTAssertFalse(cookies.contains { $0.name == "test_session" && $0.domain == "collector.example" })
                    done.fulfill()
                }
            }
        }
        wait(for: [done], timeout: 10)
    }
}
