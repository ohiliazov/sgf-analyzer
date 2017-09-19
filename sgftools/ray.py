import hashlib
import sys
import time
import config

from subprocess import Popen, PIPE
from sgftools.ReaderThread import start_reader_thread
from sgftools.utils import convert_position


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

        self.popen = None
        self.stdout_thread = None
        self.stderr_thread = None
        self.history = []

    def drain(self):
        """
        Drain all remaining stdout and stderr contents
        """
        stdout = self.stdout_thread.read_all_lines()
        stderr = self.stderr_thread.read_all_lines()
        return stdout, stderr

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
        self.popen.stdin.write(cmd + "\n")
        time.sleep(0.2)
        self.popen.stdin.flush()

        while tries <= timeout and self.popen is not None:
            # Loop readline until reach given number of success
            while True:
                line = self.stdout_thread.readline()

                # Ray follows GTP and prints a line starting with "=" upon success.
                if '=' in line:
                    success_count += 1
                    if success_count >= expected_success_count:
                        if drain:
                            # TODO: check why this needed
                            stdout, stderr = self.drain()
                            print('TODO: ' + stdout)
                            print('TODO: ' + stderr)
                        return None

                # Break readline loop, sleep and wait for more
                if line == "":
                    break

            time.sleep(0.1)
            tries += 1

        raise Exception("Failed to send command '%s' to Ray" % cmd)

    def start(self):
        """
        Start Ray process
        """
        if self.verbosity > 0:
            print("Starting ray...", file=sys.stderr)

        # TODO: fix config.ray_settings format, should be array?
        popen = Popen(self.executable + config.ray_settings, stdout=PIPE, stdin=PIPE, stderr=PIPE,
                      universal_newlines=True)

        # Set board size, komi and time settings
        self.popen = popen
        self.stdout_thread = start_reader_thread(popen.stdout)
        self.stderr_thread = start_reader_thread(popen.stderr)
        # TODO: test 3 and 5 secs delay
        time.sleep(4)

        if self.verbosity > 0:
            print("Setting board size %d and komi %f to Rey" % (self.board_size, self.komi), file=sys.stderr)
            print("Setting time settings 0 %d 1 to Rey" % self.seconds_per_search, file=sys.stderr)

        self.send_command('boardsize %d' % self.board_size)
        self.send_command('komi %f' % self.komi)
        self.send_command('time_settings 0 %d 1' % self.seconds_per_search)

    def stop(self):
        """
        Stop Ray process
        """
        if self.verbosity > 0:
            print("Stopping ray...", file=sys.stderr)

        if self.popen is not None:
            popen = self.popen
            stdout_thread = self.stdout_thread
            stderr_thread = self.stderr_thread
            self.popen = None
            self.stdout_thread = None
            self.stderr_thread = None
            stdout_thread.stop()
            stderr_thread.stop()

            try:
                popen.stdin.write('quit\n')
                popen.stdin.flush()
            except IOError:
                pass

            time.sleep(0.1)
            try:
                popen.terminate()
            except OSError:
                pass

    def play_move(self, pos):
        """
        Send move to Ray
        :param pos: string
        """
        color = self.whose_turn()
        cmd = 'play %s %s' % (color, pos)
        self.send_command(cmd)

    def reset(self):
        """
        Clear board
        """
        self.send_command('clear_board')

    def board_state(self):
        """
        Show board
        """
        self.send_command("showboard", drain=False)
        (stdout, stderr) = self.drain()

        # TODO: check why stdout is not used
        print('TODO:' + stdout)
        return "".join(stderr)

    def go_to_position(self):
        """
        Send all moves from history to Ray
        """
        count = len(self.history)
        cmd = "\n".join(self.history)
        self.send_command(cmd, expected_success_count=count)

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
        Convert given SGF coordinates to board coordinates and writes them to history as a command to Ray
        :param color: str
        :param pos: str
        """
        move = 'pass' if pos in ['', 'tt'] else convert_position(self.board_size, pos)
        cmd = "play %s %s" % (color, move)
        self.history.append(cmd)

    def pop_move(self):
        self.history.pop()

    def clear_history(self):
        self.history.clear()

    def whose_turn(self):
        """
        Return color of next move, based on number of handicap stones and moves
        :return: "black" | "white"
        """
        if len(self.history) == 0:
            return "white" if self.is_handicap_game else "black"
        else:
            return "black" if "white" in self.history[-1] else "white"
