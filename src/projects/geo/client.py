"""
geo Client implementation

@author: Saurya Jonchhe
@version: 2026.9
"""

import argparse
import logging
import socket
import sys

HOST = "localhost"
PORT = 4300
BUFFER_SIZE = 1024
QUIT_MESSAGE = "BYE"

logger = logging.getLogger("root")


def format_message(message: str) -> bytes:
    """Convert the message to bytes

    :param message: message to encode
    :return: message as bytes
    """
    return message.encode("utf-8")


def parse_data(data: bytes) -> str:
    """Convert bytes to a string

    :param data: data received
    :return: decoded string
    """
    return data.decode("utf-8")


def read_user_input() -> str:
    """Read user input from the console

    :return: country name
    """
    try:
        return input().strip()
    except EOFError:
        return QUIT_MESSAGE


def client_loop():
    """Main client loop"""
    print("The client has started")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        while True:
            print(f"Enter the country name ({QUIT_MESSAGE} to quit): ", end="", flush=True)
            country = read_user_input()
            logger.debug("Sending %s to %s:%d", country, HOST, PORT)
            sock.sendto(format_message(country), (HOST, PORT))
            data, server_address = sock.recvfrom(BUFFER_SIZE)
            response = parse_data(data)
            logger.debug("Received %s from %s", response, server_address)
            if country == QUIT_MESSAGE:
                break
            print(response)
    print("The client has finished")


def main():
    """Main function"""
    arg_parser = argparse.ArgumentParser(description="Enable debugging")
    arg_parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable logging.DEBUG mode"
    )
    args = arg_parser.parse_args()
    logger = logging.getLogger("root")
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logger.level)
    client_loop()


if __name__ == "__main__":
    main()
