// Native observation only. Never shipped with System Pulse or used by its helper.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Management;
using System.Runtime.InteropServices;
using System.Text;

public sealed class PulseProcessTrace : IDisposable
{
    readonly object gate = new object();
    readonly List<Dictionary<string, object>> events = new List<Dictionary<string, object>>();
    readonly ManagementEventWatcher starts;
    readonly ManagementEventWatcher stops;

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetProcessTimes(IntPtr handle, out long creation, out long exit, out long kernel, out long user);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool QueryFullProcessImageName(IntPtr handle, uint flags, StringBuilder path, ref int size);
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool GetTokenInformation(IntPtr token, int kind, out int value, int size, out int length);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CommandLineToArgvW(string commandLine, out int count);
    [DllImport("kernel32.dll")]
    static extern IntPtr LocalFree(IntPtr memory);

    public static long Creation(IntPtr handle)
    {
        long creation, exit, kernel, user;
        if (!GetProcessTimes(handle, out creation, out exit, out kernel, out user)) throw new Win32Exception();
        return creation;
    }

    public static bool Elevated(IntPtr handle)
    {
        IntPtr token;
        if (!OpenProcessToken(handle, 8, out token)) throw new Win32Exception();
        try
        {
            int value, length;
            if (!GetTokenInformation(token, 20, out value, 4, out length)) throw new Win32Exception();
            return value != 0;
        }
        finally { if (!CloseHandle(token)) throw new Win32Exception(); }
    }

    public PulseProcessTrace()
    {
        // Provider timestamps are event times, never process creation identities.
        // Consent events record only lifetime metadata; no credential UI is read.
        string filter = " WHERE ProcessName = 'system-pulse.exe' OR ProcessName = 'consent.exe'";
        starts = new ManagementEventWatcher("SELECT * FROM Win32_ProcessStartTrace" + filter);
        // On the verification host StopTrace truncates this image name to
        // "system-pulse.e". Keep prefix matches and correlate by PID with exact
        // start events; a truncated stop name alone never identifies a helper.
        stops = new ManagementEventWatcher("SELECT * FROM Win32_ProcessStopTrace WHERE ProcessName LIKE 'system-pulse%' OR ProcessName = 'consent.exe'");
        starts.EventArrived += delegate(object sender, EventArrivedEventArgs args) { Record(args.NewEvent, true); };
        stops.EventArrived += delegate(object sender, EventArrivedEventArgs args) { Record(args.NewEvent, false); };
        try { starts.Start(); stops.Start(); }
        catch { starts.Dispose(); stops.Dispose(); throw; }
    }

    void Record(ManagementBaseObject nativeEvent, bool started)
    {
        var row = new Dictionary<string, object>();
        try
        {
            uint pid = Convert.ToUInt32(nativeEvent["ProcessID"]);
            string name = Convert.ToString(nativeEvent["ProcessName"]);
            row["kind"] = started ? "start" : "stop";
            row["pid"] = pid;
            row["parent_pid"] = Convert.ToUInt32(nativeEvent["ParentProcessID"]);
            row["session_id"] = Convert.ToUInt32(nativeEvent["SessionID"]);
            row["name"] = name;
            row["event_ticks"] = Convert.ToUInt64(nativeEvent["TIME_CREATED"]);
            row["observed_utc"] = DateTime.UtcNow.ToString("o");
            if (!started) row["exit_code"] = Convert.ToUInt32(nativeEvent["ExitStatus"]);
            if (started && name.Equals("system-pulse.exe", StringComparison.OrdinalIgnoreCase))
                ObserveLiveProcess(pid, row);
        }
        catch (Exception error) { row["observation_error"] = error.ToString(); }
        finally
        {
            nativeEvent.Dispose();
            lock (gate) { events.Add(row); }
        }
    }

    static void ObserveLiveProcess(uint pid, Dictionary<string, object> row)
    {
        IntPtr handle = OpenProcess(0x1000, false, pid);
        if (handle == IntPtr.Zero)
        {
            // A one-shot helper may have already exited when WMI delivers its event.
            // Preserve that limitation instead of inventing a live token observation.
            row["live_observation_error"] = Marshal.GetLastWin32Error();
            return;
        }
        try
        {
            long creation, exit, kernel, user;
            if (!GetProcessTimes(handle, out creation, out exit, out kernel, out user))
                throw new Win32Exception();
            row["creation_ticks"] = creation;
            var path = new StringBuilder(32768);
            int size = path.Capacity;
            if (!QueryFullProcessImageName(handle, 0, path, ref size)) throw new Win32Exception();
            row["image"] = path.ToString();
            IntPtr token;
            if (!OpenProcessToken(handle, 8, out token)) throw new Win32Exception();
            try
            {
                int value, length;
                if (!GetTokenInformation(token, 20, out value, 4, out length)) throw new Win32Exception();
                row["elevated"] = value != 0;
                if (!GetTokenInformation(token, 18, out value, 4, out length)) throw new Win32Exception();
                row["elevation_type"] = value;
            }
            finally { if (!CloseHandle(token)) row["token_close_failed"] = true; }
            // WMI command lines are not needed for consent.exe and are never read.
            using (var process = new ManagementObject("Win32_Process.Handle='" + pid + "'"))
            {
                process.Get();
                string commandLine = Convert.ToString(process["CommandLine"]);
                if (String.IsNullOrEmpty(commandLine)) throw new InvalidOperationException("No live command line");
                row["command_line"] = commandLine;
                int count;
                IntPtr arguments = CommandLineToArgvW(commandLine, out count);
                if (arguments == IntPtr.Zero) throw new Win32Exception();
                try
                {
                    var values = new string[count];
                    for (int index = 0; index < count; index++)
                        values[index] = Marshal.PtrToStringUni(Marshal.ReadIntPtr(arguments, index * IntPtr.Size));
                    row["argv"] = values;
                }
                finally { if (LocalFree(arguments) != IntPtr.Zero) row["argv_free_failed"] = true; }
            }
        }
        catch (Exception error) { row["live_observation_error"] = error.ToString(); }
        finally { if (!CloseHandle(handle)) row["process_close_failed"] = true; }
    }

    public static Dictionary<string, object> Describe(uint pid)
    {
        var row = new Dictionary<string, object>();
        ObserveLiveProcess(pid, row);
        return row;
    }

    public Dictionary<string, object>[] Snapshot()
    {
        lock (gate) { return events.ToArray(); }
    }

    public void Dispose()
    {
        try { starts.Stop(); }
        finally
        {
            try { stops.Stop(); }
            finally { starts.Dispose(); stops.Dispose(); }
        }
    }
}
