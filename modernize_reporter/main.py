"""\
Python Modernize Reporter\
"""

from __future__ import print_function
from __future__ import absolute_import

import sys
import os
import logging
import optparse

try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3

try:
    from teamcity import is_running_under_teamcity
except ImportError:
    def is_running_under_teamcity(): return False  # noqa: E301, E704

try:
    from teamcity.messages import TeamcityServiceMessages
except ImportError:
    TeamcityServiceMessages = None

# testStarted,
# testFinished,
# testIgnored,
# testFailed,
# testStdOut,
# testStdErr,

from modernize_reporter import __version__
from libmodernize import __version__ as __version_modernize__
from libmodernize.main import main as modernize_main  # Depends on customizations

SCRIPT_NAME = 'python-modernize-reporter'
TC = TeamcityServiceMessages
LOG_CAPTURE_STRING = StringIO()
LOG_LEVEL = logging.DEBUG
VERBOSE = False
USE_TEAMCITY = False

usage = __doc__ + """\
 %s

Usage: %s [options] file|dir ...
""" % (SCRIPT_NAME, __version__)


def format_usage(usage):
    """Method that doesn't output "Usage:" prefix"""
    return usage


def walk_tree(args, root, excluded_files=None, excluded_dirs=None):
    print("walking  :", root)
    print()
    excluded_files = [] if excluded_files is None else excluded_files
    excluded_dirs = [] if excluded_dirs is None else excluded_dirs
    if os.path.isfile(root):
        check_modernizations(args, root)
    else:
        for path, dirs, files in os.walk(root):
            path_cleaned = path
            if path_cleaned.startswith('./'):
                path_cleaned = path_cleaned.split('./', 1)[1]
            if path_cleaned in excluded_dirs:
                if VERBOSE:
                    print('=' * 78)
                print("skip dir :", path_cleaned + '/')
                print()
                dirs[:] = []
                files[:] = []
                continue
            dirs[:] = [e for e in sorted(dirs) if not e.startswith('.')]
            files[:] = [e for e in sorted(files) if not e.startswith('.')]
            for elem in files:
                filename = os.path.join(path, elem)
                if filename.startswith('./'):
                    filename = filename.split('./', 1)[1]
                if filename in excluded_files:
                    if VERBOSE:
                        print('=' * 78)
                    print("skip file:", filename)
                    print()
                    continue
                if os.path.splitext(elem)[1].lower() == '.py':
                    check_modernizations(args, filename)
                    print()


def check_modernizations(args, filename):
    """ Modernize (and 2to3) don't provide a uniform exit code to work with.
        Parse all possible outputs to determine the true final state.
    """
    if VERBOSE:
        print('=' * 78)
    full_args = args[:]
    full_args.append(filename)
    if VERBOSE:
        print('process  :', filename)
        print('arguments:', full_args)
    if USE_TEAMCITY:
        TC.testStarted(filename)

    # stdout/stderr diversion block
    stdout_orig = sys.stdout
    stdout_buffer = StringIO()
    sys.stdout = stdout_buffer
    stderr_orig = sys.stderr
    stderr_buffer = StringIO()
    sys.stderr = stderr_buffer
    exitcode = -1
    try:
        exitcode = modernize_main(full_args)
    except SystemExit as e:
        print("'Modernize' exited abnormally: {}".format(e))
        exitcode = -1
    finally:
        sys.stdout.flush()
        sys.stdout = stdout_orig
        sys.stderr.flush()
        sys.stderr = stderr_orig
    # stdout/stderr diversion block ends

    sout = stdout_buffer.getvalue()
    serr = stderr_buffer.getvalue()
    slog = LOG_CAPTURE_STRING.getvalue()
    LOG_CAPTURE_STRING.flush()
    LOG_CAPTURE_STRING.seek(0)
    LOG_CAPTURE_STRING.truncate(0)

    if VERBOSE:
        print('Exitcode (initial):', exitcode)
    if VERBOSE or exitcode == -1:
        for line in sout.split('\n'):
            print('STDOUT___:', line)
        for line in serr.split('\n'):
            print('STDERR___:', line)
        for line in slog.split('\n'):
            print('STDlog___:', line)
    mods = []
    for line in sout.split('\n'):
        if mods or line.endswith('\t(original)'):
            mods.append(line)
    details = '\n'.join(mods)
    if exitcode == 2:
        if slog.find('RefactoringTool: No changes to ') != -1:
            exitcode = 0
            if VERBOSE:
                print('File NOT changed per RefactoringTool')
    if details:
        # Final arbiter: if there are mods in the output, something definitely happened!
        exitcode = 2
        if VERBOSE:
            print('File changed per actual output')
    if VERBOSE:
        print('Exitcode (final):', exitcode)

    cmd_line = 'modernize {}'.format(' '.join(args[:]))
    if exitcode == 0:
        print('no change: {}'.format(filename))
    elif exitcode == 2:
        print('needs fix: {}'.format(filename))
        if USE_TEAMCITY:
            TC.testFailed(filename, message='Migration needed', details='\nSuggested changes from `{}`:\n\n'.format(cmd_line) + details)
        else:
            print('\nSuggested changes from `{}`:\n\n'.format(cmd_line) + details)
    else:
        print('UNK_ERROR: {}'.format(filename))
        if USE_TEAMCITY:
            TC.testFailed(filename, message='Unknown error', details='\nUnexpected output from `{}`:\n\n'.format(cmd_line) + details)
        else:
            print('\nUnexpected output from `{}`:\n\n'.format(cmd_line) + details)

    if USE_TEAMCITY:
        TC.testFinished(filename)

    return (sout, serr, exitcode)


def main(args=None):
    """ Most options are the same as Modernize for pass-through """
    parser = optparse.OptionParser(usage=usage,
                                   version="%s %s" % (SCRIPT_NAME, __version__))
    parser.formatter.format_usage = format_usage
    parser.add_option("-v", "--verbose", action="store_true",
                      help="Show more verbose logging.")
    parser.add_option("-f", "--fix", action="append", default=[],
                      help="Each FIX specifies a transformation; '-f default' includes default fixers.")
    parser.add_option("-x", "--nofix", action="append", default=[],
                      help="Prevent a fixer from being run.")
    parser.add_option("-p", "--print-function", action="store_true",
                      help="Modify the grammar so that print() is a function.")
    parser.add_option("-w", "--write", action="store_true",
                      help="Write back modified files.")
    parser.add_option("-n", "--nobackups", action="store_true", default=False,
                      help="Don't write backups for modified files.")
    parser.add_option("--six-unicode", action="store_true", default=False,
                      help="Wrap unicode literals in six.u().")
    parser.add_option("--future-unicode", action="store_true", default=False,
                      help="Use 'from __future__ import unicode_literals'"
                      "(only useful for Python 2.6+).")
    parser.add_option("--no-six", action="store_true", default=False,
                      help="Exclude fixes that depend on the six package.")
    parser.add_option("--enforce", action="store_true", default=False,
                      help="Returns non-zero exit code of any fixers had to be applied.  "
                           "Useful for enforcing Python 3 compatibility.")
    parser.add_option("-e", "--exclude", action="append", default=[],
                      help="Exclude a file or directory")
    parser.add_option("--teamcity", action="store", type="choice", default=None,
                      choices=['true', 'false'],
                      help="Force TeamCity state [true/false]")
    (options, args) = parser.parse_args(args)

    if options.verbose:
        global VERBOSE
        VERBOSE = True

    global TC, USE_TEAMCITY
    elems_included = args[:]
    elems_excluded = []
    args_passed = []
    args_local = []
    for option, value in options.__dict__.items():
        option = option.replace('_', '-')  # restore dashes changed by optparse
        target = args_passed
        if option in ['teamcity']:
            target = args_local
            if value == 'false':
                USE_TEAMCITY = False
            elif value == 'true':
                USE_TEAMCITY = True
            else:
                USE_TEAMCITY = is_running_under_teamcity()
        elif isinstance(value, list):
            if option in ['exclude']:
                elems_excluded.extend(options.exclude)
            else:
                new_opts = ["--{}={}".format(option, v) for v in value]
                target.extend(new_opts)
        elif isinstance(value, bool):
            if value is True:
                new_opts = ["--{}".format(option)]
                target.extend(new_opts)
        elif value is None:
            pass
        else:
            print("Argument '{}' not handled here: {}".format(option, value))
            parser.print_help()
            return -1

    logger = logging.getLogger('RefactoringTool')
    logger.setLevel(LOG_LEVEL)
    ch = logging.StreamHandler(LOG_CAPTURE_STRING)
    formatter = logging.Formatter('%(name)s: %(message)s')
    ch.setFormatter(formatter)
    ch.setLevel(LOG_LEVEL)
    logger.addHandler(ch)

    if not elems_included:
        elems_included = ['.']

    print('{} {} (using libmodernize {})'.format(SCRIPT_NAME, __version__, __version_modernize__))
    print()
    if USE_TEAMCITY:
        print('Note: Running with TeamCity hooks')
        TC = TeamcityServiceMessages()
    else:
        print('Note: NOT running with TeamCity hooks')
    print()

    if VERBOSE:
        print("Original options:", options)
        print("Original args:   ", args)
        print("Local options:   ", args_local)
        print("Passing options: ", args_passed)
        print("Included elems:  ", elems_included)
        print("Excluded elems:  ", elems_excluded)
        print()

    excluded_files = set()
    excluded_dirs = set()
    for exclusion in elems_excluded:
        exclusion = exclusion.rstrip('/')
        if os.path.isfile(exclusion):
            excluded_files.add(exclusion)
        elif os.path.isdir(exclusion):
            excluded_dirs.add(exclusion)
        else:
            print("UNKNOWN:", exclusion)

    for root in elems_included:
        walk_tree(args=args_passed, root=root, excluded_files=excluded_files, excluded_dirs=excluded_dirs)
    if VERBOSE:
        print('=' * 78)

    return 0
