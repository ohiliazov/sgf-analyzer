import sys
import re
import time
import hashlib
from queue import Queue, Empty
from threading import Thread
from subprocess import Popen, PIPE, STDOUT

update_regex = r'Nodes: ([0-9]+), ' \
               r'Win: ([0-9]+\.[0-9]+)\% \(MC:[0-9]+\.[0-9]+\%\/VN:[0-9]+\.[0-9]+\%\), ' \
               r'PV:(( [A-Z][0-9]+)+)'
update_regex_no_vn = r'Nodes: ([0-9]+), ' \
                     r'Win: ([0-9]+\.[0-9]+)\%, ' \
                     r'PV:(( [A-Z][0-9]+)+)'

status_regex = r'MC winrate=([0-9]+\.[0-9]+), NN eval=([0-9]+\.[0-9]+), score=([BW]\+[0-9]+\.[0-9]+)'
status_regex_no_vn = r'MC winrate=([0-9]+\.[0-9]+), score=([BW]\+[0-9]+\.[0-9]+)'

move_regex = r'^([A-Z][0-9]+) -> +([0-9]+) \(W: +(\-?[0-9]+\.[0-9]+)\%\) \(U: +(\-?[0-9]+\.[0-9]+)\%\) ' \
             r'\(V: +([0-9]+\.[0-9]+)\%: +([0-9]+)\) \(N: +([0-9]+\.[0-9]+)\%\) PV: (.*)$'
move_regex_no_vn = r'^([A-Z][0-9]+) -> +([0-9]+) \(U: +(\-?[0-9]+\.[0-9]+)\%\) \(R: +([0-9]+\.[0-9]+)\%: +([0-9]+)\) ' \
                   r'\(N: +([0-9]+\.[0-9]+)\%\) PV: (.*)$'

best_regex = r'([0-9]+) visits, score (\-? ?[0-9]+\.[0-9]+)\% \(from \-? ?[0-9]+\.[0-9]+\%\) PV: (.*)'
stats_regex = r'([0-9]+) visits, ([0-9]+) nodes(?:, ([0-9]+) playouts)(?:, ([0-9]+) p/s)'
bookmove_regex = r'([0-9]+) book moves, ([0-9]+) total positions'
finished_regex = r'= ([A-Z][0-9]+|resign|pass)'


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
                # print(line)
            except IOError:
                time.sleep(0.2)
                pass
            if line is not None and len(line) > 0:
                self.queue.put(line)
                # print(self.queue.queue)
                # print(self.queue.get_nowait())

    def readline(self):
        try:
            line = self.queue.get_nowait()
            # print(line)
        except Empty:
            return ""
        return line

    def read_all_lines(self):
        lines = []
        while True:
            try:
                line = self.queue.get_nowait()
                # print(line)
            except Empty:
                break
            lines.append(line)
        # print(lines)
        return lines


def start_reader_thread(fd):
    rt = ReaderThread(fd)

    def begin_loop():
        rt.loop()

    t = Thread(target=begin_loop)
    t.start()
    return rt


class CLI(object):
    def __init__(self, board_size, executable, is_handicap_game, komi, seconds_per_search, verbosity):
        self.history = []
        self.executable = executable
        self.verbosity = verbosity
        self.board_size = board_size
        self.is_handicap_game = is_handicap_game
        self.komi = komi
        self.seconds_per_search = seconds_per_search + 1  # add one to account for lag time
        self.p = None

    def convert_position(self, pos):
        abet = 'abcdefghijklmnopqrstuvwxyz'
        mapped = 'abcdefghjklmnopqrstuvwxyz'
        pos = '%s%d' % (mapped[abet.index(pos[0])], self.board_size - abet.index(pos[1]))
        return pos

    def parse_position(self, pos):
        # Pass moves are the empty string in sgf files
        if pos == "pass":
            return ""

        abet = 'abcdefghijklmnopqrstuvwxyz'
        mapped = 'abcdefghjklmnopqrstuvwxyz'

        x = mapped.index(pos[0].lower())
        y = self.board_size - int(pos[1:])

        return "%s%s" % (abet[x], abet[y])

    def history_hash(self):
        h = hashlib.md5()
        for cmd in self.history:
            _, c, p = cmd.decode().split()
            # print(cmd, _, c[0], p)
            h.update(bytes((c[0] + p), 'utf-8'))
        return h.hexdigest()

    def add_move(self, color, pos):
        if pos == '' or pos == 'tt':
            pos = 'pass'
        else:
            pos = self.convert_position(pos)
        cmd = "play %s %s" % (color, pos)
        self.history.append(cmd.encode())

    def pop_move(self):
        self.history.pop()

    def clear_history(self):
        self.history = []

    def whose_turn(self):
        if len(self.history) == 0:
            if self.is_handicap_game:
                return "white"
            else:
                return "black"
        elif b'white' in self.history[-1]:
            return 'black'
        else:
            return 'white'

    def parse_status_update(self, message):
        m = re.match(update_regex, message)
        if m is None:
            m = re.match(update_regex_no_vn, message)

        if m is not None:
            visits = int(m.group(1))
            winrate = self.to_fraction(m.group(2))
            seq = m.group(3)
            seq = [self.parse_position(p) for p in seq.split()]

            return {'visits': visits, 'winrate': winrate, 'seq': seq}
        return {}

    # Drain all remaining stdout and stderr current contents
    def drain(self):
        so = self.stdout_thread.read_all_lines()
        se = self.stderr_thread.read_all_lines()
        print(so, se)
        return so, se

    # Send command and wait for ack
    def send_command(self, cmd, expected_success_count=1, drain=True, timeout=20):
        self.p.stdin.write(cmd + "\n")
        sleep_per_try = 0.1
        tries = 0
        success_count = 0
        while tries * sleep_per_try <= timeout and self.p is not None:
            time.sleep(sleep_per_try)
            tries += 1
            self.p.stdin.flush()
            self.p.stdout.flush()
            # Readline loop
            while True:
                s = self.stdout_thread.readline()
                # Leela follows GTP and prints a line starting with "=" upon success.
                if '=' in s:
                    success_count += 1
                    if success_count >= expected_success_count:
                        if drain:
                            self.drain()
                        return
                # No output, so break readline loop and sleep and wait for more
                if s == "":
                    break
        raise Exception("Failed to send command '%s' to Leela" % cmd)

    def start(self):
        xargs = []

        if self.verbosity > 0:
            print("Starting leela...", file=sys.stderr)

        p = Popen([self.executable] + xargs, stdout=PIPE, stdin=PIPE, stderr=PIPE, universal_newlines=True)
        self.p = p

        self.stdout_thread = start_reader_thread(p.stdout)
        self.stderr_thread = start_reader_thread(p.stderr)
        time.sleep(2)
        if self.verbosity > 0:
            print("Setting board size %d and komi %f to Leela" % (self.board_size, self.komi),
                  end="\n", file=sys.stderr)

        self.send_command('boardsize %d' % self.board_size)
        self.send_command('komi %f' % self.komi)
        self.send_command('time_settings 0 %d 1' % self.seconds_per_search)
        self.send_command('play b a1')

    def stop(self):
        if self.verbosity > 0:
            print("Stopping leela...", end="\n", file=sys.stderr)

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
                p.stdin.write('exit\n')
            except IOError:
                pass
            time.sleep(0.1)
            try:
                p.terminate()
            except OSError:
                pass

    def play_move(self, pos):
        color = self.whose_turn()
        cmd = 'play %s %s' % (color, pos)
        self.send_command(cmd)
        self.history.append(cmd)

    def reset(self):
        self.send_command('clear_board')

    def board_state(self):
        self.send_command("showboard", drain=False)
        (so, se) = self.drain()
        return "".join(se)

    def goto_position(self):
        count = len(self.history)
        cmd = "\n".join(self.history)
        self.send_command(cmd, expected_success_count=count)

    def analyze(self):
        p = self.p
        if self.verbosity > 1:
            print("Analyzing state:", end="\n", file=sys.stderr)
            print(self.whose_turn() + " to play", end="\n", file=sys.stderr)
            print(self.board_state(), end="\n", file=sys.stderr)

        self.send_command('time_left black %d 1\n' % self.seconds_per_search)
        self.send_command('time_left white %d 1\n' % self.seconds_per_search)

        cmd = "genmove %s\n" % (self.whose_turn())
        p.stdin.write(cmd)

        updated = 0
        stderr = []
        stdout = []

        while updated < 20 + self.seconds_per_search * 2 and self.p is not None:
            o, l = self.drain()
            stdout.extend(o)
            stderr.extend(l)

            d = self.parse_status_update("".join(l))
            if 'visits' in d:
                if self.verbosity > 0:
                    print("Visited %d positions" % (d['visits']), end="\n", file=sys.stderr)
                updated = 0
            updated += 1
            if re.search(finished_regex, ''.join(stdout)) is not None:
                if re.search(stats_regex, ''.join(stderr)) is not None or re.search(bookmove_regex,
                                                                                    ''.join(stderr)) is not None:
                    break
            time.sleep(1)

        p.stdin.write("\n")
        time.sleep(1)
        o, l = self.drain()
        stdout.extend(o)
        stderr.extend(l)

        stats, move_list = self.parse(stdout, stderr)
        if self.verbosity > 0:
            print("Chosen move: %s" % (stats['chosen']), end="\n", file=sys.stderr)
            if 'best' in stats:
                print("Best move: %s" % (stats['best']), end="\n", file=sys.stderr)
                print("Winrate: %f" % (stats['winrate']), end="\n", file=sys.stderr)
                print("Visits: %d" % (stats['visits']), end="\n", file=sys.stderr)

        return stats, move_list

    def to_fraction(self, v):
        v = v.strip()
        return 0.01 * float(v)

    def parse(self, stdout, stderr):
        if self.verbosity > 2:
            print("LEELA STDOUT", end="\n", file=sys.stderr)
            print("".join(stdout), end="\n", file=sys.stderr)
            print("END OF LEELA STDOUT", end="\n", file=sys.stderr)
            print("LEELA STDERR", end="\n", file=sys.stderr)
            print("".join(stderr), end="\n", file=sys.stderr)
            print("END OF LEELA STDERR", end="\n", file=sys.stderr)

        stats = {}
        move_list = []

        flip_winrate = self.whose_turn() == "white"

        def maybe_flip(winrate):
            return (1.0 - winrate) if flip_winrate else winrate

        finished = False
        summarized = False
        for line in stderr:
            line = line.strip()
            if line.startswith('================'):
                finished = True

            m = re.match(bookmove_regex, line)
            if m is not None:
                stats['bookmoves'] = int(m.group(1))
                stats['positions'] = int(m.group(2))

            m = re.match(status_regex, line)
            if m is not None:
                stats['mc_winrate'] = maybe_flip(float(m.group(1)))
                stats['nn_winrate'] = maybe_flip(float(m.group(2)))
                stats['margin'] = m.group(3)

            m = re.match(status_regex_no_vn, line)
            if m is not None:
                stats['mc_winrate'] = maybe_flip(float(m.group(1)))
                stats['margin'] = m.group(2)

            m = re.match(move_regex, line)
            if m is not None:
                pos = self.parse_position(m.group(1))
                visits = int(m.group(2))
                w = maybe_flip(self.to_fraction(m.group(3)))
                u = maybe_flip(self.to_fraction(m.group(4)))
                vp = maybe_flip(self.to_fraction(m.group(5)))
                vn = int(m.group(6))
                n = self.to_fraction(m.group(7))
                seq = m.group(8)
                seq = [self.parse_position(p) for p in seq.split()]

                info = {
                    'pos': pos,
                    'visits': visits,
                    'winrate': w, 'mc_winrate': u, 'nn_winrate': vp, 'nn_count': vn,
                    'policy_prob': n, 'pv': seq
                }
                move_list.append(info)

            m = re.match(move_regex_no_vn, line)
            if m is not None:
                pos = self.parse_position(m.group(1))
                visits = int(m.group(2))
                u = maybe_flip(self.to_fraction(m.group(3)))
                r = maybe_flip(self.to_fraction(m.group(4)))
                rn = int(m.group(5))
                n = self.to_fraction(m.group(6))
                seq = m.group(7)
                seq = [self.parse_position(p) for p in seq.split()]

                info = {
                    'pos': pos,
                    'visits': visits,
                    'winrate': u, 'mc_winrate': u, 'r_winrate': r, 'r_count': rn,
                    'policy_prob': n, 'pv': seq
                }
                move_list.append(info)

            if finished and not summarized:
                m = re.match(best_regex, line)
                if m is not None:
                    stats['best'] = self.parse_position(m.group(3).split()[0])
                    stats['winrate'] = maybe_flip(self.to_fraction(m.group(2)))

                m = re.match(stats_regex, line)
                if m is not None:
                    stats['visits'] = int(m.group(1))
                    summarized = True

        m = re.search(finished_regex, "".join(stdout))
        if m is not None:
            if m.group(1) == "resign":
                stats['chosen'] = "resign"
            else:
                stats['chosen'] = self.parse_position(m.group(1))

        if 'bookmoves' in stats and len(move_list) == 0:
            move_list.append({'pos': stats['chosen'], 'is_book': True})
        else:
            required_keys = ['mc_winrate', 'margin', 'best', 'winrate', 'visits']
            for k in required_keys:
                if k not in stats:
                    print("WARNING: analysis stats missing data %s" % k, end="\n", file=sys.stderr)

            move_list = sorted(move_list,
                               key=(lambda info: 1000000000000000 if info['pos'] == stats['best'] else info['visits']),
                               reverse=True)
            move_list = [info for (i, info) in enumerate(move_list) if i == 0 or info['visits'] > 0]

            # In the case where leela resigns, rather than resigning, just replace with the move Leela did think was best
            if stats['chosen'] == "resign":
                stats['chosen'] = stats['best']

        return stats, move_list
