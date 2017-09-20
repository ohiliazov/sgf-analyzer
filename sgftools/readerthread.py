import time

from queue import Queue, Empty
from threading import Thread


class ReaderThread:
    """
    ReaderThread perpetually reads from the given file descriptor and pushes the result to a queue.
    """

    def __init__(self, fd):
        self.queue = Queue()
        self.fd = fd  # stdout or stderr is given
        self.stopped = False

    def stop(self):
        """
        No lock since this is just a simple bool that only ever changes one way
        """
        self.stopped = True

    def loop(self):
        """
        Loop fd.readline() due to EOF until the process is closed
        """
        while not self.stopped and not self.fd.closed:
            try:
                line = self.fd.readline()
                if len(line) > 0:
                    self.queue.put(line)
            except IOError:
                time.sleep(0.2)
                pass

    def readline(self):
        """
        Read single line from queue
        :return: str
        """
        try:
            line = self.queue.get_nowait()
            return line
        except Empty:
            return ""

    def read_all_lines(self):
        """
        Read all lines from queue.
        :return: list
        """
        lines = []

        while True:
            try:
                line = self.queue.get_nowait()
                lines.append(line)
            except Empty:
                break

        return lines


def start_reader_thread(fd):
    """
    Start file descriptor loop thread
    :param fd: stdout | stderr
    :return: ReaderThread
    """
    reader_thread = ReaderThread(fd)

    def begin_loop():
        reader_thread.loop()

    t = Thread(target=begin_loop)
    t.start()

    return reader_thread
