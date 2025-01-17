import logging
import select
import os
import struct
import collections
import time

if hasattr(os, 'scandir'):
    from os import walk
    scandirmode = 'builtin'
else:
    try:
        from scandir import walk
        scandirmode = 'external'
    except ImportError:
        from os import walk
        scandirmode = 'unavailable'

from errno import EINTR

import inotify.constants
import inotify.calls

# Constants.

_DEFAULT_EPOLL_BLOCK_DURATION_S = 1
_HEADER_STRUCT_FORMAT = 'iIII'

# todo: the real terminal event beside IN_Q_OVERFLOW is IN_IGNORED
# ohterwise the IN_DELETE_SELF would count as much as IN_UNMOUNT
# where both could be handled differently, depending on context
_DEFAULT_TERMINAL_EVENTS = (
    'IN_Q_OVERFLOW',
    'IN_UNMOUNT',
)

# Globals.

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Inotify initialized with scandir state '%s'.", scandirmode)

_INOTIFY_EVENT = collections.namedtuple(
                    '_INOTIFY_EVENT',
                    [
                        'wd',
                        'mask',
                        'cookie',
                        'len',
                    ])

_STRUCT_HEADER_LENGTH = struct.calcsize(_HEADER_STRUCT_FORMAT)
_IS_DEBUG = bool(int(os.environ.get('DEBUG', '0')))

#todo: we should have a master exception for the whole adapter
class EventTimeoutException(Exception):
    pass


#todo: we should have a master exception for the whole adapter
class TerminalEventException(Exception):
    def __init__(self, type_name, event):
        super(TerminalEventException, self).__init__(type_name)
        self.event = event


class Inotify(object):
    def __init__(self, paths=[], block_duration_s=_DEFAULT_EPOLL_BLOCK_DURATION_S):
        self.__block_duration = block_duration_s
        self.__watches = {}
        self.__watches_r = {}
        self.__buffer = b''

        self.__inotify_fd = inotify.calls.inotify_init()
        _LOGGER.debug("Inotify handle is (%d).", self.__inotify_fd)

        self.__epoll = select.epoll()
        self.__epoll.register(self.__inotify_fd, select.POLLIN)

        self.__last_success_return = None

        for path in paths:
            self.add_watch(path)

    def __get_block_duration(self):
        """Allow the block-duration to be an integer or a function-call."""

        try:
            return self.__block_duration()
        except TypeError:
            # A scalar value describing seconds.
            return self.__block_duration

    def __del__(self):
        _LOGGER.debug("Cleaning-up inotify.")
        os.close(self.__inotify_fd)

    def add_watch(self, path_unicode, mask=inotify.constants.IN_ALL_EVENTS_WATCH):
        _LOGGER.debug("Adding watch: [%s]", path_unicode)
        # todo: log a warning if user supplies something in mask that is not valid as mask (but silently ignored)
        # defined IN_ALL_MASKVALS for that (should encourage user to understand when they are requesting something
        # wrong and make it more likely that they log an issue if they have some valid mask value from sources
        # which isn't implemented in PyInotify

        # todo: handle removes for same object (with possible different pathnames)
        # more outcome-oriented

        # todo: cope with the mentioned race-conditions
        # Because there might be race-conditions in the recursive handling (see
        # the notes in the documentation), we recommend to add watches using
        # data from a secondary channel, if possible, which means that we might
        # then be adding it, yet again, if we then receive it in the normal
        # fashion afterward.
        if path_unicode in self.__watches:
            # to consider: a raise would be more appropriate for most cases
            _LOGGER.warning("Path already being watched: [%s]", path_unicode)
            return

        path_bytes = path_unicode.encode('utf8')

        wd = inotify.calls.inotify_add_watch(self.__inotify_fd, path_bytes, mask)
        _LOGGER.debug("Added watch (%d): [%s]", wd, path_unicode)

        self.__watches[path_unicode] = wd
        self.__watches_r[wd] = path_unicode

        return wd

    def _remove_watch(self, wd, path, superficial=False):
        _LOGGER.debug("Removing watch for watch-handle (%d): [%s]",
                      wd, path)

        if superficial is not None:
            del self.__watches[path]
            del self.__watches_r[wd]
            inotify.adapters._LOGGER.debug(".. removed from adaptor")
        if superficial is not False:
            return
        inotify.calls.inotify_rm_watch(self.__inotify_fd, wd)
        _LOGGER.debug(".. removed from inotify")


    def remove_watch(self, path, superficial=False):
        """Remove our tracking information and call inotify to stop watching
        the given path. When a directory is removed, we'll just have to remove
        our tracking since inotify already cleans-up the watch.
        With superficial set to None it is also possible to remove only inotify
        watch to be able to wait for the final IN_IGNORED event received for
        the wd (useful for example in threaded applications).
        """

        # todo: handle removes for same object (with possible different pathnames)
        # more outcome-oriented

        wd = self.__watches.get(path)
        if wd is None:
            _LOGGER.warning("Path not in watch list: [%s]", path)
            #todo: returning always None but no success indicator is not fine
            # to consider: a raise would be more appropriate for most cases
            return
        self._remove_watch(wd, path, superficial)

    def remove_watch_with_id(self, wd, superficial=False):
        """Same as remove_watch but does the same by id"""
        path = self.__watches_r.get(wd)
        if path is None:
            #todo: returning always None but no success indicator is not fine
            # to consider: a raise would be more appropriate for most cases
            _LOGGER.warning("Watchdescriptor not in watch list: [%d]", wd)
            return
        self._remove_watch(wd, path, superficial)

    def _get_event_names(self, event_type):
        try:
            return inotify.constants.MASK_LOOKUP_COMB[event_type][:]
        except KeyError as ex:
            raise AssertionError("We could not resolve all event-types (%x)" % event_type)

    def _handle_inotify_event(self, wd):
        """Handle a series of events coming-in from inotify."""

        # to consider: inotify should always return only complete events
        # for a single read, so implementation could be optimized
        b = os.read(wd, 1024)
        if not b:
            return

        self.__buffer += b

        while 1:
            length = len(self.__buffer)

            if length < _STRUCT_HEADER_LENGTH:
                _LOGGER.debug("Not enough bytes for a header.")
                return

            # We have, at least, a whole-header in the buffer.

            peek_slice = self.__buffer[:_STRUCT_HEADER_LENGTH]

            header_raw = struct.unpack(
                            _HEADER_STRUCT_FORMAT,
                            peek_slice)

            header = _INOTIFY_EVENT(*header_raw)
            type_names = self._get_event_names(header.mask)
            _LOGGER.debug("Events received in stream: {0}".format(type_names))

            event_length = (_STRUCT_HEADER_LENGTH + header.len)
            if length < event_length:
                return

            filename = self.__buffer[_STRUCT_HEADER_LENGTH:event_length]

            # Our filename is 16-byte aligned and right-padded with NULs.
            filename_bytes = filename.rstrip(b'\0')

            self.__buffer = self.__buffer[event_length:]

            #todo: proper accounting for renames missing (it's possible to leave
            # that up to the user but the user currently cannot rename a watch)
            path = self.__watches_r.get(header.wd)
            if path is not None:
                filename_unicode = filename_bytes.decode('utf8')
                yield (header, type_names, path, filename_unicode)

            buffer_length = len(self.__buffer)
            if buffer_length < _STRUCT_HEADER_LENGTH:
                break

    def event_gen(
            self, timeout_s=None, yield_nones=True, filter_predicate=None,
            terminal_events=_DEFAULT_TERMINAL_EVENTS, mask=inotify.constants.IN_ALL_EVENTS):
        """Yield one event after another. If `timeout_s` is provided, we'll
        break when no event is received for that many seconds.
        """

        # todo: implement proper one-shot mechanism
        # currently for that a function (! :-() is needed to temporary set
        # block_duration which can only be specified for the whole instance
        # to zero - in addition we would need to enable (or keep default :-()
        # yield_nones and check for two nones in succession to then break iteration
        # thats very inefficent and requires to much code for such a simple request

        # We will either return due to the optional filter or because of a
        # timeout. The former will always set this. The latter will never set
        # this.
        self.__last_success_return = None

        last_hit_s = time.time()
        while True:
            block_duration_s = self.__get_block_duration()

            # Poll, but manage signal-related errors.

            try:
                events = self.__epoll.poll(block_duration_s)
            except IOError as e:
                if e.errno != EINTR:
                    raise

                if timeout_s is not None:
                    time_since_event_s = time.time() - last_hit_s
                    if time_since_event_s > timeout_s:
                        break

                continue

            # Process events.

            for fd, event_type in events:
                # (fd) looks to always match the inotify FD.
                
                #names = self._get_event_names(event_type)
                #_LOGGER.debug("Events received from epoll: {}".format(names))
                #remove confusing event name... if resolved it should resolve to
                #proper EPOLL* name (EPOLLIN/1 should be common case)
                #but implement this just for this single debug line?
                _LOGGER.debug("Events received from epoll (mask o%o)", event_type)

                for (header, type_names, path, filename) \
                        in self._handle_inotify_event(fd):
                    last_hit_s = time.time()

                    e = (header, type_names, path, filename)
                    for type_name in type_names:
                        if filter_predicate is not None and \
                           filter_predicate(type_name, e) is False:
                             self.__last_success_return = (type_name, e)
                             return
                        elif type_name in terminal_events:
                            raise TerminalEventException(type_name, e)

                    if header.mask & mask:
                        yield e

            if timeout_s is not None:
                time_since_event_s = time.time() - last_hit_s
                if time_since_event_s > timeout_s:
                    break

            if yield_nones is True:
                yield None

    @property
    def last_success_return(self):
        return self.__last_success_return


class _BaseTree(object):
    def __init__(self, mask=inotify.constants.IN_ALL_EVENTS,
                 block_duration_s=_DEFAULT_EPOLL_BLOCK_DURATION_S, ignored_dirs=[]):

        # No matter what we actually received as the mask, make sure we have
        # the minimum that we require to curate our list of watches.
        if mask & (inotify.constants.IN_MASK_CREATE | inotify.constants.IN_MASK_ADD | inotify.constants.IN_ONESHOT):
            raise ValueError('mask must not contain IN_MASK_CREATE/IN_MASK_ADD/IN_ONESHOT for ' + self.__class__.__name__)
        if mask & inotify.constants.IN_DONT_FOLLOW:
            _LOGGER.info('IN_DONT_FOLLOW (or the opposite) currently not implemented for ' + self.__class__.__name__)
        if mask & inotify.constants.IN_ONLYDIR:
            _LOGGER.info('IN_ONLYDIR (or the opposite) currently not implemented for ' + self.__class__.__name__)
        # if we would want to give user the opportunity to get only IS_DIR events this would need to be implemented
        # in a dedicated way
        self._consumer_mask = mask & (~inotify.constants.IN_ISDIR)
        self._mask = mask | \
                        inotify.constants.IN_CREATE | \
                        inotify.constants.IN_MOVED_TO | \
                        inotify.constants.IN_DELETE | \
                        inotify.constants.IN_MOVED_FROM | \
                        inotify.constants.IN_DELETE_SELF | \
                        inotify.constants.IN_MOVE_SELF

        ignored_dirs_lookup = {}
        for parent, child in (os.path.split(ignored.rstrip('/')) for ignored in ignored_dirs):
            if not parent:
                parent = '.'
            if parent in ignored_dirs_lookup:
                ignored_dirs_lookup[parent].add(child)
            else:
                ignored_dirs_lookup[parent] = set((child,))
        self._ignored_dirs = ignored_dirs_lookup

        self._moved_out_dirs = {}
        self._deleted_dirs = {}
        self._top_level_watches = {}

        self._i = Inotify(block_duration_s=block_duration_s)

    def __directory_deleted(self, full_path):
        self._i.remove_watch(full_path, superficial=True)

    def __directory_moved_out(self, full_path):
        try:
            self._i.remove_watch(full_path, superficial=False)
        except inotify.calls.InotifyError as ex:
            # for the unlikely case the moved diretory is deleted
            # and automatically unregistered before we try to
            # unregister....
            pass


    def event_gen(self, ignore_missing_new_folders=False, **kwargs):
        """This is a secondary generator that wraps the principal one, and
        adds/removes watches as directories are added/removed.

        If we're doing anything funky and allowing the events to queue while a
        rename occurs then the folder may no longer exist. In this case, set
        `ignore_missing_new_folders`.
        """

        consumer_mask = self._consumer_mask
        for event in self._i.event_gen(**kwargs):
            if event is not None:
                (header, type_names, path, filename) = event

                if header.mask & inotify.constants.IN_ISDIR:
                    full_path = os.path.join(path, filename)

                    if (header.mask & inotify.constants.IN_MOVED_TO)\
                     or (header.mask & inotify.constants.IN_CREATE):
                        # todo: as long as the "Path already being watche/not in watch list" warnings
                        # instead of exceptions are in place, it should really be default to also log
                        # only a warning if target folder does not exists in tree autodiscover mode.
                        # - but probably better to implement that with try/catch around add_watch
                        # when errno fix is merged and also this should normally not be an argument
                        # to event_gen but to InotifyTree(s) constructor (at least set default there)
                        # to not steal someones use case to specify this differently for each event_gen 
                        # call?? Even more this expression is simply wrong.
                        if (ignore_missing_new_folders is False or os.path.exists(full_path) is True)\
                         and (path not in self._ignored_dirs or filename not in self._ignored_dirs[path]):
                            _LOGGER.debug("A directory has been created. We're "
                                          "adding a watch on it (because we're "
                                          "being recursive): [%s]", full_path)

                            self._load_tree(full_path)

                    elif header.mask & inotify.constants.IN_DELETE:
                        _LOGGER.debug("A directory has been removed. We're "
                                      "being recursive, but it would have "
                                      "automatically been deregistered: [%s]",
                                      full_path)

                        # todo: it would be appropriate to ensure the the watch is not removed
                        # that far that following events from the child fd are suppressed
                        # before the watch on the child disappeared
                        # also we have to take in mind that the subdirectory could be on
                        # ignore list (currently that is handled by the remove_watch but a
                        # debug message is emitted then what is not fine)

                        # The watch would've already been cleaned-up internally.
                        self.__directory_deleted(full_path)
                    elif header.mask & inotify.constants.IN_MOVED_FROM:
                        _LOGGER.debug("A directory has been renamed. We're "
                                      "being recursive, we will remove watch "
                                      "from it and re-add with IN_MOVED_TO "
                                      "if target parent dir is within "
                                      "our tree: [%s]", full_path)

                        # todo: it would be fine if no remove/add action would take place
                        # if directory is moved within watched tree (so doesn't goes out of scope
                        # by the move)
                        # also we have to take in mind that the subdirectory could be on
                        # ignore list (currently that is handled by the exception handler)
                        self.__directory_moved_out(full_path)
                if header.mask & consumer_mask:
                    yield event
            else:
                yield event

    @property
    def inotify(self):
        return self._i

    def _load_tree(self, path):
        # to be cosnidered: it would be very convenient to emit some "fake" events
        # (events that are generated by the implementation and not inotify) for all
        # found objects so that consumers do not need to scan directories again to
        # generate themself an overview of the tree

        i = self._i
        mask = self._mask | inotify.constants.IN_ONLYDIR
        wd = i.add_watch(path, mask)
        added_watches = [(path, wd)]
        ignored_dirs = self._ignored_dirs

        # todo: check whether and how to handle symlinks to directories
        for dirpath, subdirs, _f in walk(path):
            if subdirs:
                num_subdirs = len(subdirs)
                pos_subdirs = 0
                ignored_subdirs = ignored_dirs.get(dirpath)
                if ignored_subdirs:
                    while pos_subdirs < num_subdirs:
                        subdir = subdirs[pos_subdirs]
                        if subdir in ignored_subdirs:
                            del subdirs[pos_subdirs]
                            num_subdirs -= 1
                            continue
                        path = os.path.join(dirpath, subdir)
                        wd = i.add_watch(path, mask)
                        added_watches.append((path, wd))
                        pos_subdirs += 1
                else:
                    while pos_subdirs < num_subdirs:
                        subdir = subdirs[pos_subdirs]
                        path = os.path.join(dirpath, subdir)
                        wd = i.add_watch(path, mask)
                        added_watches.append((path, wd))
                        pos_subdirs += 1
        return added_watches

class InotifyTree(_BaseTree):
    """Recursively watch a path."""

    def __init__(self, path, mask=inotify.constants.IN_ALL_EVENTS,
                 block_duration_s=_DEFAULT_EPOLL_BLOCK_DURATION_S, ignored_dirs=[]):
        super(InotifyTree, self).__init__(mask=mask, block_duration_s=block_duration_s,
              ignored_dirs=ignored_dirs)

        self.__load_tree(path)

    def __load_tree(self, path):
        _LOGGER.debug("Adding initial watches on tree: [%s]", path)
        tl_watch_path, tl_watch_desc = self._load_tree(path)[0]
        self._top_level_watches[tl_watch_path] = tl_watch_desc


class InotifyTrees(_BaseTree):
    """Recursively watch over a list of trees."""

    def __init__(self, paths, mask=inotify.constants.IN_ALL_EVENTS,
                 block_duration_s=_DEFAULT_EPOLL_BLOCK_DURATION_S, ignored_dirs=[]):
        super(InotifyTrees, self).__init__(mask=mask, block_duration_s=block_duration_s,
              ignored_dirs=ignored_dirs)

        self.__load_trees(paths)

    def __load_trees(self, paths):
        _LOGGER.debug("Adding initial watches on trees: [%s]", ",".join(map(str, paths)))
        for path in paths:
            tl_watch_path, tl_watch_desc = self._load_tree(path)[0]
            self._top_level_watches[tl_watch_path] = tl_watch_desc
