import sys
import re
import time
import hashlib
from subprocess import Popen, PIPE
import arguments
import sgftools.readerthread as rt
import sgftools.utils as utils

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
move_regex_no_vn = r'^([A-Z][0-9]+) -> +([0-9]+) \(U: +(\-?[0-9]+\.[0-9]+)\%\) \(R: +([0-9]+\.[0-9]+)\%: +([0-9]+)\) ' \
                   r'\(N: +([0-9]+\.[0-9]+)\%\) PV: (.*)$'
best_regex = r'([0-9]+) visits, score (\-? ?[0-9]+\.[0-9]+)\% \(from \-? ?[0-9]+\.[0-9]+\%\) PV: (.*)'
stats_regex = r'([0-9]+) visits, ([0-9]+) nodes(?:, ([0-9]+) playouts)(?:, ([0-9]+) p/s)'
bookmove_regex = r'([0-9]+) book moves, ([0-9]+) total positions'
finished_regex = r'= ([A-Z][0-9]+|resign|pass)'

log_file = 'logs.log'

class Leela(object):
    """
    Command Line Interface object designed to work with Leela.
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
        Convert given SGF coordinates to board coordinates and writes them to history as a command to Leela
        :param color: str
        :param pos: str
        """
        move = 'pass' if pos in ['', 'tt'] else utils.convert_position(self.board_size, pos)
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

    def parse_status_update(self, message):
        """
        Parse number of visits, winrate and PV sequence
        :param message:
        :return: dictionary
        """
        m = re.match(update_regex, message)

        # For non-neural-network
        if m is None:
            m = re.match(update_regex_no_vn, message)

        if m is not None:
            visits = int(m.group(1))
            winrate = self.to_fraction(m.group(2))
            seq = m.group(3)
            seq = [utils.parse_position(self.board_size, p) for p in seq.split()]

            return {'visits': visits, 'winrate': winrate, 'seq': seq}
        return {}

    @staticmethod
    def to_fraction(v):
        return 0.01 * float(v.strip())

    def drain(self):
        """
        Drain all remaining stdout and stderr contents
        """
        so = self.stdout_thread.read_all_lines()
        se = self.stderr_thread.read_all_lines()

        if arguments.defaults['log_to_file']:
            utils.write_to_file(log_file, 'a', utils.join_list_into_str(so, ''))
            time.sleep(0.01)
            utils.write_to_file(log_file, 'a', utils.join_list_into_str(se, ''))
        return so, se

    @staticmethod
    def write_to_stdin(p, cmd=""):
        if arguments.defaults['log_to_file']:
            utils.write_to_file(log_file, 'a', utils.join_list_into_str(cmd, ''))
        p.stdin.write(cmd + "\n")
        p.stdin.flush()

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
        self.write_to_stdin(self.p, cmd)

        while tries <= timeout and self.p is not None:
            # Loop readline until reach given number of success
            while True:
                s = self.stdout_thread.readline()

                # Leela follows GTP and prints a line starting with "=" upon success.
                if '=' in s:
                    success_count += 1
                    if success_count >= expected_success_count:
                        if drain:
                            self.drain()
                        return

                # Break readline loop, sleep and wait for more
                if s == "":
                    break

            time.sleep(0.1)
            tries += 1

        raise Exception("Failed to send command '%s' to Leela" % cmd)

    def start(self):
        """
        Start Leela process
        :return:
        """
        if self.verbosity > 0:
            print("Starting leela...", file=sys.stderr)

        p = Popen([self.executable] + arguments.leela_settings, stdout=PIPE, stdin=PIPE, stderr=PIPE,
                  universal_newlines=True)

        self.p = p
        self.stdout_thread = rt.start_reader_thread(p.stdout)
        self.stderr_thread = rt.start_reader_thread(p.stderr)
        time.sleep(2)

        if self.verbosity > 0:
            print("Setting board size %d and komi %f to Leela" % (self.board_size, self.komi), file=sys.stderr)

        # Set board size, komi and time settings
        self.send_command('boardsize %d' % self.board_size)
        self.send_command('komi %f' % self.komi)
        self.send_command('time_settings 0 %d 1' % self.seconds_per_search)

    def stop(self):
        """
        Stop Leela process
        """
        if self.verbosity > 0:
            print("Stopping leela...", file=sys.stderr)

        if self.p is not None:
            p = self.p
            stdout_thread = self.stdout_thread
            stderr_thread = self.stderr_thread
            self.p = None
            self.stdout_thread = None
            self.stderr_thread = None
            stdout_thread.stop()
            stderr_thread.stop()
            try:
                self.write_to_stdin(p, 'quit')
            except IOError:
                pass
            time.sleep(0.1)
            try:
                p.terminate()
            except OSError:
                pass

    def play_move(self, pos):
        """
        Send move to Leela
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

    def save_sgf(self, sgf_fn):
        """
        Save sgf to given filename
        """
        self.send_command('printsgf %s' % sgf_fn)

    def load_sgf(self, sgf_fn):
        """
        Load sgf from given file
        """
        self.send_command('loadsgf %s' % sgf_fn)

    def board_state(self):
        """
        Show board
        """
        self.send_command("showboard", drain=False)
        (so, se) = self.drain()
        return "".join(se)

    def go_to_position(self):
        """
        Send all moves from history to Leela
        """
        count = len(self.history)
        cmd = "\n".join(self.history)
        self.send_command(cmd, expected_success_count=count)

    def parse(self, stdout, stderr):
        """
        Parse Leela stdout & stderr
        :param stdout: string
        :param stderr: string
        :return: stats, move_list
        """
        if self.verbosity > 2:
            print("LEELA STDOUT:\n" + "".join(stdout) + "\END OF LEELA STDOUT", file=sys.stderr)
            print("LEELA STDERR:\n" + "".join(stderr) + "\END OF LEELA STDERR", file=sys.stderr)

        stats = {}
        move_list = []

        def flip_winrate(wr):
            return (1.0 - wr) if self.whose_turn() == "white" else wr

        # function filter given list of moves by criteria or win-rate and visits
        def filter_redundant_moves(move_list, stats):

            best_move_visits = stats['visits']
            best_move_winrate = stats['winrate']

            return list(filter(lambda move:
                               (best_move_winrate - move['winrate']) < 0.1
                               and (best_move_visits / move['visits']) < 20, move_list))

        finished = False
        summarized = False
        for line in stderr:
            line = line.strip()
            if line.startswith('================'):
                finished = True

            # Find bookmove string
            m = re.match(bookmove_regex, line)
            if m is not None:
                stats['bookmoves'] = int(m.group(1))
                stats['positions'] = int(m.group(2))

            # Find status string
            m = re.match(status_regex, line)
            if m is not None:
                stats['mc_winrate'] = flip_winrate(float(m.group(1)))
                stats['nn_winrate'] = flip_winrate(float(m.group(2)))
                stats['margin'] = m.group(3)

            m = re.match(status_regex_no_vn, line)
            if m is not None:
                stats['mc_winrate'] = flip_winrate(float(m.group(1)))
                stats['margin'] = m.group(2)

            # Find move string
            m = re.match(move_regex, line)
            if m is not None:
                pos = utils.parse_position(self.board_size, m.group(1))
                visits = int(m.group(2))
                winrate = flip_winrate(self.to_fraction(m.group(3)))
                mc_winrate = flip_winrate(self.to_fraction(m.group(4)))
                nn_winrate = flip_winrate(self.to_fraction(m.group(5)))
                nn_count = int(m.group(6))
                policy_prob = self.to_fraction(m.group(7))
                pv = [utils.parse_position(self.board_size, p) for p in m.group(8).split()]

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

            m = re.match(move_regex_no_vn, line)
            if m is not None:
                pos = utils.parse_position(self.board_size, m.group(1))
                visits = int(m.group(2))
                mc_winrate = flip_winrate(self.to_fraction(m.group(3)))
                r_winrate = flip_winrate(self.to_fraction(m.group(4)))
                r_count = int(m.group(5))
                policy_prob = self.to_fraction(m.group(6))
                pv = m.group(7)
                pv = [utils.parse_position(self.board_size, p) for p in pv.split()]

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

            if finished and not summarized:
                m = re.match(best_regex, line)

                # Parse best move and its winrate
                if m is not None:
                    stats['best'] = utils.parse_position(self.board_size, m.group(3).split()[0])
                    stats['winrate'] = flip_winrate(self.to_fraction(m.group(2)))

                # Parse number of visits to stats
                m = re.match(stats_regex, line)
                if m is not None:
                    stats['visits'] = int(m.group(1))
                    summarized = True

        # Find finished string
        m = re.search(finished_regex, "".join(stdout))

        # Add chosen move to stats
        if m is not None:
            stats['chosen'] = "resign" if m.group(1) == "resign" else utils.parse_position(self.board_size, m.group(1))

        # Add book move to move list
        if 'bookmoves' in stats and len(move_list) == 0:
            move_list.append({'pos': stats['chosen'], 'is_book': True})
        else:
            required_keys = ['mc_winrate', 'margin', 'best', 'winrate', 'visits']

            # Check for missed data
            for k in required_keys:
                if k not in stats:
                    print("WARNING: analysis stats missing %s data" % k, file=sys.stderr)

            move_list = sorted(move_list,
                               key=(lambda key: 1000000000000000 if info['pos'] == stats['best'] else info['visits']),
                               reverse=True)
            move_list = [info for (i, info) in enumerate(move_list) if i == 0 or info['visits'] > 0]

            move_list = filter_redundant_moves(move_list, stats)

            # In the case where Leela resigns, just replace with the move Leela did think was best
            if stats['chosen'] == "resign":
                stats['chosen'] = stats['best']

        return stats, move_list

    def analyze(self, seconds_per_search):
        """
        Analyze current position with given seconds per search
        :return: tuple
        """
        p = self.p

        # Set time for search. Increased time if a mistake is detected
        self.send_command('time_left black %d 1' % seconds_per_search)
        self.send_command('time_left white %d 1' % seconds_per_search)

        if self.verbosity > 1:
            print("Analyzing state:", file=sys.stderr)
            print(self.whose_turn() + " to play", file=sys.stderr)
            print(self.board_state(), file=sys.stderr)

        # Generate next move
        self.write_to_stdin(p, "genmove %s" % self.whose_turn())

        updated = 0
        stderr = []
        stdout = []

        # Some scary loop to find end of analysis
        while updated < 20 + self.seconds_per_search * 2 and self.p is not None:
            out, err = self.drain()
            stdout.extend(out)
            stderr.extend(err)
            d = self.parse_status_update("".join(err))

            if 'visits' in d:
                if self.verbosity > 0:
                    print("Visited %d positions" % d['visits'], file=sys.stderr)
                updated = 0

            updated += 1

            if re.search(finished_regex, ''.join(stdout)) is not None:
                if re.search(stats_regex, ''.join(stderr)) is not None \
                        or re.search(bookmove_regex, ''.join(stderr)) is not None:
                    break

            time.sleep(1)

        # Confirm generated move
        self.write_to_stdin(p)

        # Drain and parse Leela stdout & stderr
        out, err = self.drain()
        stdout.extend(out)
        stderr.extend(err)
        stats, move_list = self.parse(stdout, stderr)

        if self.verbosity > 0:
            print("Chosen move: %s" % utils.convert_position(self.board_size, stats['chosen']), file=sys.stderr)

            if 'best' in stats:
                print("Best move: %s" % utils.convert_position(self.board_size, stats['best']), file=sys.stderr)
                print("Winrate: %.2f%%" % (stats['winrate'] * 100), file=sys.stderr)
                print("Visits: %d" % stats['visits'], file=sys.stderr)

        return stats, move_list
