#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static void usage(FILE *out, const char *name) {
    fprintf(out, "Usage: %s (--tcp|-t|--udp|-u) [-p PORT|--port PORT]\n", name);
}

static size_t daytime(char *buffer, size_t capacity) {
    time_t now = time(NULL);
    struct tm utc;
    if (now == (time_t)-1 || gmtime_r(&now, &utc) == NULL) return 0;
    return strftime(buffer, capacity, "%Y-%m-%dT%H:%M:%SZ\r\n", &utc);
}

int main(int argc, char **argv) {
    int type = 0, port = 13;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--help") || !strcmp(argv[i], "-h")) {
            usage(stdout, argv[0]);
            return 0;
        } else if (!strcmp(argv[i], "--tcp") || !strcmp(argv[i], "-t") ||
                   !strcmp(argv[i], "--udp") || !strcmp(argv[i], "-u")) {
            if (type) goto invalid;
            type = (!strcmp(argv[i], "--tcp") || !strcmp(argv[i], "-t"))
                       ? SOCK_STREAM : SOCK_DGRAM;
        } else if (!strcmp(argv[i], "-p") || !strcmp(argv[i], "--port")) {
            if (++i == argc || !argv[i][0]) goto invalid;
            char *end;
            errno = 0;
            long value = strtol(argv[i], &end, 10);
            if (errno || *end || value < 1 || value > 65535) goto invalid;
            port = (int)value;
        } else goto invalid;
    }
    if (!type) goto invalid;
    signal(SIGPIPE, SIG_IGN);
    int fd = socket(AF_INET, type, 0);
    if (fd < 0) { perror("socket"); return 1; }
    int reuse = 1;
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof reuse) < 0) {
        perror("setsockopt"); close(fd); return 1;
    }
    struct sockaddr_in address = {0};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    address.sin_port = htons((unsigned short)port);
    if (bind(fd, (struct sockaddr *)&address, sizeof address) < 0) {
        perror("bind"); close(fd); return 1;
    }
    if (type == SOCK_STREAM && listen(fd, 16) < 0) {
        perror("listen"); close(fd); return 1;
    }
    printf("Starting a %s server on port %d\n", type == SOCK_STREAM ? "TCP" : "UDP", port);
    fflush(stdout);
    for (;;) {
        struct sockaddr_in peer;
        socklen_t peer_size = sizeof peer;
        int client = -1;
        if (type == SOCK_STREAM) {
            client = accept(fd, NULL, NULL);
            if (client < 0) {
                if (errno == EINTR) continue;
                perror("accept"); close(fd); return 1;
            }
        } else {
            char ignored[1];
            if (recvfrom(fd, ignored, sizeof ignored, 0,
                         (struct sockaddr *)&peer, &peer_size) < 0) {
                if (errno == EINTR) continue;
                perror("recvfrom"); close(fd); return 1;
            }
        }
        char response[64];
        size_t length = daytime(response, sizeof response);
        if (!length) {
            fprintf(stderr, "Could not format current time\n");
            if (client >= 0) close(client);
            close(fd); return 1;
        }
        if (type == SOCK_STREAM) {
            size_t sent = 0;
            while (sent < length) {
                ssize_t count = send(client, response + sent, length - sent, 0);
                if (count < 0 && errno == EINTR) continue;
                if (count <= 0) { perror("send"); break; }
                sent += (size_t)count;
            }
            close(client);
        } else if (sendto(fd, response, length, 0,
                          (struct sockaddr *)&peer, peer_size) < 0) {
            perror("sendto");
        }
    }
invalid:
    usage(stderr, argv[0]);
    return 1;
}
