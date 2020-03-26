# -*- coding: utf-8 -*-
import sqlite3

import gi

import logconfig

gi.require_version('IBus', '1.0')
from gi.repository import IBus
from gi.repository import GLib
from gi.repository import GObject

import os
import sys
import getopt
import locale

logger = logconfig.get_logger()

__base_dir__ = os.path.dirname(__file__)

# gee thank you IBus :-)
num_keys = []
for n in range(1, 10):
    num_keys.append(getattr(IBus, str(n)))
num_keys.append(getattr(IBus, '0'))
del n

numpad_keys = []
for n in range(1, 10):
    numpad_keys.append(getattr(IBus, 'KP_' + str(n)))
numpad_keys.append(getattr(IBus, 'KP_0'))
del n

# sqlite3
conn = None
c = None


def gen_punctuation_map():
    # import string
    # punctuation_en = string.punctuation
    punctuation_en = '''!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~'''
    punctuation_cn = ['！', '“', '＃', '￥', '％', '＆', '‘', '（', '）', '＊', '＋', '，', '－', '。', '／', '：', '；', '《', '＝',
                      '》', '？', '＠', '「', '、', '」', '……', '——', '｀', '『', '｜', '』', '～']
    return dict(zip(punctuation_en, punctuation_cn))


punctuation_map = gen_punctuation_map()


class KeyEvent:
    '''Key event class used to make the checking of details of the key
    event easy
    '''

    def __init__(self, keyval, keycode, state):
        self.val = keyval
        self.code = keycode
        self.state = state
        self.name = IBus.keyval_name(self.val)
        self.unicode = IBus.keyval_to_unicode(self.val)
        self.shift = self.state & IBus.ModifierType.SHIFT_MASK != 0
        self.lock = self.state & IBus.ModifierType.LOCK_MASK != 0
        self.control = self.state & IBus.ModifierType.CONTROL_MASK != 0
        self.mod1 = self.state & IBus.ModifierType.MOD1_MASK != 0
        self.mod2 = self.state & IBus.ModifierType.MOD2_MASK != 0
        self.mod3 = self.state & IBus.ModifierType.MOD3_MASK != 0
        self.mod4 = self.state & IBus.ModifierType.MOD4_MASK != 0
        self.mod5 = self.state & IBus.ModifierType.MOD5_MASK != 0
        self.button1 = self.state & IBus.ModifierType.BUTTON1_MASK != 0
        self.button2 = self.state & IBus.ModifierType.BUTTON2_MASK != 0
        self.button3 = self.state & IBus.ModifierType.BUTTON3_MASK != 0
        self.button4 = self.state & IBus.ModifierType.BUTTON4_MASK != 0
        self.button5 = self.state & IBus.ModifierType.BUTTON5_MASK != 0
        self.super = self.state & IBus.ModifierType.SUPER_MASK != 0
        self.hyper = self.state & IBus.ModifierType.HYPER_MASK != 0
        self.meta = self.state & IBus.ModifierType.META_MASK != 0
        self.release = self.state & IBus.ModifierType.RELEASE_MASK != 0
        # MODIFIER_MASK: Modifier mask for the all the masks above
        self.modifier = self.state & IBus.ModifierType.MODIFIER_MASK != 0

    def __str__(self):
        return (
                "val=%s code=%s state=0x%08x name='%s' unicode='%s' "
                % (self.val,
                   self.code,
                   self.state,
                   self.name,
                   self.unicode)
                + "shift=%s control=%s mod1=%s mod5=%s release=%s"
                % (self.shift,
                   self.control,
                   self.mod1,
                   self.mod5,
                   self.release))


# the engine
class IWubi(object):
    def find_characters(self, preedit_string):
        logger.debug('preedit_string {}'.format(preedit_string))
        # return [[preedit_string, '五笔']]
        output = []
        # CREATE TABLE pinyin
        #             (pinyin TEXT, zi TEXT, freq INTEGER);
        # CREATE TABLE phrases
        # CREATE TABLE phrases
        #         (id INTEGER PRIMARY KEY, tabkeys TEXT, phrase TEXT,
        #         freq INTEGER, user_freq INTEGER);

        # freq==0 is large Chinese Table
        # query Wubi
        table_size = 5
        query = "SELECT tabkeys, phrase, user_freq FROM phrases " \
                "WHERE tabkeys LIKE '{}%' AND freq>0 LIMIT {}".format(preedit_string, table_size)
        wubi_list = list(c.execute(query))
        for row in wubi_list:
            output.append([row[1], row[1] + row[0][len(preedit_string):]])
        len_wubi_list = len(wubi_list)

        # query pinyin
        pinyin_size = table_size - len_wubi_list
        if pinyin_size > 0:
            query = "SELECT phrase FROM pinyins " \
                    "WHERE pinyin LIKE '{}%' AND freq>0 ORDER BY freq DESC LIMIT {}".format(preedit_string, pinyin_size)
            pinyin_list = list(c.execute(query))
            for phrase in pinyin_list:
                phrase = phrase[0]
                # Add Wubi tabkeys if exists
                query = "SELECT tabkeys FROM phrases " \
                        "WHERE phrase = '{}'".format(phrase)
                c.execute(query)
                tabkeys = c.fetchone()
                if tabkeys:
                    phrase_display = phrase + tabkeys[0]
                else:
                    phrase_display = phrase
                output.append([phrase, phrase_display])

        logger.debug('output {}'.format(output))
        return output, len_wubi_list


class IbusWubiEngine(IBus.Engine):
    __gtype_name__ = 'IbusWubiEngine'

    def __init__(self):
        super(IbusWubiEngine, self).__init__()
        self.candidates = []
        self.iwubi = IWubi()
        self.is_invalidate = False
        self.preedit_string = ''
        # new(page_size:int, cursor_pos:int, cursor_visible:bool, round:bool)
        self.lookup_table = IBus.LookupTable.new(5, 0, True, True)
        self.prop_list = IBus.PropList()
        self._input_mode = 0  # 0: Use direct input. 1: Use the WuBi table.
        self._prev_key = None
        self._last_wubi_list_len = 0
        logger.info("Create iwubi engine OK")

    def set_lookup_table_cursor_pos_in_current_page(self, index):
        '''Sets the cursor in the lookup table to index in the current page

        Returns True if successful, False if not.
        '''
        page_size = self.lookup_table.get_page_size()
        if index > page_size:
            return False
        page, pos_in_page = divmod(self.lookup_table.get_cursor_pos(),
                                   page_size)
        new_pos = page * page_size + index
        if new_pos > self.lookup_table.get_number_of_candidates():
            return False
        self.lookup_table.set_cursor_pos(new_pos)
        return True

    def do_candidate_clicked(self, index, dummy_button, dummy_state):
        if self.set_lookup_table_cursor_pos_in_current_page(index):
            self.commit_candidate()

    def set_input_mode(self, mode=1):
        """
        :param mode: Whether to use WuBi mode.
                     0: Use direct input.
                     1: Use the WuBi table.
        :return:
        """
        self._input_mode = mode
        logger.debug('input_mode {}'.format(mode))

    def _is_shift_hotkey(self, key):
        '''Check whether “key” matches the Shift hotkey.
        Returns True if there is a match, False if not.
        :param key: The key typed
        :type key: KeyEvent object
        :rtype: Boolean
        '''
        # Match only when keys are released
        if key.val == IBus.KEY_Shift_L and key.release:
            # If it is a key release event, the previous key
            # must have been the same key pressed down.
            if self._prev_key and key.val == self._prev_key.val:
                return True

        return False

    def _process_key_event(self, key):
        # Match mode switch hotkey
        # if self._match_hotkey(
        #         key, IBus.KEY_Shift_L,
        #         IBus.ModifierType.SHIFT_MASK):

        # Temp Fix Chrome Shift hotkey bug.
        if self._is_shift_hotkey(key):
            self.set_input_mode(int(not self._input_mode))
            if self.preedit_string:
                self.commit_string(self.preedit_string)
            return True

        keyval, keycode, state = key.val, key.code, key.state

        # ignore key release events
        is_press = ((state & IBus.ModifierType.RELEASE_MASK) == 0)
        if not is_press:
            return False

        if self.preedit_string:
            if keyval == IBus.space:
                if self.lookup_table.get_number_of_candidates() > 0:
                    self.commit_candidate()
                else:
                    self.commit_string(self.preedit_string)
                return True
            if keyval == IBus.Return:
                self.commit_string(self.preedit_string)
                return True
            elif keyval == IBus.Escape:
                self.preedit_string = ''
                self.update_candidates()
                return True
            elif keyval == IBus.BackSpace:
                self.preedit_string = self.preedit_string[:-1]
                self.invalidate()
                return True
            elif keyval in num_keys:
                index = num_keys.index(keyval)
                if self.set_lookup_table_cursor_pos_in_current_page(index):
                    self.commit_candidate()
                    return True
                return False
            elif keyval in numpad_keys:
                index = numpad_keys.index(keyval)
                if self.set_lookup_table_cursor_pos_in_current_page(index):
                    self.commit_candidate()
                    return True
                return False
            elif keyval in (IBus.Page_Up, IBus.KP_Page_Up, IBus.Left, IBus.KP_Left):
                self.page_up()
                return True
            elif keyval in (IBus.Page_Down, IBus.KP_Page_Down, IBus.Right, IBus.KP_Right):
                self.page_down()
                return True
            elif keyval in (IBus.Up, IBus.KP_Up):
                self.cursor_up()
                return True
            elif keyval in (IBus.Down, IBus.KP_Down):
                self.cursor_down()
                return True

        # ASCII letter
        if IBus.a <= keyval <= IBus.z or \
                IBus.A <= keyval <= IBus.Z:
            if state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK) == 0:
                if self._input_mode == 0:
                    # Do not use `commit_string(keyval)` to commit ASCII letter, `commit_string` may run too long time.
                    # This can lead to hotkey mistake detection error.
                    # Instead, return False, to IBus/System input the letter to App directly.
                    return False
                else:
                    # Auto commit the first Wubi
                    if len(self.preedit_string) == 4 and self._last_wubi_list_len > 0:
                        self.commit_candidate()
                        self.preedit_string = chr(keyval)
                    else:
                        self.preedit_string += chr(keyval)
                    # self.invalidate really mean?
                    self.invalidate()
                    return True
        # ASCII except letter
        else:
            if keyval < 128:
                # If is Chinse Wubi mode and keyval is punctuation, translate punctuation to Chinese punctuation
                if self._input_mode == 1:
                    if self.lookup_table.get_number_of_candidates() > 0:
                        self.commit_candidate()
                    keyval_chr = chr(keyval)
                    if chr(keyval) in punctuation_map:
                        self.commit_string(punctuation_map[keyval_chr])
                        return True
                else:
                    if self.preedit_string:
                        self.commit_string(self.preedit_string)

        # return False means IBus iWubi will not deal this key,
        # so System/IBus will input the letter or other special char/keyal (e.g. Shift, Ctrl) to App.
        return False

    def do_process_key_event(self, keyval, keycode, state):
        """ do_process_key_event = gi.VFuncInfo(process_key_event)
        :param keyval:
        :param keycode:
        :param state: Key modifier flags.
        :return:
        """
        key = KeyEvent(keyval, keycode, state)
        logger.debug('{}'.format(key))
        result = self._process_key_event(key)
        # Fix me. If the last `self._process_key_event` take too long time.
        # Maybe the new `do_process_key_event` will called before last `self._prev_key = key` is done.
        # So `self._prev_key` could be the previous previous key, lead to hotkey mistake detection error.
        # e.g.
        # 1. Shift_L press.
        # 2. u press. So input is U.
        # 3. Shift_L release. -> Lead to mistake Shift_L hotkey detection.
        # 4. u release.
        self._prev_key = key
        return result

    def _match_hotkey(self, key, keyval, state):
        '''Check whether “key” matches a “hotkey” specified by “keyval” and
        “state”.

        Returns True if there is a match, False if not.

        :param key: The key typed
        :type key: KeyEvent object
        :param keyval: The key value to match against
        :type keyval: Integer
        :param state: The state of the modifier keys to match against.
        :type state: Integer
        :rtype: Boolean
        '''
        # Match only when keys are released
        # IBus.ModifierType.RELEASE_MASK = 1073741824 (hex: 0x40000000)
        state = state | IBus.ModifierType.RELEASE_MASK  # state is Shift+Release
        if key.val == keyval and (key.state & state) == state:
            # If it is a key release event, the previous key
            # must have been the same key pressed down.
            if (self._prev_key
                    and key.val == self._prev_key.val):
                return True

        return False

    def invalidate(self):
        if self.is_invalidate:
            return
        self.is_invalidate = True
        # The glib.idle_add() function adds a function (specified by callback) to be called
        # whenever there are no higher priority events pending to the default main loop.
        GLib.idle_add(self.update_candidates)

    def page_up(self):
        # Go to previous page of an IBusLookupTable.
        # It returns FALSE if it is already at the first page, unless table>-round==TRUE, where it will go to the last page.
        if self.lookup_table.page_up():
            self._update_lookup_table()
            return True
        return False

    def page_down(self):
        if self.lookup_table.page_down():
            self._update_lookup_table()
            return True
        return False

    def cursor_up(self):
        if self.lookup_table.cursor_up():
            self._update_lookup_table()
            return True
        return False

    def cursor_down(self):
        if self.lookup_table.cursor_down():
            self._update_lookup_table()
            return True
        return False

    def commit_string(self, text):
        self.commit_text(IBus.Text.new_from_string(text))
        self.preedit_string = ''
        self.update_candidates()

    def commit_candidate(self):
        self.commit_string(self.candidates[self.lookup_table.get_cursor_pos()])

    def update_candidates(self):
        preedit_len = len(self.preedit_string)
        # IBusAttrList — AttrList of IBusText.
        # An IBusText is the main text object in IBus.
        # The text is decorated according to associated IBusAttribute,
        # e.g. the foreground/background color, underline, and applied scope.
        attrs = IBus.AttrList()
        self.lookup_table.clear()
        # reset candidate
        self.candidates = []

        if preedit_len > 0:
            iwubi_results, len_wubi_list = self.iwubi.find_characters(self.preedit_string)
            self._last_wubi_list_len = len_wubi_list
            for char_sequence, display_str in iwubi_results:
                candidate = IBus.Text.new_from_string(display_str)
                self.candidates.append(char_sequence)
                self.lookup_table.append_candidate(candidate)

        # Do not show auxiliary bar. Keep UI clean.

        attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE,
                                        IBus.AttrUnderline.SINGLE, 0, preedit_len))
        text = IBus.Text.new_from_string(self.preedit_string)
        text.set_attributes(attrs)
        # update_preedit_text: Update the pre-edit buffer.
        # text : Update content.
        # cursor_pos : Current position of cursor
        # visible : Whether the pre-edit buffer is visible.
        self.update_preedit_text(text, preedit_len, preedit_len > 0)
        self._update_lookup_table()
        self.is_invalidate = False

    def _update_lookup_table(self):
        # get_number_of_candidates: Return the number of candidate in the table.
        visible = self.lookup_table.get_number_of_candidates() > 0
        # visible: Whether the lookup_table is visible.?
        self.update_lookup_table(self.lookup_table, visible)

    def do_focus_in(self):
        logger.debug("focus_in")
        self.register_properties(self.prop_list)

    def do_focus_out(self):
        logger.debug("focus_out")
        self.do_reset()

    def do_reset(self):
        # When focus change(e.g. App/Window changes), calling order:
        # 1. do_focus_out
        # 2. do_reset
        # 3. do_focus_in
        logger.debug("reset")
        self.preedit_string = ''

    def do_property_activate(self, prop_name):
        logger.info("PropertyActivate(%s)" % prop_name)

    def do_page_up(self):
        return self.page_up()

    def do_page_down(self):
        return self.page_down()

    def do_cursor_up(self):
        return self.cursor_up()

    def do_cursor_down(self):
        return self.cursor_down()


# the app (main interface to IBus)
class IMApp:
    def __init__(self, exec_by_ibus):
        if not exec_by_ibus:
            global debug_on
            debug_on = True
        self.mainloop = GLib.MainLoop()
        self.bus = IBus.Bus()
        self.bus.connect("disconnected", self.bus_disconnected_cb)
        self.factory = IBus.Factory.new(self.bus.get_connection())
        self.factory.add_engine("iwubi", GObject.type_from_name("IbusWubiEngine"))
        if exec_by_ibus:
            self.bus.request_name("com.github.honghe.iwubi", 0)
        else:
            xml_path = os.path.join(__base_dir__, 'iwubi.xml')
            if os.path.exists(xml_path):
                component = IBus.Component.new_from_file(xml_path)
            else:
                xml_path = os.path.join(os.path.dirname(__base_dir__),
                                        'ibus', 'component', 'iwubi.xml')
                component = IBus.Component.new_from_file(xml_path)
            self.bus.register_component(component)

    def run(self):
        # open sqlite3
        db_file = os.path.join(__base_dir__, 'wubi-jidian86.db')
        global conn
        conn = sqlite3.connect(db_file)
        global c
        c = conn.cursor()
        self.mainloop.run()

    def bus_disconnected_cb(self, bus):
        logger.debug('bus {}'.format(bus))
        self.mainloop.quit()
        # close sqlite3
        if conn:
            conn.close()


def launch_engine(exec_by_ibus):
    IBus.init()
    IMApp(exec_by_ibus).run()


def print_help(out, v=0):
    print("-i, --ibus             executed by IBus.", file=out)
    print("-h, --help             show this message.", file=out)
    print("-d, --daemonize        daemonize ibus", file=out)
    sys.exit(v)


def main():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except:
        pass

    exec_by_ibus = False
    daemonize = False

    shortopt = "ihd"
    longopt = ["ibus", "help", "daemonize"]

    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopt, longopt)
    except getopt.GetoptError:
        print_help(sys.stderr, 1)

    for o, a in opts:
        if o in ("-h", "--help"):
            print_help(sys.stdout)
        elif o in ("-d", "--daemonize"):
            daemonize = True
        elif o in ("-i", "--ibus"):
            exec_by_ibus = True
        else:
            print("Unknown argument: %s" % o, file=sys.stderr)
            print_help(sys.stderr, 1)

    if daemonize:
        if os.fork():
            sys.exit()

    launch_engine(exec_by_ibus)


if __name__ == "__main__":
    logger.info('iwubi main.')
    main()
