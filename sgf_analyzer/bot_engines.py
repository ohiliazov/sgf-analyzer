import hashlib
import re
from subprocess import Popen, PIPE
from time import sleep

from .log import logger
from .readerthread import start_reader_thread
from .utils import convert_position, parse_position


def str_to_percent(value: str):
    return 0.01 * float(value.strip())


class CLIException(Exception):
    pass


class BaseCLI:
    """ Command Line Interface designed to work with GTP protocol."""

    def __init__(self, bot_type, executable, arguments,
                 board_size=19, komi=6.5, handicap=0, time_per_move=60):
        self._history = []

        self.process = None
        self.stdout_thread = None
        self.stderr_thread = None

        self.bot_type = bot_type
        self.executable = executable
        self.arguments = arguments.split()

        self.board_size = board_size
        self.komi = komi
        self.handicap = handicap
        self.time_per_move = time_per_move

    def history_hash(self) -> str:
        """Returns MD5 hash for current history."""
        history_hash = hashlib.md5()

        for command in self._history:
            history_hash.update(bytes(command, 'utf-8'))

        return history_hash.hexdigest()

    def add_move_to_history(self, color: str, pos: str):
        """ Convert given SGF coordinates to GTP console command"""
        move = convert_position(self.board_size, pos)
        command = f"play {color} {move}"
        self._history.append(command)

    def pop_move_from_history(self, count=1):
        """ Removes given number of last commands from history"""
        for i in range(count):
            self._history.pop()

    def clear_history(self):
        self._history.clear()

    def whose_turn(self) -> str:
        """ Return color of next move, based on number of handicap stones and moves."""
        if len(self._history) == 0:
            return "white" if self.handicap else "black"
        else:
            return "black" if "white" in self._history[-1] else "white"

    def drain(self):
        """ Drains all remaining stdout and stderr contents"""
        return self.stdout_thread.read_all_lines(), self.stderr_thread.read_all_lines()

    def send_command(self, cmd, timeout=100, drain=True):
        """Send command to GTP console and drains stdout/stderr"""

        commands_count = 1
        command = cmd

        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

        tries = 0
        success_count = 0
        while tries <= timeout:
            # Loop until reach given number of success
            while True:
                s = self.stdout_thread.readline()

                # Break loop, sleep and wait for more
                if s == "":
                    break

                # GTP prints a line starting with "=" upon success.
                if '=' in s:
                    if drain:
                        self.drain()
                    return

            tries += 1
            sleep(0.1)

        logger.warning(f"Failed to send command: {command}")

    def start(self):
        logger.info("Starting GTP...")

        self.process = Popen([self.executable] + self.arguments,
                             stdout=PIPE,
                             stdin=PIPE,
                             stderr=PIPE,
                             universal_newlines=True)
        sleep(2)
        self.stdout_thread = start_reader_thread(self.process.stdout)
        self.stderr_thread = start_reader_thread(self.process.stderr)

        self.send_command(f'boardsize {self.board_size}')
        self.send_command(f'komi {self.komi}')
        self.send_command(f'time_settings 0 {self.time_per_move} 1')
        logger.info("GTP started successfully.")

    def stop(self):
        """Stop GTP console"""
        logger.info("Stopping GTP...")

        if self.process is None:
            return

        self.stdout_thread.stop()
        self.stderr_thread.stop()
        self.send_command('quit')

        logger.info("GTP stopped successfully...")

    def reset(self):
        self.clear_history()
        self.stop()
        self.start()

    def clear_board(self):
        """ Clear board."""
        self.send_command('clear_board')

    def showboard(self):
        """Show board"""
        self.send_command("showboard", drain=False)
        (so, se) = self.drain()
        return "".join(se)

    def go_to_position(self):
        """Send all moves from history to GTP console"""
        self.clear_board()
        for command in self._history:
            self.send_command(command)

    def flip_winrate(self, wr):
        return (1.0 - wr) if self.whose_turn() == "white" else wr

    def genmove(self):
        self.send_command(f'time_left black {self.time_per_move:d} 1')
        self.send_command(f'time_left white {self.time_per_move:d} 1')

        logger.debug("Board state: %s to play\n%s", self.whose_turn(), self.showboard())

        # Generate next move
        self.process.stdin.write(f"genmove {self.whose_turn()}\n")
        self.process.stdin.flush()

        updated = 0
        stdout = []
        stderr = []

        while updated < self.time_per_move * 2:
            out, err = self.drain()
            stdout.extend(out)
            stderr.extend(err)

            if out:
                break

            updated += 1
            sleep(1)

        # Confirm generated move with new line
        self.process.stdin.write("\n")
        self.process.stdin.flush()

        # Drain the rest of output
        out, err = self.drain()
        stdout.extend(out)
        stderr.extend(err)

        return stdout, stderr


class LeelaCLI(BaseCLI):
    best_regex = re.compile(
        r"Playouts: (?P<playouts>\d+), "
        r"Win: (?P<winrate>\d+\.\d+)%, "
        r"PV: (?P<pv>(?:[A-Z]\d{1,2} ?)+)"
    )
    move_status_regex = re.compile(r'NN eval=(\d+\.\d+)')
    move_regex = re.compile(
        r'\s*(?P<pos>[A-Z]\d{1,2})' 
        r'\s*(?P<visits>\d+)' 
        r'\s*(?P<reuse>\d+)' 
        r'\s*(?P<ppv>-?\d+)' 
        r'\s*(?P<winrate>-?\d+\.\d+)%' 
        r'\s*(?P<agent>-?\d+\.\d+)%' 
        r'\s*(?P<lcb>-?\d+\.\d+)%' 
        r'\s*(?P<stdev>-?\d+\.\d+)%' 
        r'\s*(?P<policy>-?\d+\.\d+)%' 
        r'\s*(?P<fvisit>-?\d+\.\d+)%' 
        r'\s*(?P<alpkt>-?\d+\.\d+)' 
        r'\s*(?P<beta>-?\d+\.\d+)' 
        r'\s*(?P<w1st>-?\d+)%' 
        r'\s*(?P<pv>.*)$'  # OK
    )
    status_regex = re.compile(
        r'(?P<visits>\d+) visits, '
        r'(?P<nodes>\d+) nodes, '
        r'(?P<playouts>\d+) playouts, '
        r'(?P<ns>\d+) n/s'
    )
    finished_regex = re.compile(
        r"= (?P<chosen>[A-Z]\d{1,2}|resign|pass)"
    )

    def parse_finished(self, lines: list[str]):
        for line in lines:
            m = self.finished_regex.match(line.strip())
            if m is not None:
                logger.error(f"Parsed finished: {m.groups()}")
                result = m.group(1)
                if result != "resign":
                    result = parse_position(self.board_size, result)
                return {"chosen": result}
        return {}

    def parse_move_status(self, lines: list[str]):
        for line in lines:
            m = self.move_status_regex.match(line.strip())
            if m:
                logger.error(f"Parsed move status: {m.groups()}")
                return {'winrate': self.flip_winrate(float(m.group(1)))}
        return {}

    def parse_best(self, lines: list[str]):
        for line in lines:
            m = self.best_regex.match(line.strip())
            if m:
                logger.error(f"Parsed best: {m.groups()}")
                playouts = int(m.group(1))
                winrate = self.flip_winrate(str_to_percent(m.group(2)))
                pv = [parse_position(self.board_size, p) for p in m.group(3).split()]

                return {
                    "playouts": playouts,
                    "winrate": winrate,
                    "pv": pv,
                }
        return {}

    def parse_move(self, lines: list[str]):
        move_list = []

        for line in lines:
            m = self.move_regex.match(line.strip())
            if m is not None:
                logger.error(f"Parsed move: {m.groups()}")
                pos = parse_position(self.board_size, m.group(1))
                visits = int(m.group(2))
                winrate = self.flip_winrate(str_to_percent(m.group(5)))
                policy_prob = str_to_percent(m.group(9))
                pv = [parse_position(self.board_size, p) for p in m.group(14).split()]

                move_list.append(
                    {
                        'pos': pos,
                        'visits': visits,
                        'winrate': winrate,
                        'policy_prob': policy_prob,
                        'pv': pv,
                        'color': self.whose_turn()
                    }
                )
        return move_list

    def parse_status(self, lines: list[str]):
        for line in lines:
            m = self.status_regex.match(line.strip())
            if m is not None:
                logger.error(f"Parsed status: {m.groups()}")
                return {"visits": int(m.group(1))}
        return {}

    def parse_analysis(self, stdout: list[str], stderr: list[str]):
        """Parse stdout & stderr."""
        logger.debug(f"GTP stdout:\n%s", ''.join(stdout))
        logger.debug(f"GTP stderr:\n%s", ''.join(stderr))

        move_list = self.parse_move(stderr)

        stats = {
            "best": move_list[0]["pos"],
            "winrate": move_list[0]["winrate"],
            **self.parse_move_status(stderr),
            **self.parse_status(stderr),
            **self.parse_best(stderr),
            **self.parse_finished(stdout),
        }
        logger.error(stats)

        # Check for missed data
        for k in ['best', 'winrate', 'visits']:
            if k not in stats:
                logger.warning("Analysis stats missing %s data", k)

        # In the case where Leela resigns, just replace with the move Leela did think was best
        if stats['chosen'] == "resign":
            stats['chosen'] = stats['best']

        return stats, move_list

    def analyze(self):
        """Analyze current position with given seconds per search."""
        stdout, stderr = self.genmove()

        # Drain and parse Leela stdout & stderr
        stats, move_list = self.parse_analysis(stdout, stderr)

        if stats.get('winrate') and move_list:
            best_move = convert_position(self.board_size, move_list[0]['pos'])
            winrate = (stats['winrate'] * 100)
            visits = stats['visits']
            pv = " ".join([convert_position(self.board_size, m) for m in move_list[0]['pv']])
            logger.debug(f"Suggested: %s (winrate %.2f%%, %d visits). Perfect sequence: %s",
                         best_move, winrate, visits, pv)
        else:
            chosen_move = convert_position(self.board_size, stats['chosen'])
            logger.debug(f"Chosen move: %s", chosen_move)

        return stats, move_list
