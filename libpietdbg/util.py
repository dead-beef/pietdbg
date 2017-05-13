import pygtk
pygtk.require('2.0')
import gtk

from threading import Thread, Event
from copy import copy
from sys import exc_info
from traceback import format_exception

from base import unknown_black, unknown_white, unknown_error

def fxrange(start, stop, step):
    while start < stop:
        yield int(start)
        start += step

def show_exception():
    ex_type, ex_value, ex_traceback = exc_info()
    d = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                          gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                          ''.join(format_exception(ex_type, ex_value, ex_traceback)))
    d.run()
    d.destroy()

class in_area(object):
    def __init__(self, area, scale):
        self.area = (
            (area.y / scale - 1, (area.y + area.height) / scale + 1),
            (area.x / scale - 1, (area.x + area.width) / scale + 1)
        )
    def __call__(self, bp):
        return (bp[0] >= self.area[0][0] and bp[0] <= self.area[0][1] and
                bp[1] >= self.area[1][0] and bp[1] <= self.area[1][1])

class InputError(Exception):
    def __init__(self):
        Exception.__init__(self, 'input buffer is empty')

class open_dialog(gtk.Dialog):
    def set_cs(self, widget):
        self.codel_size = widget.get_value()
        return False

    def set_guess_cs(self, widget):
        if widget.get_active():
            self.spinbutton.set_sensitive(False)
            self.codel_size = None
        else:
            self.spinbutton.set_sensitive(True)
            self.codel_size = self.spinbutton.get_value()
        return False

    uc_funcs = (unknown_white, unknown_black, unknown_error)

    def set_uc(self, widget):
        self.unknown_colors = self.uc_funcs[widget.get_active()]
        return False

    def set_file(self, widget):
        self.fname = widget.get_filename()
        return False

    def __init__(self):
        gtk.Dialog.__init__(self, 'Open Image', None, gtk.DIALOG_MODAL,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                             gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.set_default_size(0, 0)

        file_chooser = gtk.FileChooserButton('Select A File')
        file_chooser.connect('file_set', self.set_file)

        adjustment = gtk.Adjustment(1, 1, 100, 1, 10, 0)
        self.spinbutton = gtk.SpinButton(adjustment)
        self.spinbutton.connect('value_changed', self.set_cs)

        check_guess_cs = gtk.CheckButton('Guess codel size')
        check_guess_cs.connect('toggled', self.set_guess_cs)

        liststore = gtk.ListStore(str)
        liststore.append(['white'])
        liststore.append(['black'])
        liststore.append(['error'])

        cell = gtk.CellRendererText()

        combobox = gtk.ComboBox(liststore)
        combobox.pack_start(cell, True)
        combobox.add_attribute(cell, 'text', 0)
        combobox.set_active(0)
        combobox.connect('changed', self.set_uc)

        table = gtk.Table(3, 3)

        l = gtk.Label('File')
        l.set_alignment(0, 0)
        table.attach(l, 0, 1, 0, 1, gtk.EXPAND | gtk.FILL, 0, 2, 2)
        table.attach(file_chooser, 1, 3, 0, 1, gtk.EXPAND | gtk.FILL, 0, 0, 2)
        l = gtk.Label('Codel size')
        l.set_alignment(0, 0)
        table.attach(l, 0, 1, 1, 2, gtk.EXPAND | gtk.FILL, 0, 2, 2)
        table.attach(self.spinbutton, 1, 2, 1, 2, gtk.EXPAND | gtk.FILL, 0, 2, 2)
        table.attach(check_guess_cs, 2, 3, 1, 2, 0, 0, 2, 2)
        l = gtk.Label('Unknown colors are')
        l.set_alignment(0, 0)
        table.attach(l, 0, 1, 2, 3, gtk.EXPAND | gtk.FILL, 0, 2, 2)
        table.attach(combobox, 1, 3, 2, 3, gtk.EXPAND | gtk.FILL, 0, 2, 2)

        self.get_content_area().pack_start(table, expand=False, fill=False)

        self.fname = None
        self.codel_size = 1
        self.unknown_colors = unknown_white

class config_dialog(gtk.Dialog):
    colors = (
        ('grid_color', 'Grid color'),
        ('breakpoint_color', 'Breakpoint color'),
        ('breakpoint_bg_color', 'Breakpoint background color'),
        ('selection_color', 'Selection/DP/CC color'),
        ('selection_bg_color', 'Selection/DP/CC background color')
    )

    def set_color(self, widget, var):
        self.cfg.set('config', var, str(widget.get_color()))
        return False

    def set_file(self, widget):
        self.cfg.set('config', 'path', widget.get_filename())
        return False

    def __init__(self, cfg):
        gtk.Dialog.__init__(self, 'Preferences', None, gtk.DIALOG_MODAL,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                             gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.set_default_size(0, 0)

        self.cfg = copy(cfg)

        file_chooser = gtk.FileChooserButton('Select interpreter path')
        file_chooser.connect('file_set', self.set_file)

        table = gtk.Table(6, 2)

        l = gtk.Label('Interpreter path')
        l.set_alignment(0, 0)
        table.attach(l, 0, 1, 0, 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)
        table.attach(file_chooser, 1, 2, 0, 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)

        row = 1
        for cl in self.colors:
            l = gtk.Label(cl[1])
            l.set_alignment(0, 0)
            table.attach(l, 0, 1, row, row + 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)

            l = gtk.ColorButton(gtk.gdk.color_parse(self.cfg.get('config', cl[0])))
            l.connect('color-set', self.set_color, cl[0])
            table.attach(l, 1, 2, row, row + 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)

            row += 1

        self.get_content_area().pack_start(table, expand=False, fill=False)

class interpreter_thread(object):
    def __init__(self, interpreter, cb):
        self.interpreter = interpreter
        self.callback = cb
        self.error = 0
        self._stop = Event()
        self._stop.set()
        self._thread = None

    def _run(self):
        try:
            self.interpreter.run_start()
            while self.interpreter.state != self.interpreter.ST_END and\
                  self.interpreter.cur not in self.interpreter.codel_breakpoints and\
                  not self._stop.is_set():
                self.interpreter.step()
        except InputError:
            self.error = 1
        except:
            self.error = 2
            gtk.threads_enter()
            show_exception()
            gtk.threads_leave()
        finally:
            self.interpreter.run_stop()
            gtk.threads_enter()
            self.callback()
            gtk.threads_leave()

    def start(self):
        self.error = 0
        self._stop.clear()
        self._thread = Thread(target=self._run)
        self._thread.start()

    def stop(self):
        self._stop.set()
        gtk.threads_leave()
        self._thread.join()
        gtk.threads_enter()
