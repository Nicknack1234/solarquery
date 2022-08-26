#include <unistd.h>
#include <sys/ioctl.h>
#include <stdint.h>
#include <stdio.h>
#include <pigpio.h>

//const uint8_t DE_PIN = 18;

int init() {
  gpioInitialise();
  gpioSetMode(18, PI_OUTPUT);
  gpioWrite(18, 0);
  return 0;
}

int nwrite() {
  gpioWrite(18, 1);
  return 0;
}

int nread() {
  gpioWrite(18, 0);
  return 0;
}

ssize_t writec(int fd, char *buf, size_t count) {
  gpioWrite(18, 1);
  ssize_t r = write(fd, buf, count);

  uint8_t lsr;
  do {
    int r = ioctl(fd, TIOCSERGETLSR, &lsr);
  } while (!(lsr & TIOCSER_TEMT));
  gpioWrite(18, 0);
  return r;
}

// gcc -shared -o writec.so -fPIC writec.c -lpigpio