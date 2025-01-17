# -*- coding: utf-8 -*-

import os
import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest
import errno
import shutil

import inotify.constants
import inotify.adapters
import inotify.calls
import inotify.test_support

try:
    unicode
except NameError:
    _HAS_PYTHON2_UNICODE_SUPPORT = False
else:
    _HAS_PYTHON2_UNICODE_SUPPORT = True

_HAS_DIRECTORY_ACCESS_EVENTS = None

def setUpModule():
    with inotify.test_support.temp_path() as path:
        subdirname = 'dir_acc_evt_tst'
        inner_path = os.path.join(path, subdirname)
        os.mkdir(inner_path)

        i = inotify.adapters.Inotify()
        i.add_watch(path)
        dircontent = os.listdir(inner_path)
        i.add_watch(inner_path)
        os.rmdir(inner_path)

        events = list(i.event_gen(timeout_s=1, yield_nones=False))

        expected_na = [
            (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, subdirname),
            (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, subdirname),
        ]
        expected_wa = [
            (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, subdirname),
            (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, subdirname),
            (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, subdirname),
        ]
        expected_ws = [
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742336, cookie=0, len=16), ['IN_DELETE', 'IN_ISDIR'], path, subdirname),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1024, cookie=0, len=0), ['IN_DELETE_SELF'], inner_path, ''),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=32768, cookie=0, len=0), ['IN_IGNORED'], inner_path, ''),
        ]
        expected_ns = [
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1024, cookie=0, len=0), ['IN_DELETE_SELF'], inner_path, ''),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=32768, cookie=0, len=0), ['IN_IGNORED'], inner_path, ''),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742336, cookie=0, len=16), ['IN_DELETE', 'IN_ISDIR'], path, subdirname),
        ]
        global _HAS_DIRECTORY_ACCESS_EVENTS
        global _HAS_STRONG_PARENT_AFTER_CHILD
        if events == expected_wa + expected_ns:
            _HAS_DIRECTORY_ACCESS_EVENTS = True
            _HAS_STRONG_PARENT_AFTER_CHILD = True
        elif events == expected_na + expected_ws:
            _HAS_DIRECTORY_ACCESS_EVENTS = False
            _HAS_STRONG_PARENT_AFTER_CHILD = False
        elif events == expected_wa + expected_ws:
            _HAS_DIRECTORY_ACCESS_EVENTS = True
            _HAS_STRONG_PARENT_AFTER_CHILD = False
        elif events == expected_na + expected_ns:
            _HAS_DIRECTORY_ACCESS_EVENTS = False
            _HAS_STRONG_PARENT_AFTER_CHILD = True
        else:
            print('Got unknown directory access pattern:\n%r' %(events,))
            raise AssertionError('Found neighter expected directory access pattern')


class TestInotify(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.maxDiff = None

        super(TestInotify, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        global _HAS_DIRECTORY_ACCESS_EVENTS
        cls._HAS_DIRECTORY_ACCESS_EVENTS = _HAS_DIRECTORY_ACCESS_EVENTS
        global _HAS_STRONG_PARENT_AFTER_CHILD
        cls._HAS_STRONG_PARENT_AFTER_CHILD = _HAS_STRONG_PARENT_AFTER_CHILD

    def __read_all_events(self, i):
        events = list(i.event_gen(timeout_s=1, yield_nones=False))
        return events

    @unittest.skipIf(_HAS_PYTHON2_UNICODE_SUPPORT is True, "Not in Python 3")
    def test__international_naming_python3(self):
        with inotify.test_support.temp_path() as path:
            inner_path = os.path.join(path, '新增資料夾')
            os.mkdir(inner_path)

            i = inotify.adapters.Inotify()
            i.add_watch(inner_path)

            with open(os.path.join(inner_path, 'filename'), 'w'):
                pass

            events = self.__read_all_events(i)

            expected = [
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=256, cookie=0, len=16), ['IN_CREATE'], inner_path, 'filename'),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=32, cookie=0, len=16), ['IN_OPEN'], inner_path, 'filename'),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], inner_path, 'filename'),
            ]

            self.assertEquals(events, expected)

    @unittest.skipIf(_HAS_PYTHON2_UNICODE_SUPPORT is False, "Not in Python 2")
    def test__international_naming_python2(self):
        with inotify.test_support.temp_path() as path:
            inner_path = os.path.join(unicode(path), u'新增資料夾')
            os.mkdir(inner_path)

            i = inotify.adapters.Inotify()
            i.add_watch(inner_path)

            with open(os.path.join(inner_path, u'filename料夾'), 'w'):
                pass

            events = self.__read_all_events(i)

            expected = [
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=256, cookie=0, len=16), ['IN_CREATE'], inner_path, u'filename料夾'),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=32, cookie=0, len=16), ['IN_OPEN'], inner_path, u'filename料夾'),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], inner_path, u'filename料夾'),
            ]

            self.assertEquals(events, expected)

    def test__cycle(self):
        with inotify.test_support.temp_path() as path:
            path1 = os.path.join(path, 'aa')
            os.mkdir(path1)

            path2 = os.path.join(path, 'bb')
            os.mkdir(path2)

            i = inotify.adapters.Inotify()
            i.add_watch(path1)

            with open('ignored_new_file', 'w'):
                pass

            with open(os.path.join(path1, 'seen_new_file'), 'w'):
                pass

            with open(os.path.join(path2, 'ignored_new_file'), 'w'):
                pass

            os.remove(os.path.join(path1, 'seen_new_file'))

            events = self.__read_all_events(i)

            expected = [
                (
                    inotify.adapters._INOTIFY_EVENT(wd=1, mask=256, cookie=0, len=16),
                    ['IN_CREATE'],
                    path1,
                    'seen_new_file'
                ),
                (
                    inotify.adapters._INOTIFY_EVENT(wd=1, mask=32, cookie=0, len=16),
                    ['IN_OPEN'],
                    path1,
                    'seen_new_file'
                ),
                (
                    inotify.adapters._INOTIFY_EVENT(wd=1, mask=8, cookie=0, len=16),
                    ['IN_CLOSE_WRITE'],
                    path1,
                    'seen_new_file'
                ),
                (
                    inotify.adapters._INOTIFY_EVENT(wd=1, mask=512, cookie=0, len=16),
                    ['IN_DELETE'],
                    path1,
                    'seen_new_file'
                )
            ]

            self.assertEquals(events, expected)

            # This can't be removed until *after* we've read the events because
            # they'll be flushed the moment we remove the watch.
            i.remove_watch(path1)

            with open(os.path.join(path1, 'ignored_after_removal'), 'w'):
                pass

            events = self.__read_all_events(i)
            self.assertEquals(events, [])

#test disabled because _get_event_names has been refactored
#for better performance and consistent+useful order of eventnames
#and this function now only works for what it is intended for:
#resolve possible event-names for received events
#if that breaks some other test should fail
#todo: ensure all possible returns are triggered by testcases
#    def test__get_event_names(self):
#        all_mask = 0
#        for bit in inotify.constants.MASK_LOOKUP.keys():
#            all_mask |= bit
#
#        all_names = inotify.constants.MASK_LOOKUP.values()
#        all_names = list(all_names)
#
#        i = inotify.adapters.Inotify()
#        names = i._get_event_names(all_mask)
#
#        self.assertEquals(names, all_names)

    def test__exception_errno(self):
        with inotify.test_support.temp_path() as path:
            i = inotify.adapters.Inotify()
            errnum = None
            path1 = os.path.join(path, 'abc')
            try:
                i.add_watch(path1)
            except inotify.calls.InotifyError as ex:
                errnum = ex.errno
            self.assertEquals(errnum, errno.ENOENT)

class TestInotifyTree(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.maxDiff = None

        super(TestInotifyTree, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        global _HAS_DIRECTORY_ACCESS_EVENTS
        cls._HAS_DIRECTORY_ACCESS_EVENTS = _HAS_DIRECTORY_ACCESS_EVENTS
        global _HAS_STRONG_PARENT_AFTER_CHILD
        cls._HAS_STRONG_PARENT_AFTER_CHILD = _HAS_STRONG_PARENT_AFTER_CHILD

    def __read_all_events(self, i):
        events = list(i.event_gen(timeout_s=1, yield_nones=False))
        return events

    def test__cycle(self):
        with inotify.test_support.temp_path() as path:
            path1 = os.path.join(path, 'aa')
            os.mkdir(path1)

            path2 = os.path.join(path, 'bb')
            os.mkdir(path2)

            i = inotify.adapters.InotifyTree(path)

            watches = i._i._Inotify__watches
            w2, w3 = watches[path1], watches[path2]

            with open(os.path.join(path, 'seen_new_file1'), 'w'):
                pass

            with open(os.path.join(path1, 'seen_new_file2'), 'w'):
                pass

            with open(os.path.join(path2, 'seen_new_file3'), 'w'):
                pass

            os.remove(os.path.join(path, 'seen_new_file1'))
            os.remove(os.path.join(path1, 'seen_new_file2'))
            os.remove(os.path.join(path2, 'seen_new_file3'))

            os.rmdir(path1)
            os.rmdir(path2)

            events = self.__read_all_events(i)

            if self._HAS_DIRECTORY_ACCESS_EVENTS:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                ]
                _access_dir_a = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'aa'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'aa'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'aa'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'aa'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, ''),
                ]
                _access_dir_b = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'bb'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'bb'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'bb'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'bb'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path2, ''),
                ]
            else:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                ]
                _access_dir_a = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'aa'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'aa'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, ''),
                ]
                _access_dir_b = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'bb'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'bb'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path2, ''),
                ]

            # we can't be sure about the order the watches were registered
            expected += (_access_dir_a + _access_dir_b if w2 < w3 
                        else _access_dir_b + _access_dir_a)

            expected += [
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=256, cookie=0, len=16), ['IN_CREATE'], path, 'seen_new_file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=32, cookie=0, len=16), ['IN_OPEN'], path, 'seen_new_file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path, 'seen_new_file1'),

                (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=256, cookie=0, len=16), ['IN_CREATE'], path1, 'seen_new_file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=32, cookie=0, len=16), ['IN_OPEN'], path1, 'seen_new_file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path1, 'seen_new_file2'),

                (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=256, cookie=0, len=16), ['IN_CREATE'], path2, 'seen_new_file3'),
                (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=32, cookie=0, len=16), ['IN_OPEN'], path2, 'seen_new_file3'),
                (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path2, 'seen_new_file3'),

                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=512, cookie=0, len=16), ['IN_DELETE'], path, 'seen_new_file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=512, cookie=0, len=16), ['IN_DELETE'], path1, 'seen_new_file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=512, cookie=0, len=16), ['IN_DELETE'], path2, 'seen_new_file3'),
            ]

            if self._HAS_STRONG_PARENT_AFTER_CHILD:
                expected += [
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=1024, cookie=0, len=0), ['IN_DELETE_SELF'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=32768, cookie=0, len=0), ['IN_IGNORED'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742336, cookie=0, len=16), ['IN_DELETE', 'IN_ISDIR'], path, 'aa'),

                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=1024, cookie=0, len=0), ['IN_DELETE_SELF'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=32768, cookie=0, len=0), ['IN_IGNORED'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742336, cookie=0, len=16), ['IN_DELETE', 'IN_ISDIR'], path, 'bb'),
                ]
            else:
                expected += [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742336, cookie=0, len=16), ['IN_DELETE', 'IN_ISDIR'], path, 'aa'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742336, cookie=0, len=16), ['IN_DELETE', 'IN_ISDIR'], path, 'bb'),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=1024, cookie=0, len=0), ['IN_DELETE_SELF'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=w2, mask=32768, cookie=0, len=0), ['IN_IGNORED'], path1, ''),

                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=1024, cookie=0, len=0), ['IN_DELETE_SELF'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=w3, mask=32768, cookie=0, len=0), ['IN_IGNORED'], path2, ''),
                ]

            self.assertEquals(events, expected)

    def test__renames(self):

        # Since we're not reading the events one at a time in a loop and
        # removing or renaming folders will flush any queued events, we have to
        # group things in order to check things first before such operations.

        with inotify.test_support.temp_path() as path:
            i = inotify.adapters.InotifyTree(path)

            old_path = os.path.join(path, 'old_folder')
            new_path = os.path.join(path, 'new_folder')

            os.mkdir(old_path)

            events1 = self.__read_all_events(i)

            if self._HAS_DIRECTORY_ACCESS_EVENTS:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742080, cookie=0, len=16), ['IN_CREATE', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], old_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], old_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], old_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], old_path, ''),
                ]
            else:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742080, cookie=0, len=16), ['IN_CREATE', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], old_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], old_path, ''),
                ]

            self.assertEquals(events1, expected)


            os.rename(old_path, new_path)

            events2 = self.__read_all_events(i)

            if self._HAS_DIRECTORY_ACCESS_EVENTS:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741888, cookie=events2[1][0].cookie, len=16), ['IN_MOVED_FROM', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741952, cookie=events2[0][0].cookie, len=16), ['IN_MOVED_TO', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], new_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], new_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], new_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], new_path, ''),
                ]
            else:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741888, cookie=events2[1][0].cookie, len=16), ['IN_MOVED_FROM', 'IN_ISDIR'], path, 'old_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741952, cookie=events2[0][0].cookie, len=16), ['IN_MOVED_TO', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], new_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], new_path, ''),
                ]

            self.assertEquals(events2, expected)


            with open(os.path.join(new_path, 'old_filename'), 'w'):
                pass

            os.rename(
                os.path.join(new_path, 'old_filename'),
                os.path.join(new_path, 'new_filename'))

            os.remove(os.path.join(path, 'new_folder', 'new_filename'))
            os.rmdir(os.path.join(path, 'new_folder'))

            events3 = self.__read_all_events(i)

            expected = [
                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=256, cookie=0, len=16), ['IN_CREATE'], new_path, 'old_filename'),
                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=32, cookie=0, len=16), ['IN_OPEN'], new_path, 'old_filename'),
                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], new_path, 'old_filename'),

                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=64, cookie=events3[3][0].cookie, len=16), ['IN_MOVED_FROM'], new_path, 'old_filename'),
                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=128, cookie=events3[4][0].cookie, len=16), ['IN_MOVED_TO'], new_path, 'new_filename'),

                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=512, cookie=0, len=16), ['IN_DELETE'], new_path, 'new_filename'),
            ]

            if self._HAS_STRONG_PARENT_AFTER_CHILD:
                expected += [
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1024, cookie=0, len=0), ['IN_DELETE_SELF'], new_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=32768, cookie=0, len=0), ['IN_IGNORED'], new_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742336, cookie=0, len=16), ['IN_DELETE', 'IN_ISDIR'], path, 'new_folder'),
                ]
            else:
                expected += [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742336, cookie=0, len=16), ['IN_DELETE', 'IN_ISDIR'], path, 'new_folder'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1024, cookie=0, len=0), ['IN_DELETE_SELF'], new_path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=32768, cookie=0, len=0), ['IN_IGNORED'], new_path, ''),
                ]

            self.assertEquals(events3, expected)

    def test__automatic_new_watches_on_new_paths(self):

        # Tests that watches are actively established as new folders are
        # created.

        with inotify.test_support.temp_path() as path:
            i = inotify.adapters.InotifyTree(path)

            path1 = os.path.join(path, 'folder1')
            path2 = os.path.join(path1, 'folder2')

            os.mkdir(path1)

            events = self.__read_all_events(i)

            if self._HAS_DIRECTORY_ACCESS_EVENTS:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742080, cookie=0, len=16), ['IN_CREATE', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, ''),
                ]
            else:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073742080, cookie=0, len=16), ['IN_CREATE', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, ''),
                ]

            self.assertEquals(events, expected)


            os.mkdir(path2)

            events = self.__read_all_events(i)

            if self._HAS_DIRECTORY_ACCESS_EVENTS:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073742080, cookie=0, len=16), ['IN_CREATE', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path2, ''),
                ]
            else:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073742080, cookie=0, len=16), ['IN_CREATE', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path2, ''),
                ]

            self.assertEquals(events, expected)


            with open(os.path.join(path2,'filename'), 'w'):
                pass

            events = self.__read_all_events(i)

            expected = [
                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=256, cookie=0, len=16), ['IN_CREATE'], path2, 'filename'),
                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=32, cookie=0, len=16), ['IN_OPEN'], path2, 'filename'),
                (inotify.adapters._INOTIFY_EVENT(wd=3, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path2, 'filename'),
            ]

            self.assertEquals(events, expected)

    def test__automatic_new_watches_on_existing_paths(self):

        # Tests whether the watches are recursively established when we
        # initialize.

        with inotify.test_support.temp_path() as path:
            path1 = os.path.join(path, 'folder1')
            path2 = os.path.join(path1, 'folder2')

            os.mkdir(path1)
            os.mkdir(path2)

            i = inotify.adapters.InotifyTree(path)

            with open(os.path.join(path2,'filename'), 'w'):
                pass

            events = self.__read_all_events(i)

            if self._HAS_DIRECTORY_ACCESS_EVENTS:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=256, cookie=0, len=16), ['IN_CREATE'], path2, 'filename'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=32, cookie=0, len=16), ['IN_OPEN'], path2, 'filename'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path2, 'filename'),
                ]
            else:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, 'folder1'),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, 'folder2'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=256, cookie=0, len=16), ['IN_CREATE'], path2, 'filename'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=32, cookie=0, len=16), ['IN_OPEN'], path2, 'filename'),
                    (inotify.adapters._INOTIFY_EVENT(wd=3, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path2, 'filename'),
                ]

            self.assertEquals(events, expected)

    def test__exclude_subdirectories(self):

        # Tests whether the skip_dires parameter works as expected

        with inotify.test_support.temp_path() as path:
            for foldernum1 in range(1,5):
                path1 = os.path.join(path, 'folder%d' % foldernum1)
                os.mkdir(path1)
                for foldernum2 in range(1,5):
                    path2 = os.path.join(path1, 'subfolder%d' % foldernum2)
                    os.mkdir(path2)
                    for foldernum3 in range(1,3):
                        path3 = os.path.join(path2, 'subsubfolder%d' % foldernum3)
                        os.mkdir(path3)

            ignored_dirs = (os.path.join(path, 'folder1'),
                            os.path.join(path, 'folder2', 'subfolder2'),
                            os.path.join(path, 'folder2', 'subfolder3'),
                            os.path.join(path, 'folder2', 'subfolder4', 'subsubfolder2'),
                            os.path.join(path, 'folder3'),
                            os.path.join(path, 'folder4'),
            )

            expected_watches = (path, os.path.join(path, 'folder2'),
                                os.path.join(path, 'folder2', 'subfolder1'),
                                os.path.join(path, 'folder2', 'subfolder1', 'subsubfolder1'),
                                os.path.join(path, 'folder2', 'subfolder1', 'subsubfolder2'),
                                os.path.join(path, 'folder2', 'subfolder4'),
                                os.path.join(path, 'folder2', 'subfolder4', 'subsubfolder1'),
            )

            i = inotify.adapters.InotifyTree(path, ignored_dirs=ignored_dirs)
            events = self.__read_all_events(i)

            watches = i._i._Inotify__watches
            self.assertEquals(sorted(watches.keys()), sorted(expected_watches))

            discovered_subdirs_expects = { path: [] }

            if self._HAS_DIRECTORY_ACCESS_EVENTS:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                ]
                for dirpath, dirwd in sorted(watches.items(), key=lambda tup: tup[1])[1:]:
                    parentpath, dirname = os.path.split(dirpath)
                    parentwd = watches[parentpath]
                    expects = [
                        (inotify.adapters._INOTIFY_EVENT(wd=parentwd, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], parentpath, dirname),
                        (inotify.adapters._INOTIFY_EVENT(wd=dirwd, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], dirpath, ''),
                        (inotify.adapters._INOTIFY_EVENT(wd=parentwd, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], parentpath, dirname),
                        (inotify.adapters._INOTIFY_EVENT(wd=dirwd, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], dirpath, ''),
                        (inotify.adapters._INOTIFY_EVENT(wd=parentwd, mask=1073741825, cookie=0, len=16), ['IN_ACCESS', 'IN_ISDIR'], parentpath, dirname),
                        (inotify.adapters._INOTIFY_EVENT(wd=dirwd, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], dirpath, ''),
                        (inotify.adapters._INOTIFY_EVENT(wd=parentwd, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], parentpath, dirname),
                        (inotify.adapters._INOTIFY_EVENT(wd=dirwd, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], dirpath, ''),
                    ]
                    discovered_subdirs_expects[parentpath].append((dirpath, expects))
                    discovered_subdirs_expects[dirpath] = []
            else:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path, ''),
                ]
                for dirpath, dirwd in sorted(watches.items(), key=lambda tup: tup[1])[1:]:
                    parentpath, dirname = os.path.split(dirpath)
                    parentwd = watches[parentpath]
                    expects = [
                        (inotify.adapters._INOTIFY_EVENT(wd=parentwd, mask=1073741856, cookie=0, len=16), ['IN_OPEN', 'IN_ISDIR'], parentpath, dirname),
                        (inotify.adapters._INOTIFY_EVENT(wd=dirwd, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], dirpath, ''),
                        (inotify.adapters._INOTIFY_EVENT(wd=parentwd, mask=1073741840, cookie=0, len=16), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], parentpath, dirname),
                        (inotify.adapters._INOTIFY_EVENT(wd=dirwd, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], dirpath, ''),
                    ]
                    discovered_subdirs_expects[parentpath].append((dirpath, expects))
                    discovered_subdirs_expects[dirpath] = []

            for dirpath, expects in discovered_subdirs_expects[path]:
                expected += expects
                for dirpath, expects in discovered_subdirs_expects[dirpath]:
                    expected += expects
                    for dirpath, expects in discovered_subdirs_expects[dirpath]:
                        expected += expects

            self.assertEquals(events, expected)

    def test__moving_readded_folder(self):
        #test for https://github.com/dsoprea/PyInotify/issues/46
        #doing no checks of genereated events as current master does
        #not generate events that should really be expected in this case
        #avoid having to adjust this - also not implement chcking for expected
        #wd assignment now..
        #just check for no exception and expected watches in the end
        #emulate slow mkdir/rmdir/rename... (because of another unfixed bug and
        #because this is needed to reproduces issue)
        with inotify.test_support.temp_path() as path:
            path1 = os.path.join(path, 'org_folder')
            path2 = os.path.join(path, 'ren_folder')

            i = inotify.adapters.InotifyTree(path)
            os.mkdir(path1)
            events = self.__read_all_events(i)
            os.rmdir(path1)
            events = self.__read_all_events(i)
            os.mkdir(path1)
            events = self.__read_all_events(i)
            os.rename(path1, path2)
            events = self.__read_all_events(i)

            watches = i._i._Inotify__watches
            watches_reverse = i._i._Inotify__watches_r

            watches_expect = sorted((path,path2))
            watches_reg_names = sorted(watches.keys())
            watches_reg_check = dict((value, key) for key, value in watches.items())

            self.assertEquals(watches_expect, watches_reg_names)
            self.assertEquals(watches_reg_check, watches_reverse)

    def test__readd_deleted_folder(self):
        #test for https://github.com/dsoprea/PyInotify/issues/51
        #doing no checks the directory-discovery events as current master does
        #not generate events that should really be expected in this case
        #avoid having to adjust this - also not implement chcking for expected
        #wd assignment now..
        #just check for no exception, file creation events and expected watches
        #at the end. emulate slow succession of filesystem actions... (because
        #of another unfixed bug and because this is needed to reproduces issue)
        with inotify.test_support.temp_path() as path:
            path1 = os.path.join(path, 'folder')
            file1 = os.path.join(path1, 'file1')
            file2 = os.path.join(path1, 'file2')

            i = inotify.adapters.InotifyTree(path)
            os.mkdir(path1)
            events = self.__read_all_events(i)
            with open(file1, 'w'):
                pass
            with open(file2, 'w'):
                pass
            events = self.__read_all_events(i)

            expected = [
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=256, cookie=0, len=16), ['IN_CREATE'], path1, 'file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=32, cookie=0, len=16), ['IN_OPEN'], path1, 'file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path1, 'file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=256, cookie=0, len=16), ['IN_CREATE'], path1, 'file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=32, cookie=0, len=16), ['IN_OPEN'], path1, 'file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path1, 'file2'),
            ]
            self.assertEquals(events, expected)

            shutil.rmtree(path1)
            events = self.__read_all_events(i)

            #could do the following asserts here to prove the the assumption of amigian74 in
            #his 5th point in issue 51 ("everything until now works fine") false, but that is
            #not target of this test, also it is not his reposibility to verify this...
            #so to get same issue he describes it's just a comment...
            #self.assertEquals(len(i._i._Inotify__watches), 1)
            #self.assertEquals(len(i._i._Inotify__watches_r), 1)
            #self.assertNotIn(path1, i._i._Inotify__watches)

            os.mkdir(path1)
            events = self.__read_all_events(i)
            with open(file1, 'w'):
                pass
            with open(file2, 'w'):
                pass
            events = self.__read_all_events(i)

            watches = i._i._Inotify__watches
            watches_reverse = i._i._Inotify__watches_r

            watches_expect = sorted((path,path1))
            watches_reg_names = sorted(watches.keys())
            watches_reg_check = dict((value, key) for key, value in watches.items())

            self.assertEquals(watches_expect, watches_reg_names)
            self.assertEquals(watches_reg_check, watches_reverse)

            wd = watches[path1]
            expected = [
                (inotify.adapters._INOTIFY_EVENT(wd=wd, mask=256, cookie=0, len=16), ['IN_CREATE'], path1, 'file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=wd, mask=32, cookie=0, len=16), ['IN_OPEN'], path1, 'file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=wd, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path1, 'file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=wd, mask=256, cookie=0, len=16), ['IN_CREATE'], path1, 'file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=wd, mask=32, cookie=0, len=16), ['IN_OPEN'], path1, 'file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=wd, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path1, 'file2'),
            ]
            self.assertEquals(events, expected)


class TestInotifyTrees(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.maxDiff = None

        super(TestInotifyTrees, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        global _HAS_DIRECTORY_ACCESS_EVENTS
        cls._HAS_DIRECTORY_ACCESS_EVENTS = _HAS_DIRECTORY_ACCESS_EVENTS
        global _HAS_STRONG_PARENT_AFTER_CHILD
        cls._HAS_STRONG_PARENT_AFTER_CHILD = _HAS_STRONG_PARENT_AFTER_CHILD

    def __read_all_events(self, i):
        events = list(i.event_gen(timeout_s=1, yield_nones=False))
        return events

    def test__cycle(self):
        with inotify.test_support.temp_path() as path:
            path1 = os.path.join(path, 'aa')
            os.mkdir(path1)

            path2 = os.path.join(path, 'bb')
            os.mkdir(path2)

            i = inotify.adapters.InotifyTrees([path1, path2])

            with open(os.path.join(path1, 'seen_new_file1'), 'w'):
                pass

            with open(os.path.join(path2, 'seen_new_file2'), 'w'):
                pass

            events = self.__read_all_events(i)

            if self._HAS_DIRECTORY_ACCESS_EVENTS:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741825, cookie=0, len=0), ['IN_ACCESS', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path2, ''),
                ]
            else:
                expected = [
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=1, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path1, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741856, cookie=0, len=0), ['IN_OPEN', 'IN_ISDIR'], path2, ''),
                    (inotify.adapters._INOTIFY_EVENT(wd=2, mask=1073741840, cookie=0, len=0), ['IN_CLOSE_NOWRITE', 'IN_ISDIR'], path2, ''),
                ]

            expected += [
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=256, cookie=0, len=16), ['IN_CREATE'], path1, 'seen_new_file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=32, cookie=0, len=16), ['IN_OPEN'], path1, 'seen_new_file1'),
                (inotify.adapters._INOTIFY_EVENT(wd=1, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path1, 'seen_new_file1'),

                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=256, cookie=0, len=16), ['IN_CREATE'], path2, 'seen_new_file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=32, cookie=0, len=16), ['IN_OPEN'], path2, 'seen_new_file2'),
                (inotify.adapters._INOTIFY_EVENT(wd=2, mask=8, cookie=0, len=16), ['IN_CLOSE_WRITE'], path2, 'seen_new_file2'),
            ]

            self.assertEquals(events, expected)
