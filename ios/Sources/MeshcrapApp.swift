import SwiftUI
import WebKit
import UIKit

@main struct MeshcrapApp: App {
    var body: some Scene { WindowGroup { DashboardScreen() } }
}

struct DashboardScreen: View {
    @AppStorage("dashboardURL") private var savedAddress = ""
    @StateObject private var browser = DashboardBrowser()
    @State private var editing = false
    @State private var address = ""
    @State private var invalid = false
    @State private var confirmForget = false
    @State private var forgetting = false
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if browser.loading { ProgressView().padding(8).accessibilityLabel("Loading dashboard") }
                if let message = browser.error {
                    Text(message).font(.callout).padding().accessibilityAddTraits(.isStaticText)
                }
                if browser.base == nil {
                    VStack(spacing: 16) {
                        Image(systemName: "antenna.radiowaves.left.and.right").font(.largeTitle)
                        Text("Your mesh, on your iPhone").font(.title2)
                        Text("Connect to your existing private HTTPS dashboard. Keep Tailscale connected if your dashboard requires it.")
                        Button("Connect dashboard") { address = savedAddress; editing = true }.buttonStyle(.borderedProminent)
                        Text("Dashboard and controls • Bluetooth surveys are not included.").font(.footnote)
                    }.padding()
                } else { DashboardWebView(browser: browser) }
            }
            .navigationTitle("Meshcrap").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItemGroup(placement: .bottomBar) {
                    Button { browser.web.goBack() } label: { Label("Back", systemImage: "chevron.left") }.disabled(!browser.canGoBack)
                    Spacer()
                    Button { browser.web.reload() } label: { Label("Reload", systemImage: "arrow.clockwise") }.disabled(browser.base == nil)
                    Spacer()
                    Button { address = savedAddress; editing = true } label: { Label("Settings", systemImage: "gearshape") }
                }
            }
            .sheet(isPresented: $editing) {
                NavigationStack {
                    Form {
                        Section("Private dashboard address") {
                            TextField("https://collector.example", text: $address).keyboardType(.URL)
                                .textInputAutocapitalization(.never).autocorrectionDisabled()
                            Text("Use the HTTPS origin only—no password, key, path or query parameters.").font(.footnote)
                            if invalid { Text("Enter a valid HTTPS dashboard address.").foregroundColor(.red) }
                        }
                        Section {
                            Text("Unlock controls inside the dashboard with your existing key. This app does not bypass dashboard permissions or issue commands on its own.")
                            Text("Website sessions stay on this device. Lock controls before sharing your phone, or forget the dashboard to remove its saved website data.")
                            if let base = browser.base { Link("Open dashboard in Safari", destination: base) }
                            if !savedAddress.isEmpty {
                                Button("Forget dashboard and sign out", role: .destructive) { confirmForget = true }
                                    .disabled(forgetting)
                            }
                        }
                    }
                    .navigationTitle("Connection")
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) { Button("Cancel") { editing = false; invalid = false } }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Connect") {
                                guard let url = DashboardAddress.parse(address) else { invalid = true; return }
                                savedAddress = url.absoluteString; invalid = false; editing = false; browser.connect(url)
                            }.disabled(forgetting)
                        }
                    }
                    .confirmationDialog("Remove this app's saved dashboard address and all website data?", isPresented: $confirmForget, titleVisibility: .visible) {
                        Button("Forget and sign out", role: .destructive) {
                            forgetting = true
                            browser.forget {
                                savedAddress = ""; address = ""; invalid = false; forgetting = false; editing = false
                            }
                        }
                    } message: {
                        Text("This clears this app's cookies and saved website sessions. It does not change the collector, other phones or Safari.")
                    }
                }
            }
            .onAppear { if !forgetting, browser.base == nil, let url = DashboardAddress.parse(savedAddress) { browser.connect(url) } }
        }
    }
}

struct DashboardWebView: UIViewRepresentable {
    let browser: DashboardBrowser
    func makeUIView(context: Context) -> WKWebView { browser.web }
    func updateUIView(_ uiView: WKWebView, context: Context) {} // Never reload on SwiftUI refresh.
}

final class DashboardBrowser: NSObject, ObservableObject, WKNavigationDelegate, WKUIDelegate {
    private(set) var web = WKWebView(frame: .zero)
    private var resetting = false
    private var resetCompletions: [() -> Void] = []
    @Published var base: URL?
    @Published var loading = false
    @Published var canGoBack = false
    @Published var error: String?
    override init() {
        super.init(); configureWebView()
    }
    private func configureWebView() {
        web.navigationDelegate = self; web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = true
    }
    func connect(_ url: URL) {
        guard !resetting else { return }
        base = url; error = nil; web.load(URLRequest(url: url))
    }
    func forget(completion: @escaping () -> Void) {
        resetCompletions.append(completion)
        guard !resetting else { return }
        resetting = true
        let store = web.configuration.websiteDataStore
        web.navigationDelegate = nil; web.uiDelegate = nil
        web.stopLoading(); base = nil; loading = false; canGoBack = false; error = nil
        store.removeData(ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(), modifiedSince: .distantPast) {
            DispatchQueue.main.async {
                // Do not attach another page to the default store while its data is being removed.
                // Replacing the view then releases the old page, navigation history and timers.
                self.web = WKWebView(frame: .zero); self.configureWebView()
                self.resetting = false
                let completions = self.resetCompletions; self.resetCompletions.removeAll()
                completions.forEach { $0() }
            }
        }
    }
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) { guard base != nil else { return }; loading = true; error = nil }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { guard base != nil else { return }; loading = false; canGoBack = webView.canGoBack }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { failed(error) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { failed(error) }
    private func failed(_ failure: Error) {
        guard base != nil else { return }
        loading = false
        if (failure as NSError).code != NSURLErrorCancelled { error = "Unable to load your dashboard. Check its address, certificate and private-network connection, then reload." }
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url, let base = base, DashboardAddress.sameOrigin(url, base) else {
            decisionHandler(.cancel); error = "This link leaves your configured dashboard. Open the dashboard in Safari to follow external links."; return
        }
        if action.targetFrame == nil { decisionHandler(.cancel); web.load(action.request); return }
        decisionHandler(.allow)
    }
    private func presenter() -> UIViewController? {
        var controller = web.window?.rootViewController
        while let next = controller?.presentedViewController { controller = next }
        return controller
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        guard let controller = presenter() else { completionHandler(false); return }
        let dialog = UIAlertController(title: "Dashboard confirmation", message: message, preferredStyle: .alert)
        dialog.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
        dialog.addAction(UIAlertAction(title: "Continue", style: .default) { _ in completionHandler(true) })
        controller.present(dialog, animated: true)
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        guard let controller = presenter() else { completionHandler(); return }
        let dialog = UIAlertController(title: "Dashboard", message: message, preferredStyle: .alert)
        dialog.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() }); controller.present(dialog, animated: true)
    }
}
