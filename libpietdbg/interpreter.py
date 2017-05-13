from fractions import gcd
from itertools import islice
from base import interpreter_base, unknown_black, unknown_white, unknown_error

#import gtk
#import profile
#import _interpreter
#i = _interpreter.interpreter()
#pa = gtk.gdk.pixbuf_new_from_file('examples/pietquest.png').get_pixels_array()
#profile.run('i.init(pa)')

colors = {
    "#FFC0C0": 0,
    "#FF0000": 1,
    "#C00000": 2,
    "#FFFFC0": 3,
    "#FFFF00": 4,
    "#C0C000": 5,
    "#C0FFC0": 6,
    "#00FF00": 7,
    "#00C000": 8,
    "#C0FFFF": 9,
    "#00FFFF": 10,
    "#00C0C0": 11,
    "#C0C0FF": 12,
    "#0000FF": 13,
    "#0000C0": 14,
    "#FFC0FF": 15,
    "#FF00FF": 16,
    "#C000C0": 17,
    "#FFFFFF": 18,
    "#000000": 19
}
CL_WHITE = 18
CL_BLACK = 19
N_HUES = 6
N_LIGHTS = 3

class codel(object):
    def __init__(self, color):
        rgb = '#%02X%02X%02X' % (color[0], color[1], color[2])
        try:
            self.color = colors[rgb]
        except KeyError:
            self.color = self.unknown_color(rgb)

        self.block = None
        if self.color == CL_WHITE:
            self.used = []

class block(object):
    def __init__(self, image, co, blocks):
        c = image[co[0]][co[1]]
        self.image = image
        self.codels = [c]
        self.blocks = blocks
        self.bounds = [[co for y in xrange(2)] for x in xrange(4)]
        self.size = None
        self.white = (c.color == CL_WHITE)
        #image[co[0]][co[1]].block = self
        blocks.append(self)

    def _update_bounds(self, co):
        if co[1] > self.bounds[0][1][1]:
            self.bounds[0][1] = co
            self.bounds[0][0] = co
        elif co[1] < self.bounds[2][1][1]:
            self.bounds[2][1] = co
            self.bounds[2][0] = co
        else:
            if co[1] == self.bounds[0][1][1]:
                if co[0] > self.bounds[0][1][0]:
                    self.bounds[0][1] = co
                elif co[0] < self.bounds[0][0][0]:
                    self.bounds[0][0] = co
            if co[1] == self.bounds[2][1][1]:
                if co[0] < self.bounds[2][1][0]:
                    self.bounds[2][1] = co
                elif co[0] > self.bounds[2][0][0]:
                    self.bounds[2][0] = co

        if co[0] > self.bounds[1][1][0]:
            self.bounds[1][1] = co
            self.bounds[1][0] = co
        elif co[0] < self.bounds[3][1][0]:
            self.bounds[3][1] = co
            self.bounds[3][0] = co
        else:
            if co[0] == self.bounds[1][1][0]:
                if co[1] < self.bounds[1][1][1]:
                    self.bounds[1][1] = co
                elif co[1] > self.bounds[1][0][1]:
                    self.bounds[1][0] = co
            if co[0] == self.bounds[3][1][0]:
                if co[1] > self.bounds[3][1][1]:
                    self.bounds[3][1] = co
                elif co[1] < self.bounds[3][0][1]:
                    self.bounds[3][0] = co

    def __iadd__(self, co):
        c = self.image[co[0]][co[1]]
        c.block = self
        self.codels.append(c)
        self._update_bounds(co)
        return self

    def __le__(self, bl):
        for co in bl.codels:
            co.block = self
        for dpb in bl.bounds:
            for b in dpb:
                self._update_bounds(b)
        self.codels += bl.codels
        self.blocks.remove(bl)
        return self

class interpreter(interpreter_base):
    def _add(self):
        if len(self.stack) >= 2:
            x = self.stack.pop()
            self.stack[-1] += x
    def _divide(self):
        if len(self.stack) >= 2:
            x = self.stack.pop()
            if x != 0:
                self.stack[-1] /= x
            else:
                self.stack.append(x)
    def _greater(self):
        if len(self.stack) >= 2:
            x = self.stack.pop()
            y = self.stack.pop()
            self.stack.append(int(y > x))
    def _duplicate(self):
        if len(self.stack) > 0:
            self.stack.append(self.stack[-1])
    def _in_char(self):
        self.stack.append(ord(self.get_char()))
    def _push(self):
        self.stack.append(self.arg)
    def _subtract(self):
        if len(self.stack) >= 2:
            x = self.stack.pop()
            self.stack[-1] -= x
    def _mod(self):
        if len(self.stack) >= 2:
            x = self.stack.pop()
            if x != 0:
                self.stack[-1] %= x
            else:
                self.stack.append(x)
    def _pointer(self):
        if len(self.stack) > 0:
            x = self.stack.pop()
            self.dp = (self.dp + x) % 4
    def _roll(self):
        if len(self.stack) >= 2:
            x = self.stack.pop()
            y = self.stack.pop()
            if y < 0 or len(self.stack) <= y:
                self.stack += [y, x]
            elif y > 0:
                y += 1
                x %= y
                if x > 0:
                    tmp = self.stack[-x:]
                    self.stack[x - y:] = self.stack[-y : -x]
                    self.stack[-y : x - y] = tmp
    def _out_number(self):
        if len(self.stack) > 0:
            self.put_int(self.stack[-1])
            self.stack.pop()
    def _pop(self):
        if len(self.stack) > 0:
            self.stack.pop()
    def _multiply(self):
        if len(self.stack) >= 2:
            x = self.stack.pop()
            self.stack[-1] *= x
    def _not(self):
        if len(self.stack) > 0:
            x = self.stack.pop()
            self.stack.append(int(x == 0))
    def _switch(self):
        if len(self.stack) > 0:
            self.cc ^= self.stack.pop() & 1
    def _in_number(self):
        self.stack.append(self.get_int())
    def _out_char(self):
        if len(self.stack) > 0:
            self.put_char(unichr(self.stack[len(self.stack) - 1]))
            self.stack.pop()

    _ops = {
        (1,0): ('add', _add),
        (2,0): ('divide', _divide),
        (3,0): ('greater', _greater),
        (4,0): ('duplicate', _duplicate),
        (5,0): ('in(char)', _in_char),
        (0,1): ('push', _push),
        (1,1): ('subtract', _subtract),
        (2,1): ('mod', _mod),
        (3,1): ('pointer', _pointer),
        (4,1): ('roll', _roll),
        (5,1): ('out(number)', _out_number),
        (0,2): ('pop', _pop),
        (1,2): ('multiply', _multiply),
        (2,2): ('not', _not),
        (3,2): ('switch', _switch),
        (4,2): ('in(number)', _in_number),
        (5,2): ('out(char)', _out_char),
    }

    def __init__(self):
        interpreter_base.__init__(self)
        self.image = None
        self.unknown_color = None
        self.get_codel = None
        self.turns = 0
        self.block_breakpoints = []

    def diff(self, c_from, c_to):
        f_hue, f_light = divmod(self.image[c_from[0]][c_from[1]].color, N_LIGHTS)
        t_hue, t_light = divmod(self.image[c_to[0]][c_to[1]].color, N_LIGHTS)
        hue_diff = t_hue - f_hue
        light_diff = t_light - f_light
        if hue_diff < 0:
            hue_diff += N_HUES
        if light_diff < 0:
            light_diff += N_LIGHTS
        return (hue_diff, light_diff)

    def is_white(self, co):
        return self.image[co[0]][co[1]].color == CL_WHITE
    def is_black(self, co):
        return co[0] < 0 or co[0] >= self.height or\
               co[1] < 0 or co[1] >= self.width or\
               self.image[co[0]][co[1]].color == CL_BLACK
    def next(self, co):
        o = self._offset[self.dp]
        return (co[0] + o[0], co[1] + o[1])
    def bound(self, co):
        return self.image[co[0]][co[1]].block.bounds[self.dp][self.cc]
    def size(self, co):
        return self.image[co[0]][co[1]].block.size

    def _clear(self, co):
        for c in self.image[co[0]][co[1]].block.codels:
            c.used = []

    def _st_next(self):
        self.prev = self.cur
        self.prev_color = self.cur_color
        if self.is_white(self.cur):
            self.arg = None
            while self.is_white(self.cur):
                co = self.next(self.cur)
                if self.is_black(co):
                    self.turns = 0
                    self.state = self.ST_BLACK
                    self.cur_color = self.image[self.cur[0]][self.cur[1]]
                    return
                self.cur = co
            self.state = self.ST_NEXT
            self.cur_color = self.image[self.cur[0]][self.cur[1]]
        else:
            self.arg = self.size(self.cur)
            self.cur = self.bound(self.cur)
            self.state = self.ST_OUT

    def _st_out(self):
        co = self.next(self.cur)
        if self.is_black(co):
            self.state = self.ST_BLACK
        elif self.is_white(co) or self.is_white(self.cur):
            self.prev = self.cur
            self.prev_color = self.cur_color
            self.cur = co
            self.turns = 0
            self.state = self.ST_NEXT
            self.cur_color = self.image[self.cur[0]][self.cur[1]]
        else:
            self.prev = self.cur
            self.prev_color = self.cur_color
            self.cur = co
            self.hldiff = self.diff(self.prev, self.cur)
            self.op = self._ops[self.hldiff][0]
            self.turns = 0
            self.state = self.ST_OP
            self.cur_color = self.image[self.cur[0]][self.cur[1]]

    def _st_op(self):
        self._ops[self.hldiff][1](self)
        self.op = 'none'
        self.hldiff = None
        self.state = self.ST_NEXT

    def _st_black(self):
        self.prev_dp = self.dp
        self.prev_cc = self.cc
        if self.is_white(self.cur):
            self.cc ^= 1
            self.dp = (self.dp + 1) & 3
            self.prev = self.cur
            self.prev_color = self.cur_color
            co = self.next(self.cur)
            while not self.is_black(co):
                if self.is_white(co):
                    if self.dp in self.image[co[0]][co[1]].used:
                        self.state = self.ST_END
                        return
                    else:
                        self.image[co[0]][co[1]].used.append(self.dp)
                        self.cur = co
                        co = self.next(co)
                else:
                    self._clear(self.cur)
                    self.cur = co
                    self.cur_color = self.image[self.cur[0]][self.cur[1]]
                    self.state = self.ST_NEXT
                    return
        else:
            self.turns += 1
            if self.turns >= 8:
                self.state = self.ST_END
            else:
                if self.turns & 1:
                    self.cc ^= 1
                else:
                    self.dp = (self.dp + 1) & 3
                self.prev = self.cur
                self.prev_color = self.cur_color
                self.cur = self.bound(self.cur)
                self.cur_color = self.image[self.cur[0]][self.cur[1]]
                self.state = self.ST_OUT

    def _st_end(self):
        pass

    _state_func = (
        _st_next,
        _st_end,
        _st_black,
        _st_out,
        _st_op
    )

    def step(self):
        self._state_func[self.state](self)
    def lstep(self):
        self.step()
        while self.state != self.ST_END and self.state != self.ST_NEXT:
            if self.cur in self.codel_breakpoints or\
               self.image[self.cur[0]][self.cur[1]].block in self.block_breakpoints:
                return
            self._state_func[self.state](self)
    def run(self):
        self.step()
        while self.state != self.ST_END:
            if self.cur in self.codel_breakpoints or\
               self.image[self.cur[0]][self.cur[1]].block in self.block_breakpoints:
                return
            self._state_func[self.state](self)

    def get_color(self, cl):
        rgb = '#%02X%02X%02X' % (cl[0], cl[1], cl[2])
        try:
            return colors[rgb]
        except KeyError:
            return self.unknown_color(rgb)

    def _is_color_block(self, pixels, cl, prev, ret):
        for i in xrange(prev, ret):
            for j in xrange(0, prev):
                if self.get_color(pixels[i][j]) != cl or\
                   self.get_color(pixels[j][i]) != cl:
                    return False
            for j in xrange(prev, ret):
                if self.get_color(pixels[i][j]) != cl:
                    return False
        return True

    def guess_codel_size(self, pixels, w, h):
        prev = 1
        ret = 2
        cl = self.get_color(pixels[0][0])
        m = gcd(w, h)
        while ret <= m and self._is_color_block(pixels, cl, prev, ret):
            prev = ret
            ret += 1
        ret = prev
        while w % ret or h % ret:
            ret -= 1
        return ret

    def init(self, pixels,
             gc = None, pc = None, gi = None, pi = None,
             cs = None, uc = unknown_white):
        self.height = len(pixels)
        if self.height <= 0:
            raise ValueError(''.join('invalid image height: %d' % self.height))
        self.width = len(pixels[0])
        if self.width <= 0:
            raise ValueError(''.join('invalid image width: %d' % self.width))
        if cs is None:
            self.codel_size = self.guess_codel_size(pixels, self.width, self.height)
        else:
            if cs <= 0:
                raise ValueError('invalid codel size: %d' % cs)
            if self.width % cs or cs > self.width:
                raise ValueError('codel size %u does not match width of %u pixels' % (cs, self.width))
            elif self.height % cs or cs > self.height:
                raise ValueError('codel size %u does not match height of %u pixels' % (cs, self.height))
            self.codel_size = cs

        blocks = []
        self.image = [ [ codel(cl) for cl in islice(row, 0, self.width, self.codel_size) ] for row in islice(pixels, 0, self.height, self.codel_size) ]
        self.width /= self.codel_size
        self.height /= self.codel_size
        for y in xrange(self.height):
            for x in xrange(self.width):
                p = self.image[y][x]
                if p.color <= CL_WHITE:
                    if x and self.image[y][x - 1].color == p.color:
                        self.image[y][x - 1].block += (y, x)
                    if y and self.image[y - 1][x].color == p.color:
                        if p.block is None:
                            self.image[y - 1][x].block += (y, x)
                        elif self.image[y - 1][x].block != p.block:
                            self.image[y - 1][x].block <= p.block
                    if p.block is None:
                        p.block = block(self.image, (y, x), blocks)

        for b in blocks:
            b.size = len(b.codels)
            if not b.white:
                del b.codels
            del b.image
            del b.blocks

        if self.image[0][0].color == CL_BLACK:
            self.state = self.ST_END
        else:
            self.state = self.ST_NEXT

        self.stack = []
        self.prev = (0, 0)
        self.cur = (0, 0)
        self.op = 'none'
        self.arg = None
        self.hldiff = None
        self.dp = 0
        self.cc = 0
        self.turns = 0
        self.codel_breakpoints = []
        self.block_breakpoints = []

        if gc is not None:
            self.get_char = gc
        if pc is not None:
            self.put_char = pc
        if gi is not None:
            self.get_int = gi
        if pi is not None:
            self.put_int = pi
        self.unknown_color = uc

    def reset(self):
        if self.image is not None:
            if self.state == self.ST_BLACK and self.is_white(self.cur):
                self._clear(self.cur)

            if self.image[0][0].color == CL_BLACK:
                self.state = self.ST_END
            else:
                self.state = self.ST_NEXT
            interpreter_base.reset(self)
            self.turns = 0
