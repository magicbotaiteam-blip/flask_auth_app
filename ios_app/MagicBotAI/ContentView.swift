import SwiftUI
import WebKit

struct ContentView: View {
    @State private var isLoading = true
    @State private var progress: Double = 0
    @State private var canGoBack = false
    @State private var showError = false
    
    // Change this to your server URL
    private let homeURL = "http://192.168.1.213:5000"
    
    var body: some View {
        NavigationStack {
            ZStack {
                WebViewContainer(
                    urlString: homeURL,
                    isLoading: $isLoading,
                    progress: $progress,
                    canGoBack: $canGoBack,
                    showError: $showError
                )
                .ignoresSafeArea()
                
                if isLoading {
                    VStack {
                        ProgressView(value: progress)
                            .progressViewStyle(LinearProgressViewStyle())
                            .tint(Color(red: 0.4, green: 0.23, blue: 0.93))
                            .padding(.top, 0)
                        Spacer()
                    }
                    .transition(.opacity)
                }
                
                if showError {
                    ErrorView(url: homeURL) {
                        showError = false
                        isLoading = true
                    }
                }
            }
            .toolbar {
                ToolbarItemGroup(placement: .navigation) {
                    if canGoBack {
                        Button(action: goBack) {
                            Image(systemName: "chevron.left")
                                .font(.title3)
                        }
                    }
                }
                ToolbarItemGroup(placement: .primaryAction) {
                    Button(action: reload) {
                        Image(systemName: "arrow.clockwise")
                            .font(.title3)
                    }
                }
            }
            .toolbarBackground(Color(red: 0.06, green: 0.09, blue: 0.16), for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .preferredColorScheme(.dark)
    }
    
    private func goBack() {
        NotificationCenter.default.post(name: .goBack, object: nil)
    }
    
    private func reload() {
        NotificationCenter.default.post(name: .reloadPage, object: nil)
        showError = false
        isLoading = true
    }
}

struct WebViewContainer: UIViewRepresentable {
    let urlString: String
    @Binding var isLoading: Bool
    @Binding var progress: Double
    @Binding var canGoBack: Bool
    @Binding var showError: Bool
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        config.defaultWebpagePreferences = preferences
        config.preferences.javaScriptCanOpenWindowsAutomatically = false
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.refreshControl = UIRefreshControl()
        webView.scrollView.refreshControl?.addTarget(
            context.coordinator,
            action: #selector(Coordinator.handleRefresh),
            for: .valueChanged
        )
        webView.backgroundColor = UIColor(red: 0.06, green: 0.09, blue: 0.16, alpha: 1)
        webView.isOpaque = false
        
        // Add observers
        webView.addObserver(context.coordinator, forKeyPath: #keyPath(WKWebView.estimatedProgress), options: .new, context: nil)
        webView.addObserver(context.coordinator, forKeyPath: #keyPath(WKWebView.title), options: .new, context: nil)
        
        // Load URL
        if let url = URL(string: urlString) {
            webView.load(URLRequest(url: url))
        }
        
        // Listen for commands
        NotificationCenter.default.addObserver(
            context.coordinator,
            selector: #selector(Coordinator.goBack),
            name: .goBack,
            object: nil
        )
        NotificationCenter.default.addObserver(
            context.coordinator,
            selector: #selector(Coordinator.reload),
            name: .reloadPage,
            object: nil
        )
        
        return webView
    }
    
    func updateUIView(_ uiView: WKWebView, context: Context) {}
    
    class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var parent: WebViewContainer
        weak var webView: WKWebView?
        
        init(_ parent: WebViewContainer) {
            self.parent = parent
        }
        
        override func observeValue(forKeyPath keyPath: String?, of object: Any?, change: [NSKeyValueChangeKey: Any]?, context: UnsafeMutableRawPointer?) {
            guard let webView = object as? WKWebView else { return }
            
            if keyPath == #keyPath(WKWebView.estimatedProgress) {
                parent.progress = Double(webView.estimatedProgress)
                if webView.estimatedProgress >= 1.0 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                        self.parent.isLoading = false
                    }
                }
            }
            
            if keyPath == #keyPath(WKWebView.title) {
                parent.canGoBack = webView.canGoBack
            }
        }
        
        @objc func handleRefresh() {
            webView?.reload()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                self.webView?.scrollView.refreshControl?.endRefreshing()
            }
        }
        
        @objc func goBack() {
            if webView?.canGoBack == true {
                webView?.goBack()
            }
        }
        
        @objc func reload() {
            webView?.reload()
        }
        
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.isLoading = true
            parent.showError = false
        }
        
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.isLoading = false
            parent.canGoBack = webView.canGoBack
            webView.scrollView.refreshControl?.endRefreshing()
        }
        
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            webView.scrollView.refreshControl?.endRefreshing()
        }
        
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            parent.showError = true
            webView.scrollView.refreshControl?.endRefreshing()
        }
        
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.cancel)
                return
            }
            
            // Open external URLs in Safari
            if url.absoluteString.hasPrefix("http") &&
               !url.absoluteString.contains("192.168.1.213") &&
               !url.absoluteString.contains("localhost") &&
               !url.absoluteString.contains("127.0.0.1") {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
                return
            }
            
            decisionHandler(.allow)
        }
        
        // Allow new windows to open in same WebView
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if navigationAction.targetFrame == nil {
                webView.load(navigationAction.request)
            }
            return nil
        }
        
        deinit {
            if let webView = webView {
                webView.removeObserver(self, forKeyPath: #keyPath(WKWebView.estimatedProgress))
                webView.removeObserver(self, forKeyPath: #keyPath(WKWebView.title))
            }
            NotificationCenter.default.removeObserver(self)
        }
    }
}

struct ErrorView: View {
    let url: String
    let onRetry: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "antenna.radiowaves.left.and.right.slash")
                .font(.system(size: 60))
                .foregroundColor(Color(red: 0.38, green: 0.64, blue: 0.96))
            
            Text("Can't Reach Server")
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(.white)
            
            Text("Make sure your Mac is running the app and you're on the same Wi-Fi network.")
                .font(.body)
                .foregroundColor(Color(red: 0.58, green: 0.64, blue: 0.72))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            
            Button(action: onRetry) {
                Text("Try Again")
                    .fontWeight(.semibold)
                    .font(.body)
                    .padding(.horizontal, 40)
                    .padding(.vertical, 14)
                    .background(Color(red: 0.23, green: 0.51, blue: 0.96))
                    .foregroundColor(.white)
                    .cornerRadius(12)
            }
            
            Text("Server: \(url)")
                .font(.caption)
                .foregroundColor(Color(red: 0.39, green: 0.45, blue: 0.53))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(red: 0.06, green: 0.09, blue: 0.16))
    }
}

extension Notification.Name {
    static let goBack = Notification.Name("goBack")
    static let reloadPage = Notification.Name("reloadPage")
}

#Preview {
    ContentView()
}
