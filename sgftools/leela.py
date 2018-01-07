import sys
import re
import hashlib
from subprocess import Popen, PIPE
from sgftools.readerthread import start_reader_thread, ReaderThread
from sgftools.utils import convert_position, parse_position
from time import sleep
from .logger import gtp_logger


def str_to_percent(value: str):
    return 0.01 * float(value.strip())


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
        gtp_logger.info(f"Sending command [{']['.join(command.splitlines())}] to GTP console...")

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

        gtp_logger.warning(f"Analyzing state: {self.whose_turn()} to play\n{self.show_board()}")

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

            if '=' in out:
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
        """Parse stdout & stderr."""
        gtp_logger.warning("LEELA STDOUT:\n" + "".join(stdout) + "\END OF LEELA STDOUT")
        gtp_logger.warning("LEELA STDERR:\n" + "".join(stderr) + "\END OF LEELA STDERR")

        stats = {}
        move_list = []

        finished = False
        summarized = False

        for line in stderr:
            line = line.strip()
            if line.startswith('================'):
                finished = True

            stats = self.parse_bookmove(stats, line)
            stats = self.parse_move_status(stats, line)
            move_list = self.parse_move(move_list, line)

            if finished and not summarized:
                stats = self.parse_best(stats, line)
                stats, summarized = self.parse_status(stats, summarized, line)

        stats = self.parse_finished(stats, stdout)

        if 'bookmoves' in stats and len(move_list) == 0:
            move_list.append({'pos': stats['chosen'], 'is_book': True})
        else:
            required_keys = ['margin', 'best', 'winrate', 'visits']

            # Check for missed data
            for k in required_keys:
                if k not in stats:
                    gtp_logger.warning("Analysis stats missing %s data" % k, file=sys.stderr)

            # In the case where Leela resigns, just replace with the move Leela did think was best
            if stats['chosen'] == "resign":
                stats['chosen'] = stats['best']

        move_list = sorted(move_list,
                           key=(lambda move: 1000000000000000 if move['pos'] == stats['best'] else move['visits']),
                           reverse=True)

        return stats, move_list

    def parse_bookmove(self, stats, line):
        pass

    def parse_move_status(self, stats, line):
        pass

    def parse_move(self, move_list, line):
        pass

    def parse_best(self, stats, line):
        pass

    def parse_status(self, stats, summarized, line):
        return None, None

    def parse_finished(self, stats, stdout):
        pass


class Leela(GTPConsole):
    update_regex = r'Nodes: ([0-9]+), ' \
                   r'Win: ([0-9]+\.[0-9]+)\% \(MC:[0-9]+\.[0-9]+\%\/VN:[0-9]+\.[0-9]+\%\), ' \
                   r'PV:(( [A-Z][0-9]+)+)'
    update_regex_no_vn = r'Nodes: ([0-9]+), ' \
                         r'Win: ([0-9]+\.[0-9]+)\%, ' \
                         r'PV:(( [A-Z][0-9]+)+)'
    status_regex = r'MC winrate=([0-9]+\.[0-9]+), ' \
                   r'NN eval=([0-9]+\.[0-9]+), ' \
                   r'score=([BW]\+[0-9]+\.[0-9]+)'
    status_regex_no_vn = r'MC winrate=([0-9]+\.[0-9]+), ' \
                         r'score=([BW]\+[0-9]+\.[0-9]+)'
    move_regex = r'^([A-Z][0-9]+) -> +([0-9]+) \(W: +(\-?[0-9]+\.[0-9]+)\%\) \(U: +(\-?[0-9]+\.[0-9]+)\%\) ' \
                 r'\(V: +([0-9]+\.[0-9]+)\%: +([0-9]+)\) \(N: +([0-9]+\.[0-9]+)\%\) PV: (.*)$'
    move_regex_no_vn = r'^([A-Z][0-9]+) -> +([0-9]+) \(U: +(\-?[0-9]+\.[0-9]+)\%\) ' \
                       r'\(R: +([0-9]+\.[0-9]+)\%: +([0-9]+)\) \(N: +([0-9]+\.[0-9]+)\%\) PV: (.*)$'
    best_regex = r'([0-9]+) visits, score (\-? ?[0-9]+\.[0-9]+)\% \(from \-? ?[0-9]+\.[0-9]+\%\) PV: (.*)'
    stats_regex = r'([0-9]+) visits, ([0-9]+) nodes(?:, ([0-9]+) playouts)(?:, ([0-9]+) p/s)'
    bookmove_regex = r'([0-9]+) book moves, ([0-9]+) total positions'
    finished_regex = r'= ([A-Z][0-9]+|resign|pass)'

    arguments = ['--gtp', '--noponder']

    def parse_status_update(self, message):
        m = re.match(self.update_regex, message)

        if m is not None:
            visits = int(m.group(1))
            winrate = str_to_percent(m.group(2))
            seq = m.group(3)
            seq = [parse_position(self.board_size, p) for p in seq.split()]

            return {'visits': visits, 'winrate': winrate, 'seq': seq}
        return {}

    def parse_bookmove(self, stats, line):
        # Find bookmove string
        m = re.match(self.bookmove_regex, line)
        if m is not None:
            stats['bookmoves'] = int(m.group(1))
            stats['positions'] = int(m.group(2))
        return stats

    def parse_move_status(self, stats, line):
        # Find status string
        m = re.match(self.status_regex, line)
        if m is not None:
            stats['mc_winrate'] = self.flip_winrate(float(m.group(1)))
            stats['nn_winrate'] = self.flip_winrate(float(m.group(2)))
            stats['margin'] = m.group(3)

        m = re.match(self.status_regex_no_vn, line)
        if m is not None:
            stats['mc_winrate'] = self.flip_winrate(float(m.group(1)))
            stats['margin'] = m.group(2)

        return stats

    def parse_move(self, move_list, line):
        m = re.match(self.move_regex, line)
        if m is not None:
            pos = parse_position(self.board_size, m.group(1))
            visits = int(m.group(2))
            winrate = self.flip_winrate(str_to_percent(m.group(3)))
            mc_winrate = self.flip_winrate(str_to_percent(m.group(4)))
            nn_winrate = self.flip_winrate(str_to_percent(m.group(5)))
            nn_count = int(m.group(6))
            policy_prob = str_to_percent(m.group(7))
            pv = [parse_position(self.board_size, p) for p in m.group(8).split()]

            info = {
                'pos': pos,
                'visits': visits,
                'winrate': winrate,
                'mc_winrate': mc_winrate,
                'nn_winrate': nn_winrate,
                'nn_count': nn_count,
                'policy_prob': policy_prob,
                'pv': pv,
                'color': self.whose_turn()
            }
            move_list.append(info)

        m = re.match(self.move_regex_no_vn, line)
        if m is not None:
            pos = parse_position(self.board_size, m.group(1))
            visits = int(m.group(2))
            mc_winrate = self.flip_winrate(str_to_percent(m.group(3)))
            r_winrate = self.flip_winrate(str_to_percent(m.group(4)))
            r_count = int(m.group(5))
            policy_prob = str_to_percent(m.group(6))
            pv = m.group(7)
            pv = [parse_position(self.board_size, p) for p in pv.split()]

            info = {
                'pos': pos,
                'visits': visits,
                'winrate': mc_winrate,
                'mc_winrate': mc_winrate,
                'r_winrate': r_winrate,
                'r_count': r_count,
                'policy_prob': policy_prob,
                'pv': pv,
                'color': self.whose_turn()
            }
            move_list.append(info)
        return move_list

    def parse_best(self, stats, line):
        m = re.match(self.best_regex, line)
        if m is not None:
            stats['best'] = parse_position(self.board_size, m.group(3).split()[0])
            stats['winrate'] = self.flip_winrate(str_to_percent(m.group(2)))
        return stats

    def parse_status(self, stats, summarized, line):
        m = re.match(self.stats_regex, line)
        if m is not None:
            stats['visits'] = int(m.group(1))
            summarized = True
        return stats, summarized

    def parse_finished(self, stats, stdout):
        m = re.search(self.finished_regex, "".join(stdout))
        if m is not None:
            stats['chosen'] = "resign" if m.group(1) == "resign" else parse_position(self.board_size, m.group(1))
        return stats
