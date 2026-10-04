import XCTest
@testable import Meshcrap

final class DashboardAddressTests: XCTestCase {
    func testRejectCredentialsAndNonHTTPS() {
        for text in ["http://collector.example", "https://user:password@collector.example", "https://collector.example/?key=test", "https://collector.example/path", "https://collector.example/#fragment"] {
            XCTAssertNil(DashboardAddress.parse(text))
        }
    }
    func testOriginIncludesPort() {
        let base = DashboardAddress.parse("https://collector.example")!
        XCTAssertTrue(DashboardAddress.sameOrigin(URL(string: "https://collector.example:443/nodes")!, base))
        XCTAssertFalse(DashboardAddress.sameOrigin(URL(string: "https://collector.example:8443/")!, base))
        XCTAssertFalse(DashboardAddress.sameOrigin(URL(string: "https://other.example/")!, base))
    }
}
