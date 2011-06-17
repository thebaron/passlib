"""passlib utility functions"""
#=================================================================================
#imports
#=================================================================================
#core
from base64 import b64encode, b64decode
from codecs import lookup as _lookup_codec
from cStringIO import StringIO
from functools import update_wrapper
from hashlib import sha256
import logging; log = logging.getLogger(__name__)
from math import log as logb
import os
import sys
import random
import time
from warnings import warn
#site
#pkg
#local
__all__ = [
    #decorators
    "classproperty",
##    "memoized_class_property",
##    "abstractmethod",
##    "abstractclassmethod",

    #byte compat aliases
    'bytes', 'native_str',

    #misc
    'os_crypt',

    #tests
    'is_crypt_handler',
    'is_crypt_context',

    #bytes<->unicode
    'to_bytes',
    'to_unicode',
    'is_same_codec',

    #byte manipulation
    "xor_bytes",

    #random
    'rng',
    'getrandbytes',
    'getrandstr',

    #constants
    'sys_bits',
    'unix_crypt_schemes',
]

#=================================================================================
#constants
#=================================================================================

#: detect what we're running on
pypy_vm = hasattr(sys, "pypy_version_info")

#: number of bits in system architecture
sys_bits = int(logb(sys.maxint,2)+1.5)
assert sys_bits in (32,64), "unexpected sys_bits value: %r" % (sys_bits,)

#: list of names of hashes found in unix crypt implementations...
unix_crypt_schemes = [
    "sha512_crypt", "sha256_crypt",
    "sha1_crypt", "bcrypt",
    "md5_crypt",
    "bsdi_crypt", "des_crypt"
    ]

#: list of rounds_cost constants
rounds_cost_values = [ "linear", "log2" ]

#: special byte string containing all possible byte values, used in a few places.
#XXX: treated as singleton by some of the code for efficiency.
ALL_BYTE_VALUES = ''.join(chr(x) for x in xrange(256))

#NOTE: Undef is only used in *one* place now, could just remove it
class UndefType(object):
    _undef = None

    def __new__(cls):
        if cls._undef is None:
            cls._undef = object.__new__(cls)
        return cls._undef

    def __repr__(self):
        return '<Undef>'

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

#: singleton used as default kwd value in some functions, indicating "NO VALUE"
Undef = UndefType()

#==========================================================
#bytes compat aliases - bytes, native_str, b()
#==========================================================

# Py2k #
if sys.version_info < (2,6):
    #py25 doesn't define 'bytes', so we have to here -
    #and then import it everywhere bytes is needed,
    #just so we retain py25 compat - if that were sacrificed,
    #the need for this would go away
    bytes = str
else:
    bytes = bytes #just so it *can* be imported from this module
native_str = bytes
# Py3k #
#bytes = bytes #just so it *can* be imported from this module
#native_str = unicode
# end Py3k #

#=================================================================================
#os crypt helpers
#=================================================================================
try:
    #NOTE: just doing this import once, for all the various hashes that need it.
    from crypt import crypt as os_crypt
except ImportError: #pragma: no cover
    os_crypt = None

#=================================================================================
#decorators and meta helpers
#=================================================================================
class classproperty(object):
    """Function decorator which acts like a combination of classmethod+property (limited to read-only properties)"""

    def __init__(self, func):
        self.im_func = func

    def __get__(self, obj, cls):
        return self.im_func(cls)

#works but not used
##class memoized_class_property(object):
##    """function decorator which calls function as classmethod, and replaces itself with result for current and all future invocations"""
##    def __init__(self, func):
##        self.im_func = func
##
##    def __get__(self, obj, cls):
##        func = self.im_func
##        value = func(cls)
##        setattr(cls, func.__name__, value)
##        return value

#works but not used...
##def abstractmethod(func):
##    """Method decorator which indicates this is a placeholder method which
##    should be overridden by subclass.
##
##    If called directly, this method will raise an :exc:`NotImplementedError`.
##    """
##    msg = "object %(self)r method %(name)r is abstract, and must be subclassed"
##    def wrapper(self, *args, **kwds):
##        text = msg % dict(self=self, name=wrapper.__name__)
##        raise NotImplementedError(text)
##    update_wrapper(wrapper, func)
##    return wrapper

#works but not used...
##def abstractclassmethod(func):
##    """Class Method decorator which indicates this is a placeholder method which
##    should be overridden by subclass, and must be a classmethod.
##
##    If called directly, this method will raise an :exc:`NotImplementedError`.
##    """
##    msg = "class %(cls)r method %(name)r is abstract, and must be subclassed"
##    def wrapper(cls, *args, **kwds):
##        text = msg % dict(cls=cls, name=wrapper.__name__)
##        raise NotImplementedError(text)
##    update_wrapper(wrapper, func)
##    return classmethod(wrapper)

#==========================================================
#protocol helpers
#==========================================================
def is_crypt_handler(obj):
    "check if object follows the :ref:`password-hash-api`"
    return all(hasattr(obj, name) for name in (
        "name",
        "setting_kwds", "context_kwds",
        "genconfig", "genhash",
        "verify", "encrypt", "identify",
        ))

def is_crypt_context(obj):
    "check if object follows :class:`CryptContext` interface"
    return all(hasattr(obj, name) for name in (
        "hash_needs_update",
        "genconfig", "genhash",
        "verify", "encrypt", "identify",
        ))

def has_rounds_info(handler):
    "check if handler provides the optional :ref:`rounds information <optional-rounds-attributes>` attributes"
    return 'rounds' in handler.setting_kwds and getattr(handler, "min_rounds", None) is not None

def has_salt_info(handler):
    "check if handler provides the optional :ref:`salt information <optional-salt-attributes>` attributes"
    return 'salt' in handler.setting_kwds and getattr(handler, "min_salt_size", None) is not None

#==========================================================
#bytes <-> unicode conversion helpers
#==========================================================

def to_bytes(source, encoding="utf-8", source_encoding=None, errname="value"):
    """helper to encoding unicode -> bytes
    
    this function takes in a ``source`` string.
    if unicode, encodes it using the specified ``encoding``.    
    if bytes, returns unchanged - unless ``source_encoding``
    is specified, in which case the bytes are transcoded
    if and only if the source encoding doesn't match
    the desired encoding.
    all other types result in a :exc:`TypeError`.
    
    :arg source: source bytes/unicode to process
    :arg encoding: target character encoding or ``None``.
    :param source_encoding: optional source encoding
    :param errname: optional name of variable/noun to reference when raising errors

    :raises TypeError: if unicode encountered but ``encoding=None`` specified;
                       or if source is not unicode or bytes.
    
    :returns: bytes object
    
    .. note::
    
        if ``encoding`` is set to ``None``, then unicode strings
        will be rejected, and only byte strings will be allowed through.
    """
    if isinstance(source, bytes):
        if source_encoding and encoding and \
                not is_same_codec(source_encoding, encoding):
            return source.decode(source_encoding).encode(encoding)
        else:
            return source
    elif not encoding:
        raise TypeError("%s must be bytes, not %s" % (errname, type(source)))    
    elif isinstance(source, unicode):
        return source.encode(encoding)
    elif source_encoding:
        raise TypeError("%s must be unicode or %s-encoded bytes, not %s" %
                        (errname, source_encoding, type(source)))
    else:
        raise TypeError("%s must be unicode or bytes, not %s" % (errname, type(source)))
    
def to_unicode(source, source_encoding="utf-8", errname="value"):
    """take in unicode or bytes, return unicode
    
    if bytes provided, decodes using specified encoding.
    leaves unicode alone.
    
    :raises TypeError: if source is not unicode or bytes.
    
    :arg source: source bytes/unicode to process
    :arg source_encoding: encoding to use when decoding bytes instances
    :param errname: optional name of variable/noun to reference when raising errors

    :returns: unicode object
    """
    if isinstance(source, unicode):
        return source
    elif not source_encoding:
        raise TypeError("%s must be unicode, not %s" % (errname, type(source)))
    elif isinstance(source, bytes):
        return source.decode(source_encoding)
    else:
        raise TypeError("%s must be unicode or %s-encoded bytes, not %s" %
                        (errname, source_encoding, type(source)))

#--------------------------------------------------
#support utils
#--------------------------------------------------
def is_same_codec(left, right):
    "check if two codecs names are aliases for same codec"
    if left == right:
        return True
    if not (left and right):
        return False
    return _lookup_codec(left).name == _lookup_codec(right).name

#=================================================================================
#string helpers
#=================================================================================
def splitcomma(source, sep=","):
    "split comma-separated string into list of elements, stripping whitespace and discarding empty elements"
    return [
        elem.strip()
        for elem in source.split(sep)
        if elem.strip()
    ]

#=================================================================================
#numeric helpers
#=================================================================================

##def int_to_bytes(value, count=None, order="big"):
##    """encode a integer into a string of bytes
##
##    :arg value: the integer
##    :arg count: optional number of bytes to expose, uses minimum needed if count not specified
##    :param order: the byte ordering; "big" (the default), "little", or "native"
##
##    :raises ValueError:
##        * if count specified and integer too large to fit.
##        * if integer is negative
##
##    :returns:
##        bytes encoding integer
##    """
##
##
##def bytes_to_int(value, order="big"):
##    """decode a byte string into an integer representation of it's binary value.
##
##    :arg value: the string to decode.
##    :param order: the byte ordering; "big" (the default), "little", or "native"
##
##    :returns: the decoded positive integer.
##    """
##    if not value:
##        return 0
##    if order == "native":
##        order = sys.byteorder
##    if order == "little":
##        value = reversed(value)
##    out = 0
##    for v in value:
##        out = (out<<8) | ord(v)
##    return out

def bytes_to_int(value):
    "decode string of bytes as single big-endian integer"
    out = 0
    for v in value:
        out = (out<<8) | ord(v)
    return out

def int_to_bytes(value, count):
    "encodes integer into single big-endian byte string"
    assert value < (1<<(8*count)), "value too large for %d bytes: %d" % (count, value)
    return ''.join(
        chr((value>>s) & 0xff)
        for s in xrange(8*count-8,-8,-8)
    )

_join = "".join
def xor_bytes(left, right):
    "perform bitwise-xor of two byte-strings"
    return _join(chr(ord(l) ^ ord(r)) for l, r in zip(left, right))

#=================================================================================
#alt base64 encoding
#=================================================================================

def adapted_b64_encode(data):
    """encode using variant of base64

    the output of this function is identical to b64_encode,
    except that it uses ``.`` instead of ``+``,
    and omits trailing padding ``=`` and whitepsace.

    it is primarily used for by passlib's custom pbkdf2 hashes.
    """
    return b64encode(data, "./").strip("=\n")

def adapted_b64_decode(data, sixthree="."):
    """decode using variant of base64

    the input of this function is identical to b64_decode,
    except that it uses ``.`` instead of ``+``,
    and should not include trailing padding ``=`` or whitespace.

    it is primarily used for by passlib's custom pbkdf2 hashes.
    """
    off = len(data) % 4
    if off == 0:
        return b64decode(data, "./")
    elif off == 1:
        raise ValueError("invalid bas64 input")
    elif off == 2:
        return b64decode(data + "==", "./")
    else:
        return b64decode(data + "=", "./")

#=================================================================================
#randomness
#=================================================================================

#-----------------------------------------------------------------------
# setup rng for generating salts
#-----------------------------------------------------------------------

#NOTE:
# generating salts (eg h64_gensalt, below) doesn't require cryptographically
# strong randomness. it just requires enough range of possible outputs
# that making a rainbow table is too costly.
# so python's builtin merseen twister prng is used, but seeded each time
# this module is imported, using a couple of minor entropy sources.

try:
    os.urandom(1)
    has_urandom = True
except NotImplementedError: #pragma: no cover
    has_urandom = False

def genseed(value=None):
    "generate prng seed value from system resources"
    #if value is rng, extract a bunch of bits from it's state
    if hasattr(value, "getrandbits"):
        value = value.getrandbits(256)
    text = "%s %s %s %.15f %s" % (
        value,
            #if user specified a seed value (eg current rng state), mix it in

        os.getpid(),
            #add current process id

        id(object()),
            #id of a freshly created object.
            #(at least 2 bytes of which should be hard to predict)

        time.time(),
            #the current time, to whatever precision os uses

        os.urandom(16) if has_urandom else 0,
            #if urandom available, might as well mix some bytes in.
        )
    #hash it all up and return it as int
    return long(sha256(text).hexdigest(), 16)

if has_urandom:
    rng = random.SystemRandom()
else: #pragma: no cover
    #NOTE: to reseed - rng.seed(genseed(rng))
    rng = random.Random(genseed())

#-----------------------------------------------------------------------
# some rng helpers
#-----------------------------------------------------------------------

def getrandbytes(rng, count):
    """return byte-string containing *count* number of randomly generated bytes, using specified rng"""
    #NOTE: would be nice if this was present in stdlib Random class

    ###just in case rng provides this...
    ##meth = getattr(rng, "getrandbytes", None)
    ##if meth:
    ##    return meth(count)

    #XXX: break into chunks for large number of bits?
    if not count:
        return ''
    value = rng.getrandbits(count<<3)
    buf = StringIO()
    for i in xrange(count):
        buf.write(chr(value & 0xff))
        value //= 0xff
    return buf.getvalue()

def getrandstr(rng, charset, count):
    """return character string containg *count* number of chars, whose elements are drawn from specified charset, using specified rng"""
    #check alphabet & count
    if count < 0:
        raise ValueError("count must be >= 0")
    letters = len(charset)
    if letters == 0:
        raise ValueError("alphabet must not be empty")
    if letters == 1:
        return charset * count

    #get random value, and write out to buffer
    #XXX: break into chunks for large number of letters?
    value = rng.randrange(0, letters**count)
    buf = StringIO()
    for i in xrange(count):
        buf.write(charset[value % letters])
        value //= letters
    assert value == 0
    return buf.getvalue()

def generate_password(size=10, charset=u'2346789ABCDEFGHJKMNPQRTUVWXYZabcdefghjkmnpqrstuvwxyz'):
    """generate random password using given length & chars

    :param size:
        size of password.

    :param charset:
        optional string specified set of characters to draw from.

        the default charset contains all normal alphanumeric characters,
        except for the characters ``1IiLl0OoS5``, which were omitted
        due to their visual similarity.

    :returns: randomly generated password.
    """
    return getrandstr(rng, charset, size)

#=================================================================================
#eof
#=================================================================================
