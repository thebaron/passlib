"""passlib.handlers.digests - plain hash digests
"""
#=========================================================
#imports
#=========================================================
#core
from base64 import b64encode, b64decode
from hashlib import md5, sha1
import logging; log = logging.getLogger(__name__)
import re
from warnings import warn
#site
#libs
from passlib.utils import handlers as uh, unix_crypt_schemes, b, bytes, to_hash_str
#pkg
#local
__all__ = [
    "ldap_plaintext",
    "ldap_md5",
    "ldap_sha1",
    "ldap_salted_md5",
    "ldap_salted_sha1",

    ##"get_active_ldap_crypt_schemes",
    "ldap_des_crypt",
    "ldap_bsdi_crypt",
    "ldap_md5_crypt",
    "ldap_sha1_crypt"
    "ldap_bcrypt",
    "ldap_sha256_crypt",
    "ldap_sha512_crypt",
]

#=========================================================
#ldap helpers
#=========================================================
#reference - http://www.openldap.org/doc/admin24/security.html

class _Base64DigestHelper(uh.StaticHandler):
    "helper for ldap_md5 / ldap_sha1"
    #XXX: could combine this with hex digests in digests.py

    ident = None #required - prefix identifier
    _hash_func = None #required - hash function
    _pat = None #required - regexp to recognize hash
    checksum_chars = uh.PADDED_B64_CHARS

    @classmethod
    def identify(cls, hash):
        return uh.identify_regexp(hash, cls._pat)

    @classmethod
    def genhash(cls, secret, hash):
        if secret is None:
            raise TypeError("no secret provided")
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        if hash is not None and not cls.identify(hash):
            raise ValueError("not a %s hash" % (cls.name,))
        chk = cls._hash_func(secret).digest()
        hash = cls.ident + b64encode(chk).decode("ascii")
        return to_hash_str(hash)

class _SaltedBase64DigestHelper(uh.HasRawSalt, uh.HasRawChecksum, uh.GenericHandler):
    "helper for ldap_salted_md5 / ldap_salted_sha1"
    setting_kwds = ("salt",)
    checksum_chars = uh.PADDED_B64_CHARS

    ident = None #required - prefix identifier
    _hash_func = None #required - hash function
    _pat = None #required - regexp to recognize hash
    _stub_checksum = None #required - default checksum to plug in
    min_salt_size = max_salt_size = 4

    @classmethod
    def identify(cls, hash):
        return uh.identify_regexp(hash, cls._pat)

    @classmethod
    def from_string(cls, hash):
        if not hash:
            raise ValueError("no hash specified")
        if isinstance(hash, bytes):
            hash = hash.decode('ascii')
        m = cls._pat.match(hash)
        if not m:
            raise ValueError("not a %s hash" % (cls.name,))
        data = b64decode(m.group("tmp").encode("ascii"))
        chk, salt = data[:-4], data[-4:]
        return cls(checksum=chk, salt=salt, strict=True)

    def to_string(self):
        data = (self.checksum or self._stub_checksum) + self.salt        
        hash = self.ident + b64encode(data).decode("ascii")
        return to_hash_str(hash)
        
    def calc_checksum(self, secret):
        if secret is None:
            raise TypeError("no secret provided")
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        return self._hash_func(secret + self.salt).digest()

#=========================================================
#implementations
#=========================================================
class ldap_md5(_Base64DigestHelper):
    """This class stores passwords using LDAP's plain MD5 format, and follows the :ref:`password-hash-api`.

    The :meth:`encrypt()` and :meth:`genconfig` methods have no optional keywords.
    """
    name = "ldap_md5"
    setting_kwds = ()

    ident = u"{MD5}"
    _hash_func = md5
    _pat = re.compile(ur"^\{MD5\}(?P<chk>[+/a-zA-Z0-9]{22}==)$")

class ldap_sha1(_Base64DigestHelper):
    """This class stores passwords using LDAP's plain SHA1 format, and follows the :ref:`password-hash-api`.

    The :meth:`encrypt()` and :meth:`genconfig` methods have no optional keywords.
    """
    name = "ldap_sha1"
    setting_kwds = ()

    ident = u"{SHA}"
    _hash_func = sha1
    _pat = re.compile(ur"^\{SHA\}(?P<chk>[+/a-zA-Z0-9]{27}=)$")

class ldap_salted_md5(_SaltedBase64DigestHelper):
    """This class stores passwords using LDAP's salted MD5 format, and follows the :ref:`password-hash-api`.

    It supports a 4-byte salt.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keyword:

    :param salt:
        Optional salt string.
        If not specified, one will be autogenerated (this is recommended).
        If specified, it must be a 4 byte string; each byte may have any value from 0x00 .. 0xff.
    """
    name = "ldap_salted_md5"
    ident = u"{SMD5}"
    _hash_func = md5
    _pat = re.compile(ur"^\{SMD5\}(?P<tmp>[+/a-zA-Z0-9]{27}=)$")
    _stub_checksum = b('\x00') * 16

class ldap_salted_sha1(_SaltedBase64DigestHelper):
    """This class stores passwords using LDAP's salted SHA1 format, and follows the :ref:`password-hash-api`.

    It supports a 4-byte salt.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keyword:

    :param salt:
        Optional salt string.
        If not specified, one will be autogenerated (this is recommended).
        If specified, it must be a 4 byte string; each byte may have any value from 0x00 .. 0xff.
    """
    name = "ldap_salted_sha1"
    ident = u"{SSHA}"
    _hash_func = sha1
    _pat = re.compile(ur"^\{SSHA\}(?P<tmp>[+/a-zA-Z0-9]{32})$")
    _stub_checksum = b('\x00') * 20

class ldap_plaintext(uh.StaticHandler):
    """This class stores passwords in plaintext, and follows the :ref:`password-hash-api`.

    This class acts much like the generic :class:`!passlib.hash.plaintext` handler,
    except that it will identify a hash only if it does NOT begin with the ``{XXX}`` identifier prefix
    used by RFC2307 passwords.

    Unicode passwords will be encoded using utf-8.
    """
    name = "ldap_plaintext"

    _2307_pat = re.compile(ur"^\{\w+\}.*$")

    @classmethod
    def identify(cls, hash):
        if not hash:
            return False
        if isinstance(hash, bytes):
            try:
                hash = hash.decode("utf-8")
            except UnicodeDecodeError:
                return False
        #NOTE: identifies all strings EXCEPT those which match...
        return cls._2307_pat.match(hash) is None

    @classmethod
    def genhash(cls, secret, hash):
        if hash is not None and not cls.identify(hash):
            raise ValueError("not a valid ldap_plaintext hash")
        if secret is None:
            raise TypeError("secret must be string")
        return to_hash_str(secret, "utf-8")

#=========================================================
#{CRYPT} wrappers
#=========================================================

# the following are wrappers around the base crypt algorithms,
# which add the ldap required {CRYPT} prefix

ldap_crypt_schemes = [ 'ldap_' + name for name in unix_crypt_schemes ]

def _init_ldap_crypt_handlers():
    #XXX: it's not nice to play in globals like this,
    # but don't want to write all all these handlers
    g = globals()
    for wname in unix_crypt_schemes:
        name = 'ldap_' + wname
        g[name] = uh.PrefixWrapper(name, wname, prefix=u"{CRYPT}", lazy=True)
    del g
_init_ldap_crypt_handlers()

##_lcn_host = None
##def get_host_ldap_crypt_schemes():
##    global _lcn_host
##    if _lcn_host is None:
##        from passlib.hosts import host_context
##        schemes = host_context.policy.schemes()
##        _lcn_host = [
##            "ldap_" + name
##            for name in unix_crypt_names
##            if name in schemes
##        ]
##    return _lcn_host

#=========================================================
#eof
#=========================================================
