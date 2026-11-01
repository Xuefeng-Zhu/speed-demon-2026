// sysc.c: count memory-management syscalls of a process and all its threads
// with ptrace (no strace on the sandbox). Usage: sysc CMD [ARGS...]
// Prints one line: mmap munmap mprotect madvise brk mremap total-syscalls
// minor-faults. Timing under ptrace is meaningless; only the counts are used.
#define _GNU_SOURCE
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ptrace.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <sys/user.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    pid_t child = fork();
    if (child == 0) {
        ptrace(PTRACE_TRACEME, 0, 0, 0);
        raise(SIGSTOP);
        execvp(argv[1], argv + 1);
        _exit(127);
    }
    int st;
    waitpid(child, &st, 0);
    ptrace(PTRACE_SETOPTIONS, child, 0,
           PTRACE_O_TRACESYSGOOD | PTRACE_O_TRACECLONE | PTRACE_O_EXITKILL);
    ptrace(PTRACE_SYSCALL, child, 0, 0);
    long n[512] = {0}, total = 0;
    for (;;) {
        pid_t t = waitpid(-1, &st, __WALL);
        if (t < 0) break;
        if (WIFEXITED(st) || WIFSIGNALED(st)) {
            if (t == child) break;
            continue;
        }
        int sig = 0;
        if (WIFSTOPPED(st)) {
            int s = WSTOPSIG(st);
            if (s == (SIGTRAP | 0x80)) {
                // Stops alternate entry, exit per thread.
                static unsigned char in[1 << 22];
                struct user_regs_struct r;
                if ((in[t] ^= 1) && ptrace(PTRACE_GETREGS, t, 0, &r) == 0) {
                    total++;
                    if (r.orig_rax < 512) n[r.orig_rax]++;
                }
            } else if (s == SIGTRAP || s == SIGSTOP) {
                sig = 0; // clone event or initial stop of a new thread
            } else {
                sig = s;
            }
        }
        ptrace(PTRACE_SYSCALL, t, 0, sig);
    }
    while (waitpid(-1, &st, __WALL) > 0) {
    }
    struct rusage ru;
    getrusage(RUSAGE_CHILDREN, &ru);
    printf("mmap %ld munmap %ld mprotect %ld madvise %ld brk %ld mremap %ld total %ld minflt %ld\n",
           n[SYS_mmap], n[SYS_munmap], n[SYS_mprotect], n[SYS_madvise], n[SYS_brk], n[SYS_mremap],
           total, ru.ru_minflt);
    return 0;
}
