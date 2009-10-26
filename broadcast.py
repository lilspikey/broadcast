from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
from threading import Condition

import re
import cgi
from time import time

def acquire_then_notify(fn):
    def _decorated(self, *arg, **kw):
        val = fn(self, *arg, **kw)
        self._condition.notifyAll()
        return val
    return acquire(_decorated)

def acquire(fn):
    def _decorated(self, *arg, **kw):
        self._condition.acquire()
        try:
            return fn(self, *arg, **kw)
        finally:
            self._condition.release()
    return _decorated

class Broadcaster(object):
    def __init__(self):
        self._condition = Condition()
        self._last_id = 0
        self._queue = []
    
    @acquire_then_notify
    def send(self, item):
        print "Sending message", item
        self._last_id += 1
        self._queue.append((self._last_id, item))
    
    def _find_items(self, since_id=None):
        if not since_id:
            found = self._queue
        else:
            found = [(id, item) for (id,item) in self._queue if id > since_id]
        return found
    
    @acquire
    def recv(self, since_id=None, timeout=10):
        end_time = time() + timeout
        while time() < end_time:
            found = self._find_items(since_id)
            if found:
                break
            print "Waiting"
            self._condition.wait(timeout)
        print "found %d" % len(found)
        return found

broadcast = Broadcaster()

def send_response(content_type='text/html'):
    def _decorator(fn):
        def _decorated(self, *arg, **kw):
            returned = fn(self, *arg, **kw)
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.end_headers()
            self.wfile.write(returned)
        return _decorated
    return _decorator

_content_types={
    'html': 'text/html',
    'js': 'text/javascript',
    'css': 'text/css'
}

def file_suffix(file_name):
    suffix=''
    dot_index=file_name.rfind('.')
    if dot_index > -1:
        suffix=file_name[dot_index+1:]
    return suffix

class BroadcastRequestHandler(BaseHTTPRequestHandler):
    
    def _serve_file(self,file_name):
        suffix=file_suffix(file_name)
        self.send_response(200)
        self.send_header("Content-type", _content_types.get(suffix,"text/plain") )
        self.end_headers()
        f=open(file_name)
        try:
            while True:
                bytes=f.read(1024)
                if bytes:
                    self.wfile.write(bytes)
                else:
                    break
        finally:
            f.close()
    
    def do_GET(self):
        if self.path == '/':
            self._serve_file('index.html')
        elif self.path == '/jquery.js':
            self._serve_file('jquery-1.3.2.min.js')
        elif self.path == '/broadcast.js':
            self._serve_file('broadcast.js')
        else:
            m = re.match(r'^/since/(\d*)$', self.path)
            if m:
                self.recv_GET(m.group(1))
            else:
                self.send_error(404, "Not found: %s" % self.path) 
    
    def do_POST(self):
        self.send_POST()
    
    @send_response(content_type='text/plain')
    def recv_GET(self, since_id=None):
        if since_id:
            since_id = int(since_id)
        messages = broadcast.recv(since_id, timeout=3*60)
        return '[ %s ]' % (',\n'.join('{ id: %r, message: %r }' % (id, message) for (id, message) in messages))
    
    @send_response(content_type='text/plain')
    def send_POST(self):
        form = cgi.FieldStorage(
                fp=self.rfile, 
                headers=self.headers,
                environ={'REQUEST_METHOD':'POST',
                         'CONTENT_TYPE':self.headers['Content-Type'],
                })
        if 'message' in form:
            message = form['message'].value
            broadcast.send(message)
            
        return 'Received'

class BroadcastHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == '__main__':
    server_address = ('192.168.1.237', 8192)
    httpd = BroadcastHTTPServer(server_address, BroadcastRequestHandler)
    print "Listening on ", server_address
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()