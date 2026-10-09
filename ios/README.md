# Meshcrap for iPhone and iPad — native source preview

Dashboard and controls first. This SwiftUI app hosts the existing dashboard in Apple's WKWebView, preserving the dashboard's permissions, confirmation dialogs and current features. Bluetooth surveying is not included.

**Status: native source preview with unsigned simulator build and URL/origin tests configured in CI. No signed IPA, physical-device validation or App Store release exists.** The development workspace is Windows and has no Xcode. A green **iOS simulator checks** result on the exact commit is the evidence for compilation and XCTest success; configuring the workflow alone does not establish either. Use the existing Safari Add to Home Screen option today, or build this project on a Mac.

## Build on a Mac

1. Install Xcode and the iOS simulator components. Install [XcodeGen](https://github.com/yonaskolb/XcodeGen) following its own instructions.
2. In this directory run `xcodegen generate` and open `Meshcrap.xcodeproj`.
3. Select the Meshcrap scheme and an iPhone simulator. Run Product → Test, then Run.
4. For a real iPhone, select your own signing team and unique bundle identifier in Signing & Capabilities. Keep certificates, profiles and credentials outside this repository. Distribution/TestFlight requires appropriate Apple signing access.
5. Enter your dashboard's HTTPS origin, without credentials, paths or query parameters. Connect your private network/Tailscale separately. Unlock controls inside the dashboard using its existing mechanism.

Command-line simulator build: `xcodebuild -project Meshcrap.xcodeproj -scheme Meshcrap -sdk iphonesimulator -configuration Debug CODE_SIGNING_ALLOWED=NO build`. Run tests with an available simulator destination selected from `xcodebuild -showdestinations`.

## Security and behavior

- Only HTTPS dashboard origins are accepted; embedded credentials are rejected. Navigation stays on the configured origin. External links/download flows can be handled by opening the dashboard in Safari through Settings.
- Default system TLS verification remains intact. No certificate bypass, ATS exception, JavaScript-to-native command bridge or hardcoded dashboard address/key.
- Only the dashboard address is stored by the shell. WebKit retains the website's own sessions/cookies, separately from Safari. Use dashboard lock/sign-out controls before sharing a phone. Switching addresses does not erase existing website sessions; **Settings → Forget dashboard and sign out** removes the saved address and all website data in this app, including sessions retained from previous addresses. It also releases the old page and its navigation history. Safari and other devices are unaffected.
- Refresh is user-triggered; SwiftUI updates do not reload the page. The dashboard retains its normal polling. No native background polling or radio commands are added.
- iOS local-network permission may be requested for LAN access. No Bluetooth or location permission is requested by the native shell.
- The privacy manifest declares app-local UserDefaults use. No analytics SDK or app-operated tracking service is included. A deployment's dashboard and optional providers have their own network/privacy behavior; review that before distribution.

## Validation still required

The `iOS simulator checks` workflow generates the project on a macOS runner, builds without a signing identity and runs the XCTest URL/origin cases. Its result bundle is retained for seven days. Check that workflow on the exact revision being reviewed. No real dashboard credentials, pairing tokens or network hosts are provided to CI.

Check iPhone and iPad layouts, VoiceOver, keyboard entry, local-network/Tailscale access, trusted TLS, server-unavailable recovery, session persistence/removal, control confirmations and external-link blocking on a device. Test controls with a synthetic/test collector before real radios. Review privacy disclosures, app icon, signing and distribution requirements before any public release. Simulator compilation, source review and a valid plist are not substitutes for these checks.

## Sources and licensing

Original app source uses the repository [LICENSE](../LICENSE). Runtime dependencies are Apple's SwiftUI, UIKit, Foundation and WebKit frameworks, provided by the SDK/OS; no third-party runtime packages are embedded. XcodeGen is an optional project-generation tool (MIT), not bundled in the app.

References: [Apple WKNavigationDelegate](https://developer.apple.com/documentation/webkit/wknavigationdelegate), [Apple UserDefaults privacy reasons](https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacyaccessedapitypes/nsprivacyaccessedapitype), [XcodeGen project specification](https://github.com/yonaskolb/XcodeGen/blob/master/Docs/ProjectSpec.md).
