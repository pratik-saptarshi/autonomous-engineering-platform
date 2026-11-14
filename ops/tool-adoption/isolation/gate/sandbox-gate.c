/*
 * sandbox-gate — 2a hardening gate for the isolation composite.
 *
 * Runs INSIDE the chroot (as root, immediately after chroot, before the
 * payload exists as a process), then replaces itself with the payload:
 *
 *   1. Builds a Landlock ruleset from --rule PATH:CLASS arguments,
 *      confining filesystem access to the declared sandbox paths.
 *   2. Drops the process to a dedicated unprivileged uid/gid
 *      (setgroups/setgid/setuid, verified).
 *   3. Sets no_new_privs (required for Landlock restrict and seccomp).
 *   4. Applies the Landlock ruleset to itself (survives exec).
 *   5. Installs a seccomp denylist (classic BPF, hand-built; no
 *      libseccomp dependency — the runtime ships the libseccomp runtime
 *      library but no header/dev symlink) returning EPERM for the
 *      denied syscall set.
 *   6. execvp()s the payload command after `--`.
 *
 * Fail-closed: any error before exec prints to stderr and exits 65;
 * the payload never runs.
 *
 * Record: ~/workspace/isolation-pilot/ADOPTION-ADDENDUM.md
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef SYS_landlock_create_ruleset
#define SYS_landlock_create_ruleset 444
#endif
#ifndef SYS_landlock_add_rule
#define SYS_landlock_add_rule 445
#endif
#ifndef SYS_landlock_restrict_self
#define SYS_landlock_restrict_self 446
#endif
/* ABI 5 (kernel 6.10) FS right; the 6.8 distro header predates it. */
#ifndef LANDLOCK_ACCESS_FS_IOCTL_DEV
#define LANDLOCK_ACCESS_FS_IOCTL_DEV (1ULL << 15)
#endif

static void die(const char *what) {
    fprintf(stderr, "sandbox-gate: FAILED: %s: %s\n", what, strerror(errno));
    exit(65);
}

/* ---- Landlock rights classes (intersected with the handled mask) ---- */
#define RIGHTS_RO   (LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_READ_FILE | \
                     LANDLOCK_ACCESS_FS_READ_DIR)
#define RIGHTS_RW   (LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_WRITE_FILE | \
                     LANDLOCK_ACCESS_FS_READ_FILE | LANDLOCK_ACCESS_FS_READ_DIR | \
                     LANDLOCK_ACCESS_FS_REMOVE_DIR | LANDLOCK_ACCESS_FS_REMOVE_FILE | \
                     LANDLOCK_ACCESS_FS_MAKE_CHAR | LANDLOCK_ACCESS_FS_MAKE_DIR | \
                     LANDLOCK_ACCESS_FS_MAKE_REG | LANDLOCK_ACCESS_FS_MAKE_SOCK | \
                     LANDLOCK_ACCESS_FS_MAKE_FIFO | LANDLOCK_ACCESS_FS_MAKE_BLOCK | \
                     LANDLOCK_ACCESS_FS_MAKE_SYM | LANDLOCK_ACCESS_FS_REFER | \
                     LANDLOCK_ACCESS_FS_TRUNCATE | LANDLOCK_ACCESS_FS_IOCTL_DEV)
#define RIGHTS_DEV  (LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_READ_FILE | \
                     LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_READ_DIR)
#define RIGHTS_ROOT (LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_READ_DIR)
#define RIGHTS_FILE_RO (LANDLOCK_ACCESS_FS_READ_FILE)

static uint64_t rights_for_class(const char *cls) {
    if (!strcmp(cls, "rw"))     return RIGHTS_RW;
    if (!strcmp(cls, "ro"))     return RIGHTS_RO;
    if (!strcmp(cls, "dev"))    return RIGHTS_DEV;
    if (!strcmp(cls, "root"))   return RIGHTS_ROOT;
    if (!strcmp(cls, "filero")) return RIGHTS_FILE_RO;
    fprintf(stderr, "sandbox-gate: FAILED: unknown rule class '%s'\n", cls);
    exit(65);
}

/* ---- Seccomp denylist (x86_64 numbers). Rationale per group is in
 *      ADOPTION-ADDENDUM.md. Action: SECCOMP_RET_ERRNO | EPERM.
 *      Deliberately NOT denied: clone/clone3 (the workload's thread and
 *      process creation; glibc may route through clone3), prctl and
 *      seccomp themselves (a payload can only ever ADD restrictions to
 *      itself, never remove these), capset (payload holds no caps). */
struct deny { int nr; const char *name; };
static const struct deny DENYLIST[] = {
    /* mount / namespace manipulation — would reshape the confinement */
    {165, "mount"}, {166, "umount2"}, {155, "pivot_root"}, {161, "chroot"},
    {428, "open_tree"}, {429, "move_mount"}, {430, "fsopen"}, {431, "fsconfig"},
    {432, "fsmount"}, {442, "mount_setattr"}, {272, "unshare"}, {308, "setns"},
    /* kernel module / kernel control */
    {175, "init_module"}, {313, "finit_module"}, {176, "delete_module"},
    {174, "create_module"}, {246, "kexec_load"}, {320, "kexec_file_load"},
    {169, "reboot"}, {103, "syslog"}, {156, "_sysctl"}, {177, "get_kernel_syms"},
    {178, "query_module"}, {180, "nfsservctl"}, {179, "quotactl"}, {163, "acct"},
    /* cross-process introspection / fd theft */
    {101, "ptrace"}, {310, "process_vm_readv"}, {311, "process_vm_writev"},
    {312, "kcmp"}, {438, "pidfd_getfd"},
    /* kernel keyring */
    {248, "add_key"}, {249, "request_key"}, {250, "keyctl"},
    /* eBPF / perf / fault-injection kernel surface */
    {321, "bpf"}, {298, "perf_event_open"}, {323, "userfaultfd"},
    /* io_uring — large kernel surface that bypasses syscall mediation */
    {425, "io_uring_setup"}, {426, "io_uring_enter"}, {427, "io_uring_register"},
    /* file-handle path bypass */
    {303, "name_to_handle_at"}, {304, "open_by_handle_at"},
    /* device-node creation (also Landlock MAKE_*-gated) */
    {133, "mknod"}, {259, "mknodat"},
    /* clock / swap / personality hardening */
    {164, "settimeofday"}, {227, "clock_settime"}, {159, "adjtimex"},
    {167, "swapon"}, {168, "swapoff"}, {153, "vhangup"}, {135, "personality"},
};
#define DENY_COUNT (sizeof(DENYLIST) / sizeof(DENYLIST[0]))

static void install_seccomp(void) {
    /* Layout: arch check, nr load, one JEQ+RET pair per denied syscall,
     * final RET_ALLOW. 3 + 2*DENY_COUNT + 1 instructions. */
    struct sock_filter f[3 + 2 * 64 + 1];
    if (DENY_COUNT > 64) { errno = E2BIG; die("denylist too large"); }
    size_t n = 0;
    f[n++] = (struct sock_filter)BPF_STMT(BPF_LD + BPF_W + BPF_ABS,
                                          offsetof(struct seccomp_data, arch));
    f[n++] = (struct sock_filter)BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K,
                                          AUDIT_ARCH_X86_64, 1, 0);
    f[n++] = (struct sock_filter)BPF_STMT(BPF_RET + BPF_K,
                                          SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA));
    f[n++] = (struct sock_filter)BPF_STMT(BPF_LD + BPF_W + BPF_ABS,
                                          offsetof(struct seccomp_data, nr));
    for (size_t i = 0; i < DENY_COUNT; i++) {
        f[n++] = (struct sock_filter)BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K,
                                              DENYLIST[i].nr, 0, 1);
        f[n++] = (struct sock_filter)BPF_STMT(BPF_RET + BPF_K,
                                              SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA));
    }
    f[n++] = (struct sock_filter)BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW);
    struct sock_fprog prog = { .len = (unsigned short)n, .filter = f };
    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) != 0)
        die("prctl(PR_SET_SECCOMP)");
}

int main(int argc, char **argv) {
    long uid = -1, gid = -1;
    struct { char *path; uint64_t rights; int fd; } rules[32];
    size_t nrules = 0;
    int i = 1;
    for (; i < argc; i++) {
        if (!strcmp(argv[i], "--")) { i++; break; }
        if (!strncmp(argv[i], "--uid=", 6)) uid = atol(argv[i] + 6);
        else if (!strncmp(argv[i], "--gid=", 6)) gid = atol(argv[i] + 6);
        else if (!strncmp(argv[i], "--rule=", 7)) {
            if (nrules >= 32) { errno = E2BIG; die("too many rules"); }
            char *spec = argv[i] + 7;
            char *colon = strrchr(spec, ':');
            if (!colon) { errno = EINVAL; die("--rule needs PATH:CLASS"); }
            *colon = '\0';
            rules[nrules].path = spec;
            rules[nrules].rights = rights_for_class(colon + 1);
            rules[nrules].fd = -1;
            nrules++;
        } else {
            fprintf(stderr, "sandbox-gate: FAILED: unknown argument '%s'\n", argv[i]);
            exit(65);
        }
    }
    if (uid <= 0 || gid <= 0 || nrules == 0 || i >= argc) {
        fprintf(stderr, "sandbox-gate: FAILED: --uid/--gid/--rule and a command are required\n");
        exit(65);
    }

    /* Runtime ABI query (this host reported 8 during discovery). */
    long abi = syscall(SYS_landlock_create_ruleset, NULL, 0,
                       LANDLOCK_CREATE_RULESET_VERSION);
    if (abi < 0) die("landlock ABI query (Landlock unavailable?)");
    uint64_t handled = (1ULL << 13) - 1;                  /* ABI 1 base */
    if (abi >= 2) handled |= LANDLOCK_ACCESS_FS_REFER;    /* bit 13 */
    if (abi >= 3) handled |= LANDLOCK_ACCESS_FS_TRUNCATE; /* bit 14 */
    if (abi >= 5) handled |= LANDLOCK_ACCESS_FS_IOCTL_DEV;/* bit 15 */

    /* Open all rule paths BEFORE dropping privileges. */
    for (size_t r = 0; r < nrules; r++) {
        rules[r].fd = open(rules[r].path, O_PATH | O_CLOEXEC);
        if (rules[r].fd < 0) die("open rule path");
    }

    struct landlock_ruleset_attr attr;
    memset(&attr, 0, sizeof(attr));
    attr.handled_access_fs = handled;
    int rsfd = syscall(SYS_landlock_create_ruleset, &attr, sizeof(attr), 0);
    if (rsfd < 0) die("landlock_create_ruleset");
    for (size_t r = 0; r < nrules; r++) {
        struct landlock_path_beneath_attr pb;
        memset(&pb, 0, sizeof(pb));
        pb.allowed_access = rules[r].rights & handled;
        pb.parent_fd = rules[r].fd;
        if (syscall(SYS_landlock_add_rule, rsfd, LANDLOCK_RULE_PATH_BENEATH,
                    &pb, 0) != 0)
            die("landlock_add_rule");
        close(rules[r].fd);
    }

    /* Drop to the dedicated unprivileged uid (closes the pilot's
     * root-in-namespace residual for the payload). */
    if (setgroups(0, NULL) != 0) die("setgroups");
    if (setgid((gid_t)gid) != 0) die("setgid");
    if (setuid((uid_t)uid) != 0) die("setuid");
    if (getuid() != (uid_t)uid || geteuid() != (uid_t)uid ||
        getgid() != (gid_t)gid)
        die("uid/gid drop did not take effect");

    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) die("PR_SET_NO_NEW_PRIVS");

    if (syscall(SYS_landlock_restrict_self, rsfd, 0) != 0)
        die("landlock_restrict_self");
    close(rsfd);

    install_seccomp();

    fprintf(stderr,
            "sandbox-gate: landlock ABI %ld, %zu path rules applied; "
            "seccomp denylist installed (%zu syscalls -> EPERM); "
            "payload uid/gid %ld/%ld\n",
            abi, nrules, DENY_COUNT, uid, gid);
    execvp(argv[i], &argv[i]);
    die("execvp payload");
    return 65;
}
