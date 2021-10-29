"""
Compare:
- https://github.com/pangeo-forge/pangeo-forge-recipes/blob/master/tests/http_auth_server.py
- https://blog.anvileight.com/posts/simple-python-http-server/#do-post
"""
import ast
import base64
import http.server
import json
import socketserver

import click


@click.command()
@click.option("--address")
@click.option("--port")
@click.option("--username")
@click.option("--password")
def serve_forever(address, port, username, password):

    port = int(port)

    class Handler(http.server.SimpleHTTPRequestHandler):

        def do_GET(self):
            return http.server.SimpleHTTPRequestHandler.do_GET(self)

        def do_POST(self):
            if username:
                auth = self.headers.get("Authorization")
                if (
                    auth is None
                    or not auth.startswith("Basic")
                    or auth[6:]
                    != str(base64.b64encode((username + ":" + password).encode("utf-8")), "utf-8")
                ):
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", "Basic")
                    self.end_headers()
                    return

            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            d = ast.literal_eval(body.decode("utf-8"))
            outpath = self.path[1:]  # drop leading `"/"`

            with open(outpath, mode="w") as f:
                json.dump(d, f)  # assumes tests are always/only POSTing JSON, which I think is true

            self.send_response(200)
            self.end_headers()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((address, port), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    serve_forever()
