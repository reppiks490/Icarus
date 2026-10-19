from types import SimpleNamespace

from icarus_engine.runtime import Portfolio


class _Stop:
    def __init__(self):
        self.delays = []

    def is_set(self):
        return False

    def wait(self, delay):
        self.delays.append(delay)
        return False


class _Journal:
    def __init__(self):
        self.rows = []

    def log(self, level, message):
        self.rows.append((level, message))


def test_startup_warmup_retries_transient_failure_without_marking_ready():
    portfolio = Portfolio.__new__(Portfolio)
    portfolio._stop = _Stop()
    portfolio.journal = _Journal()

    class Runner:
        symbol = "YM"
        spec = SimpleNamespace(kind="futures", feed="yahoo")
        warm = False
        bar_index = -1
        errors = 0
        last_error = ""
        runtime_error = ""
        feed_error = ""

        def __init__(self):
            self.attempts = 0
            self.resets = 0

        def warmup(self):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("temporary provider throttle")
            self.bar_index = 0
            self.warm = True

        def reset_failed_startup_warmup(self):
            self.resets += 1
            self.bar_index = -1
            self.warm = False

    runner = Runner()
    assert portfolio._warmup_with_retry(runner) is True
    assert runner.attempts == 2
    assert runner.resets == 1
    assert runner.errors == 1
    assert runner.warm is True
    assert runner.last_error == ""
    assert portfolio._stop.delays == [5.0]
    assert "retrying in 5s" in portfolio.journal.rows[0][1]
