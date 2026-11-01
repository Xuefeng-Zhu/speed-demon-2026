// LD_PRELOAD shim for the heterogeneity emulation (test-only, never part of the solution).
//
// SD_EMU_CPUS="c0,c1,...,c(n-1)": the i-th thread the process creates is pinned to CPU
// c[i % n] before it starts (the affinity is put into its pthread attributes), and it
// waits until all n threads of its batch (threads n*(i/n) .. n*(i/n)+n-1) exist. Track B's
// par() spawns its n workers in order k = 0..n-1, once for the index and once for the
// answers, so with n = SD_THREADS worker k always runs on CPU c[k], and all workers start
// together, as they do on an idle box. (Without the start gate the unpinned main thread
// shares a vCPU with already running workers and the last workers start up to 90 ms late.)
// The main thread is not pinned. Without SD_EMU_CPUS the shim does nothing.
//
// Build: gcc -O2 -Wall -shared -fPIC -o pin.so pin.c -ldl
#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <sched.h>
#include <stdlib.h>

static int cpus[1024], ncpus = -1, created;
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cv = PTHREAD_COND_INITIALIZER;

struct start {
    void *(*f)(void *);
    void *arg;
    int end; // the thread may run once `created` reaches this
};

static void *gate(void *p) {
    struct start s = *(struct start *)p;
    free(p);
    pthread_mutex_lock(&mu);
    while (created < s.end) pthread_cond_wait(&cv, &mu);
    pthread_mutex_unlock(&mu);
    return s.f(s.arg);
}

int pthread_create(pthread_t *t, const pthread_attr_t *attr, void *(*f)(void *), void *arg) {
    static int (*real)(pthread_t *, const pthread_attr_t *, void *(*)(void *), void *);
    if (!real) real = dlsym(RTLD_NEXT, "pthread_create");
    if (ncpus < 0) {
        ncpus = 0;
        for (char *s = getenv("SD_EMU_CPUS"); s && *s && ncpus < 1024;) {
            cpus[ncpus++] = (int)strtol(s, &s, 10);
            while (*s == ',') s++;
        }
    }
    if (ncpus == 0) return real(t, attr, f, arg);
    pthread_attr_t own;
    pthread_attr_t *a = (pthread_attr_t *)attr;
    if (!a) {
        pthread_attr_init(&own);
        a = &own;
    }
    pthread_mutex_lock(&mu);
    int i = created;
    pthread_mutex_unlock(&mu);
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpus[i % ncpus], &set);
    pthread_attr_setaffinity_np(a, sizeof set, &set);
    struct start *s = malloc(sizeof *s);
    *s = (struct start){f, arg, (i / ncpus + 1) * ncpus};
    int r = real(t, a, gate, s);
    if (a == &own) pthread_attr_destroy(&own);
    pthread_mutex_lock(&mu);
    created++;
    if (created % ncpus == 0) pthread_cond_broadcast(&cv);
    pthread_mutex_unlock(&mu);
    return r;
}
