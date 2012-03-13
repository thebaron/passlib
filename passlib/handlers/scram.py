"""passlib.handlers.scram - hash for SCRAM credential storage"""
#=========================================================
#imports
#=========================================================
#core
from binascii import hexlify, unhexlify
from base64 import b64encode, b64decode
import hashlib
import re
import logging; log = logging.getLogger(__name__)
from warnings import warn
#site
#libs
from passlib.exc import PasslibHashWarning
from passlib.utils import ab64_decode, ab64_encode, consteq, saslprep, \
                          to_native_str, xor_bytes
from passlib.utils.compat import b, bytes, bascii_to_str, iteritems, \
                                 itervalues, PY3, u, unicode
from passlib.utils.pbkdf2 import pbkdf2, get_prf, norm_hash_name
import passlib.utils.handlers as uh
#pkg
#local
__all__ = [
    "scram",
]

#=========================================================
# scram credentials hash
#=========================================================
class scram(uh.HasRounds, uh.HasRawSalt, uh.HasRawChecksum, uh.GenericHandler):
    """This class provides a format for storing SCRAM passwords, and follows
    the :ref:`password-hash-api`.

    It supports a variable-length salt, and a variable number of rounds.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keywords:

    :param salt:
        Optional salt bytes.
        If specified, the length must be between 0-1024 bytes.
        If not specified, a 12 byte salt will be autogenerated
        (this is recommended).

    :param salt_size:
        Optional number of bytes to use when autogenerating new salts.
        Defaults to 12 bytes, but can be any value between 0 and 1024.

    :param rounds:
        Optional number of rounds to use.
        Defaults to 6400, but must be within ``range(1,1<<32)``.

    :param algs:
        Specify list of digest algorithms to use.

        By default each scram hash will contain digests for SHA-1,
        SHA-256, and SHA-512. This can be overridden by specify either be a
        list such as ``["sha-1", "sha-256"]``, or a comma-separated string
        such as ``"sha-1, sha-256"``. Names are case insensitive, and may
        use :mod:`!hashlib` or `IANA <http://www.iana.org/assignments/hash-function-text-names>`_
        hash names.

    In addition to the standard :ref:`password-hash-api` methods,
    this class also provides the following methods for manipulating Passlib
    scram hashes in ways useful for pluging into a SCRAM protocol stack:

    .. automethod:: extract_digest_info
    .. automethod:: extract_digest_algs
    .. automethod:: derive_digest
    """
    #=========================================================
    #class attrs
    #=========================================================

    # NOTE: unlike most GenericHandler classes, the 'checksum' attr of
    # ScramHandler is actually a map from digest_name -> digest, so
    # many of the standard methods have been overridden.

    # NOTE: max_salt_size and max_rounds are arbitrarily chosen to provide
    # a sanity check; the underlying pbkdf2 specifies no bounds for either.

    #--GenericHandler--
    name = "scram"
    summary = "PBKDF2-based hash used to store credentials for the SCRAM protocol"
    setting_kwds = ("salt", "salt_size", "rounds", "algs")
    ident = u("$scram$")

    #--HasSalt--
    default_salt_size = 12
    min_salt_size = 0
    max_salt_size = 1024

    #--HasRounds--
    default_rounds = 6400
    min_rounds = 1
    max_rounds = 2**32-1
    rounds_cost = "linear"

    #--custom--

    # default algorithms when creating new hashes.
    default_algs = ["sha-1", "sha-256", "sha-512"]

    # list of algs verify prefers to use, in order.
    _verify_algs = ["sha-256", "sha-512", "sha-224", "sha-384", "sha-1"]

    #=========================================================
    # instance attrs
    #=========================================================

    # 'checksum' is different from most GenericHandler subclasses,
    # in that it contains a dict mapping from alg -> digest,
    # or None if no checksum present.

    #: list of algorithms to create/compare digests for.
    algs = None

    #=========================================================
    # scram frontend helpers
    #=========================================================
    @classmethod
    def extract_digest_info(cls, hash, alg):
        """return (salt, rounds, digest) for specific hash algorithm.

        :arg hash:
            :class:`!scram` hash stored for desired user

        :arg alg:
            Name of digest algorithm (e.g. ``"sha-1"``) requested by client.

            This value is run through :func:`~passlib.utils.pbkdf2.norm_hash_name`,
            so it is case-insensitive, and can be the raw SCRAM
            mechanism name (e.g. ``"SCRAM-SHA-1"``), the IANA name,
            or the hashlib name.

        :raises KeyError:
            If the hash does not contain an entry for the requested digest
            algorithm.

        :returns:
            A tuple containing ``(salt, rounds, digest)``,
            where *digest* matches the raw bytes returned by
            SCRAM's :func:`Hi` function for the stored password,
            the provided *salt*, and the iteration count (*rounds*).
            *salt* and *digest* are both raw (unencoded) bytes.
        """
        # XXX: this could be sped up by writing custom parsing routine
        # that just picks out relevant digest, and doesn't bother
        # with full structure validation each time it's called.
        alg = norm_hash_name(alg, 'iana')
        self = cls.from_string(hash)
        chkmap = self.checksum
        if not chkmap:
            raise ValueError("scram hash contains no digests")
        return self.salt, self.rounds, chkmap[alg]

    @classmethod
    def extract_digest_algs(cls, hash, format="iana"):
        """Return names of all algorithms stored in a given hash.

        :arg hash:
            The :class:`!scram` hash to parse

        :param format:
            This changes the naming convention used by the
            returned algorithm names. By default the names
            are IANA-compatible; see :func:`~passlib.utils.pbkdf2.norm_hash_name`
            for possible values.

        :returns:
            Returns a list of digest algorithms; e.g. ``["sha-1"]``
        """
        # XXX: this could be sped up by writing custom parsing routine
        # that just picks out relevant names, and doesn't bother
        # with full structure validation each time it's called.
        algs = cls.from_string(hash).algs
        if format == "iana":
            return algs
        else:
            return [norm_hash_name(alg, format) for alg in algs]

    @classmethod
    def derive_digest(cls, password, salt, rounds, alg):
        """helper to create SaltedPassword digest for SCRAM.

        This performs the step in the SCRAM protocol described as::

            SaltedPassword  := Hi(Normalize(password), salt, i)

        :arg password: password as unicode or utf-8 encoded bytes.
        :arg salt: raw salt as bytes.
        :arg rounds: number of iterations.
        :arg alg: name of digest to use (e.g. ``"sha-1"``).

        :returns:
            raw bytes of ``SaltedPassword``
        """
        if isinstance(password, bytes):
            password = password.decode("utf-8")
        password = saslprep(password).encode("utf-8")
        if not isinstance(salt, bytes):
            raise TypeError("salt must be bytes")
        if rounds < 1:
            raise ValueError("rounds must be >= 1")
        alg = norm_hash_name(alg, "hashlib")
        return pbkdf2(password, salt, rounds, -1, "hmac-" + alg)

    #=========================================================
    # serialization
    #=========================================================

    @classmethod
    def from_string(cls, hash):
        # parse hash
        if not hash:
            raise ValueError("no hash specified")
        hash = to_native_str(hash, "ascii", errname="hash")
        if not hash.startswith("$scram$"):
            raise ValueError("invalid scram hash")
        parts = hash[7:].split("$")
        if len(parts) != 3:
            raise ValueError("invalid scram hash")
        rounds_str, salt_str, chk_str = parts

        # decode rounds
        rounds = int(rounds_str)
        if rounds_str != str(rounds): #forbid zero padding, etc.
            raise ValueError("invalid scram hash")

        # decode salt
        try:
            salt = ab64_decode(salt_str.encode("ascii"))
        except TypeError:
            raise ValueError("malformed scram hash")

        # decode algs/digest list
        if not chk_str:
            # scram hashes MUST have something here.
            raise ValueError("invalid scram hash")
        elif "=" in chk_str:
            # comma-separated list of 'alg=digest' pairs
            algs = None
            chkmap = {}
            for pair in chk_str.split(","):
                alg, digest = pair.split("=")
                try:
                    chkmap[alg] = ab64_decode(digest.encode("ascii"))
                except TypeError:
                    raise ValueError("malformed scram hash")
        else:
            # comma-separated list of alg names, no digests
            algs = chk_str
            chkmap = None

        # return new object
        return cls(
            rounds=rounds,
            salt=salt,
            checksum=chkmap,
            algs=algs,
        )

    def to_string(self, withchk=True):
        salt = bascii_to_str(ab64_encode(self.salt))
        chkmap = self.checksum
        if withchk and chkmap:
            chk_str = ",".join(
                "%s=%s" % (alg, bascii_to_str(ab64_encode(chkmap[alg])))
                for alg in self.algs
            )
        else:
            chk_str = ",".join(self.algs)
        return '$scram$%d$%s$%s' % (self.rounds, salt, chk_str)

    #=========================================================
    # init
    #=========================================================
    def __init__(self, algs=None, **kwds):
        super(scram, self).__init__(**kwds)
        self.algs = self._norm_algs(algs)

    def _norm_checksum(self, checksum):
        if checksum is None:
            return None
        for alg, digest in iteritems(checksum):
            if alg != norm_hash_name(alg, 'iana'):
                raise ValueError("malformed algorithm name in scram hash: %r" %
                                 (alg,))
            if len(alg) > 9:
                raise ValueError("SCRAM limits algorithm names to "
                                 "9 characters: %r" % (alg,))
            if not isinstance(digest, bytes):
                raise TypeError("digests must be raw bytes")
            # TODO: verify digest size (if digest is known)
        if 'sha-1' not in checksum:
            # NOTE: required because of SCRAM spec.
            raise ValueError("sha-1 must be in algorithm list of scram hash")
        return checksum

    def _norm_algs(self, algs):
        "normalize algs parameter"
        # determine default algs value
        if algs is None:
            # derive algs list from checksum (if present).
            chk = self.checksum
            if chk is not None:
                return sorted(chk)
            elif self.use_defaults:
                return list(self.default_algs)
            else:
                raise TypeError("no algs list specified")
        elif self.checksum is not None:
            raise RuntimeError("checksum & algs kwds are mutually exclusive")

        # parse args value
        if isinstance(algs, str):
            algs = algs.split(",")
        algs = sorted(norm_hash_name(alg, 'iana') for alg in algs)
        if any(len(alg)>9 for alg in algs):
            raise ValueError("SCRAM limits alg names to max of 9 characters")
        if 'sha-1' not in algs:
            # NOTE: required because of SCRAM spec (rfc 5802)
            raise ValueError("sha-1 must be in algorithm list of scram hash")
        return algs

    #=========================================================
    # digest methods
    #=========================================================

    @classmethod
    def _deprecation_detector(cls, **settings):
        "generate a deprecation detector for CryptContext to use"
        # generate deprecation hook which marks hashes as deprecated
        # if they don't support a superset of current algs.
        algs = frozenset(cls(use_defaults=True, **settings).algs)
        def detector(hash):
            return not algs.issubset(cls.from_string(hash).algs)
        return detector

    def _calc_checksum(self, secret, alg=None):
        rounds = self.rounds
        salt = self.salt
        hash = self.derive_digest
        if alg:
            # if requested, generate digest for specific alg
            return hash(secret, salt, rounds, alg)
        else:
            # by default, return dict containing digests for all algs
            return dict(
                (alg, hash(secret, salt, rounds, alg))
                for alg in self.algs
            )

    @classmethod
    def verify(cls, secret, hash, full=False):
        self = cls.from_string(hash)
        chkmap = self.checksum
        if not chkmap:
            raise ValueError("expected %s hash, got %s config string instead" %
                             (cls.name, cls.name))

        # NOTE: to make the verify method efficient, we just calculate hash
        # of shortest digest by default. apps can pass in "full=True" to
        # check entire hash for consistency.
        if full:
            correct = failed = False
            for alg, digest in iteritems(chkmap):
                other = self._calc_checksum(secret, alg)
                # NOTE: could do this length check in norm_algs(),
                # but don't need to be that strict, and want to be able
                # to parse hashes containing algs not supported by platform.
                # it's fine if we fail here though.
                if len(digest) != len(other):
                    raise ValueError("mis-sized %s digest in scram hash: %r != %r"
                                     % (alg, len(digest), len(other)))
                if consteq(other, digest):
                    correct = True
                else:
                    failed = True
            if correct and failed:
                warning("scram hash verified inconsistently, may be corrupted",
                        PasslibHashWarning)
                return False
            else:
                return correct
        else:
            # otherwise only verify against one hash, pick one w/ best security.
            for alg in self._verify_algs:
                if alg in chkmap:
                    other = self._calc_checksum(secret, alg)
                    return consteq(other, chkmap[alg])
            # there should *always* be at least sha-1.
            raise AssertionError("sha-1 digest not found!")

    #=========================================================
    #
    #=========================================================

#=========================================================
# code used for testing scram against protocol examples during development.
#=========================================================
#def _test_reference_scram():
#    "quick hack testing scram reference vectors"
#    # NOTE: "n,," is GS2 header - see https://tools.ietf.org/html/rfc5801
#    from passlib.utils.compat import print_
#
#    engine = _scram_engine(
#        alg="sha-1",
#        salt='QSXCR+Q6sek8bf92'.decode("base64"),
#        rounds=4096,
#        password=u("pencil"),
#    )
#    print_(engine.digest.encode("base64").rstrip())
#
#    msg = engine.format_auth_msg(
#        username="user",
#        client_nonce = "fyko+d2lbbFgONRv9qkxdawL",
#        server_nonce = "3rfcNHYJY1ZVvWVs7j",
#        header='c=biws',
#    )
#
#    cp = engine.get_encoded_client_proof(msg)
#    assert cp == "v0X8v3Bz2T0CJGbJQyF0X+HI4Ts=", cp
#
#    ss = engine.get_encoded_server_sig(msg)
#    assert ss == "rmF9pqV8S7suAoZWja4dJRkFsKQ=", ss
#
#class _scram_engine(object):
#    """helper class for verifying scram hash behavior
#    against SCRAM protocol examples. not officially part of Passlib.
#
#    takes in alg, salt, rounds, and a digest or password.
#
#    can calculate the various keys & messages of the scram protocol.
#
#    """
#    #=========================================================
#    # init
#    #=========================================================
#
#    @classmethod
#    def from_string(cls, hash, alg):
#        "create record from scram hash, for given alg"
#        return cls(alg, *scram.extract_digest_info(hash, alg))
#
#    def __init__(self, alg, salt, rounds, digest=None, password=None):
#        self.alg = norm_hash_name(alg)
#        self.salt = salt
#        self.rounds = rounds
#        self.password = password
#        if password:
#            data = scram.derive_digest(password, salt, rounds, alg)
#            if digest and data != digest:
#                raise ValueError("password doesn't match digest")
#            else:
#                digest = data
#        elif not digest:
#            raise TypeError("must provide password or digest")
#        self.digest = digest
#
#    #=========================================================
#    # frontend methods
#    #=========================================================
#    def get_hash(self, data):
#        "return hash of raw data"
#        return hashlib.new(iana_to_hashlib(self.alg), data).digest()
#
#    def get_client_proof(self, msg):
#        "return client proof of specified auth msg text"
#        return xor_bytes(self.client_key, self.get_client_sig(msg))
#
#    def get_encoded_client_proof(self, msg):
#        return self.get_client_proof(msg).encode("base64").rstrip()
#
#    def get_client_sig(self, msg):
#        "return client signature of specified auth msg text"
#        return self.get_hmac(self.stored_key, msg)
#
#    def get_server_sig(self, msg):
#        "return server signature of specified auth msg text"
#        return self.get_hmac(self.server_key, msg)
#
#    def get_encoded_server_sig(self, msg):
#        return self.get_server_sig(msg).encode("base64").rstrip()
#
#    def format_server_response(self, client_nonce, server_nonce):
#        return 'r={client_nonce}{server_nonce},s={salt},i={rounds}'.format(
#            client_nonce=client_nonce,
#            server_nonce=server_nonce,
#            rounds=self.rounds,
#            salt=self.encoded_salt,
#            )
#
#    def format_auth_msg(self, username, client_nonce, server_nonce,
#                        header='c=biws'):
#        return (
#            'n={username},r={client_nonce}'
#                ','
#            'r={client_nonce}{server_nonce},s={salt},i={rounds}'
#                ','
#            '{header},r={client_nonce}{server_nonce}'
#            ).format(
#                username=username,
#                client_nonce=client_nonce,
#                server_nonce=server_nonce,
#                salt=self.encoded_salt,
#                rounds=self.rounds,
#                header=header,
#                )
#
#    #=========================================================
#    # helpers to calculate & cache constant data
#    #=========================================================
#    def _calc_get_hmac(self):
#        return get_prf("hmac-" + iana_to_hashlib(self.alg))[0]
#
#    def _calc_client_key(self):
#        return self.get_hmac(self.digest, b("Client Key"))
#
#    def _calc_stored_key(self):
#        return self.get_hash(self.client_key)
#
#    def _calc_server_key(self):
#        return self.get_hmac(self.digest, b("Server Key"))
#
#    def _calc_encoded_salt(self):
#        return self.salt.encode("base64").rstrip()
#
#    #=========================================================
#    # hacks for calculated attributes
#    #=========================================================
#
#    def __getattr__(self, attr):
#        if not attr.startswith("_"):
#            f = getattr(self, "_calc_" + attr, None)
#            if f:
#                value = f()
#                setattr(self, attr, value)
#                return value
#        raise AttributeError("attribute not found")
#
#    def __dir__(self):
#        cdir = dir(self.__class__)
#        attrs = set(cdir)
#        attrs.update(self.__dict__)
#        attrs.update(attr[6:] for attr in cdir
#                     if attr.startswith("_calc_"))
#        return sorted(attrs)
#    #=========================================================
#    # eoc
#    #=========================================================

#=========================================================
#eof
#=========================================================
