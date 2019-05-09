import hashlib
from subprocess import Popen, PIPE
from time import sleep

import re

from readerthread import start_reader_thread

from log import logger
from utils import convert_position, parse_position


def str_to_percent(value: str):
    return 0.01 * float(value.strip())


class CLIException(Exception):
    pass


class BaseCLI:
    """ Command Line Interface designed to work with GTP protocol."""

    def __init__(self, bot_type, executable, arguments, board_size=19, komi=6.5, handicap=0, time_per_move=60):
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
        """ Convert given SGF coordinates to board coordinates and writes them to history as a command to GTP console"""
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
        if isinstance(cmd, list):
            commands_count = len(cmd)
            command = '\n'.join(cmd)
        else:
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
                    success_count += 1
                    if success_count >= commands_count:
                        if drain:
                            self.drain()
                        return

            tries += 1
            sleep(0.1)

        logger.warning(f"Failed to send command: {command}")

    def start(self):
        logger.info("Starting GTP...")

        self.process = Popen([self.executable] + self.arguments, stdout=PIPE, stdin=PIPE, stderr=PIPE,
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
        self.send_command(self._history)

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

            self.parse_status_update("".join(err))

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

    def parse_status_update(self, message):
        raise NotImplementedError("parse_status_update not implemented.")

    def parse_analysis(self, stdout, stderr):
        raise NotImplementedError("parse_analysis not implemented.")

    def parse_bookmove(self, stats, line):
        pass

    def parse_move_status(self, line):
        pass

    def parse_move(self, move_list, line):
        raise NotImplementedError("parse_analysis not implemented.")

    def parse_best(self, stats, line):
        pass

    def parse_status(self, stats, summarized, line):
        return None, None

    def parse_finished(self, stats, stdout):
        pass

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


class LeelaCLI(BaseCLI):
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

    def parse_analysis(self, stdout, stderr):
        """Parse stdout & stderr."""
        logger.debug(f"GTP stdout:\n%s", ''.join(stdout))
        logger.debug(f"GTP stderr:\n%s", ''.join(stderr))
        stats = {}
        move_list = []

        finished = False
        summarized = False

        for line in stderr:
            line = line.strip()
            if line.startswith('================'):
                finished = True

            stats = self.parse_bookmove(stats, line)
            stats.update(self.parse_move_status(line))
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
                    logger.warning("Analysis stats missing %s data", k)

            # In the case where Leela resigns, just replace with the move Leela did think was best
            if stats['chosen'] == "resign":
                stats['chosen'] = stats['best']

        if 'best' in stats:
            move_list = sorted(move_list,
                               key=(lambda move: 1000000000000000 if move['pos'] == stats['best'] else move['visits']),
                               reverse=True)

        return stats, move_list

    def parse_status_update(self, message):
        m = re.match(self.update_regex, message)

        if m is not None:
            visits = int(m.group(1))
            winrate = self.flip_winrate(str_to_percent(m.group(2)))
            pv = ' '.join([str(move) for move in m.group(3).split()])
            logger.debug("Visited %s positions, black winrate %.2f%%, PV: %s", visits, winrate * 100, pv)

    def parse_bookmove(self, stats, line):
        m = re.match(self.bookmove_regex, line)
        if m is not None:
            stats['bookmoves'] = int(m.group(1))
            stats['positions'] = int(m.group(2))
        return stats

    def parse_move_status(self, line):
        m = re.match(self.status_regex, line)
        if m is not None:
            return {'mc_winrate': self.flip_winrate(float(m.group(1))),
                    'nn_winrate': self.flip_winrate(float(m.group(2))),
                    'margin': m.group(3)}

        m = re.match(self.status_regex_no_vn, line)
        if m is not None:
            return {'mc_winrate': self.flip_winrate(float(m.group(1))),
                    'margin': m.group(2)}
        return {}

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


class LeelaZeroCLI(LeelaCLI):
    update_regex = r'Playouts: ([0-9]+), Win: ([0-9]+\.[0-9]+)\%, PV:(( [A-Z][0-9]+)+)'  # OK
    status_regex = r'NN eval=([0-9]+\.[0-9]+)'  # OK
    move_regex = r'\s*([A-Z][0-9]+) -> +([0-9]+) \(V: +([0-9]+\.[0-9]+)\%\) \([^\)]*\) \(N: +([0-9]+\.[0-9]+)\%\) PV: (.*)'
    stats_regex = r'([0-9]+) visits, ([0-9]+) nodes(?:, ([0-9]+) playouts)(?:, ([0-9]+) n/s)'  # OK
    finished_regex = r'= ([A-Z][0-9]+|resign|pass)'  # OK

    def parse_analysis(self, stdout, stderr):
        """Parse stdout & stderr."""
        logger.debug(f"GTP stdout:\n%s", ''.join(stdout))
        logger.debug(f"GTP stderr:\n%s", ''.join(stderr))

        stats = {}
        move_list = []

        for line in stderr:
            line = line.strip()
            stats = self.parse_bookmove(stats, line)
            stats.update(self.parse_move_status(line))
            move_list = self.parse_move(move_list, line)
            stats = self.parse_status(stats, None, line)

        try:
            stats['best'] = move_list[0]['pos']
            stats['winrate'] = move_list[0]['winrate']
        except (IndexError, KeyError) as e:
            logger.warning("Analysis has no move list, index out of bounds.")

        stats = self.parse_finished(stats, stdout)

        required_keys = ['best', 'winrate', 'visits']

        # Check for missed data
        for k in required_keys:
            if k not in stats:
                logger.warning("Analysis stats missing %s data", k)

        # In the case where Leela resigns, just replace with the move Leela did think was best
        if stats['chosen'] == "resign":
            stats['chosen'] = stats['best']

        return stats, move_list

    def parse_move_status(self, line):
        # Find status string
        m = re.match(self.status_regex, line)
        if m is not None:
            return {'winrate': self.flip_winrate(float(m.group(1)))}
        return {}

    def parse_move(self, move_list, line):
        m = re.match(self.move_regex, line)
        if m is not None:
            pos = parse_position(self.board_size, m.group(1))
            visits = int(m.group(2))
            winrate = self.flip_winrate(str_to_percent(m.group(3)))
            policy_prob = str_to_percent(m.group(4))
            pv = [parse_position(self.board_size, p) for p in m.group(5).split()]

            info = {
                'pos': pos,
                'visits': visits,
                'winrate': winrate,
                'policy_prob': policy_prob,
                'pv': pv,
                'color': self.whose_turn()
            }
            move_list.append(info)
        return move_list

    def parse_status(self, stats, summarized, line):
        m = re.match(self.stats_regex, line)
        if m is not None:
            stats['visits'] = int(m.group(1))
        return stats

