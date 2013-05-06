"""passlib.handlers.django- Django password hash support"""
#=============================================================================
# imports
#=============================================================================
# core
from base64 import b64encode
from hashlib import md5, sha1
import logging; log = logging.getLogger(__name__)
# site
# pkg
from passlib.utils import classproperty
from passlib.utils.compat import str_to_uascii, unicode, u
from passlib.utils.pbkdf2 import pbkdf2
import passlib.utils.handlers as uh
# local
__all__ = [
    "django_salted_sha1",
    "django_salted_md5",
    "django_bcrypt",
    "django_pbkdf2_sha1",
    "django_pbkdf2_sha256",
    "django_des_crypt",
    "django_disabled",
]

#=============================================================================
# lazy imports & constants
#=============================================================================
des_crypt = None

def _import_des_crypt():
    global des_crypt
    if des_crypt is None:
        from passlib.hash import des_crypt
    return des_crypt

# django 1.4's salt charset
SALT_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

#=============================================================================
# salted hashes
#=============================================================================
class DjangoSaltedHash(uh.HasSalt, uh.GenericHandler):
    """base class providing common code for django hashes"""
    # name, ident, checksum_size must be set by subclass.
    # ident must include "$" suffix.
    setting_kwds = ("salt", "salt_size")

    min_salt_size = 0
        # NOTE: django 1.0-1.3 would accept empty salt strings.
        #       django 1.4 won't, but this appears to be regression
        #       (https://code.djangoproject.com/ticket/18144)
        #       so presumably it will be fixed in a later release.
    default_salt_size = 12
    max_salt_size = None
    salt_chars = SALT_CHARS

    checksum_chars = uh.LOWER_HEX_CHARS

    @classproperty
    def _stub_checksum(cls):
        return cls.checksum_chars[0] * cls.checksum_size

    @classmethod
    def from_string(cls, hash):
        salt, chk = uh.parse_mc2(hash, cls.ident, handler=cls)
        return cls(salt=salt, checksum=chk)

    def to_string(self):
        return uh.render_mc2(self.ident, self.salt,
                             self.checksum or self._stub_checksum)

class DjangoVariableHash(uh.HasRounds, DjangoSaltedHash):
    """base class providing common code for django hashes w/ variable rounds"""
    setting_kwds = DjangoSaltedHash.setting_kwds + ("rounds",)

    min_rounds = 1

    @classmethod
    def from_string(cls, hash):
        rounds, salt, chk = uh.parse_mc3(hash, cls.ident, handler=cls)
        return cls(rounds=rounds, salt=salt, checksum=chk)

    def to_string(self):
        return uh.render_mc3(self.ident, self.rounds, self.salt,
                             self.checksum or self._stub_checksum)

class django_salted_sha1(DjangoSaltedHash):
    """This class implements Django's Salted SHA1 hash, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and uses a single round of SHA1.

    The :meth:`~passlib.ifc.PasswordHash.encrypt` and :meth:`~passlib.ifc.PasswordHash.genconfig` methods accept the following optional keywords:

    :type salt: str
    :param salt:
        Optional salt string.
        If not specified, a 12 character one will be autogenerated (this is recommended).
        If specified, may be any series of characters drawn from the regexp range ``[0-9a-zA-Z]``.

    :type salt_size: int
    :param salt_size:
        Optional number of characters to use when autogenerating new salts.
        Defaults to 12, but can be any positive value.

    This should be compatible with Django 1.4's :class:`!SHA1PasswordHasher` class.

    .. versionchanged: 1.6
        This class now generates 12-character salts instead of 5,
        and generated salts uses the character range ``[0-9a-zA-Z]`` instead of
        the ``[0-9a-f]``. This is to be compatible with how Django >= 1.4
        generates these hashes; but hashes generated in this manner will still be
        correctly interpreted by earlier versions of Django.
    """
    name = "django_salted_sha1"
    django_name = "sha1"
    ident = u("sha1$")
    checksum_size = 40

    def _calc_checksum(self, secret):
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        return str_to_uascii(sha1(self.salt.encode("ascii") + secret).hexdigest())

class django_salted_md5(DjangoSaltedHash):
    """This class implements Django's Salted MD5 hash, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and uses a single round of MD5.

    The :meth:`~passlib.ifc.PasswordHash.encrypt` and :meth:`~passlib.ifc.PasswordHash.genconfig` methods accept the following optional keywords:

    :type salt: str
    :param salt:
        Optional salt string.
        If not specified, a 12 character one will be autogenerated (this is recommended).
        If specified, may be any series of characters drawn from the regexp range ``[0-9a-zA-Z]``.

    :type salt_size: int
    :param salt_size:
        Optional number of characters to use when autogenerating new salts.
        Defaults to 12, but can be any positive value.

    This should be compatible with the hashes generated by
    Django 1.4's :class:`!MD5PasswordHasher` class.

    .. versionchanged: 1.6
        This class now generates 12-character salts instead of 5,
        and generated salts uses the character range ``[0-9a-zA-Z]`` instead of
        the ``[0-9a-f]``. This is to be compatible with how Django >= 1.4
        generates these hashes; but hashes generated in this manner will still be
        correctly interpreted by earlier versions of Django.
    """
    name = "django_salted_md5"
    django_name = "md5"
    ident = u("md5$")
    checksum_size = 32

    def _calc_checksum(self, secret):
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        return str_to_uascii(md5(self.salt.encode("ascii") + secret).hexdigest())

django_bcrypt = uh.PrefixWrapper("django_bcrypt", "bcrypt",
    prefix=u('bcrypt$'), ident=u("bcrypt$"),
    # NOTE: this docstring is duplicated in the docs, since sphinx
    # seems to be having trouble reading it via autodata::
    doc="""This class implements Django 1.4's BCrypt wrapper, and follows the :ref:`password-hash-api`.

    This is identical to :class:`!bcrypt` itself, but with
    the Django-specific prefix ``"bcrypt$"`` prepended.

    See :doc:`/lib/passlib.hash.bcrypt` for more details,
    the usage and behavior is identical.

    This should be compatible with the hashes generated by
    Django 1.4's :class:`!BCryptPasswordHasher` class.

    .. versionadded:: 1.6
    """)
django_bcrypt.django_name = "bcrypt"

class django_pbkdf2_sha256(DjangoVariableHash):
    """This class implements Django's PBKDF2-HMAC-SHA256 hash, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and a variable number of rounds.

    The :meth:`~passlib.ifc.PasswordHash.encrypt` and :meth:`~passlib.ifc.PasswordHash.genconfig` methods accept the following optional keywords:

    :type salt: str
    :param salt:
        Optional salt string.
        If not specified, a 12 character one will be autogenerated (this is recommended).
        If specified, may be any series of characters drawn from the regexp range ``[0-9a-zA-Z]``.

    :type salt_size: int
    :param salt_size:
        Optional number of characters to use when autogenerating new salts.
        Defaults to 12, but can be any positive value.

    :type rounds: int
    :param rounds:
        Optional number of rounds to use.
        Defaults to 10000, but must be within ``range(1,1<<32)``.

    :type relaxed: bool
    :param relaxed:
        By default, providing an invalid value for one of the other
        keywords will result in a :exc:`ValueError`. If ``relaxed=True``,
        and the error can be corrected, a :exc:`~passlib.exc.PasslibHashWarning`
        will be issued instead. Correctable errors include ``rounds``
        that are too small or too large, and ``salt`` strings that are too long.

    This should be compatible with the hashes generated by
    Django 1.4's :class:`!PBKDF2PasswordHasher` class.

    .. versionadded:: 1.6
    """
    name = "django_pbkdf2_sha256"
    django_name = "pbkdf2_sha256"
    ident = u('pbkdf2_sha256$')
    min_salt_size = 1
    max_rounds = 0xffffffff # setting at 32-bit limit for now
    checksum_chars = uh.PADDED_BASE64_CHARS
    checksum_size = 44 # 32 bytes -> base64
    default_rounds = 10000 # NOTE: using django default here
    _prf = "hmac-sha256"

    def _calc_checksum(self, secret):
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        hash = pbkdf2(secret, self.salt.encode("ascii"), self.rounds,
                      keylen=None, prf=self._prf)
        return b64encode(hash).rstrip().decode("ascii")

class django_pbkdf2_sha1(django_pbkdf2_sha256):
    """This class implements Django's PBKDF2-HMAC-SHA1 hash, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and a variable number of rounds.

    The :meth:`~passlib.ifc.PasswordHash.encrypt` and :meth:`~passlib.ifc.PasswordHash.genconfig` methods accept the following optional keywords:

    :type salt: str
    :param salt:
        Optional salt string.
        If not specified, a 12 character one will be autogenerated (this is recommended).
        If specified, may be any series of characters drawn from the regexp range ``[0-9a-zA-Z]``.

    :type salt_size: int
    :param salt_size:
        Optional number of characters to use when autogenerating new salts.
        Defaults to 12, but can be any positive value.

    :type rounds: int
    :param rounds:
        Optional number of rounds to use.
        Defaults to 10000, but must be within ``range(1,1<<32)``.

    :type relaxed: bool
    :param relaxed:
        By default, providing an invalid value for one of the other
        keywords will result in a :exc:`ValueError`. If ``relaxed=True``,
        and the error can be corrected, a :exc:`~passlib.exc.PasslibHashWarning`
        will be issued instead. Correctable errors include ``rounds``
        that are too small or too large, and ``salt`` strings that are too long.

    This should be compatible with the hashes generated by
    Django 1.4's :class:`!PBKDF2SHA1PasswordHasher` class.

    .. versionadded:: 1.6
    """
    name = "django_pbkdf2_sha1"
    django_name = "pbkdf2_sha1"
    ident = u('pbkdf2_sha1$')
    checksum_size = 28 # 20 bytes -> base64
    _prf = "hmac-sha1"

#=============================================================================
# other
#=============================================================================
class django_des_crypt(uh.HasSalt, uh.GenericHandler):
    """This class implements Django's :class:`des_crypt` wrapper, and follows the :ref:`password-hash-api`.

    It supports a fixed-length salt.

    The :meth:`~passlib.ifc.PasswordHash.encrypt` and :meth:`~passlib.ifc.PasswordHash.genconfig` methods accept the following optional keywords:

    :type salt: str
    :param salt:
        Optional salt string.
        If not specified, one will be autogenerated (this is recommended).
        If specified, it must be 2 characters, drawn from the regexp range ``[./0-9A-Za-z]``.

    This should be compatible with the hashes generated by
    Django 1.4's :class:`!CryptPasswordHasher` class.
    Note that Django only supports this hash on Unix systems
    (though :class:`!django_des_crypt` is available cross-platform
    under Passlib).

    .. versionchanged:: 1.6
        This class will now accept hashes with empty salt strings,
        since Django 1.4 generates them this way.
    """
    name = "django_des_crypt"
    django_name = "crypt"
    setting_kwds = ("salt", "salt_size")
    ident = u("crypt$")
    checksum_chars = salt_chars = uh.HASH64_CHARS
    checksum_size = 11
    min_salt_size = default_salt_size = 2
    _stub_checksum = u('.')*11

    @classmethod
    def from_string(cls, hash):
        salt, chk = uh.parse_mc2(hash, cls.ident, handler=cls)
        if chk:
            # chk should be full des_crypt hash
            if not salt:
                # django 1.4 always uses empty salt field,
                # so extract salt from des_crypt hash <chk>
                salt = chk[:2]
            elif salt[:2] != chk[:2]:
                # django 1.0 stored 5 chars in salt field, and duplicated
                # the first two chars in <chk>. we keep the full salt,
                # but make sure the first two chars match as sanity check.
                raise uh.exc.MalformedHashError(cls,
                    "first two digits of salt and checksum must match")
            # in all cases, strip salt chars from <chk>
            chk = chk[2:]
        return cls(salt=salt, checksum=chk)

    def to_string(self):
        # NOTE: always filling in salt field, so that we're compatible
        # with django 1.0 (which requires it)
        salt = self.salt
        chk = salt[:2] + (self.checksum or self._stub_checksum)
        return uh.render_mc2(self.ident, salt, chk)

    def _calc_checksum(self, secret):
        # NOTE: we lazily import des_crypt,
        #       since most django deploys won't use django_des_crypt
        global des_crypt
        if des_crypt is None:
            _import_des_crypt()
        return des_crypt(salt=self.salt[:2])._calc_checksum(secret)

class django_disabled(uh.StaticHandler):
    """This class provides disabled password behavior for Django, and follows the :ref:`password-hash-api`.

    This class does not implement a hash, but instead
    claims the special hash string ``"!"`` which Django uses
    to indicate an account's password has been disabled.

    * newly encrypted passwords will hash to ``!``.
    * it rejects all passwords.
    """
    name = "django_disabled"

    @classmethod
    def identify(cls, hash):
        hash = uh.to_unicode_for_identify(hash)
        return hash == u("!")

    def _calc_checksum(self, secret):
        return u("!")

    @classmethod
    def verify(cls, secret, hash):
        uh.validate_secret(secret)
        if not cls.identify(hash):
            raise uh.exc.InvalidHashError(cls)
        return False

#=============================================================================
# eof
#=============================================================================
