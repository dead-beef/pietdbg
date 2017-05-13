import pygtk
pygtk.require('2.0')
import gtk

from sys import exc_info
from traceback import format_exception
from itertools import ifilter, izip
from collections import deque
from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError
import os

from util import fxrange, in_area, InputError,\
                 open_dialog, config_dialog,\
                 interpreter_thread,\
                 show_exception

from base import colors, states,\
                 unknown_black, unknown_white, unknown_error
import npiet

class debugger(object):
    def destroy(self, widget, data = None):
        fp = None
        try:
            fp = open(self.cfg_path, 'w')
            self.cfg.write(fp)
        except:
            show_exception()
        finally:
            if fp is not None:
                fp.close()
        if self.interpreter is not None:
            if self.running:
                self.pause()
            self.interpreter.reset()
        gtk.main_quit()
        return False

    def key_press(self, widget, event):
        #key = gtk.gdk.keyval_name(event.keyval)
        #print key
        return False

    def key_release(self, widget, event):
        #key = gtk.gdk.keyval_name(event.keyval)
        #print key
        return False

    def leave_notify(self, widget, event):
        self.codel = None
        self.statusbar.pop(self.context)
        return False

    def motion_notify(self, widget, event):
        if event.is_hint:
            x, y, state = event.window.get_pointer()
        else:
            state = event.state

        x = event.x_root
        y = event.y_root

        a = self.sw_img.get_allocation()

        if state & (gtk.gdk.BUTTON2_MASK | gtk.gdk.BUTTON1_MASK):
            a = self.sw_img.get_allocation()
            xsb = self.sw_img.get_hscrollbar()
            xadj = xsb.get_adjustment()
            newx = xsb.get_value() + (self.prev_x - x)
            if newx >= xadj.lower and newx <= xadj.upper - xadj.page_size:
                xsb.set_value(newx)

            ysb = self.sw_img.get_vscrollbar()
            yadj = ysb.get_adjustment()
            newy = ysb.get_value() + (self.prev_y - y)
            if newy >= yadj.lower and newy <= yadj.upper - yadj.page_size:
                ysb.set_value(newy)
        elif self.pixbuf is not None:
            self.statusbar.pop(self.context)
            self.codel = (int(event.x / self.pixel_size), int(event.y / self.pixel_size))
            self.statusbar.push(self.context, str(self.codel))

        self.prev_x = x
        self.prev_y = y

        return False

    def button_press(self, widget, event):
        if self.pixbuf is not None and\
           event.button == 3 and\
           not self.running and\
           event.x < self.pixbuf.get_width() and\
           event.y < self.pixbuf.get_height():
            co = (int(event.y / self.pixel_size),
                  int(event.x / self.pixel_size))
            try:
                self.interpreter.codel_breakpoints.remove(co)
            except ValueError:
                self.interpreter.codel_breakpoints.append(co)
            self.da.queue_draw()
        return False

    def scroll(self, co):
        for x, sb in izip(co, (self.sw_img.get_hscrollbar(), self.sw_img.get_vscrollbar())):
            adj = sb.get_adjustment()
            max = adj.upper - adj.page_size
            val = int((x + 0.5) * self.pixel_size - adj.page_size * 0.5)
            if val < 0:
                val = 0
            elif val > max:
                val = max
            sb.set_value(val)
        self.da.queue_draw()

    def scroll_1(self):
        for x, x1, sb in izip(self.codel,
                              self.da.get_pointer(),
                              (self.sw_img.get_hscrollbar(), self.sw_img.get_vscrollbar())):
            adj = sb.get_adjustment()
            x1 -= adj.get_value()
            max = adj.upper - adj.page_size
            val = int((x + 0.5) * self.pixel_size) - x1
            if val < 0:
                val = 0
            elif val > max:
                val = max
            sb.set_value(val)
        #self.da.queue_draw()

    def size_allocate(self, widget, allocation):
        if self.codel is not None:
            self.scroll_1()
        elif self.codel_1 is not None:
            self.scroll(self.codel_1)

    def scroll_event(self, widget, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            if event.direction == gtk.gdk.SCROLL_UP:
                self.zoom_in(None)
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                self.zoom_out(None)
            return True
        return False

    def update_pixbuf(self):
        width = int(self.image.get_width() * self.scale)
        height = int(self.image.get_height() * self.scale)
        if width <= 0 or height <= 0:
            return False

        self.codel_1 = tuple(int((adj.get_value() + adj.get_page_size() / 2.0) / self.pixel_size)
                             for adj in (self.sw_img.get_hadjustment(), self.sw_img.get_vadjustment()))

        self.pixbuf = self.image.scale_simple(width, height, gtk.gdk.INTERP_NEAREST)
        self.pixbuf_rect = gtk.gdk.Rectangle(0, 0, self.pixbuf.get_width(), self.pixbuf.get_height())
        self.pixel_size = self.scale * self.interpreter.codel_size
        self.da.set_size_request(self.pixbuf.get_width(), self.pixbuf.get_height())
        return True

    def zoom_in(self, widget):
        if self.pixbuf is not None:
            self.scale *= 1.25
            if not self.update_pixbuf():
                self.scale /= 1.25

    def zoom_out(self, widget):
        if self.pixbuf is not None:
            self.scale /= 1.25
            if not self.update_pixbuf():
                self.scale *= 1.25

    def zoom_100(self, widget):
        if self.pixbuf is not None:
            self.scale = 1.0
            self.pixel_size = self.interpreter.codel_size
            self.pixbuf = self.image
            self.pixbuf_rect = gtk.gdk.Rectangle(0, 0, self.pixbuf.get_width(), self.pixbuf.get_height())
            self.da.set_size_request(self.pixbuf.get_width(), self.pixbuf.get_height())
            self.da.queue_draw()

    dp_s = (
        (1, 0),
        (0, 1),
        (-1, 0),
        (0, -1)
    )

    def draw_dp_cc(self, w, gc):
        gc.set_rgb_fg_color(self.selection_bg_color)

        ls = max(5, int(self.pixel_size / 2))

        gc.set_line_attributes(ls, gtk.gdk.LINE_SOLID,
                               gtk.gdk.CAP_ROUND, gtk.gdk.JOIN_ROUND)

        x = int(self.interpreter.cur[1] * self.pixel_size + self.pixel_size / 2)
        y = int(self.interpreter.cur[0] * self.pixel_size + self.pixel_size / 2)

        d = max(16, int(4 * self.pixel_size))
        d1 = int(d / 2)
        #d2 = int(d1 / 2)
        #d3 = int(d2 / 2)
        dps = self.dp_s[self.interpreter.dp]
        if self.interpreter.cc:
            ccs = (-dps[1], dps[0])
        else:
            ccs = (dps[1], -dps[0])
        x1 = x + dps[0] * d
        y1 = y + dps[1] * d
        x2 = x + ccs[0] * d1
        y2 = y + ccs[1] * d1
        #dx1 = d2 * dps[0]
        #dy1 = d3 * dps[1]

        w.draw_line(gc, x, y, x1, y1)
        w.draw_line(gc, x, y, x2, y2)
        gc.set_line_attributes(ls, gtk.gdk.LINE_SOLID,
                               gtk.gdk.CAP_ROUND, gtk.gdk.JOIN_MITER)
        #w.draw_line(gc, x1, y1, x1 - dx1, y - dy1)
        #w.draw_line(gc, x1, y1, x1 - dx1, y + dy1)

        ls -= 2
        dps = (2 * dps[0], 2 * dps[1])
        #dx1 -= dps[0]
        #dy1 -= dps[1]
        x1 -= dps[0]
        y1 -= dps[1]
        x2 -= 2 * ccs[0]
        y2 -= 2 * ccs[1]

        gc.set_rgb_fg_color(self.selection_color)
        gc.set_rgb_bg_color(self.selection_bg_color)
        gc.set_line_attributes(ls, gtk.gdk.LINE_SOLID,
                               gtk.gdk.CAP_ROUND, gtk.gdk.JOIN_ROUND)
        w.draw_line(gc, x, y, x1, y1)
        gc.set_line_attributes(ls, gtk.gdk.LINE_DOUBLE_DASH,
                               gtk.gdk.CAP_ROUND, gtk.gdk.JOIN_ROUND)
        w.draw_line(gc, x, y, x2, y2)
        #gc.set_line_attributes(ls, gtk.gdk.LINE_SOLID,
        #                       gtk.gdk.CAP_ROUND, gtk.gdk.JOIN_MITER)
        #w.draw_line(gc, x1, y1, x1 - dx1, y1 - dy1)
        #w.draw_line(gc, x1, y1, x1 - dx1, y1 + dy1)

    def highlight_codel(self, w, gc, x, y, r):
        x0 = int(x + self.pixel_size / 2 - r)
        y0 = int(y + self.pixel_size / 2 - r)
        r *= 2
        w.draw_arc(gc, False, x0, y0, r, r, 0, 23040)
        #r += 2
        #w.draw_arc(gc, False, x0 - 2, y0 - 2, r, r, 0, 23040)

    def expose(self, widget, event):
        if self.pixbuf is not None:
            area = event.area.intersect(self.pixbuf_rect)
            if area.width > 0 and area.height > 0:
                gc = self.da.style.black_gc 
                w = self.da.window
                w.draw_pixbuf(
                    gc,
                    self.pixbuf,
                    area.x, area.y,
                    area.x, area.y,
                    area.width, area.height)

                if self.pixel_size >= 3:
                    gc.set_line_attributes(2, gtk.gdk.LINE_SOLID,
                                           gtk.gdk.CAP_BUTT, gtk.gdk.JOIN_MITER)
                    gc.set_rgb_fg_color(self.grid_color)

                    x0 = area.x - area.x % self.pixel_size
                    y0 = area.y - area.y % self.pixel_size

                    y = area.y
                    y1 = area.y + area.height

                    for x in fxrange(x0, area.x + area.width, self.pixel_size):
                        w.draw_line(gc, x, y, x, y1)

                    x = area.x
                    x1 = area.x + area.width
                    for y in fxrange(y0, area.y + area.height, self.pixel_size):
                        w.draw_line(gc, x, y, x1, y)

                r = max(4, int(self.pixel_size / 3))
                gc.set_line_attributes(r, gtk.gdk.LINE_DOUBLE_DASH,
                                       gtk.gdk.CAP_ROUND, gtk.gdk.JOIN_ROUND)
                gc.set_rgb_fg_color(self.breakpoint_color)
                gc.set_rgb_bg_color(self.breakpoint_bg_color)

                for bp in ifilter(in_area(area, self.pixel_size), self.interpreter.codel_breakpoints):
                    self.highlight_codel(w, gc,
                                         int(bp[1] * self.pixel_size),
                                         int(bp[0] * self.pixel_size),
                                         r)

                if not self.running:
                    self.draw_dp_cc(w, gc)
                    gc.set_line_attributes(r, gtk.gdk.LINE_DOUBLE_DASH,
                                           gtk.gdk.CAP_ROUND, gtk.gdk.JOIN_ROUND)
                    self.highlight_codel(w, gc,
                                         int(self.interpreter.cur[1] * self.pixel_size),
                                         int(self.interpreter.cur[0] * self.pixel_size),
                                         r)
                    self.highlight_codel(w, gc,
                                         int(self.interpreter.prev[1] * self.pixel_size),
                                         int(self.interpreter.prev[0] * self.pixel_size),
                                         r)

                gc.set_rgb_fg_color(self.black)
                gc.set_rgb_bg_color(self.white)
                gc.set_line_attributes(r, gtk.gdk.LINE_SOLID,
                                       gtk.gdk.CAP_ROUND, gtk.gdk.JOIN_ROUND)

        return False

    uc_str = {
        unknown_black: 'black',
        unknown_white: 'white',
        unknown_error: 'error'
    }
    dp_str = ('right', 'down', 'left', 'up')
    cc_str = ('left', 'right')

    def update_labels_1(self):
        self.l_state.set_text(states[self.interpreter.state])
        self.l_dp.set_text(self.dp_str[self.interpreter.dp])
        self.l_cc.set_text(self.cc_str[self.interpreter.cc])
        self.l_co.set_text(str((self.interpreter.cur[1], self.interpreter.cur[0])))
        if self.interpreter.cur_color is None:
            self.l_cl.set_text('N/A')
        else:
            self.l_cl.set_text(self.interpreter.cur_color[1])
        self.l_prev_dp.set_text(self.dp_str[self.interpreter.prev_dp])
        self.l_prev_cc.set_text(self.cc_str[self.interpreter.prev_cc])
        self.l_prev_co.set_text(str((self.interpreter.prev[1], self.interpreter.prev[0])))
        if self.interpreter.prev_color is None:
            self.l_prev_cl.set_text('N/A')
        else:
            self.l_prev_cl.set_text(self.interpreter.prev_color[1])
        if self.interpreter.hldiff is None:
            self.l_hdiff.set_text('N/A')
            self.l_ldiff.set_text('N/A')
        else:
            self.l_hdiff.set_text(str(self.interpreter.hldiff[0]))
            self.l_ldiff.set_text(str(self.interpreter.hldiff[1]))
        if self.interpreter.op is None:
            self.l_op.set_text('N/A')
        else:
            self.l_op.set_text(self.interpreter.op)
        if self.interpreter.arg is None:
            self.l_arg.set_text('N/A')
        else:
            self.l_arg.set_text(str(self.interpreter.arg))

    def update_labels(self):
        if self.pixbuf is None:
            self.l_cs.set_text('N/A')
            self.l_uc.set_text('N/A')
            self.l_state.set_text('N/A')
            self.l_dp.set_text('N/A')
            self.l_cc.set_text('N/A')
            self.l_co.set_text('N/A')
            self.l_cl.set_text('N/A')
            self.l_prev_dp.set_text('N/A')
            self.l_prev_cc.set_text('N/A')
            self.l_prev_co.set_text('N/A')
            self.l_prev_cl.set_text('N/A')
            self.l_hdiff.set_text('N/A')
            self.l_ldiff.set_text('N/A')
            self.l_op.set_text('N/A')
            self.l_arg.set_text('N/A')
        else:
            self.l_cs.set_text(str(self.interpreter.codel_size))
            self.l_uc.set_text(self.unknown_colors)
            self.update_labels_1()

        self.statusbar.pop(self.context)
        self.input_buf.clear()
        buf = self.tv_out.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        self.ls_stack.clear()
        self.stack_size = 0

        if self.image is None:
            self.da.set_size_request(0, 0)
        else:
            self.da.set_size_request(int(self.image.get_width() * self.scale),
                                     int(self.image.get_height() * self.scale))

    def update_stack(self):
        st = self.interpreter.stack
        x = len(st) - self.stack_size
        if x > 0:
            for i in xrange(x):
                self.ls_stack.prepend([st[i]])
        else:
            for i in xrange(x, 0):
                self.ls_stack.remove(self.ls_stack.get_iter_first())
            i = -1
        self.stack_size = len(st)
        for i in xrange(i + 1, self.stack_size):
            self.ls_stack.set(self.ls_stack.iter_nth_child(None, i), 0, st[i])

    def set_open(self, b):
        self.update_labels()
        self.btn_close.set_sensitive(b)
        self.btn_step.set_sensitive(b)
        self.btn_run.set_sensitive(b)
        self.btn_clear.set_sensitive(b)
        self.btn_zoom_in.set_sensitive(b)
        self.btn_zoom_out.set_sensitive(b)
        self.btn_zoom_100.set_sensitive(b)
        self.btn_reset.set_sensitive(b)
        self.sw_out.set_sensitive(b)
        self.entry.set_sensitive(b)

    def do_open(self, fname, c_s, u_c):
        try:
            is_open = False
            if self.running:
                self.pause()
            self.interpreter.init(fname, cs=c_s, uc=u_c)
            self.image = gtk.gdk.pixbuf_new_from_file(fname)
            self.pixbuf = self.image
            self.pixbuf_rect = gtk.gdk.Rectangle(0, 0, self.pixbuf.get_width(), self.pixbuf.get_height())
            self.scale = 1.0
            self.pixel_size = self.interpreter.codel_size
            self.unknown_colors = self.uc_str[u_c]
            is_open = True
        except RuntimeError:
            self.image = None
            self.pixbuf = self.image
            show_exception()

        self.set_open(is_open)
        self.da.queue_draw()

    def open(self, widget):
        if self.interpreter is not None:
            dialog = open_dialog()
            dialog.show_all()
            response = dialog.run()
            if response == gtk.RESPONSE_OK and dialog.fname is not None:
                self.do_open(dialog.fname, dialog.codel_size, dialog.unknown_colors)
            dialog.destroy()

    def close(self, widget):
        if self.running:
            self.pause()
        self.interpreter.reset()
        self.image = None
        self.pixbuf = self.image
        self.set_open(False)
        self.codel = None
        self.codel_1 = None
        self.da.queue_draw()

    def clear_breakpoints(self, widget):
        if self.interpreter is not None:
            self.interpreter.codel_breakpoints = []
            self.interpreter.block_breakpoints = []
            self.da.queue_draw()

    def step(self, widget):
        try:
            self.update_stack()
            self.interpreter.step()
            self.update_labels_1()
            self.da.queue_draw()
        except InputError:
            self.update_labels_1()
            self.da.queue_draw()
        except:
            show_exception()
            self.close(None)

    def set_running(self, b):
        self.running = b
        self.btn_stop.set_sensitive(b)
        b = not b
        self.btn_step.set_sensitive(b)
        self.btn_run.set_sensitive(b)
        self.btn_clear.set_sensitive(b)
        self.entry.set_sensitive(b)

    def run(self, widget):
        try:
            self.set_running(True)
            self.da.queue_draw()
            self.thread.start()
        except:
            ex_type, ex_value, ex_traceback = exc_info()
            show_exception()
        return False
        #try:
        #    self.interpreter.run()
        #    self.update_labels_1()
        #    self.update_stack()
        #    self.da.queue_draw()
        #except InputError:
        #    self.update_labels_1()
        #    self.da.queue_draw()
        #except:
        #    ex_type, ex_value, ex_traceback = exc_info()
        #    d = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
        #                          gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
        #                          ''.join(format_exception(ex_type, ex_value, ex_traceback)))
        #    d.run()
        #    d.destroy()
        #    self.close(None)

    def run_cb(self):
        self.set_running(False)
        if self.thread.error < 2:
            self.update_labels_1()
            if self.thread.error == 0:
                self.update_stack()
            self.da.queue_draw()
        else:
            self.close(None)

    def pause(self, widget=None):
        #self.thread.set_callback(None)
        self.thread.stop()
        #self.run_cb()
        #self.thread.set_callback(self.run_cb)
        return False

    def rewind(self, widget):
        if self.pixbuf is not None:
            try:
                if self.running:
                    self.pause()
                self.interpreter.rewind()
                self.update_labels()
                self.da.queue_draw()
            except:
                show_exception()
                self.close(None)
        return False

    def scroll_tv(self):
        vs = self.sw_out.get_vscrollbar()
        if vs is not None:
            vs.set_value(self.sw_out.get_vadjustment().get_upper())

    def get_char(self):
        if len(self.input_buf) == 0:
            raise InputError()
        return self.input_buf.popleft()

    def put_char(self, c):
        if self.running:
            gtk.threads_enter()
        tb = self.tv_out.get_buffer()
        tb.insert(tb.get_end_iter(), c)
        self.scroll_tv()
        if self.running:
            gtk.threads_leave()

    def get_int(self):
        c = None
        while len(self.input_buf) > 0:
            c = self.input_buf.popleft()
            if c.isdigit():
                break
        if c is None or not c.isdigit():
            raise InputError()
        i = int(c)
        while len(self.input_buf) > 0:
            c = self.input_buf.popleft()
            if not c.isdigit():
                self.input_buf.appendleft(c)
                break
            else:
                i = i * 10 + int(c)
        return i

    def put_int(self, i):
        if self.running:
            gtk.threads_enter()
        tb = self.tv_out.get_buffer()
        tb.insert(tb.get_end_iter(), str(i))
        self.scroll_tv()
        if self.running:
            gtk.threads_leave()

    def input(self, widget, event):
        if ord(event.string[0]) == 13 or ord(event.string[0]) == 10:
            for c in widget.get_text():
                self.input_buf.append(c)
            self.input_buf.append('\n')
            tb = self.tv_out.get_buffer()
            tb.insert(tb.get_end_iter(), widget.get_text())
            tb.insert(tb.get_end_iter(), '\n')
            self.scroll()
            widget.set_text('')

    def configure(self, widget):
        dialog = config_dialog(self.cfg)
        dialog.show_all()
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            self.cfg = dialog.cfg
            self.npiet_path = self.cfg.get('config', 'path')
            self.interpreter.npiet = self.npiet_path
            self.grid_color = gtk.gdk.color_parse(self.cfg.get('config', 'grid_color'))
            self.breakpoint_color = gtk.gdk.color_parse(self.cfg.get('config', 'breakpoint_color'))
            self.breakpoint_bg_color = gtk.gdk.color_parse(self.cfg.get('config', 'breakpoint_bg_color'))
            self.selection_color = gtk.gdk.color_parse(self.cfg.get('config', 'selection_color'))
            self.selection_bg_color = gtk.gdk.color_parse(self.cfg.get('config', 'selection_bg_color'))
            self.da.queue_draw()

        dialog.destroy()

    def cfg_get(self, section, option, value):
        try:
            return self.cfg.get(section, option)
        except NoOptionError:
            ex_type, ex_value, ex_traceback = exc_info()
            print(''.join(format_exception(ex_type, ex_value, ex_traceback)))
            self.cfg.set(section, option, value)
            return value

    def __init__(self, cfgpath = None):
        if cfgpath is None:
            self.cfg_path = os.path.expanduser('~/.pietdbg')
        else:
            self.cfg_path = cfgpath
        self.cfg = SafeConfigParser()
        try:
            fp = open(self.cfg_path)
            self.cfg.readfp(fp)
            fp.close()
        except:
            ex_type, ex_value, ex_traceback = exc_info()
            print(''.join(format_exception(ex_type, ex_value, ex_traceback)))

        self.black = gtk.gdk.Color(0, 0, 0)
        self.white = gtk.gdk.Color(65535, 65535, 65535)

        section = True
        try:
            self.npiet_path = self.cfg.get('config', 'path')
        except NoSectionError:
            ex_type, ex_value, ex_traceback = exc_info()
            print(''.join(format_exception(ex_type, ex_value, ex_traceback)))

            self.cfg.add_section('config')
            self.cfg.set('config', 'path', './npiet')
            self.cfg.set('config', 'grid_color', '#000000')
            self.cfg.set('config', 'breakpoint_color', '#C08080')
            self.cfg.set('config', 'breakpoint_bg_color', '#408080')
            self.cfg.set('config', 'selection_color', '#80C0C0')
            self.cfg.set('config', 'selection_bg_color', '#804040')

            self.grid_color = gtk.gdk.Color(0, 0, 0)
            self.breakpoint_color = gtk.gdk.Color(49151, 32767, 32767)
            self.breakpoint_bg_color = gtk.gdk.Color(16383, 32767, 32767)
            self.selection_color = gtk.gdk.Color(32767, 49151, 49151)
            self.selection_bg_color = gtk.gdk.Color(32767, 16383, 16383)
            self.npiet_path = './npiet'

            section = False
        except NoOptionError:
            ex_type, ex_value, ex_traceback = exc_info()
            print(''.join(format_exception(ex_type, ex_value, ex_traceback)))

            self.npiet_path = './npiet'
            self.cfg.set('config', 'path', './npiet')

        if section:
            self.grid_color = gtk.gdk.color_parse(self.cfg_get('config', 'grid_color', '#000000'))
            self.breakpoint_color = gtk.gdk.color_parse(self.cfg_get('config', 'breakpoint_color', '#C08080'))
            self.breakpoint_bg_color = gtk.gdk.color_parse(self.cfg_get('config', 'breakpoint_bg_color', '#408080'))
            self.selection_color = gtk.gdk.color_parse(self.cfg_get('config', 'selection_color', '#80C0C0'))
            self.selection_bg_color = gtk.gdk.color_parse(self.cfg_get('config', 'selection_bg_color', '#804040'))

        self.interpreter = npiet.interpreter(self.npiet_path,
                                             self.get_char, self.put_char,
                                             self.get_int, self.put_int)
        self.thread = interpreter_thread(self.interpreter, self.run_cb)
        self.image = None
        self.pixbuf = self.image
        self.pixbuf_rect = None
        self.scale = 1.0
        self.pixel_size = 1
        self.input_buf = deque()
        self.stack_size = 0

        self.running = False

        self.prev_x = 0
        self.prev_y = 0

        self.codel = None
        self.codel_1 = None

        t = gtk.Tooltips()

        self.btn_open = gtk.ToolButton(gtk.STOCK_OPEN)
        self.btn_open.set_tooltip(t, 'Open')
        self.btn_open.connect('clicked', self.open)

        self.btn_close = gtk.ToolButton(gtk.STOCK_CLOSE)
        self.btn_close.set_tooltip(t, 'Close')
        self.btn_close.connect('clicked', self.close)
        self.btn_close.set_sensitive(False)

        self.btn_exit = gtk.ToolButton(gtk.STOCK_QUIT)
        self.btn_exit.set_tooltip(t, 'Quit')
        self.btn_exit.connect('clicked', self.destroy)

        self.btn_cfg = gtk.ToolButton(gtk.STOCK_PREFERENCES)
        self.btn_cfg.set_tooltip(t, 'Preferences')
        self.btn_cfg.connect('clicked', self.configure)

        self.btn_reset = gtk.ToolButton(gtk.STOCK_MEDIA_REWIND)
        self.btn_reset.set_tooltip(t, 'Restart')
        self.btn_reset.connect('clicked', self.rewind)
        self.btn_reset.set_sensitive(False)

        self.btn_stop = gtk.ToolButton(gtk.STOCK_MEDIA_PAUSE)
        self.btn_stop.set_tooltip(t, 'Pause')
        self.btn_stop.connect('clicked', self.pause)
        self.btn_stop.set_sensitive(False)

        self.btn_step = gtk.ToolButton(gtk.STOCK_MEDIA_PLAY)
        self.btn_step.set_tooltip(t, 'Step')
        self.btn_step.connect('clicked', self.step)
        self.btn_step.set_sensitive(False)

        self.btn_run = gtk.ToolButton(gtk.STOCK_MEDIA_FORWARD)
        self.btn_run.set_tooltip(t, 'Run')
        self.btn_run.connect('clicked', self.run)
        self.btn_run.set_sensitive(False)

        self.btn_clear = gtk.ToolButton(gtk.STOCK_CLEAR)
        self.btn_clear.set_tooltip(t, 'Delete all breakpoints')
        self.btn_clear.connect('clicked', self.clear_breakpoints)
        self.btn_clear.set_sensitive(False)

        self.btn_zoom_in = gtk.ToolButton(gtk.STOCK_ZOOM_IN)
        self.btn_zoom_in.set_tooltip(t, 'Zoom in')
        self.btn_zoom_in.connect('clicked', self.zoom_in)
        self.btn_zoom_in.set_sensitive(False)

        self.btn_zoom_out = gtk.ToolButton(gtk.STOCK_ZOOM_OUT)
        self.btn_zoom_out.set_tooltip(t, 'Zoom out')
        self.btn_zoom_out.connect('clicked', self.zoom_out)
        self.btn_zoom_out.set_sensitive(False)

        self.btn_zoom_100 = gtk.ToolButton(gtk.STOCK_ZOOM_100)
        self.btn_zoom_100.set_tooltip(t, 'Normal size')
        self.btn_zoom_100.connect('clicked', self.zoom_100)
        self.btn_zoom_100.set_sensitive(False)

        self.toolbar = gtk.Toolbar()
        self.toolbar.insert(self.btn_open, -1)
        self.toolbar.insert(self.btn_close, -1)
        self.toolbar.insert(self.btn_exit, -1)
        self.toolbar.insert(gtk.SeparatorToolItem(), -1)
        self.toolbar.insert(self.btn_cfg, -1)
        self.toolbar.insert(gtk.SeparatorToolItem(), -1)
        self.toolbar.insert(self.btn_reset, -1)
        self.toolbar.insert(self.btn_stop, -1)
        self.toolbar.insert(self.btn_step, -1)
        self.toolbar.insert(self.btn_run, -1)
        self.toolbar.insert(gtk.SeparatorToolItem(), -1)
        self.toolbar.insert(self.btn_clear, -1)
        self.toolbar.insert(gtk.SeparatorToolItem(), -1)
        self.toolbar.insert(self.btn_zoom_in, -1)
        self.toolbar.insert(self.btn_zoom_out, -1)
        self.toolbar.insert(self.btn_zoom_100, -1)

        self.da = gtk.DrawingArea()
        self.da.set_events(gtk.gdk.POINTER_MOTION_MASK |
                           gtk.gdk.POINTER_MOTION_HINT_MASK |
                           gtk.gdk.LEAVE_NOTIFY_MASK |
                           gtk.gdk.BUTTON_PRESS_MASK |
                           gtk.gdk.BUTTON_MOTION_MASK)
        self.da.set_flags(gtk.CAN_FOCUS)
        self.da.connect('size_allocate', self.size_allocate)
        self.da.connect('motion_notify_event', self.motion_notify)
        self.da.connect('leave_notify_event', self.leave_notify)
        self.da.connect('button_press_event', self.button_press)
        self.da.connect('scroll_event', self.scroll_event)
        self.da.connect('expose_event', self.expose)

        self.sw_img = gtk.ScrolledWindow()
        self.sw_img.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.sw_img.add_with_viewport(self.da)

        self.t_img = gtk.Table(2, 2)

        self.t_img.attach(self.sw_img, 1, 2, 1, 2, gtk.EXPAND | gtk.FILL, gtk.EXPAND | gtk.FILL)

        self.tv_out = gtk.TextView()
        self.tv_out.set_wrap_mode(gtk.WRAP_CHAR)
        self.tv_out.set_editable(False)

        self.sw_out = gtk.ScrolledWindow()
        self.sw_out.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.sw_out.add_with_viewport(self.tv_out)
        self.sw_out.set_sensitive(False)

        self.entry = gtk.Entry(max=0)
        self.entry.set_events(gtk.gdk.KEY_RELEASE_MASK)
        self.entry.connect('key_release_event', self.input)
        self.entry.set_sensitive(False)

        self.hbox_i = gtk.HBox(False, 5)
        self.hbox_i.pack_start(gtk.Label('Input:'), expand=False)
        self.hbox_i.pack_start(self.entry)

        self.vbox_io = gtk.VBox(False, 5)
        self.vbox_io.pack_start(self.sw_out)
        self.vbox_io.pack_start(self.hbox_i, expand=False)

        self.f_io = gtk.Frame()
        self.f_io.set_label_align(-1.0, 0.0)
        self.f_io.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self.f_io.set_label('Output')
        self.f_io.add(self.vbox_io)

        self.vpaned = gtk.VPaned()
        self.vpaned.pack1(self.t_img, True, False)
        self.vpaned.pack2(self.f_io, False, True)

        self.l_cs = gtk.Label('N/A')
        self.l_uc = gtk.Label('N/A')
        self.l_state = gtk.Label('N/A')
        self.l_dp = gtk.Label('N/A')
        self.l_cc = gtk.Label('N/A')
        self.l_co = gtk.Label('N/A')
        self.l_cl = gtk.Label('N/A')
        self.l_prev_dp = gtk.Label('N/A')
        self.l_prev_cc = gtk.Label('N/A')
        self.l_prev_co = gtk.Label('N/A')
        self.l_prev_cl = gtk.Label('N/A')
        self.l_hdiff = gtk.Label('N/A')
        self.l_ldiff = gtk.Label('N/A')
        self.l_op = gtk.Label('N/A')
        self.l_arg = gtk.Label('N/A')

        labels = (
            ('Codel size', self.l_cs),
            ('Unknown colors', self.l_uc),
            ('Interpreter state', self.l_state),
            ('DP', self.l_dp),
            ('CC', self.l_cc),
            ('Codel', self.l_co),
            ('Color', self.l_cl),
            ('Previous DP', self.l_prev_dp),
            ('Previous CC', self.l_prev_cc),
            ('Previous codel', self.l_prev_co),
            ('Previous color', self.l_prev_cl),
            ('Light change', self.l_ldiff),
            ('Hue change', self.l_hdiff),
            ('Command', self.l_op),
            ('Command argument', self.l_arg)
        )

        self.table = gtk.Table(len(labels), 2, True)
        self.table.set_row_spacings(5)
        self.table.set_col_spacings(10)
        y = 0
        for l in labels:
            lb = gtk.Label(l[0])
            #lb.set_alignment(0, 0)
            self.table.attach(lb, 0, 1, y, y + 1)
            l[1].set_alignment(0, 0)
            self.table.attach(l[1], 1, 2, y, y + 1)
            y += 1

        self.ls_stack = gtk.ListStore(int)

        self.cr_stack = gtk.CellRendererText()

        self.tvc_stack = gtk.TreeViewColumn('Stack')
        self.tvc_stack.pack_start(self.cr_stack, False)
        self.tvc_stack.add_attribute(self.cr_stack, "text", 0)

        self.tv_stack = gtk.TreeView(self.ls_stack)
        self.tv_stack.append_column(self.tvc_stack)

        self.sw_stack = gtk.ScrolledWindow()
        self.sw_stack.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.sw_stack.add_with_viewport(self.tv_stack)

        self.vbox_is = gtk.VBox(False, 5)
        self.vbox_is.pack_start(self.table, expand=False)
        self.vbox_is.pack_start(gtk.HSeparator(), expand=False)
        self.vbox_is.pack_start(self.sw_stack)

        self.hbox = gtk.HBox()
        self.hbox.pack_start(self.vpaned)
        self.hbox.pack_start(self.vbox_is, expand=False)

        self.statusbar = gtk.Statusbar()
        self.context = self.statusbar.get_context_id('test')

        self.vbox = gtk.VBox(False, 5)
        self.vbox.pack_start(self.toolbar, expand=False)
        self.vbox.pack_start(self.hbox)
        self.vbox.pack_start(self.statusbar, expand=False)

        self.wnd = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.wnd.set_default_size(600, 400)
        self.wnd.set_title('Piet debugger')
        self.wnd.connect('key_press_event', self.key_press)
        self.wnd.connect('key_release_event', self.key_release)
        self.wnd.connect('destroy', self.destroy)
        self.wnd.add(self.vbox)
        self.wnd.show_all()

    def main(self):
        gtk.threads_init()
        gtk.main()

