import re
import config
from sgftools.utils import parse_position
from sgftools.logger import gtp_logger
from . import GTPConsole


def str_to_percent(value: str):
    return 0.01 * float(value.strip())


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

    arguments = ['--gtp', '--noponder', '--nobook', '--playouts', str(config.playouts)]

    def parse_analysis(self, stdout, stderr):
        """Parse stdout & stderr."""
        gtp_logger.debug(f"GTP console stdout:\n{''.join(stdout)}")
        gtp_logger.debug(f"GTP console stderr:\n{''.join(stderr)}")

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
                    gtp_logger.warning("Analysis stats missing %s data" % k)

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
            winrate = str_to_percent(m.group(2))
            seq = m.group(3)
            gtp_logger.info(f"Visited {visits} positions, "
                            f"black winrate {round(self.flip_winrate(winrate)*100, 2)}%, "
                            f"PV: {' '.join([move for move in seq.split()])}")

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


class LeelaZero(Leela):
    update_regex = r'Playouts: ([0-9]+), Win: ([0-9]+\.[0-9]+)\%, PV:(( [A-Z][0-9]+)+)'  # OK
    status_regex = r'NN eval=([0-9]+\.[0-9]+)'  # OK
    move_regex = r'\s*([A-Z][0-9]+) -> +([0-9]+) \(V: +([0-9]+\.[0-9]+)\%\) \(N: +([0-9]+\.[0-9]+)\%\) PV: (.*)$'  # OK
    # best_regex = r'([0-9]+) visits, score (\-? ?[0-9]+\.[0-9]+)\% \(from \-? ?[0-9]+\.[0-9]+\%\) PV: (.*)'  # OK
    stats_regex = r'([0-9]+) visits, ([0-9]+) nodes(?:, ([0-9]+) playouts)(?:, ([0-9]+) n/s)'  # OK
    finished_regex = r'= ([A-Z][0-9]+|resign|pass)'  # OK

    arguments = ['--gtp',
                 '--noponder',
                 '--weights', config.path_to_leela_zero_weights,
                 '--playouts', str(config.playouts)]

    def parse_analysis(self, stdout, stderr):
        """Parse stdout & stderr."""
        gtp_logger.debug(f"GTP console stdout:\n{''.join(stdout)}")
        gtp_logger.debug(f"GTP console stderr:\n{''.join(stderr)}")

        stats = {}
        move_list = []

        for line in stderr:
            line = line.strip()
            stats = self.parse_bookmove(stats, line)
            stats = self.parse_move_status(stats, line)
            move_list = self.parse_move(move_list, line)
            stats = self.parse_status(stats, line)

        stats['best'] = move_list[0]['pos']
        stats = self.parse_finished(stats, stdout)

        required_keys = ['best', 'winrate', 'visits']

        # Check for missed data
        for k in required_keys:
            if k not in stats:
                gtp_logger.warning("Analysis stats missing %s data" % k)

        # In the case where Leela resigns, just replace with the move Leela did think was best
        if stats['chosen'] == "resign":
            stats['chosen'] = stats['best']

        return stats, move_list

    def parse_move_status(self, stats, line):
        # Find status string
        m = re.match(self.status_regex, line)
        if m is not None:
            stats['winrate'] = self.flip_winrate(float(m.group(1)))
        return stats

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
            if len(move_list) < config.move_list_max_length:
                move_list.append(info)
        return move_list

    def parse_best(self, stats, line):
        m = re.match(self.best_regex, line)
        if m is not None:
            print(m.groups())
            stats['best'] = parse_position(self.board_size, m.group(3).split()[0])
            stats['winrate'] = self.flip_winrate(str_to_percent(m.group(2)))
        return stats

    def parse_status(self, stats, line):
        m = re.match(self.stats_regex, line)
        if m is not None:
            stats['visits'] = int(m.group(1))
        return stats

