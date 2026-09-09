/* Independent SDK-based verification of the restricted process metadata ABI. */
#include <sys/types.h>
#include <sys/sysctl.h>
#include <sys/proc.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    int pid = atoi(argv[1]);
    int mib[] = { CTL_KERN, KERN_PROC, KERN_PROC_PID, pid };
    struct kinfo_proc info = {0};
    size_t size = sizeof(info);
    if (pid <= 0 || sysctl(mib, 4, &info, &size, NULL, 0) != 0 ||
        size != sizeof(info) || info.kp_proc.p_pid != pid) return 3;
    printf("{\"pid\":%d,\"ppid\":%d,\"uid\":%u,\"gid\":%u,"
           "\"ruid\":%u,\"rgid\":%u,\"svuid\":%u,\"svgid\":%u,"
           "\"seconds\":%lld,\"micros\":%d}\n",
           info.kp_proc.p_pid, info.kp_eproc.e_ppid,
           info.kp_eproc.e_ucred.cr_uid, info.kp_eproc.e_ucred.cr_groups[0],
           info.kp_eproc.e_pcred.p_ruid, info.kp_eproc.e_pcred.p_rgid,
           info.kp_eproc.e_pcred.p_svuid, info.kp_eproc.e_pcred.p_svgid,
           (long long)info.kp_proc.p_starttime.tv_sec,
           info.kp_proc.p_starttime.tv_usec);
    return 0;
}
