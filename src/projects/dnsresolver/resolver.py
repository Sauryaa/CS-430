"""
Client implementation

@author:
@version: 2026.10
"""

import argparse
import logging
from ipaddress import IPv4Address
from random import choice, randint
from socket import AF_INET, SOCK_DGRAM, socket

PORT = 53

DNS_TYPES = {"A": 1, "AAAA": 28, "CNAME": 5, "MX": 15, "NS": 2, "PTR": 12, "TXT": 16}

PUBLIC_DNS_SERVER = [
    "1.0.0.1",  # Cloudflare
    "1.1.1.1",  # Cloudflare
    "8.8.4.4",  # Google
    "8.8.8.8",  # Google
    "9.9.9.9",  # Quad9
    "64.6.64.6",  # Verisign
    "64.6.65.6",  # Verisign
    "208.67.220.220",  # OpenDNS
    "208.67.222.222",  # OpenDNS
]


def val_to_2_bytes(value: int) -> tuple[int, int]:
    """
    Split a value into 2 bytes
    Return the result as a tuple of 2 integers
    """
    return val_to_n_bytes(value, 2)


def val_to_n_bytes(value: int, n_bytes: int) -> tuple[int, ...]:
    """
    Split a value into n bytes
    Return the result as a tuple of n integers
    """
    return tuple((value >> (8 * shift)) & 0xFF for shift in range(n_bytes - 1, -1, -1))


def bytes_to_val(data: bytes | list[int]) -> int:
    """Merge n bytes into a value"""
    value = 0
    for byte in data:
        value = (value << 8) | byte
    return value


def get_2_bits(data: bytes | list[int]) -> int:
    """
    Extract first two bits of a two-byte sequence
    Return the result as a decimal value
    """
    return data[0] >> 6


def get_domain_name_location(data: bytes | list[int]) -> int:
    """
    Extract size of the offset from a two-byte sequence
    Return the result as a decimal value
    """
    return bytes_to_val(data) & 0x3FFF


def parse_cli_query(
    q_domain: str, q_type: str, q_server: str | None = None
) -> tuple[list, int, str]:
    """
    Parse command-line query
    Return a tuple of the domain (as a list of subdomains), numeric type, and the server
    If the server is not specified, pick a random one from `PUBLIC_DNS_SERVER`
    If type is not `A` or `AAAA`, raise `ValueError`
    """
    if q_type not in ("A", "AAAA"):
        raise ValueError(f"{q_type} is an unknown query type")
    domain = q_domain.removesuffix(".").split(".")
    try:
        domain = [label.encode("idna").decode("ascii") for label in domain]
    except UnicodeError as exc:
        raise ValueError("Invalid domain name") from exc
    if any(not label or len(label) > 63 for label in domain):
        raise ValueError("Domain labels must contain 1 to 63 bytes")
    if sum(len(label) + 1 for label in domain) + 1 > 255:
        raise ValueError("Domain name exceeds 255 bytes")
    if q_server is not None:
        try:
            IPv4Address(q_server)
        except ValueError as exc:
            raise ValueError("DNS server must be an IPv4 address") from exc
    return domain, DNS_TYPES[q_type], q_server if q_server is not None else choice(PUBLIC_DNS_SERVER)


def format_query(q_domain: list, q_type: int) -> bytearray:
    """
    Format DNS query
    Take the domain name (as a list) and the record type as parameters
    Return a properly formatted query
    Assumpions (defaults):
    - transaction id: random 0..65535
    - flags: recursive query set
    - questions: 1
    - class: Internet
    """
    query = bytearray()
    for value in (randint(0, 65535), 0x0100, 1, 0, 0, 0):
        query.extend(val_to_2_bytes(value))
    for label in q_domain:
        encoded = label.encode("ascii")
        if not 1 <= len(encoded) <= 63:
            raise ValueError("Domain labels must contain 1 to 63 bytes")
        query.append(len(encoded))
        query.extend(encoded)
    query.append(0)
    if len(query) - 12 > 255:
        raise ValueError("Domain name exceeds 255 bytes")
    query.extend(val_to_2_bytes(q_type))
    query.extend(val_to_2_bytes(1))
    return query


def _require_bytes(data: bytes, offset: int, length: int) -> None:
    """Reject truncated fields before indexing a DNS message."""
    if offset < 0 or length < 0 or offset + length > len(data):
        raise ValueError("Truncated DNS message")


def _parse_name(data: bytes, offset: int) -> tuple[str, int]:
    """Read labels and compression pointers, preserving the next field offset."""
    labels = []
    next_offset = None
    visited = set()
    name_length = 1
    while True:
        if offset in visited:
            raise ValueError("DNS compression pointer loop")
        visited.add(offset)
        _require_bytes(data, offset, 1)
        length = data[offset]
        if length & 0xC0 == 0xC0:
            _require_bytes(data, offset, 2)
            if next_offset is None:
                next_offset = offset + 2
            offset = get_domain_name_location(data[offset:offset + 2])
            continue
        if length & 0xC0:
            raise ValueError("Invalid DNS label length")
        offset += 1
        if length == 0:
            return ".".join(labels), next_offset if next_offset is not None else offset
        _require_bytes(data, offset, length)
        name_length += length + 1
        if name_length > 255:
            raise ValueError("Domain name exceeds 255 bytes")
        labels.append(data[offset:offset + length].decode("ascii"))
        offset += length


def parse_response(resp_bytes: bytes) -> list[tuple]:
    """
    Parse server response
    Take response bytes as a parameter
    Return a list of tuples in the format of (name, address, ttl)
    """
    _require_bytes(resp_bytes, 0, 12)
    questions = bytes_to_val(resp_bytes[4:6])
    answers = bytes_to_val(resp_bytes[6:8])
    offset = 12
    for _ in range(questions):
        _, offset = _parse_name(resp_bytes, offset)
        _require_bytes(resp_bytes, offset, 4)
        offset += 4
    return parse_answers(resp_bytes, offset, answers)


def parse_answers(resp_bytes: bytes, answer_start: int, rr_ans: int) -> list[tuple]:
    """
    Parse DNS server answers
    Take response bytes, offset, and the number of answers as parameters
    Return a list of tuples in the format of (name, address, ttl)
    """
    answers = []
    offset = answer_start
    for _ in range(rr_ans):
        name, offset = _parse_name(resp_bytes, offset)
        _require_bytes(resp_bytes, offset, 10)
        record_type = bytes_to_val(resp_bytes[offset:offset + 2])
        record_class = bytes_to_val(resp_bytes[offset + 2:offset + 4])
        ttl = bytes_to_val(resp_bytes[offset + 4:offset + 8])
        length = bytes_to_val(resp_bytes[offset + 8:offset + 10])
        offset += 10
        _require_bytes(resp_bytes, offset, length)
        address_bytes = resp_bytes[offset:offset + length]
        if record_class == 1 and record_type in (1, 28):
            parser = parse_address_a if record_type == 1 else parse_address_aaaa
            answers.append((name, parser(length, address_bytes), ttl))
        offset += length
    return answers


def parse_address_a(addr_len: int, addr_bytes: bytes) -> str:
    """
    Parse IPv4 address
    Convert bytes to human-readable dotted-decimal
    """
    if addr_len != 4 or len(addr_bytes) != 4:
        raise ValueError("IPv4 addresses must contain 4 bytes")
    return ".".join(str(byte) for byte in addr_bytes)


def parse_address_aaaa(addr_len: int, addr_bytes: bytes) -> str:
    """Extract IPv6 address"""
    if addr_len != 16 or len(addr_bytes) != 16:
        raise ValueError("IPv6 addresses must contain 16 bytes")
    return ":".join(f"{bytes_to_val(addr_bytes[i:i + 2]):x}" for i in range(0, 16, 2))


def resolve(query: tuple) -> None:
    """Resolve the query"""
    try:
        q_domain, q_type, q_server = parse_cli_query(*query)
    except ValueError as ve:
        print(ve.args[0])
        raise SystemExit(2)
    logging.info(f"Resolving type {q_type} for {q_domain} using {q_server}")
    query_bytes = format_query(q_domain, q_type)
    with socket(AF_INET, SOCK_DGRAM) as sock:
        sock.settimeout(5)
        sock.sendto(query_bytes, (q_server, PORT))
        response_data, _ = sock.recvfrom(65535)
    answers = parse_response(response_data)
    print(f"DNS server used: {q_server}")
    for a in answers:
        print()
        print(f"{'Name:':10s}{a[0]}")
        print(f"{'Address:':10s}{a[1]}")
        print(f"{'TTL:':10s}{a[2]}")


def main():
    """Main function"""
    arg_parser = argparse.ArgumentParser(description="Parse arguments")
    arg_parser.add_argument("domain", help="Domain name to resolve")
    arg_parser.add_argument("-t", "--type", default="A", help="Record type: A or AAAA")
    arg_parser.add_argument("-s", "--server", help="IPv4 address of the DNS server")
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

    try:
        resolve((args.domain, args.type, args.server))
    except (OSError, ValueError) as exc:
        arg_parser.exit(1, f"DNS lookup failed: {exc}\n")


if __name__ == "__main__":
    main()
