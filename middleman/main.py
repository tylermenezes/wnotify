import tornado.ioloop
import tornado.web
import collections
import datetime
import hashlib
import json
import time
import email
import os

class AsyncCallbackMixin(object):
    listeners = collections.defaultdict(collections.defaultdict)
    def wait_for_message(self, id, callback):
        if not(id in AsyncCallbackMixin.listeners):
            AsyncCallbackMixin.listeners[id] = collections.defaultdict(list)

        AsyncCallbackMixin.listeners[id][self.client_id].append(callback)

    def send_message(self, id, message):
        for client in AsyncCallbackMixin.listeners[id].values():
            while True:
                try:
                    callback = client.pop()
                except:
                    # No one is listening here
                    break

                try:
                    callback(message)
                except:
                    # This connection was closed, continue to the next one
                    pass
                else:
                    break


class WnotifyMessageMixin(AsyncCallbackMixin):
    id_lookup = collections.defaultdict(str)

    def register_waiter(self, private_id, callback):
        public_id = hashlib.sha256(private_id).hexdigest()
        WnotifyMessageMixin.id_lookup[public_id] = private_id
        self.wait_for_message(private_id, callback)

    def send_event(self, public_id, event_name, data):
        if public_id in WnotifyMessageMixin.id_lookup:
            private_id = WnotifyMessageMixin.id_lookup[public_id]

            self.send_message(private_id, json.dumps({
                "account": private_id,
                "event": event_name,
                "time": int(time.time()),
                "data": data
            }))

class ListenerHandler(tornado.web.RequestHandler, WnotifyMessageMixin):
    @tornado.web.asynchronous
    def get(self, private_id):
        if 'client_id' in self.request.arguments:
            self.client_id = self.request.arguments['client_id'][0];
        else:
            if self.request.remote_ip == '127.0.0.1':
                self.client_id = self.request.headers.get("X-Real-Ip", None)
            else:
                self.client_id = self.request.remote_ip

        def callback(message):
            self.set_header('Content-type', 'application/json')
            self.set_header('Access-Control-Allow-Origin', '*')
            self.set_header('Cache-Control', 'no-cache')
            self.write(message)
            self.finish()

        self.register_waiter(private_id, callback)

class ClientHandler(tornado.web.RequestHandler, WnotifyMessageMixin):
    def get(self, public_id, event_type):
        self.set_header('Content-type', 'application/json')
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Cache-Control', 'no-cache')
        self.send_event(public_id, event_type, self.request.arguments)
        self.write(json.dumps({
                "ok": True
            }))

class StaticFileHandler(tornado.web.RequestHandler):
    def initialize(self, path, default_filename=None):
        self.root = os.path.abspath(path) + os.path.sep
        self.default_filename = default_filename

    def head(self, path):
        self.get(path, include_body=False)

    def get(self, path, include_body=True):
        if os.path.sep != "/":
            path = path.replace("/", os.path.sep)
        abspath = os.path.abspath(os.path.join(self.root, path))
        # os.path.abspath strips a trailing /
        # it needs to be temporarily added back for requests to root/
        if not (abspath + os.path.sep).startswith(self.root):
            raise HTTPError(403, "%s is not in root static directory", path)
        if os.path.isdir(abspath) and self.default_filename is not None:
            # need to look at the request.path here for when path is empty
            # but there is some prefix to the path that was already
            # trimmed by the routing
            if not self.request.path.endswith("/"):
                self.redirect(self.request.path + "/")
                return
            abspath = os.path.join(abspath, self.default_filename)
        if not os.path.exists(abspath):
            raise HTTPError(404)
        if not os.path.isfile(abspath):
            raise HTTPError(403, "%s is not a file", path)

        stat_result = os.stat(abspath)
        modified = int(os.path.getmtime(abspath))

        self.set_header("Last-Modified", str(modified))
        if "v" in self.request.arguments:
            self.set_header("Expires", datetime.datetime.utcnow() + \
                                       datetime.timedelta(days=365*10))
            self.set_header("Cache-Control", "max-age=" + str(86400*365*10))
        else:
            self.set_header("Cache-Control", "public")
        mime_type, encoding = tornado.web.mimetypes.guess_type(abspath)
        if mime_type:
            self.set_header("Content-Type", mime_type)

        self.set_header('Access-Control-Allow-Origin', '*')

        # Check the If-Modified-Since, and don't send the result if the
        # content has not been modified
        ims_value = self.request.headers.get("If-Modified-Since")
        if ims_value is not None:
            if ims_value >= modified:
                self.set_status(304)
                return

        if not include_body:
            return
        file = open(abspath, "rb")
        try:
            self.write(file.read())
        finally:
            file.close()

application = tornado.web.Application([
    (r"/watch/(?P<private_id>.*)", ListenerHandler),
    (r"/track/(?P<public_id>.*)/(?P<event_type>.*)", ClientHandler),
    (r"/static/(.*)", StaticFileHandler, {"path": "static"})
])

if __name__ == "__main__":
    application.listen(6378)
    tornado.ioloop.IOLoop.instance().start()
