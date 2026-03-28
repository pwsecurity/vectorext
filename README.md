# Vector AI — Local Server Setup (Windows)

Run Vector AI **on your own computer** instead of the cloud. Faster, works offline (after login), no lag!

---

## 📋 What You Need Before Starting

1. **Windows 10 or 11** computer
2. **Internet connection** (for initial setup and first login only)
3. **Vector Chrome Extension** already installed in your browser
4. **Vector Device Manager** already installed ([download here](https://github.com/pwsecurity/vectorext/tree/main/VectorDeviceManager_Win))

---

## 🚀 Installation (One-Time Setup)

### Step 1: Open Windows Terminal

- **Right-click** on the **Start button** (Windows logo, bottom-left corner)
- Click **"Terminal"** or **"Windows PowerShell"**

> 💡 **Can't find it?** Press `Win + X` on your keyboard, then click "Terminal"

### Step 2: Copy and Paste This Command

Copy this entire line (click the copy button on the right):

```
powershell -Command "irm https://raw.githubusercontent.com/pwsecurity/vectorext/main/VectorLocalServer/VectorServerSetup.ps1 | iex"
```

### Step 3: Paste into Terminal

- **Right-click** inside the Terminal window (this pastes the command)
- Press **Enter**

### Step 4: Wait

- If it asks "Do you want to allow this app to make changes?" → Click **Yes**
- The installer will:
  - ✅ Check if Python is installed (installs it if missing)
  - ✅ Download server files
  - ✅ Install required packages
  - ✅ Create a shortcut on your Desktop
- **Wait about 2-3 minutes** on first install

### Step 5: Done!

You will see a **"Installation Complete!"** message. You're ready!

---

## 🖱️ How to Use (Every Day)

### Starting the Server

1. **Double-click** the **"Vector Server"** icon on your Desktop
2. A black terminal window will open showing: `Vector AI Local Server Running on http://localhost:5002`
3. **Keep this window open** while using Vector

### Using the Extension

1. Open **Google Chrome**
2. Click the **Vector extension** icon
3. **Login** with your email and password (same as before)
4. Start chatting! 🎉

> 💡 The extension **automatically detects** your local server. You don't need to change any settings!

### Stopping the Server

- Just **close the black terminal window** (click the X button)
- Or **shut down your computer** — the server stops automatically

### Next Day

- **Double-click** the "Vector Server" shortcut again
- That's it!

---

## ❓ Troubleshooting

### "Python is not recognized"
- Restart your computer after the installer finishes
- Run the installer command again

### "Server unreachable" in extension
- Make sure the black terminal window is still open
- Make sure it says "Running on http://localhost:5002"

### "Access denied" or "No API keys"
- Login to the extension first
- Make sure you have API keys saved in the extension's Key settings

### Extension still connecting to the cloud
- Close and reopen the Chrome extension
- The extension checks for local server every time it opens

---

## 📁 File Locations

| What | Where |
|------|-------|
| Server files | `C:\VectorAI\Server\` |
| Desktop shortcut | `Desktop\Vector Server.lnk` |
| Python | Auto-installed to default location |

---

## 🔄 Updating

To update the server, just run the install command again. It will download the latest files and overwrite the old ones. Your settings and login are not affected.
