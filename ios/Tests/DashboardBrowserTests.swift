import XCTest
import WebKit
@testable import Meshcrap

final class DashboardBrowserTests: XCTestCase {
    @MainActor func testForgetRemovesWebsiteSessionAndOldView() async {
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
            store.httpCookieStore.getAllCookies { before in
                XCTAssertTrue(before.contains { $0.name == "test_session" && $0.domain == "collector.example" })
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
        }
        // Yield the main actor while WebKit and the completion handler make progress.
        await fulfillment(of: [done], timeout: 10)
    }
}
