"""
geo Server implementation

@author: Saurya Jonchhe
@version: 2026.9
"""

import argparse
import logging
import socket
from csv import DictReader

HOST = "localhost"
PORT = 4300
BUFFER_SIZE = 1024
NOT_FOUND = "No such country."
QUIT_MESSAGE = "BYE"

logger = logging.getLogger("root")


def read_file(filename: str) -> tuple[dict[str, str], int]:
    """Read the world countries and their capitals from the file
    Make sure not to count United States of America and USA as two different countries

    :param filename: file to read
    :return: the tuple of (dictionary, count) where
            `dictionary` is a map {country:capital} and
            `count` is the number of countries in the world
    """
    world: dict[str, str] = {}
    count = 0
    with open(filename, "r", encoding="utf-8") as data_file:
        for record in DictReader(data_file, delimiter=";"):
            capital = record["Capital"].strip()
            for name in record["Country"].split(","):
                world[name.strip()] = capital
            count += 1
    return world, count


def find_capital(world: dict, country: str) -> str:
    """Find the capital of an existing country
    Return *No such country* otherwise

    :param world: dictionary representing the world
    :param country: country to look up
    :return: capital of the specified country
    """
    return world.get(country.strip(), NOT_FOUND)


def format_message(message: str) -> bytes:
    """Convert the message to bytes

    :param message: message to send
    :return: message converted to bytes
    """
    return message.encode("utf-8")


def parse_data(data: bytes) -> str:
    """Convert bytes to a string

    :param data: data to decode
    :return: decoded data
    """
    return data.decode("utf-8")


def server_loop(world: dict):
    """Main server loop"""
    print("The server has started")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((HOST, PORT))
        logger.debug("Listening on %s:%d", HOST, PORT)
        while True:
            data, client_address = sock.recvfrom(BUFFER_SIZE)
            country = parse_data(data)
            logger.debug("Received %s from %s", country, client_address)
            if country == QUIT_MESSAGE:
                sock.sendto(format_message(QUIT_MESSAGE), client_address)
                logger.debug("Disconnecting from %s", client_address)
                break
            capital = find_capital(world, country)
            logger.debug("Sending %s to %s", capital, client_address)
            sock.sendto(format_message(capital), client_address)
    print("The server has finished")


def main():
    """Main function"""
    arg_parser = argparse.ArgumentParser(description="Enable debugging")
    arg_parser.add_argument("file", type=str, help="File name")
    arg_parser.add_argument("-d", "--debug", action="store_true", help="Enable logging.DEBUG mode")
    args = arg_parser.parse_args()

    logger = logging.getLogger("root")
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logger.level)
    world, _ = read_file(args.file)
    server_loop(world)


if __name__ == "__main__":
    main()
