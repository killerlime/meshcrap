import XCTest
@testable import Meshcrap

final class DashboardAddressTests: XCTestCase {
    func testRejectCredentialsAndNonHTTPS() {
        for text in ["http://collector.example", "file:///etc/hosts", "javascript:alert(1)", "https://user:password@collector.example", "https://user@collector.example", "https://collector.example/?key=test", "https://collector.example/path", "https://collector.example/#fragment", "https://collector.example:0", "https://collector.example:65536", "https://"] {
            XCTAssertNil(DashboardAddress.parse(text))
        }
    }
    func testOriginIncludesPort() {
        let base = DashboardAddress.parse("https://collector.example")!
        XCTAssertTrue(DashboardAddress.sameOrigin(URL(string: "https://collector.example:443/nodes")!, base))
        XCTAssertFalse(DashboardAddress.sameOrigin(URL(string: "https://collector.example:8443/")!, base))
        XCTAssertFalse(DashboardAddress.sameOrigin(URL(string: "https://other.example/")!, base))
        XCTAssertFalse(DashboardAddress.sameOrigin(URL(string: "http://collector.example/")!, base))
        XCTAssertFalse(DashboardAddress.sameOrigin(URL(string: "https://collector.example.other.example/")!, base))
        XCTAssertFalse(DashboardAddress.sameOrigin(URL(string: "https://user@collector.example/")!, base))
    }
    func testTrimAndPreservePrivateHTTPSOrigin() {
        let base = DashboardAddress.parse(" \nhttps://collector.example:8443/ \n")!
        XCTAssertEqual(base.port, 8443)
        XCTAssertTrue(DashboardAddress.sameOrigin(URL(string: "https://COLLECTOR.example:8443/#view=nodes")!, base))
        XCTAssertFalse(DashboardAddress.sameOrigin(URL(string: "https://collector.example/nodes")!, base))
    }
}
