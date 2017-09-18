import sys
import re
import time
import hashlib

from subprocess import Popen, PIPE  # STDOUT

from sgftools.ReaderThread import start_reader_thread
from sgftools.regex_collection import update_regex, update_regex_no_vn



class CLI(object):
    def __init__(self, executable, seconds_per_search, verbosity):
        self.history = []
        self.executable = executable
        self.verbosity = verbosity
        self.board_size = 19 #move to config
        self.is_handicap_game = False # move to config
        self.komi = 6.5 # move to config
        self.seconds_per_search = seconds_per_search + 1  # add one to account for lag time
        self.p = None
        self.stdout_thread = None
        self.stderr_thread = None

    def convert_position(self, pos):
        abet = 'abcdefghijklmnopqrstuvwxyz'
        mapped = 'abcdefghjklmnopqrstuvwxyz'
        return '%s%d' % (mapped[abet.index(pos[0])], self.board_size - abet.index(pos[1]))

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
            _, c, p = cmd.split()
            h.update(bytes((c[0] + p), 'utf-8'))
        return h.hexdigest()

    def add_move(self, color, pos):
        if pos == '' or pos == 'tt':
            pos = 'pass'
        else:
            pos = self.convert_position(pos)
        cmd = "play %s %s" % (color, pos)
        self.history.append(cmd)

    def pop_move(self):
        self.history.pop()

    def clear_history(self):
        self.history.clear()

    def whoseturn(self):
        if len(self.history) == 0:
            return "white" if self.is_handicap_game else "black"
        else:
            return "black" if "white" in self.history[-1] else "white"


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

    @staticmethod
    def to_fraction(v):
        return 0.01 * float(v.strip())

    def drain(self):
        # Drain all remaining stdout and stderr current contents
        so = self.stdout_thread.read_all_lines()
        # print(so)
        se = self.stderr_thread.read_all_lines()
        # print(se)
        return so, se

    def send_command(self, cmd, expected_success_count=1, drain=True, timeout=20):
        self.p.stdin.write(cmd + "\n")
        time.sleep(1)
        self.p.stdin.flush()
        sleep_per_try = 0.1
        tries = 0
        success_count = 0
        while tries * sleep_per_try <= timeout and self.p is not None:
            time.sleep(sleep_per_try)
            tries += 1
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


        p = Popen(self.executable, stdout=PIPE, stdin=PIPE, stderr=PIPE,
                  universal_newlines=True)
        self.p = p

        self.stdout_thread = start_reader_thread(p.stdout)
        self.stderr_thread = start_reader_thread(p.stderr)
        time.sleep(1)

        if self.verbosity > 0:
            print("Setting board size %d and komi %f to Leela" % (self.board_size, self.komi), file=sys.stderr)

        #self.send_command('boardsize %d' % self.board_size)
        self.send_command('boardsize 19')

        self.send_command('komi %f' % self.komi)
        self.send_command('time_settings 0 %d 1' % self.seconds_per_search) # --const-time 5

    def stop(self):
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
                p.stdin.write('exit\n')
            except IOError:
                pass
            time.sleep(0.1)
            try:
                p.terminate()
            except OSError:
                pass

    def playmove(self, pos):
        color = self.whoseturn()
        cmd = 'play %s %s' % (color, pos)
        self.send_command(cmd)
        self.history.append(cmd)

    def reset(self):
        self.send_command('clear_board')

    def boardstate(self):
        self.send_command("showboard", drain=False)
        (so, se) = self.drain()
        return "".join(se)

    def goto_position(self):
        count = len(self.history)
        cmd = "\n".join(self.history)
        # print(cmd)
        self.send_command(cmd, expected_success_count=count)

    def analyze(self):
        p = self.p
        if self.verbosity > 1:
            print("Analyzing state:", file=sys.stderr)
            print(self.whoseturn() + " to play", file=sys.stderr)
            print(self.boardstate(), file=sys.stderr)

        self.send_command('time_left black %d 1' % self.seconds_per_search)
        self.send_command('time_left white %d 1' % self.seconds_per_search)

        cmd = "genmove %s\n" % self.whoseturn()
        # print(cmd)
        p.stdin.write(cmd)
        time.sleep(1)
        p.stdin.flush()

        updated = 0
        stderr = []
        stdout = []

        while updated < 20 + self.seconds_per_search * 2 and self.p is not None:
            o, l = self.drain()
            stdout.extend(o)
            stderr.extend(l)


            # print in console Ray responce
            
            if len(o) > 0:
                print('Ray_1: \n')

                for element in o:
                    print(element, end='\n')

            if len(l) != 0:
                for element in l:
                    print(element, end='\n')


            d = self.parse_status_update("".join(l))
            if 'visits' in d:
                if self.verbosity > 0:
                    print("Visited %d positions" % d['visits'], file=sys.stderr)
                updated = 0
            updated += 1

            time.sleep(1)

        p.stdin.write("\n")
        time.sleep(1)
        p.stdin.flush()

        o, l = self.drain()
        stdout.extend(o)
        stderr.extend(l)

        stats, move_list = self.parse(stdout, stderr)
        if self.verbosity > 0:
            print("Chosen move: %s" % stats['chosen'], file=sys.stderr)
            if 'best' in stats:
                print("Best move: %s" % stats['best'], file=sys.stderr)
                print("Winrate: %f" % stats['winrate'], file=sys.stderr)
                print("Visits: %d" % stats['visits'], file=sys.stderr)

        return stats, move_list

    def parse(self, stdout, stderr):
        if self.verbosity > 2:
            print("LEELA STDOUT", file=sys.stderr)
            print("".join(stdout), file=sys.stderr)
            print("END OF LEELA STDOUT", file=sys.stderr)
            print("LEELA STDERR", file=sys.stderr)
            print("".join(stderr), file=sys.stderr)
            print("END OF LEELA STDERR", file=sys.stderr)

        stats = {}
        move_list = []


