from subprocess import Popen, PIPE, STDOUT
from itertools import islice
import re
from base import interpreter_base,\
                 unknown_black, unknown_white, unknown_error,\
                 colors as color_names

colors = {
    "lR": 0,
    "nR": 1,
    "dR": 2,
    "lY": 3,
    "nY": 4,
    "dY": 5,
    "lG": 6,
    "nG": 7,
    "dG": 8,
    "lC": 9,
    "nC": 10,
    "dC": 11,
    "lB": 12,
    "nB": 13,
    "dB": 14,
    "lM": 15,
    "nM": 16,
    "dM": 17,
    "WW": 18,
    "BB": 19
}
N_HUES = 6
N_LIGHTS = 3

class interpreter(interpreter_base):
    def __init__(self, npiet, gc = None, pc = None, gi = None, pi = None):
        interpreter_base.__init__(self)
        self._proc = None
        self.npiet = npiet
        self.re_step = re.compile('[0-9]+  \(([0-9]+),([0-9]+)\/(.,.) (..) -> ([0-9]+),([0-9]+)\/(.,.) (..)\)\:$')
        self.re_size = re.compile('^info: got ([0-9]+) x ([0-9]+) ')
        self.re_failed = re.compile('[^ ]* failed: ')
        self._update_stack = 0
        self._stack_str = None
        self._s = None
        self._white = False
        self.get_char = gc
        self.put_char = pc
        self.get_int = gi
        self.put_int = pi

    def diff(self, c_from, c_to):
        f_hue, f_light = divmod(colors[c_from], N_LIGHTS)
        t_hue, t_light = divmod(colors[c_to], N_LIGHTS)
        hue_diff = t_hue - f_hue
        light_diff = t_light - f_light
        if hue_diff < 0:
            hue_diff += N_HUES
        if light_diff < 0:
            light_diff += N_LIGHTS
        return (hue_diff, light_diff)

    def _in_char(self):
        if self._s is None:
            self._s = self._proc.stdout.read(2)
        self._proc.stdin.write(self.get_char())
        self._proc.stdin.flush()
        self._s = None
        self.state = self.ST_NEXT

    def _in_number(self):
        if self._s is None:
            self._s = self._proc.stdout.read(2)
        self._proc.stdin.write(str(self.get_int()))
        self._proc.stdin.flush()
        self._s = None
        self.state = self.ST_NEXT

    def _out_char(self):
        if self._s is None:
            self._s = self._proc.stdout.readline()[:1]
        self.put_char(self._s)
        self._s = None
        self.state = self.ST_NEXT

    def _out_number(self):
        if self._s is None:
            self._s = int(self._proc.stdout.readline())
        self.put_int(self._s)
        self._s = None
        self.state = self.ST_NEXT

    _io_ops = {
        "in(char)": _in_char,
        "in(number)": _in_number,
        "out(char)": _out_char,
        "out(number)": _out_number
    }

    def step(self):
        if self.state != self.ST_END:
            if self.state == self.ST_OP:
                self._op_func(self)
            s = self._proc.stdout.readline()
            while s != '\n':
                if s == '':
                    raise RuntimeError('terminated')
                elif s.startswith('info:'):
                    if self.re_failed.match(s, 6) is not None:
                        self._update_stack = 1
                    elif s.startswith('program end', 6):
                        self.state = self.ST_END
                        self._proc.wait()
                        self._proc = None
                        return
                elif s.startswith('trace:'):
                    if s.startswith('step', 7):
                        self.op = None
                        self.arg = None
                        m = self.re_step.match(s, 12)
                        if m is None:
                            raise RuntimeError(s)
                        self.prev = (int(m.group(2)), int(m.group(1)))
                        self.cur = (int(m.group(6)), int(m.group(5)))
                        g = m.group(7)
                        self.dp = 'rdlu'.index(g[0])
                        self.cc = int(g[2] == 'r')
                        g = m.group(3)
                        self.prev_dp = 'rdlu'.index(g[0])
                        self.prev_cc = int(g[2] == 'r')
                        cf = m.group(4)
                        ct = m.group(8)
                        self.prev_color = color_names[colors[cf]]
                        self.cur_color = color_names[colors[ct]]
                        if cf == 'WW' or ct == 'WW':
                            self.hldiff = None
                        elif self._white:
                            self.hldiff = None
                            self._white = False
                        else:
                            self.hldiff = self.diff(cf, ct)
                    elif s.startswith('stack', 7):
                        if self._update_stack == 0:
                            if s.startswith('stack is empty'):
                                self.stack = []
                            else:
                                self.stack = map(int, islice(s.rsplit(), 4, None))
                        elif self._update_stack == 1:
                            self._update_stack = 0
                        else:
                            if s.startswith('stack is empty'):
                                self._stack_str = ''
                            else:
                                i = s.index(':')
                                self._stack_str = s
                    elif s.startswith('white cell(s) crossed', 7):
                        self._white = True
                elif s.startswith('action:'):
                    try:
                        i = s.index(',')
                        self.op = s[8:i]
                        self.arg = int(s[i + 8:])
                    except ValueError:
                        self.op = s[8:-1]
                        self.arg = None
                    try:
                        self._op_func = self._io_ops[self.op]
                        self.state = self.ST_OP
                        self._s = None
                        self._op_func(self)
                    except KeyError:
                        pass
                else:
                    raise RuntimeError(s)
                s = self._proc.stdout.readline()

    lstep = step

    def run_start(self):
        self._update_stack = 2
        self.step()

    def run_stop(self):
        self._update_stack = 0
        if self._stack_str is not None:
            if self._stack_str == '':
                self.stack = []
            else:
                self.stack = map(int, islice(self._stack_str.rsplit(), 4, None))
            self._stack_str = None

    def run(self):
        try:
            self.run_start()
            while self.state != self.ST_END and not self.cur in self.codel_breakpoints:
                self.step()
        finally:
            self.run_stop()

    def reset(self, bp = True):
        self.state = self.ST_END
        interpreter_base.reset(self, bp)
        self._white = False
        self._s = None
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None

    def rewind(self, bp = False):
        self.reset(bp)
        try:
            self._proc = Popen(self.args, executable = self.npiet, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
        except OSError, e:
            self._proc = None
            raise RuntimeError('Cound not start interpreter: ' + str(e))
        try:
            s = self._proc.stdout.readline()
            cs = self.codel_size
            while s != '\n':
                if s == '':
                    raise RuntimeError('terminated')
                if not s.startswith('info:'):
                    if s.startswith('trace:'):
                        if s.startswith('special case: we started at a black cell', 7):
                            self._proc.terminate()
                            self._proc.wait()
                            self._proc = None
                    else:
                        raise RuntimeError(s)
                elif s.startswith('codelsize guessed is ', 6):
                    cs = int(s[27:-7])
                else:
                    m = self.re_size.match(s)
                    if m is not None:
                        self.width = int(m.group(1))
                        self.height = int(m.group(2))
                s = self._proc.stdout.readline()
            self.state = self.ST_NEXT
            self.codel_size = cs
            self.width /= self.codel_size
            self.height /= self.codel_size
        except RuntimeError:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None
            raise

    def init(self, fname,
             gc = None, pc = None, gi = None, pi = None,
             cs = None, uc = unknown_white):
        self.args = [self.npiet, '-v', '-t']
        if cs is not None:
            self.args += [ '-cs', str(cs) ]
        if uc == unknown_black:
            self.args.append('-ub')
        elif uc == unknown_error:
            self.args.append('-uu')
        self.args.append(fname)

        if gc is not None:
            self.get_char = gc
        if pc is not None:
            self.put_char = pc
        if gi is not None:
            self.get_int = gi
        if pi is not None:
            self.put_int = pi

        self.rewind(True)
