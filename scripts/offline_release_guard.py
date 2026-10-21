"""Contain offline release checks and their Python children in disposable storage."""
import os
import importlib.util
from pathlib import Path
import shlex
import sys
import tempfile
import uuid
from urllib.parse import unquote, urlparse
from scripts.offline_loopback import loopback_socket_allowed
from scripts.offline_socketpair import stdlib_socketpair_allowed


def install():
    scratch = Path(os.environ['JOB_MATCH_TEST_SCRATCH']).resolve()
    root = Path(os.environ['JOB_MATCH_TEST_ROOT']).resolve()
    guard_dir = os.environ['JOB_MATCH_TEST_GUARD_DIR']
    docx_spec = importlib.util.find_spec('docx')
    template = (Path(docx_spec.origin).resolve().parent/'templates/default.docx') if docx_spec and docx_spec.origin else None
    if template is not None and not template.is_relative_to(Path(sys.prefix).resolve()):
        template = None
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(scratch)

    def guard(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            if os.fsdecode(args[0]).upper() in ('NUL', r'\\.\NUL'):
                return
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1] or '', args[2] if len(args) > 2 else 0
            writing = any(c in str(mode) for c in 'wax+') or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if path.name.casefold() in ('.env', 'secrets.toml'):
                raise RuntimeError('Offline checks prohibit secret-file access')
            if writing and not path.is_relative_to(scratch):
                raise RuntimeError('Offline checks prohibit writes outside disposable scratch: '+str(path))
            if (path.suffix.lower() in ('.db', '.sqlite', '.sqlite3', '.docx', '.pdf')
                    and path != template and not path.is_relative_to(scratch) and not path.is_relative_to(root/'tests/fixtures')):
                raise RuntimeError('Offline checks prohibit candidate/database artifact access: '+str(path))
        if event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.rename'):
            paths = args[:2] if event == 'os.rename' else args[:1]
            for value in paths:
                if isinstance(value, (str, bytes, os.PathLike)) and not Path(os.fsdecode(value)).resolve().is_relative_to(scratch):
                    raise RuntimeError('Offline checks prohibit filesystem mutation outside disposable scratch: '+str(value))
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind', 'socket.sendto', 'socket.sendmsg',
                     'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.getnameinfo'):
            if loopback_socket_allowed(event, args):
                return
            if stdlib_socketpair_allowed(event, args):
                return
            raise RuntimeError('Offline checks prohibit network access')
        if event == 'sqlite3.connect':
            name = str(args[0])
            if name == ':memory:':
                return
            if name.startswith('file:'):
                name = unquote(urlparse(name).path)
                if len(name) > 2 and name[0] == '/' and name[2] == ':':
                    name = name[1:]
            if not Path(name.split('?')[0]).resolve().is_relative_to(scratch):
                raise RuntimeError('Offline checks prohibit non-disposable SQLite access')
        if event == 'subprocess.Popen':
            executable, argv, _, env = args
            tokens = shlex.split(argv, posix=False) if isinstance(argv, str) else argv
            program = Path(executable or tokens[0].strip('"')).stem.lower()
            frame = sys._getframe(1)
            while frame:
                if (program == 'cmd' and frame.f_globals.get('__name__') == 'platform'
                        and frame.f_code.co_name == '_syscmd_ver'
                        and str(argv).lower().replace('"', '').strip().endswith(' ver')):
                    return  # standard-library read-only Windows version query
                frame = frame.f_back
            if program.startswith('python'):
                child = env or os.environ
                if guard_dir not in child.get('PYTHONPATH', '') or any(flag in tokens for flag in ('-I', '-S', '-E')):
                    raise RuntimeError('Offline Python children must inherit containment')
            elif program == 'git':
                if not any(t in tokens for t in ('show', 'status', 'rev-parse', 'ls-files', 'diff')):
                    raise RuntimeError('Offline checks prohibit Git mutations')
            else:
                raise RuntimeError('Offline checks prohibit uncontained subprocess: '+program)

    sys.addaudithook(guard)
    if os.name == 'nt':
        # Python 3.13's Windows 0700 temporary ACL is inaccessible in this
        # sandbox. Inherit the explicitly disposable parent's ACL instead.
        def inherited_mkdtemp(suffix=None, prefix=None, dir=None):
            for _ in range(100):
                path = Path(dir or tempfile.gettempdir())/((prefix or 'tmp')+uuid.uuid4().hex+(suffix or ''))
                try:
                    path.mkdir()
                except FileExistsError:
                    continue
                return str(path)
            raise FileExistsError('No disposable temporary name available')
        tempfile.mkdtemp = inherited_mkdtemp
    # Optional Chroma imports instantiate Settings with an explicit env_file;
    # PYTHON_DOTENV_DISABLED alone does not cover that path.
    try:
        from pydantic_settings import DotEnvSettingsSource
    except ImportError:
        pass
    else:
        DotEnvSettingsSource._read_env_files = lambda self: {}
