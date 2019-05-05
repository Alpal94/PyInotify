import logging
import ctypes
import os

import inotify.library

_LOGGER = logging.getLogger(__name__)

_LIB = inotify.library.instance


# todo: make this properly a subclass of OSError
class InotifyError(Exception):
    def __init__(self, message, *args, **kwargs):
        errnum = ctypes.get_errno()
        self.errno = errnum
        try: errmsg = os.strerror(errnum)
        except ValueError as ex: errmsg = ''
        message += " ERRNO=%d %s" % (errnum,errmsg)

        super(InotifyError, self).__init__(message, *args, **kwargs)

# todo: remove (comment-out) unused checks to avoid dead code and increase test.coverage
def _check_zero(result):
    if result != 0:
        raise InotifyError("Call failed (should return zero): (%d)" % 
                           (result,))

    return result

# todo: remove (comment-out) unused checks to avoid dead code and increase test.coverage
def _check_nonzero(result):
    if result == 0:
        raise InotifyError("Call failed (should return nonzero): (%d)" % 
                           (result,))

    return result

def _check_nonnegative(result):
    if result == -1:
        raise InotifyError("Call failed (should not be -1): (%d)" % 
                           (result,))

    return result

inotify_init = _LIB.inotify_init
inotify_init.argtypes = []
inotify_init.restype = _check_nonnegative

inotify_add_watch = _LIB.inotify_add_watch
inotify_add_watch.argtypes = [
    ctypes.c_int, 
    ctypes.c_char_p, 
    ctypes.c_uint32]

inotify_add_watch.restype = _check_nonnegative

inotify_rm_watch = _LIB.inotify_rm_watch
inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
inotify_rm_watch.restype = _check_nonnegative

if getattr(_LIB, 'errno', None) is not None:
    errno = _LIB.errno
elif getattr(_LIB, 'err', None) is not None:
    errno = _LIB.err
else:
    raise EnvironmentError("'errno' not found in library")
