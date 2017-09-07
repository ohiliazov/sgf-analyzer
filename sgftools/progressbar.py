import sys
import datetime


class ProgressBar(object):
    def __init__(self, min_value=0, max_value=100, width=50, frequency=1, stream=sys.stderr):
        self.max_value = max_value
        self.min_value = min_value
        self.value = min_value

        self.message = None
        self.width = width
        self.stream = stream
        self.update_cnt = 0
        self.frequency = frequency

        self.start_time = datetime.datetime.now()

    def start(self):
        self.start_time = datetime.datetime.now()
        self.stream.write("\n")
        self.update(0, self.max_value)

    def estimate_time(self, percent):
        if percent == 0:
            return "Est..."

        n = datetime.datetime.now()
        delta = n - self.start_time
        time_seconds = delta.total_seconds()
        total_time = time_seconds / percent
        time_remaining = total_time - time_seconds

        hours = int(time_remaining / 3600)
        time_remaining -= hours * 3600
        minutes = int(time_remaining / 60)
        time_remaining -= minutes * 60
        seconds = int(time_remaining)

        return "%d:%02d:%02d" % (hours, minutes, seconds)

    def elapsed_time(self):

        n = datetime.datetime.now()
        delta = n - self.start_time

        time_elapsed = delta.total_seconds()

        hours = int(time_elapsed / 3600)
        time_elapsed -= hours * 3600
        minutes = int(time_elapsed / 60)
        time_elapsed -= minutes * 60
        seconds = int(time_elapsed)

        return "%d:%02d:%02d" % (hours, minutes, seconds)

    def update(self, value, max_value):
        self.value = value
        self.max_value = max_value

        D = float(self.max_value - self.min_value)
        if D == 0:
            percent = 1.0
        else:
            percent = float(self.value - self.min_value) / D
        bar_cnt = int(self.width * percent)

        bar_str = "=" * bar_cnt
        bar_str += " " * (self.width - bar_cnt)

        percent_str = "%0.2f" % (100.0 * percent)
        time_remaining = self.estimate_time(percent)

        if self.update_cnt == 0:
            self.stream.write("|%s| %6s%% | %s | %s / %s\n" % (bar_str, "done", "Est...", "done", "total"))

        if self.update_cnt % self.frequency == 0:
            if self.message is None:
                self.stream.write(
                    "|%s| %6s%% | %s | %d / %d\n" % (bar_str, percent_str, time_remaining, value, self.max_value))
            else:
                self.stream.write("|%s| %6s%% | %s | %d / %d | %s\n" % (
                bar_str, percent_str, time_remaining, value, self.max_value, self.message))
        self.update_cnt += 1

    def set_message(self, message):
        self.message = message

    def finish(self):
        self.update(self.max_value, self.max_value)
        bar_str = "=" * self.width
        time_remaining = self.elapsed_time()
        self.stream.write(
            "\r|%s| 100.00%% | Done. | Elapsed Time: %s                                             \n" %
            (bar_str, time_remaining)
        )
