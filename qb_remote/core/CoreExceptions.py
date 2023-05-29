
import collections.abc
import os


class qException(Exception):
    def __str__(self):

        if isinstance(self.args, collections.abc.Iterable):

            s = []

            for arg in self.args:

                try:
                    s.append(str(arg))

                except:
                    s.append(repr(arg))

        else:
            s = [repr(self.args)]

        return os.linesep.join(s)


class UnknownException(qException):
    """Unknown exception"""


class Shutdown_Exception(qException):
    """Raised to signal shutting down"""



class Data_Missing(qException):
    """Raised when there is no data"""



class Cache_Exception(qException):
    """
    Cache Base Exception
    """

class Cache_Lookup_Exception(qException):
    """
    Cache Lookup Exception

    Raised when a cache lookup has no data
    """

class Cache_Expired_Exception(qException):
    """
    Cache Expired Exception

    Raised when trying to access expired data from a cache
    """