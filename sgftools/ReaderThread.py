import time

from queue import Queue, Empty
from threading import Thread


# Start a thread that perpetually reads from the given file descriptor
# and pushes the result on to a queue, to simulate non-blocking io. We
# could just use fcntl and make the file descriptor non-blocking, but
# fcntl isn't available on windows so we do this horrible hack.
class ReaderThread:
    def __init__(self, fd):
        self.queue = Queue()
        self.fd = fd
        self.stopped = False

    def stop(self):
        # No lock since this is just a simple bool that only ever changes one way
        self.stopped = True

    def loop(self):
        while not self.stopped and not self.fd.closed:
            line = None
            # fd.readline() should return due to eof once the process is closed
            # at which point
            try:
                line = self.fd.readline()
            except IOError:
                time.sleep(0.2)
                pass
            if line is not None and len(line) > 0:
                self.queue.put(line)

    def readline(self):
        try:
            line = self.queue.get_nowait()
        except Empty:
            return ""
        return line

    def read_all_lines(self):
        lines = []
        while True:
            try:
                line = self.queue.get_nowait()
            except Empty:
                break
            lines.append(line)
        return lines


def start_reader_thread(fd):
    rt = ReaderThread(fd)

    def begin_loop():
        rt.loop()

    t = Thread(target=begin_loop)
    t.start()
    return rt
