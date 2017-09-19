import time
import hashlib
import re
import sys
from queue import Queue, Empty
from threading import Thread
from subprocess import Popen, PIPE, STDOUT
import config

SGF_COORD = 'abcdefghijklmnopqrstuvwxy'
BOARD_COORD = 'abcdefghjklmnopqrstuvwxyz'  # without "i"


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
                time.sleep(0.1)
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


#
def start_reader_thread(fd):
    """
    Start file descriptor loop thread
    :param fd: stdout | stderr
    :return: ReaderThread
    """
    rt = ReaderThread(fd)
    t = Thread(target=rt.loop())
    t.start()

    return rt


class CLI(object):
    """
    Command Line Interface object designed to work with Ray.
    """

    def __init__(self, board_size, executable, is_handicap_game, komi, seconds_per_search, verbosity):
        self.board_size = board_size
        self.executable = executable
        self.is_handicap_game = is_handicap_game
        self.komi = komi
        self.seconds_per_search = seconds_per_search
        self.verbosity = verbosity

        self.p = None
        self.stdout_thread = None
        self.stderr_thread = None
        self.history = []

    def convert_position(self, pos):
        """
        Convert SGF coordinates to board position coordinates
        Example aa -> a1, qq -> p15
        :param pos: string
        :return: string
        """

        x = BOARD_COORD[SGF_COORD.index(pos[0])]
        y = self.board_size - SGF_COORD.index(pos[1])

        return '%s%d' % (x, y)

    def parse_position(self, pos):
        """
        Convert board position coordinates to SGF coordinates
        Example A1 -> aa, P15 -> qq
        :param pos: string
        :return: string
        """

        # Pass moves are the empty string in sgf files
        if pos == "pass":
            return ""

        x = BOARD_COORD.index(pos[0].lower())
        y = self.board_size - int(pos[1:])

        return "%s%s" % (SGF_COORD[x], SGF_COORD[y])

    def history_hash(self):
        """
        Return hash for checkpoint filename
        :return: string
        """
        h = hashlib.md5()

        for cmd in self.history:
            _, c, p = cmd.split()
            h.update(bytes((c[0] + p), 'utf-8'))

        return h.hexdigest()

    def add_move(self, color, pos):
        """
        Convert given SGF coordinates to board coordinates and writes them to history as a command
        :param color: str
        :param pos: str
        """
        move = 'pass' if pos in ['', 'tt'] else self.convert_position(pos)
        cmd = "play %s %s" % (color, move)
        self.history.append(cmd)

    def pop_move(self):
        self.history.pop()

    def clear_history(self):
        self.history.clear()

    def whose_turn(self):
        if len(self.history) == 0:
            return "white" if self.is_handicap_game else "black"
        else:
            return "black" if "white" in self.history[-1] else "white"

    @staticmethod
    def to_fraction(v):
        return 0.01 * float(v.strip())

    def parse_status_update(self, message):
        # Dummy cause Ray may work differently
        pass

    def drain(self):
        """
        Drain all remaining stdout and stderr contents
        """
        so = self.stdout_thread.read_all_lines()
        se = self.stderr_thread.read_all_lines()
        return so, se

    def send_command(self, cmd, expected_success_count=1, drain=True):
        """
        Send command to Ray and drains stdout/stderr
        :param cmd: string
        :param expected_success_count: how many '=' should Ray return
        :param drain: should drain or not
        """
        tries = 0
        success_count = 0
        timeout = 200

        # Sending command
        self.p.stdin.write(cmd + "\n")
        self.p.stdin.flush()

        while tries <= timeout and self.p is not None:
            # Loop readline until reach given number of success
            while True:
                s = self.stdout_thread.readline()

                # Ray follows GTP and prints a line starting with "=" upon success.
                if '=' in s:
                    success_count += 1
                    if success_count >= expected_success_count:
                        if drain:
                            self.drain()
                        return None

                # Break readline loop, sleep and wait for more
                if s == "":
                    break

            time.sleep(0.1)
            tries += 1

        raise Exception("Failed to send command '%s' to Ray" % cmd)

    def start(self):
        if self.verbosity > 0:
            print("Starting ray...", file=sys.stderr)

        p = Popen(self.executable + config.ray_settings, stdout=PIPE, stdin=PIPE, stderr=PIPE,
                  universal_newlines=True)

        self.p = p
        self.stdout_thread = start_reader_thread(p.stdout)
        self.stderr_thread = start_reader_thread(p.stderr)

        time.sleep(2)

        if self.verbosity > 0:
            print("Setting board size %d and komi %f to Leela" % (self.board_size, self.komi), file=sys.stderr)

        self.send_command('boardsize %d' % self.board_size)
        self.send_command('komi %f' % self.komi)
        self.send_command('time_settings 0 %d 1' % self.seconds_per_search)
