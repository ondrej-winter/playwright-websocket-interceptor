from playwright.sync_api import Page

def test_default(page):
    page.goto("http://localhost:8000/")
    page.wait_for_timeout(8_000)

def test_constant_mid_run(page: Page, ws_behavior):
    page.goto("http://localhost:8000/")
    page.wait_for_timeout(4_000)

    current_value = page.locator("css=#current-value").inner_html()
    ws_behavior.set_mode("constant", const=float(current_value))
    page.wait_for_timeout(8_000)

def test_increasing_then_decreasing(page, ws_behavior):
    page.goto("http://localhost:8000")
    page.wait_for_timeout(4_000)

    current_value = page.locator("css=#current-value").inner_html()
    ws_behavior.set_mode("increasing", start=float(current_value), step=5.0)
    page.wait_for_timeout(8_000)

    current_value = page.locator("css=#current-value").inner_html()
    ws_behavior.set_mode("decreasing", start=float(current_value), step=10.0)
    page.wait_for_timeout(8_000)