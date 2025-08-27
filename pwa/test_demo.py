# def test_ticks(page):
#     page.goto("https://staging-my.simuxm.com/")
#     page.click('xpath=//button[contains(text(), "Accept All")]')
#     page.fill('xpath=//input[@inputmode="email"]', 'qaf564cb10@xm.com')
#     page.fill('xpath=//input[@type="password"]', 'Password$123')
#     page.click('xpath=//button[@type="submit"]')
#     page.wait_for_timeout(2_000)
#     page.goto('https://staging-my.simuxm.com/symbol-info/GOLDm%23')
#
#     # make GOLDm# tick use a constant mid-price, ba = [1234.5, 1234.5]
#     page.evaluate("""() => {
#       const c = window.__ws_intercept__;
#       c.mode = 'constant';
#       c.constant = 1234.5;
#       c.targetSymbol = 'GOLDm#';    // optional; defaults to GOLDm#
#       c.baMode = 'same';            // or 'spread'
#     }""")
#
#     page.wait_for_timeout(20_000)
#
#     # switch to increasing series and widen the book via spread
#     page.evaluate("""() => {
#       const c = window.__ws_intercept__;
#       c.mode = 'increasing';
#       c.start = 1000;
#       c.step = 2.5;
#       c.current = 1000;
#       c.baMode = 'spread';
#       c.spreadDelta = 3;            // ba becomes [target-3, target+3]
#     }""")
#
#     page.wait_for_timeout(2_000_000)


def test_ticks(page):
    page.goto("https://staging-my.simuxm.com/")
    page.click('xpath=//button[contains(text(), "Accept All")]')
    page.fill('xpath=//input[@inputmode="email"]', 'qaf564cb10@xm.com')
    page.fill('xpath=//input[@type="password"]', 'Password$123')
    page.click('xpath=//button[@type="submit"]')
    page.wait_for_timeout(2_000)

    page.wait_for_timeout(2_000_000)