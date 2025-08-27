from playwright.sync_api import Page


def test_shared_worker_chart(page: Page):
    page.goto("https://staging-my.simuxm.com/")
    page.click('xpath=//button[contains(text(), "Accept All")]')
    page.fill('xpath=//input[@inputmode="email"]', 'qaf564cb10@xm.com')
    page.fill('xpath=//input[@type="password"]', 'Password$123')
    page.click('xpath=//button[@type="submit"]')
    page.wait_for_timeout(2_000)
    page.goto('https://staging-my.simuxm.com/symbol-info/GOLDm%23')

    # # Switch interception mode at runtime
    # page.evaluate("() => { window.__ws_intercept__.mode = 'constant' }")
    # page.evaluate("() => { window.__ws_intercept__.constant = 123.45 }")
    #
    # # Now all WS/SharedWorker messages with a `value` field will be rewritten to 123.45
    # page.wait_for_timeout(10_000)
    #
    # # Change to increasing mode (start at 0.0, step 0.5)
    # page.evaluate("""() => {
    #     const cfg = window.__ws_intercept__;
    #     cfg.mode = 'increasing';
    #     cfg.start = 0.0;
    #     cfg.step = 5;
    #     cfg.current = 0.0;
    # }""")

    page.wait_for_timeout(150_000)


a = {"messages": [{"ts": {"tk": {"sl": "GOLDm#", "ba": [3382.16, 3382.39], "tt": "2025-08-27T12:33:18.776Z"},
                          "tc": {"id": {"msb": "14848903807473306924", "lsb": "9267597542865988793"},
                                 "tt": "2025-08-27T12:33:18.779Z"}, "sid": 50}}],
     "tc": {"id": {"msb": "234685002014671684", "lsb": "10356922026948632816"}, "tt": "2025-08-27T12:33:18.796810344Z"}}
