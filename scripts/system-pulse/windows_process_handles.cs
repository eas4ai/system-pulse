// Native verification only. Capture the owned dashboard's handle table, never
// process memory, thread contexts, window pixels or unrelated process state.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class PulseProcessHandles
{
    // PSS_HANDLE_ENTRY from the Windows SDK, for the x64 package under test.
    // Only documented fields are read. Object names are never read or retained.
    [StructLayout(LayoutKind.Explicit, Size = 136)]
    struct HandleEntry
    {
        [FieldOffset(0)] public IntPtr Handle;
        [FieldOffset(8)] public uint Flags;
        [FieldOffset(12)] public uint ObjectType;
        [FieldOffset(28)] public uint GrantedAccess;
        [FieldOffset(56)] public ushort TypeNameLength;
        [FieldOffset(64)] public IntPtr TypeName;
        [FieldOffset(116)] public uint ProcessId;
    }
    [DllImport("kernel32.dll")]
    static extern uint PssCaptureSnapshot(IntPtr process, uint flags, uint context, out IntPtr snapshot);
    [DllImport("kernel32.dll")]
    static extern uint PssWalkMarkerCreate(IntPtr allocator, out IntPtr marker);
    [DllImport("kernel32.dll")]
    static extern uint PssWalkMarkerFree(IntPtr marker);
    [DllImport("kernel32.dll")]
    static extern uint PssWalkSnapshot(IntPtr snapshot, int kind, IntPtr marker, out HandleEntry entry, uint size);
    [DllImport("kernel32.dll")]
    static extern uint PssFreeSnapshot(IntPtr process, IntPtr snapshot);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint GetProcessId(IntPtr process);
    [DllImport("kernel32.dll")]
    static extern uint WaitForSingleObject(IntPtr process, uint milliseconds);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool DuplicateHandle(IntPtr source, IntPtr handle, IntPtr destination,
        out IntPtr copy, uint access, bool inherit, uint options);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr handle);

    static uint ProcessIdFromHandle(IntPtr dashboard, HandleEntry entry, ref int nonduplicable, ref int closed)
    {
        if (entry.ObjectType == 1 && (entry.Flags & 9) == 9 && entry.ProcessId != 0) return entry.ProcessId;
        if ((entry.Flags & 1) != 0 && entry.TypeName != IntPtr.Zero)
        {
            if (entry.TypeNameLength == 0 || entry.TypeNameLength > 256 || entry.TypeNameLength % 2 != 0)
                throw new InvalidOperationException("Invalid native handle type name");
            string type = Marshal.PtrToStringUni(entry.TypeName, entry.TypeNameLength / 2).TrimEnd('\0');
            if (type != "Process") return 0;
        }
        // PSS cannot supply a PID for a synchronization-only process handle.
        // Resolve the pinned object through an observer-owned duplicate. Never
        // close the source handle or enable a privilege in either process.
        IntPtr copy;
        if (!DuplicateHandle(dashboard, entry.Handle, new IntPtr(-1), out copy, 0, false, 2))
        {
            int error = Marshal.GetLastWin32Error();
            if (error == 6) { closed++; return 0; } // The source handle was closed.
            // Process handles support duplication. Nonduplicable private handle
            // types cannot be the process handle returned by ShellExecuteExW.
            if (error == 50) { nonduplicable++; return 0; }
            throw new Win32Exception(error);
        }
        try
        {
            uint pid = GetProcessId(copy);
            if (pid != 0) return pid;
            int error = Marshal.GetLastWin32Error();
            if (error == 6) return 0; // A valid duplicate of a non-process object.
            if (error != 5) throw new Win32Exception(error);
            IntPtr query;
            if (!DuplicateHandle(new IntPtr(-1), copy, new IntPtr(-1), out query, 0x1000, false, 0))
                throw new Win32Exception();
            try
            {
                pid = GetProcessId(query);
                if (pid == 0) throw new Win32Exception();
                return pid;
            }
            finally { if (!CloseHandle(query)) throw new Win32Exception(); }
        }
        finally { if (!CloseHandle(copy)) throw new Win32Exception(); }
    }

    public static Dictionary<string, object> Capture(IntPtr dashboard, uint[] ownedPids)
    {
        if (IntPtr.Size != 8) throw new InvalidOperationException("Handle observation requires the x64 package");
        if (ownedPids == null || ownedPids.Length == 0 || ownedPids.Length > 16)
            throw new ArgumentException("Expected bounded owned process identities");
        var counts = new Dictionary<uint, int[]>();
        foreach (uint pid in ownedPids)
        {
            if (pid == 0 || counts.ContainsKey(pid)) throw new ArgumentException("Invalid owned PID list");
            counts.Add(pid, new int[2]);
        }
        uint dashboardPid = GetProcessId(dashboard);
        if (dashboardPid == 0) throw new Win32Exception();
        if (WaitForSingleObject(dashboard, 0) != 258)
            throw new InvalidOperationException("Dashboard exited before handle observation");
        IntPtr snapshot, marker = IntPtr.Zero;
        // HANDLES | BASIC | TYPE_SPECIFIC_INFORMATION. Type names are available
        // with these flags; object-name capture is deliberately not requested.
        uint error = PssCaptureSnapshot(dashboard, 0x34, 0, out snapshot);
        if (error != 0) throw new Win32Exception((int)error);
        int scanned = 0, nonduplicable = 0, closed = 0;
        try
        {
            error = PssWalkMarkerCreate(IntPtr.Zero, out marker);
            if (error != 0) throw new Win32Exception((int)error);
            for (;;)
            {
                HandleEntry entry;
                error = PssWalkSnapshot(snapshot, 2, marker, out entry, 136); // PSS_WALK_HANDLES
                if (error == 259) break; // ERROR_NO_MORE_ITEMS
                if (error != 0) throw new Win32Exception((int)error);
                if (++scanned > 100000) throw new InvalidOperationException("Dashboard handle observation exceeded its bound");
                uint processId = ProcessIdFromHandle(dashboard, entry, ref nonduplicable, ref closed);
                int[] count;
                if (!counts.TryGetValue(processId, out count)) continue;
                if ((entry.Flags & 4) == 0)
                    throw new InvalidOperationException("Owned process handle access rights could not be classified");
                count[0]++;
                if ((entry.GrantedAccess & 1) != 0) count[1]++; // PROCESS_TERMINATE
            }
        }
        finally
        {
            uint walkError = marker == IntPtr.Zero ? 0 : PssWalkMarkerFree(marker);
            // The snapshot was allocated in this observer, not in the dashboard.
            uint freeError = PssFreeSnapshot(new IntPtr(-1), snapshot);
            if (walkError != 0 || freeError != 0)
                throw new InvalidOperationException("Native handle snapshot cleanup failed");
        }
        if (WaitForSingleObject(dashboard, 0) != 258)
            throw new InvalidOperationException("Dashboard exited during handle observation");
        if (scanned == 0) throw new InvalidOperationException("Native handle snapshot was empty");
        var rows = new List<Dictionary<string, object>>();
        foreach (uint pid in ownedPids)
            rows.Add(new Dictionary<string, object> {
                { "pid", pid }, { "count", counts[pid][0] }, { "termination_count", counts[pid][1] }
            });
        return new Dictionary<string, object> {
            { "dashboard_pid", dashboardPid }, { "dashboard_alive", true },
            { "captured_utc", DateTime.UtcNow.ToString("o") },
            { "scanned_handles", scanned }, { "unclassified_handles", 0 },
            { "nonduplicable_handles", nonduplicable }, { "closed_during_capture", closed },
            { "snapshot_released", true }, { "process_handles", rows }
        };
    }
}
