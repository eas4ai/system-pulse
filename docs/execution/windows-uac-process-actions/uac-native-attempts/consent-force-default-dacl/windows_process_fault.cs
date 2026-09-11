// Fault injection only for a fixture we created or an identity-validated helper.
// This file is never part of the application or its elevated entry point.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;

public sealed class PulseOwnedProcessFault : IDisposable
{
    [StructLayout(LayoutKind.Sequential)]
    struct Luid { public uint Low; public int High; }
    [StructLayout(LayoutKind.Sequential)]
    struct TokenPrivilege { public uint Count; public Luid Luid; public uint Attributes; }
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool LookupPrivilegeValue(string system, string name, out Luid luid);
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool AdjustTokenPrivileges(IntPtr token, bool disableAll, ref TokenPrivilege privilege, uint length, IntPtr previous, IntPtr required);
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimits
    {
        public long ProcessTime, JobTime;
        public uint Flags;
        public UIntPtr MinimumWorkingSet, MaximumWorkingSet;
        public uint ActiveProcesses;
        public UIntPtr Affinity;
        public uint Priority, Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters
    {
        public ulong ReadOperations, WriteOperations, OtherOperations;
        public ulong ReadBytes, WriteBytes, OtherBytes;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct ExtendedLimits
    {
        public BasicLimits Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr security, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(IntPtr job, int kind, ref ExtendedLimits limits, uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, uint id);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenThread(uint access, bool inherit, uint id);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint GetProcessIdOfThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint SuspendThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateProcess(IntPtr process, uint code);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint WaitForSingleObject(IntPtr process, uint milliseconds);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr handle);
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool GetKernelObjectSecurity(IntPtr handle, uint information, byte[] descriptor, uint length, out uint needed);
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool SetKernelObjectSecurity(IntPtr handle, uint information, byte[] descriptor);

    readonly Process process;
    readonly IntPtr handle;
    readonly List<IntPtr> suspended = new List<IntPtr>();
    IntPtr job;

    public static void RemoveObserverDebugPrivilege()
    {
        // SSH and .NET Framework diagnostics can begin with debug privilege
        // enabled. Remove it from this disposable observer token so neither
        // inherited privileges nor later .NET initialization can bypass a DACL.
        Luid luid;
        if (!LookupPrivilegeValue(null, "SeDebugPrivilege", out luid)) throw new Win32Exception();
        IntPtr token;
        if (!OpenProcessToken(new IntPtr(-1), 0x20, out token)) throw new Win32Exception();
        try
        {
            var privilege = new TokenPrivilege { Count = 1, Luid = luid, Attributes = 4 };
            if (!AdjustTokenPrivileges(token, false, ref privilege, 0, IntPtr.Zero, IntPtr.Zero)) throw new Win32Exception();
            int error = Marshal.GetLastWin32Error();
            // ERROR_NOT_ALL_ASSIGNED means it was already absent from this token.
            if (error != 0 && error != 1300) throw new Win32Exception(error);
        }
        finally { if (!CloseHandle(token)) throw new Win32Exception(); }
    }

    public PulseOwnedProcessFault(Process ownedProcess)
    {
        process = ownedProcess;
        using (var current = Process.GetCurrentProcess())
            if (process.Id == current.Id) throw new InvalidOperationException("Cannot fault the observer");
        handle = process.Handle;
        RequireLive();
        job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new Win32Exception();
        try
        {
            var limits = new ExtendedLimits();
            limits.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if (!SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(limits))) throw new Win32Exception();
            if (!AssignProcessToJobObject(job, handle)) throw new Win32Exception();
        }
        catch { CloseHandle(job); job = IntPtr.Zero; throw; }
    }

    void RequireLive()
    {
        if (WaitForSingleObject(handle, 0) != 258) throw new InvalidOperationException("Owned process has exited");
    }

    public void DenyNewTerminationHandles()
    {
        RequireLive();
        uint needed;
        GetKernelObjectSecurity(handle, 4, null, 0, out needed);
        if (needed == 0 || needed > 65536) throw new InvalidOperationException("Invalid owned process DACL size");
        var bytes = new byte[needed];
        if (!GetKernelObjectSecurity(handle, 4, bytes, needed, out needed)) throw new Win32Exception();
        var descriptor = new RawSecurityDescriptor(bytes, 0);
        if (descriptor.DiscretionaryAcl == null) throw new InvalidOperationException("Owned process has no explicit DACL");
        descriptor.DiscretionaryAcl.InsertAce(0, new CommonAce(AceFlags.None, AceQualifier.AccessDenied, 1,
            new SecurityIdentifier(WellKnownSidType.WorldSid, null), false, null));
        bytes = new byte[descriptor.BinaryLength];
        descriptor.GetBinaryForm(bytes, 0);
        if (!SetKernelObjectSecurity(handle, 4, bytes)) throw new Win32Exception();
    }

    public int NewTerminationAccessError()
    {
        RequireLive();
        IntPtr probe = OpenProcess(0x101001, false, (uint)process.Id);
        if (probe == IntPtr.Zero) return Marshal.GetLastWin32Error();
        if (!CloseHandle(probe)) throw new Win32Exception();
        return 0;
    }

    public int Suspend()
    {
        RequireLive();
        if (suspended.Count != 0) throw new InvalidOperationException("Owned process is already suspended by this test");
        process.Refresh();
        var threads = process.Threads;
        if (threads.Count == 0 || threads.Count > 256) throw new InvalidOperationException("Unexpected helper thread count");
        try
        {
            foreach (ProcessThread thread in threads)
            {
                IntPtr pinned = OpenThread(0x802, false, (uint)thread.Id);
                if (pinned == IntPtr.Zero) throw new Win32Exception();
                try
                {
                    // Check ownership on the pinned thread and the still-live
                    // pinned process before modifying any thread state.
                    if (GetProcessIdOfThread(pinned) != (uint)process.Id) throw new InvalidOperationException("Thread owner changed");
                    RequireLive();
                    uint previous = SuspendThread(pinned);
                    if (previous == UInt32.MaxValue) throw new Win32Exception();
                    suspended.Add(pinned);
                    pinned = IntPtr.Zero;
                    if (previous != 0) throw new InvalidOperationException("Thread was already suspended");
                }
                finally { if (pinned != IntPtr.Zero && !CloseHandle(pinned)) throw new Win32Exception(); }
            }
            return suspended.Count;
        }
        catch { Resume(); throw; }
        finally { foreach (ProcessThread thread in threads) thread.Dispose(); }
    }

    public void Resume()
    {
        Exception failure = null;
        foreach (IntPtr thread in suspended)
        {
            if (ResumeThread(thread) == UInt32.MaxValue) failure = new Win32Exception();
            if (!CloseHandle(thread)) failure = new Win32Exception();
        }
        suspended.Clear();
        if (failure != null) throw failure;
    }

    public void Crash()
    {
        RequireLive();
        if (!TerminateProcess(handle, 0xC0000001)) throw new Win32Exception();
        if (WaitForSingleObject(handle, 5000) != 0) throw new InvalidOperationException("Owned helper survived injected failure");
    }

    public void Dispose()
    {
        Exception failure = null;
        if (job != IntPtr.Zero)
        {
            if (!CloseHandle(job)) failure = new Win32Exception();
            job = IntPtr.Zero;
            if (WaitForSingleObject(handle, 5000) != 0) failure = new InvalidOperationException("Owned fault target survived job cleanup");
        }
        // Closing the job terminates a suspended helper without resuming its
        // request. Windows also closes this job if the observer itself crashes.
        foreach (IntPtr thread in suspended)
            if (!CloseHandle(thread)) failure = new Win32Exception();
        suspended.Clear();
        if (failure != null) throw failure;
    }
}
