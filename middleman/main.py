import tornado.ioloop
import tornado.web
import collections
import datetime
import hashlib
import json
import time
import os

class AsyncCallbackMixin(object):
    listeners = collections.defaultdict(list)
    def wait_for_message(self, id, callback):
        AsyncCallbackMixin.listeners[id].append(callback)

    def stop_waiting_for_message(self, id, callback):
        AsyncCallbackMixin.listeners[id].remove(callback)

    def send_message(self, id, message):
        while True:
            try:
                callback = AsyncCallbackMixin.listeners[id].pop()
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
        else:
            for val in WnotifyMessageMixin.id_lookup:
                print val + "\n"

class ListenerHandler(tornado.web.RequestHandler, WnotifyMessageMixin):
    @tornado.web.asynchronous
    def get(self, private_id):
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
            date_tuple = email.utils.parsedate(ims_value)
            if_since = datetime.datetime.fromtimestamp(time.mktime(date_tuple))
            if if_since >= modified:
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