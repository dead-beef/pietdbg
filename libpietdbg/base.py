def unknown_black(cl):
    return CL_BLACK
def unknown_white(cl):
    return CL_WHITE
def unknown_error(cl):
    raise ValueError(''.join(('unknown color: ', str(cl))))

colors = (
    ('#FFC0C0', 'light red'),
    ('#FF0000', 'red'),
    ('#C00000', 'dark red'),
    ('#FFFFC0', 'light yellow'),
    ('#FFFF00', 'yellow'),
    ('#C0C000', 'dark yellow'),
    ('#C0FFC0', 'light green'),
    ('#00FF00', 'green'),
    ('#00C000', 'dark green'),
    ('#C0FFFF', 'light cyan'),
    ('#00FFFF', 'cyan'),
    ('#00C0C0', 'dark cyan'),
    ('#C0C0FF', 'light blue'),
    ('#0000FF', 'blue'),
    ('#0000C0', 'dark blue'),
    ('#FFC0FF', 'light magenta'),
    ('#FF00FF', 'magenta'),
    ('#C000C0', 'dark magenta'),
    ('#FFFFFF', 'white'),
    ('#000000', 'black')
)

states = (
    'ST_NEXT',
    'ST_END',
    'ST_BLACK',
    'ST_OUT',
    'ST_OP'
)

class interpreter_base(object):
    ST_NEXT = 0
    ST_END = 1
    ST_BLACK = 2
    ST_OUT = 3
    ST_OP = 4

    _offset = (
        (0, 1),
        (1, 0),
        (0, -1),
        (-1, 0)
    )

    def __init__(self):
        self.stack = []
        self.prev = (0, 0)
        self.cur = (0, 0)
        self.op = 'none'
        self.arg = None
        self.hldiff = None
        self.dp = 0
        self.cc = 0
        self.prev_dp = 0
        self.prev_cc = 0
        self.prev_color = None
        self.cur_color = None
        self.width = 0
        self.height = 0
        self.codel_size = 1
        self.state = self.ST_END
        self.codel_breakpoints = []
        self.get_char = None
        self.put_char = None
        self.get_int = None
        self.put_int = None

    def reset(self, bp = True):
        self.stack = []
        if bp:
            self.codel_breakpoints = []
        self.prev = (0, 0)
        self.cur = (0, 0)
        self.op = 'none'
        self.arg = None
        self.hldiff = None
        self.dp = 0
        self.cc = 0
