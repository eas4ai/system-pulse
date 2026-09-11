// Disposable native GUI target for process-action verification, never application code.
using System;
using System.IO;
using System.Threading;
using System.Windows.Forms;

class SystemPulseProcessFixture : Form
{
    readonly string mode;
    readonly string log;

    SystemPulseProcessFixture(string mode, string log)
    {
        this.mode = mode;
        this.log = log;
        Text = "System Pulse owned process fixture: " + mode;
        Width = 440;
        Height = 110;
        Shown += delegate { File.AppendAllText(log, "ready\n"); };
        // A killed or disconnected harness cannot leave its GUI targets behind.
        var expiry = new System.Windows.Forms.Timer();
        expiry.Interval = 300000;
        expiry.Tick += delegate { File.AppendAllText(log, "fixture-expired\n"); Environment.Exit(3); };
        FormClosed += delegate { expiry.Dispose(); };
        expiry.Start();
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == 0x11) // WM_QUERYENDSESSION: explicitly accept or refuse.
        {
            File.AppendAllText(log, "query-end-session\n");
            if (mode == "delayed" || mode == "refusing-delayed") Thread.Sleep(5000);
            message.Result = mode.StartsWith("refusing") ? IntPtr.Zero : new IntPtr(1);
            return;
        }
        if (message.Msg == 0x16) // WM_ENDSESSION
        {
            File.AppendAllText(log, "end-session:" + message.WParam.ToInt64() + "\n");
            if (message.WParam != IntPtr.Zero && !mode.StartsWith("refusing")) Close();
            return;
        }
        if (message.Msg == 0x10) // WM_CLOSE
        {
            File.AppendAllText(log, "close\n");
            if (mode.StartsWith("refusing")) return;
        }
        base.WndProc(ref message);
    }

    [STAThread]
    static int Main(string[] args)
    {
        if (args.Length != 2 || (args[0] != "cooperative" && args[0] != "refusing" && args[0] != "windowless" && args[0] != "delayed" && args[0] != "refusing-delayed" && args[0] != "heartbeat"))
            return 2;
        if (args[0] == "windowless")
        {
            File.WriteAllText(args[1], "ready\n");
            Thread.Sleep(300000);
        }
        else if (args[0] == "heartbeat")
        {
            File.WriteAllText(args[1], "ready\n");
            for (int index = 0; index < 3000; index++)
            {
                Thread.Sleep(100);
                File.AppendAllText(args[1], "tick\n");
            }
        }
        else Application.Run(new SystemPulseProcessFixture(args[0], args[1]));
        return 0;
    }
}
