using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using System.Net;
using System.Text;
using System.Management;
using System.Threading;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32;
using System.Security.Principal;
using System.Collections.Generic;

namespace VectorAI {
    public class DeviceManager : Form {
        // UI Components
        private Label lblStatus;
        private Panel progressBar;
        private Panel progressFill;
        private System.Windows.Forms.Timer animTimer;
        private int progressVal = 0;
        private bool isReady = false;
        private ListBox logBox;

        // Constants
        private static string AppName = "VectorAI";
        private static string AppDisplayName = "Vector Device Manager";
        private static string InstallPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), AppName);
        private static string ExeName = "VectorDeviceManager.exe";
        private static string FullPath = Path.Combine(InstallPath, ExeName);

        [DllImport("user32.dll")]
        public static extern bool ReleaseCapture();
        [DllImport("user32.dll")]
        public static extern int SendMessage(IntPtr hWnd, int Msg, int wParam, int lParam);

        public DeviceManager(bool isSilent) {
            if (!isSilent) {
                InitializeUI();
            } else {
                this.WindowState = FormWindowState.Minimized;
                this.ShowInTaskbar = false;
                this.Opacity = 0;
            }
        }

        private void InitializeUI() {
            this.FormBorderStyle = FormBorderStyle.None;
            this.Size = new Size(500, 380);
            this.BackColor = Color.FromArgb(12, 14, 20);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.TopMost = true;
            this.ShowInTaskbar = true;

            // Header
            Label lblHeader = new Label() {
                Text = "VECTOR NEURAL BRIDGE",
                ForeColor = Color.FromArgb(76, 201, 240),
                Font = new Font("Segoe UI", 18, FontStyle.Bold),
                Location = new Point(20, 30),
                AutoSize = true
            };

            Label lblSubHeader = new Label() {
                Text = "STEALTH_SYNAPSE_SYSTEM_V4.0",
                ForeColor = Color.FromArgb(100, 116, 139),
                Font = new Font("Consolas", 9),
                Location = new Point(23, 65),
                AutoSize = true
            };

            // Status
            lblStatus = new Label() {
                Text = "PROVISIONING...",
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 10, FontStyle.Bold),
                Location = new Point(20, 120),
                AutoSize = true
            };

            // Progress Bar
            progressBar = new Panel() {
                Location = new Point(20, 150),
                Size = new Size(460, 4),
                BackColor = Color.FromArgb(30, 41, 59)
            };
            progressFill = new Panel() {
                Location = new Point(0, 0),
                Size = new Size(0, 4),
                BackColor = Color.FromArgb(76, 201, 240)
            };
            progressBar.Controls.Add(progressFill);

            // LogBox
            logBox = new ListBox() {
                Location = new Point(20, 175),
                Size = new Size(460, 120),
                BackColor = Color.FromArgb(15, 23, 42),
                ForeColor = Color.FromArgb(148, 163, 184),
                BorderStyle = BorderStyle.None,
                Font = new Font("Consolas", 8)
            };

            // Dragging
            this.MouseDown += (s, e) => {
                if (e.Button == MouseButtons.Left) {
                    ReleaseCapture();
                    SendMessage(Handle, 0xA1, 0x2, 0);
                }
            };

            this.Controls.Add(lblHeader);
            this.Controls.Add(lblSubHeader);
            this.Controls.Add(lblStatus);
            this.Controls.Add(progressBar);
            this.Controls.Add(logBox);

            // Animation Timer
            animTimer = new System.Windows.Forms.Timer() { Interval = 16 };
            animTimer.Tick += (s, e) => {
                if (progressVal < 100) {
                    progressVal++;
                    progressFill.Width = (int)(progressBar.Width * (progressVal / 100.0));
                } else if (!isReady) {
                    isReady = true;
                    lblStatus.Text = "VECTOR ARMED (INVISIBLE)";
                    lblStatus.ForeColor = Color.FromArgb(16, 185, 129);
                    AddLog("[SUCCESS]: Neural Bridge Active.");
                    AddLog("[NOTICE]: This window will hide in 3 seconds.");
                    
                    var waitTimer = new System.Windows.Forms.Timer() { Interval = 3000 };
                    waitTimer.Tick += (st, se) => {
                        this.Hide();
                        waitTimer.Stop();
                    };
                    waitTimer.Start();
                }
            };

            this.Load += async (s, e) => {
                animTimer.Start();
                await RunSetup(false);
            };
        }

        private void AddLog(string msg) {
            if (logBox != null) {
                logBox.Items.Add(msg);
                logBox.TopIndex = logBox.Items.Count - 1;
            }
        }

        private async System.Threading.Tasks.Task RunSetup(bool silent) {
            try {
                // 1. Extreme Cleanup - Kill everything before we even check paths
                // This ensures we can update the EXE even if it's currently running
                string[] ecosystemProcs = { "VectorDeviceManager", "VectorAI", "vector_bridge" };
                foreach (string pName in ecosystemProcs) {
                    foreach (var proc in Process.GetProcessesByName(pName)) {
                        if (proc.Id != Process.GetCurrentProcess().Id) {
                            try { proc.Kill(); Thread.Sleep(100); } catch { }
                        }
                    }
                }

                bool isAdmin = new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator);
                string currentPath = Path.GetFullPath(Process.GetCurrentProcess().MainModule.FileName);
                string targetPath = Path.GetFullPath(FullPath);
                bool isRelocated = currentPath.Equals(targetPath, StringComparison.OrdinalIgnoreCase);

                // If silent mode is ON, we NEVER want to show a message box, even for errors.
                if (silent) {
                    if (isAdmin || isRelocated) {
                        // We are good to go
                    } else {
                        // We can't install if not admin and not silent, just exit
                        Application.Exit();
                        return;
                    }
                } else if (!isAdmin && !isRelocated) {
                    // Only show this if NOT silent and NOT admin and NOT relocated
                    MessageBox.Show("[ARMING_ERROR]: Administrator Privileges Required for Neural Pinning.", AppDisplayName, MessageBoxButtons.OK, MessageBoxIcon.Stop);
                    Application.Exit();
                    return;
                }

                if (!silent) AddLog("[BOOT]: Verifying Environment...");
                
                // 2. Deployment - Only if not already in system core
                if (!isRelocated && isAdmin) {
                    if (!silent) AddLog("[DEPLOY]: Relocating to System Core...");
                    PerformInstallation(currentPath);
                }

                // 4. Persistence & Policies - ONLY if elevated
                if (isAdmin) {
                    if (!silent) AddLog("[SEC]: Locking Persistence Hooks...");
                    RegisterStartup();
                    ApplyStealthAttributes();
                    
                    if (!silent) AddLog("[FIRE]: Synchronizing Policies...");
                    RunCmd("netsh advfirewall firewall delete rule name=\"Vector Hyper-Bridge\"");
                    RunCmd("netsh advfirewall firewall add rule name=\"Vector Hyper-Bridge\" dir=in action=allow protocol=TCP localport=5003-5050");
                }

                // 6. Start Bridge
                Thread bridgeThread = new Thread(() => StartBridge(isAdmin));
                bridgeThread.IsBackground = true;
                bridgeThread.Start();
                
                if (!silent) AddLog("[DONE]: Vector is now permanent.");
            } catch (Exception ex) {
                if (!silent) AddLog("[CRIT]: " + ex.Message);
            }
        }

        private void PerformInstallation(string sourcePath) {
            if (!Directory.Exists(InstallPath)) Directory.CreateDirectory(InstallPath);
            try {
                File.Copy(sourcePath, FullPath, true);
                if (logBox != null) AddLog("[SEC]: Files hidden in local app data.");
                
                // Register Task Scheduler persistence (Double quoted path for spaces)
                string taskCmd = string.Format("schtasks /create /tn \"{0}\" /tr \"\\\"{1}\\\" /silent\" /sc onlogon /rl highest /f", AppName, FullPath);
                RunCmd(taskCmd);
                
                Process.Start(FullPath, "/silent");
                Application.Exit();
            } catch (Exception ex) {
                if (logBox != null) AddLog("[ERROR]: " + ex.Message);
            }
        }

        private void RegisterStartup() {
            try {
                RegistryKey rk = Registry.CurrentUser.OpenSubKey("Software\\Microsoft\\Windows\\CurrentVersion\\Run", true);
                rk.SetValue(AppName, string.Format("\"{0}\" /silent", FullPath));
            } catch { }
        }

        private void ApplyStealthAttributes() {
            try {
                File.SetAttributes(FullPath, FileAttributes.Hidden | FileAttributes.System);
                DirectoryInfo di = new DirectoryInfo(InstallPath);
                di.Attributes = FileAttributes.Hidden | FileAttributes.System;
            } catch { }
        }

        private void RunCmd(string cmd) {
            ProcessStartInfo psi = new ProcessStartInfo("cmd.exe", "/c " + cmd) {
                CreateNoWindow = true, UseShellExecute = false
            };
            Process.Start(psi).WaitForExit();
        }

        private void StartBridge(bool isAdmin) {
            // Aggressively kill ALL potential ecosystem bridges to ensure port 5003 dominance
            string[] ecosystemProcs = { "VectorDeviceManager", "VectorAI", "vector_bridge", "powershell", "cmd" };
            foreach (string pName in ecosystemProcs) {
                foreach (var proc in Process.GetProcessesByName(pName)) {
                    if (proc.Id != Process.GetCurrentProcess().Id) {
                        try { 
                            if (pName == "VectorDeviceManager" || pName == "VectorAI" || pName == "vector_bridge")
                                proc.Kill(); 
                        } catch { }
                    }
                }
            }

            HttpListener listener = null;
            int activePort = -1;

            for (int p = 5003; p <= 5050; p++) {
                try {
                    listener = new HttpListener();
                    if (isAdmin) {
                        // Wildcard allows cross-IP access but needs Admin
                        listener.Prefixes.Add(string.Format("http://+:{0}/", p));
                        listener.Prefixes.Add(string.Format("http://+:{0}/uuid/", p)); 
                    } else {
                        // Standard loopback works WITHOUT Admin
                        listener.Prefixes.Add(string.Format("http://127.0.0.1:{0}/", p));
                        listener.Prefixes.Add(string.Format("http://127.0.0.1:{0}/uuid/", p));
                        listener.Prefixes.Add(string.Format("http://localhost:{0}/", p));
                        listener.Prefixes.Add(string.Format("http://localhost:{0}/uuid/", p));
                    }
                    listener.Start();
                    activePort = p;
                    break;
                } catch { 
                    if (listener != null) listener.Close(); 
                }
            }

            if (activePort == -1) return;

            try {
                while (true) {
                    HttpListenerContext context = listener.GetContext();
                    HttpListenerRequest request = context.Request;
                    HttpListenerResponse response = context.Response;

                    response.Headers.Add("Access-Control-Allow-Origin", "*");
                    response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
                    response.Headers.Add("Access-Control-Allow-Headers", "Content-Type, Accept, X-Requested-With");
                    response.Headers.Add("Access-Control-Max-Age", "86400");

                    if (request.HttpMethod == "OPTIONS") {
                        response.StatusCode = 204;
                    } else {
                        string uuid = GetUUID();
                        string json = string.Format("{{\"success\":true,\"device_id\":\"{0}\"}}", uuid);
                        byte[] buffer = Encoding.UTF8.GetBytes(json);
                        
                        response.ContentType = "application/json";
                        response.ContentLength64 = buffer.Length;
                        response.StatusCode = 200;
                        response.OutputStream.Write(buffer, 0, buffer.Length);
                    }
                    response.Close();
                }
            } catch { }
        }

        private string GetUUID() {
            try {
                foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT SerialNumber FROM Win32_BIOS").Get()) {
                    string s = obj["SerialNumber"].ToString();
                    if (!string.IsNullOrEmpty(s)) return s;
                }
            } catch { }
            return "WIN-ID-" + Guid.NewGuid().ToString().ToUpper().Substring(0, 8);
        }

        [STAThread]
        public static void Main(string[] args) {
            Application.EnableVisualStyles();
            bool silent = false;
            foreach (string arg in args) {
                if (arg.Equals("/silent", StringComparison.OrdinalIgnoreCase)) silent = true;
            }
            
            DeviceManager manager = new DeviceManager(silent);
            if (silent) {
                manager.RunSetup(true).GetAwaiter().GetResult();
                Application.Run();
            } else {
                Application.Run(manager);
            }
        }
    }
}
