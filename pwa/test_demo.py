def test_ticks(page):
    page.goto("http://localhost:8000")

    # make GOLDm# tick use a constant mid-price, ba = [1234.5, 1234.5]
    page.evaluate("""() => {
      const c = window.__ws_intercept__;
      c.mode = 'constant';
      c.constant = 1234.5;
      c.targetSymbol = 'GOLDm#';    // optional; defaults to GOLDm#
      c.baMode = 'same';            // or 'spread'
    }""")

    # switch to increasing series and widen the book via spread
    page.evaluate("""() => {
      const c = window.__ws_intercept__;
      c.mode = 'increasing';
      c.start = 1000;
      c.step = 2.5;
      c.current = 1000;
      c.baMode = 'spread';
      c.spreadDelta = 3;            // ba becomes [target-3, target+3]
    }""")
