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
    from teamcity import (
        TeamcityServiceMessages,
        is_running_under_teamcity,
        # testStarted,
        # testFinished,
        # testIgnored,
        # testFailed,
        # testStdOut,
        # testStdErr,
    )
except ImportError:
    TeamcityServiceMessages = None
    def is_running_under_teamcity(): return False  # noqa: E301, E704

from modernize_reporter import __version__
from libmodernize import __version__ as __version_modernize__
from libmodernize.main import main as modernize_main  # Depends on customizations

SCRIPT_NAME = 'python-modernize-reporter'
TC = TeamcityServiceMessages
LOG_CAPTURE_STRING = StringIO()
LOG_LEVEL = logging.DEBUG
VERBOSE = False

usage = __doc__ + """\
 %s

Usage: %s [options] file|dir ...
""" % (SCRIPT_NAME, __version__)


def format_usage(usage):
    """Method that doesn't output "Usage:" prefix"""
    return usage


def walk_tree(args, root, exclusions=None):
    if exclusions is None:
        exclusions = []
    if os.path.isfile(root):
        check_modernizaitons(args, root)
    else:
        for path, dirs, files in os.walk(root):
            dirs[:] = [e for e in sorted(dirs) if not e.startswith('.')]
            files[:] = [e for e in sorted(files) if not e.startswith('.')]
            for elem in files:
                filename = os.path.join(path, elem)
                if filename.startswith('./'):
                    filename = filename.split('./', 1)[1]
                if os.path.splitext(elem)[1].lower() == '.py':
                    check_modernizaitons(args, filename)


def check_modernizaitons(args, filename):
    if VERBOSE:
        print('=' * 78)
    if is_running_under_teamcity():
        TC.testStarted(filename)
    if VERBOSE:
        print('checking:  {}'.format(filename))
    full_args = args[:]
    full_args.append(filename)
    if VERBOSE:
        print(full_args)

    # stdout/stderr diversion block
    stdout_orig = sys.__stdout__
    stdout_buffer = StringIO()
    sys.stdout = stdout_buffer
    stderr_orig = sys.__stderr__
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
    if VERBOSE or exitcode == -1:
        for line in serr.split('\n'):
            print("STDERR:", line)
        for line in sout.split('\n'):
            print("STDOUT:", line)
        for line in slog.split('\n'):
            print("STDlog:", line)
    mods = []
    if exitcode == 2:
        if slog.find('RefactoringTool: No changes to ') != -1:
            # File was actually unchanged
            exitcode = 0
    if exitcode == 0:
        print('no change: {}'.format(filename))
    elif exitcode == 2:
        print('needs fix: {}'.format(filename))
        if is_running_under_teamcity():
            TC.testFailed(filename)
    else:
        print('UNK error: {}'.format(filename))
        if is_running_under_teamcity():
            TC.testFailed(filename)
    for line in sout.split('\n'):
        if mods or line.endswith('(original)'):
            if exitcode == 2:
                tag = "modernize"
            else:
                tag = "INT_ERROR"
            mods.append(line)
            if line:
                print("{}: {}".format(tag, line), file=sys.stderr)
    print()
    if is_running_under_teamcity():
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
    (options, args) = parser.parse_args(args)

    if options.verbose:
        global VERBOSE
        VERBOSE = True

    elems_included = args[:]
    elems_excluded = []
    args_passed = []
    args_local = []
    for option, value in options.__dict__.items():
        option = option.replace('_', '-')  # restore dashes changed by optparse
        target = args_passed
        if option in []:
            target = args_local
        if isinstance(value, list):
            if option in ['exclude']:
                elems_excluded.extend(options.exclude)
            else:
                new_opts = ["--{}={}".format(option, v) for v in value]
                target.extend(new_opts)
        elif isinstance(value, bool):
            if value is not None:
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

    # print("original options:", options)
    # print("original args:   ", args)
    # print("local options:   ", args_local)
    # print("passing options: ", args_passed)
    # print("included elems:  ", elems_included)
    # print("excluded elems:  ", elems_excluded)

    if not elems_included:
        parser.print_help()
        return -1

    print('{} {} (importing libmodernize {})'.format(SCRIPT_NAME, __version__, __version_modernize__))
    print()
    if is_running_under_teamcity():
        print('Note: Running under TeamCity')
    else:
        print('Note: NOT running under TeamCity')
    print()

    for root in elems_included:
        walk_tree(args=args_passed, root=root, exclusions=elems_excluded)
    if VERBOSE:
        print('=' * 78)

    return 0
