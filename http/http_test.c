// Server side C program to demonstrate Socket
// programming
#include <netdb.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#define PORT 8080

int main() {
  struct sockaddr_in sa;

  inet_pton(AF_INET, "10.12.110.57", &(sa.sin_addr));

  char ip4[INET_ADDRSTRLEN];

  inet_ntop(AF_INET, &(sa.sin_addr), ip4, INET_ADDRSTRLEN);

  printf("The IPv4 address is: %s\n", ip4);
}
