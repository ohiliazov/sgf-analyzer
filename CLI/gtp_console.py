import hashlib
from sgftools.readerthread import start_reader_thread, ReaderThread
from subprocess import Popen, PIPE
from time import sleep
from sgftools.utils import convert_position
from sgftools.logger import gtp_logger


def write_to_stdin(process: Popen, cmd=""):
    process.stdin.write(cmd + "\n")
    process.stdin.flush()


class GTPConsoleError(Exception):
    """Raised by [GTPConsole]"""
    pass


class GTPConsole:
    """Command Line Interface object designed to work with GTP-compatible bot."""
    arguments = None

    def __init__(self, path_to_exec: str, board_size: int, handicap_stones: int, komi: float, seconds_per_search: int):
        self.process = None  # type: Popen
        self.stdout_thread = None  # type: ReaderThread
        self.stderr_thread = None  # type: ReaderThread
        self.history = []

        self.executable = path_to_exec
        self.board_size = board_size
        self.handicap_stones = handicap_stones
        self.komi = komi
        self.seconds_per_search = seconds_per_search

    def history_hash(self) -> str:
        """Returns MD5 hash for current history."""
        history_hash = hashlib.md5()

        for command in self.history:
            history_hash.update(bytes(command, 'utf-8'))

        return history_hash.hexdigest()

    def add_move_to_history(self, color: str, pos: str):
        """ Convert given SGF coordinates to board coordinates and writes them to history as a command to GTP console"""
        move = convert_position(self.board_size, pos)
        command = f"play {color} {move}"
        self.history.append(command)

    def pop_move_from_history(self, count=1):
        """ Removes given number of last commands from history"""
        for i in range(count):
            self.history.pop()

    def clear_history(self):
        self.history.clear()

    def whose_turn(self) -> str:
        """ Return color of next move, based on number of handicap stones and moves."""
        if len(self.history) == 0:
            return "white" if self.handicap_stones else "black"
        else:
            return "black" if "white" in self.history[-1] else "white"

    def drain(self):
        """Drain all remaining stdout and stderr contents"""
        return self.stdout_thread.read_all_lines(), self.stderr_thread.read_all_lines()

    def send_command(self, command: str, expected_success_count: int = 1, drain: bool = True):
        """Send command to GTP console and drains stdout/stderr"""
        tries = 0
        success_count = 0
        timeout = 200

        # Sending command
        gtp_logger.debug(f"Sending command [{']['.join(command.splitlines())}] to GTP console...")

        write_to_stdin(self.process, command)

        while tries <= self.seconds_per_search * 10 + timeout and self.process is not None:
            # Loop until reach given number of success
            while True:
                s = self.stdout_thread.readline()

                # GTP prints a line starting with "=" upon success.
                if '=' in s:
                    success_count += 1
                    if success_count >= expected_success_count:
                        if drain:
                            self.drain()
                        return

                # Break loop, sleep and wait for more
                if s == "":
                    break

            tries += 1
            sleep(0.1)

        raise GTPConsoleError(f"Failed to send command [{command}] to Leela")

    def start(self):
        """Start GTP console"""
        gtp_logger.info("Starting GTP console...")

        process = Popen([self.executable] + self.arguments, stdout=PIPE, stdin=PIPE, stderr=PIPE,
                        universal_newlines=True)
        sleep(2)

        self.process = process
        self.stdout_thread = start_reader_thread(process.stdout)
        self.stderr_thread = start_reader_thread(process.stderr)

        gtp_logger.info(f"Setting board size {self.board_size:d} and komi {self.komi:.1f} to Leela")

        # Set board size, komi and time settings
        self.send_command(f'boardsize {self.board_size:d}')
        self.send_command(f'komi {self.komi:f}')
        self.send_command(f'time_settings 0 {self.seconds_per_search:d} 1')

        gtp_logger.info("GTP console started successfully...")

    def stop(self):
        """Stop GTP console"""
        gtp_logger.info("Stopping GTP console...")

        if self.process is not None:
            self.stdout_thread.stop()
            self.stderr_thread.stop()

            try:
                write_to_stdin(self.process, 'quit')
            except IOError:
                pass

            sleep(1)
            try:
                self.process.terminate()
            except OSError:
                pass

        gtp_logger.info("GTP console stopped successfully...")

    def restart(self):
        self.stop()
        self.start()

    def clear_board(self):
        """Clear board"""
        self.send_command('clear_board')

    def show_board(self):
        """Show board"""
        self.send_command("showboard", drain=False)
        (so, se) = self.drain()
        return "".join(se)

    def go_to_position(self):
        """Send all moves from history to GTP console"""
        count = len(self.history)
        cmd = "\n".join(self.history)
        self.send_command(cmd, expected_success_count=count)

    def generate_move(self):
        process = self.process

        self.send_command(f'time_left black {self.seconds_per_search:d} 1')
        self.send_command(f'time_left white {self.seconds_per_search:d} 1')

        gtp_logger.debug(f"Analyzing state: {self.whose_turn()} to play\n{self.show_board()}")

        # Generate next move
        write_to_stdin(process, f"genmove {self.whose_turn()}")

        updated = 0
        stdout = []
        stderr = []

        while updated < self.seconds_per_search * 2:
            out, err = self.drain()
            stdout.extend(out)
            stderr.extend(err)

            self.parse_status_update("".join(err))

            if out:
                break

            updated += 1
            sleep(1)

        # Confirm generated move with new line
        write_to_stdin(process)

        # Drain the rest of output
        out, err = self.drain()
        stdout.extend(out)
        stderr.extend(err)

        return stdout, stderr

    def flip_winrate(self, wr):
        return (1.0 - wr) if self.whose_turn() == "white" else wr

    def parse_status_update(self, message):
        pass

    def analyze(self):
        """Analyze current position with given seconds per search."""
        stdout, stderr = self.generate_move()

        # Drain and parse Leela stdout & stderr
        stats, move_list = self.parse_analysis(stdout, stderr)

        chosen_move = convert_position(self.board_size, stats['chosen'])
        if 'best' in stats:
            best_move = convert_position(self.board_size, stats['best'])
            winrate = (stats['winrate'] * 100)
            visits = stats['visits']
            gtp_logger.info(f"Chosen move: {chosen_move:3} | Best move: {best_move:3} | "
                            f"Winrate: {winrate:.2f}% | Visits: {visits}")
        else:
            gtp_logger.info(f"Chosen move: {chosen_move:3}")

        return stats, move_list

    def parse_analysis(self, stdout, stderr):
        return None, None

    def parse_bookmove(self, stats, line):
        pass

    def parse_move_status(self, line):
        pass

    def parse_move(self, move_list, line):
        pass

    def parse_best(self, stats, line):
        pass

    def parse_status(self, stats, summarized, line):
        return None, None

    def parse_finished(self, stats, stdout):
        pass
