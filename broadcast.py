from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
from threading import Condition

import re
import cgi

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
        if since_id is None:
            found = self._queue
        else:
            found = [(id, item) for (id,item) in self._queue if id > since_id]
        return found
    
    @acquire
    def recv(self, since_id=None, timeout=10000):
        while True:
            found = self._find_items(since_id)
            if found:
                print "found %d" % len(found)
                return found
            print "Waiting"
            self._condition.wait(timeout)

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

class BroadcastRequestHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        if self.path == '/':
            self.recv_GET()
        elif self.path == '/send':
            self.send_GET()
        else:
            m = re.match(r'/since/(\d+)', self.path)
            if m:
                self.recv_GET(m.group(1))
            else:
                self.send_error(404, "Not found: %s" % self.path) 
    
    def do_POST(self):
        self.send_POST()
    
    @send_response(content_type='text/plain')
    def recv_GET(self, since_id=None):
        if since_id is not None:
            since_id = int(since_id)
        messages = broadcast.recv(since_id, timeout=5*60*1000)
        return '\n'.join('%r, %r' % (id, message) for (id, message) in messages)
    
    @send_response()
    def send_GET(self):
        return '''
        <html>
        <body>
        <form action="/send" method="post">
            Message: <input type="text" name="message" />
            <input type="submit" />
        </form>
        </body>
        </html>
        '''
    
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
            
        self.send_response(302)
        self.send_header('Location', '/send')
        self.end_headers()

class BroadcastHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == '__main__':
    server_address = ('', 8192)
    httpd = BroadcastHTTPServer(server_address, BroadcastRequestHandler)
    print "Listening on ", server_address
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()