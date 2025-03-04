"""
WSGI Utilities
(from web.py)
"""

import os, sys

import http
import webapi as web
from utils import listget
from net import validaddr, validip
import httpserver
    
def runfcgi(func, addr=('localhost', 8000)):
    """Runs a WSGI function as a FastCGI server."""
    import flup.server.fcgi as flups
    return flups.WSGIServer(func, multiplexed=True, bindAddress=addr).run()

def runscgi(func, addr=('localhost', 4000)):
    """Runs a WSGI function as an SCGI server."""
    import flup.server.scgi as flups
    return flups.WSGIServer(func, bindAddress=addr).run()

def runwsgi(func):
    """
    Runs a WSGI-compatible `func` using FCGI, SCGI, or a simple web server,
    as appropriate based on context and `sys.argv`.
    """
    
    if os.environ.has_key('SERVER_SOFTWARE'): # cgi
        os.environ['FCGI_FORCE_CGI'] = 'Y'

    if (os.environ.has_key('PHP_FCGI_CHILDREN') #lighttpd fastcgi
      or os.environ.has_key('SERVER_SOFTWARE')):
        return runfcgi(func, None)

    if 'fcgi' in sys.argv or 'fastcgi' in sys.argv:
        args = sys.argv[1:]
        if 'fastcgi' in args: args.remove('fastcgi')
        elif 'fcgi' in args: args.remove('fcgi')
        return runfcgi(func, validaddr(args[0])) if args else runfcgi(func, None)
    if 'scgi' in sys.argv:
        args = sys.argv[1:]
        args.remove('scgi')
        return runscgi(func, validaddr(args[0])) if args else runscgi(func)
    return httpserver.runsimple(func, validip(listget(sys.argv, 1, '')))
    
def _is_dev_mode():
    # quick hack to check if the program is running in dev mode.
    return (
        not os.environ.has_key('SERVER_SOFTWARE')
        and not os.environ.has_key('PHP_FCGI_CHILDREN')
        and 'fcgi' not in sys.argv
        and 'fastcgi' not in sys.argv
    )

# When running the builtin-server, enable debug mode if not already set.
web.config.setdefault('debug', _is_dev_mode())