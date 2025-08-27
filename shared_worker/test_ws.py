from playwright.sync_api import Page

def test_shared_worker_chart(page: Page):
    page.goto("http://localhost:8000")
    page.wait_for_timeout(10_000)

    # Switch interception mode at runtime
    page.evaluate("() => { window.__ws_intercept__.mode = 'constant' }")
    page.evaluate("() => { window.__ws_intercept__.constant = 123.45 }")

    # Now all WS/SharedWorker messages with a `value` field will be rewritten to 123.45
    page.wait_for_timeout(10_000)

    # Change to increasing mode (start at 0.0, step 0.5)
    page.evaluate("""() => {
        const cfg = window.__ws_intercept__;
        cfg.mode = 'increasing';
        cfg.start = 0.0;
        cfg.step = 5;
        cfg.current = 0.0;
    }""")

    page.wait_for_timeout(15_000)
