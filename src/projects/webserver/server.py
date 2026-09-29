"""
Server implementation

@author: Saurya Jonchhe
@version: 2026.9
"""

import argparse
import datetime
import logging
from pathlib import Path
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket

SRVR_ADDR = "127.0.0.1"
SRVR_PORT = 4380  # Open http://127.0.0.1:4380 in a browser
SRVR_NAME = "CS430/2026"
DATA_DIR = Path("data/projects/webserver")
# A request for the key should redirect to the mapped value
REDIRECT = {"alice.txt": "alice30.txt", "test.txt": "test26.txt"}

REASON_PHRASES = {
    200: "OK",
    204: "No Content",
    301: "Moved Permanently",
    404: "Not Found",
    405: "Method Not Allowed",
    418: "I'm a teapot",
    501: "Not Implemented",
    505: "HTTP Version Not Supported",
}


def parse_request(data: bytes) -> dict[str, str]:
    """Parse the incoming request

    :return: a dictionary of key-value mappings based on the request header
    """
    text = data.decode("utf-8", errors="replace")
    header_part, _, body = text.partition("\r\n\r\n")
    lines = header_part.split("\r\n")

    method, url, version = lines[0].split(" ")
    result = {"Method": method, "Url": url, "Version": version}

    for line in lines[1:]:
        if not line:
            continue
        key, _, value = line.partition(": ")
        result[key] = value

    if body:
        result["Body"] = body

    return result


def format_response(
    http_version: str, status_code: int, header: dict | None = None, data: str = ""
) -> bytes:
    """Format the response

    :return: encoded message that includes header and data
    """
    reason = REASON_PHRASES.get(status_code, "")
    lines = [f"{http_version} {status_code} {reason}"]
    lines.append(f"Date: {datetime.datetime.now()}")
    lines.append(f"Server: {SRVR_NAME}")

    if header:
        for key, value in header.items():
            lines.append(f"{key}: {value}")

    if data:
        body = data.encode("utf-8") if isinstance(data, str) else data
        lines.append(f"Content-Length: {len(body)}")
    else:
        body = b""

    return ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8") + body


def receive_request(conn) -> bytes:
    """Read a full HTTP request (headers and, if present, body) off the socket"""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(4096)
        if not chunk:
            return data
        data += chunk

    header_bytes, _, body = data.partition(b"\r\n\r\n")
    content_length = 0
    for line in header_bytes.split(b"\r\n")[1:]:
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())
            break

    while len(body) < content_length:
        chunk = conn.recv(4096)
        if not chunk:
            break
        body += chunk

    return header_bytes + b"\r\n\r\n" + body


def handle_request(request: dict[str, str]) -> bytes:
    """Build a response for a parsed request"""
    method = request.get("Method", "")
    url = request.get("Url", "/")
    version = request.get("Version", "")

    if version != "HTTP/1.1":
        return format_response("HTTP/1.1", 505)

    if method == "HEAD":
        data = "<html><head></head><body><h1>Use GET to retrieve resources from this server</h1></body></html>"
        return format_response("HTTP/1.1", 405, data=data)

    if method == "POST":
        return format_response("HTTP/1.1", 418)

    if method == "PUT":
        return format_response("HTTP/1.1", 501)

    if method == "DELETE":
        return format_response("HTTP/1.1", 204)

    if method == "GET":
        resource = url.lstrip("/")
        if resource in REDIRECT:
            return format_response("HTTP/1.1", 301, {"Location": f"/{REDIRECT[resource]}"})

        filepath = DATA_DIR / resource
        if filepath.is_file():
            content = filepath.read_text(encoding="utf-8")
            header = {
                "Content-Type": "text/plain; charset=utf-8",
                "Last-Modified": str(datetime.datetime.fromtimestamp(filepath.stat().st_mtime)),
            }
            return format_response("HTTP/1.1", 200, header, content)

        data = f"<html><head></head><body><h1>File {url} not found on our server</h1></body></html>"
        return format_response("HTTP/1.1", 404, data=data)

    return format_response("HTTP/1.1", 501)


def server_loop(logfilename: Path):
    """Main server loop"""
    logfilename.parent.mkdir(parents=True, exist_ok=True)
    access_logger = logging.getLogger("webserver.access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    if not access_logger.handlers:
        handler = logging.FileHandler(logfilename)
        handler.setFormatter(logging.Formatter("%(message)s"))
        access_logger.addHandler(handler)

    with socket(AF_INET, SOCK_STREAM) as sock:
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind((SRVR_ADDR, SRVR_PORT))
        sock.listen()
        print("The server has started")
        while True:
            conn, addr = sock.accept()
            with conn:
                raw_request = receive_request(conn)
                if not raw_request:
                    continue
                request = parse_request(raw_request)
                access_logger.info(
                    f"{datetime.datetime.now()} | {request.get('Url', '')} | "
                    f"{addr[0]} | {request.get('User-Agent', '')}"
                )
                conn.sendall(handle_request(request))


def main():
    """Set up arguments and start the main server loop"""
    arg_parser = argparse.ArgumentParser(description="Parse arguments")
    arg_parser.add_argument(
        "-l",
        "--logfile",
        type=str,
        help="Log file name",
        default="src/projects/webserver/webserver.log",
    )
    arg_parser.add_argument("-d", "--debug", action="store_true", help="Enable logging.DEBUG mode")
    args = arg_parser.parse_args()

    logger = logging.getLogger("root")
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logger.level)

    try:
        server_loop(Path(args.logfile))
    except KeyboardInterrupt:
        print("\nThe server has stopped")


if __name__ == "__main__":
    main()
