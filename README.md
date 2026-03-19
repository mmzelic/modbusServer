# Modern Modbus Server Simulator

A Python-based Modbus TCP server simulator with a live graphical interface. This tool allows developers and integrators to spin up a fully interactive Modbus server to test HMI/SCADA communications across a local network without needing physical PLC hardware.

## Features

* **Asynchronous Server:** Runs a high-performance `asyncio` Modbus TCP server in the background while keeping the GUI perfectly responsive.
* **Real-Time Override Control:** Acts as the "Source of Truth." Clicking a bit or typing an analog value instantly alters the server's datastore, pushing the update to any connected clients.
* **Seamless Analog Entry:** No clunky "Set" buttons. Simply type a value into an analog register and press `ENTER` to commit the change to the server memory.
* **Universal `pymodbus` Compatibility:** Features dynamic imports and context adapters to ensure the server boots successfully regardless of whether you are running `pymodbus` v2.x or v3.x.
* **Unified Aesthetics:** Shares the exact same 1280x800 "Midnight Blue" layout as the client for a cohesive dual-monitor testing experience.

## Prerequisites

* Python 3.7 or higher
* `pymodbus` library

```bash
pip install pymodbus
```

## Usage

1. Run the server script:
   ```bash
   python modbus_server.py
   ```
2. **Configure the Network & Start Server:** * For a connection strictly on the same computer, leave the IP as `127.0.0.1`.
   * **For a connection from a local PC on your network, you should put the IP as `0.0.0.0` and open the ports if necessary.** This binds the server to all network interfaces.
   * Note that when you do this, the actual server IP that clients must connect to will be this local PC's IP address (e.g., `192.168.1.50`).
   * Click **🔌 GO ONLINE**. The status will change to `RUNNING`.
3. **Connect Clients:** You can now connect your SCADA client, HMI, or the companion Client Dashboard to this server.
4. **Simulate PLC Logic:**
   * The top section allows you to view incoming commands from connected clients.
   * The bottom section ("Server Override") allows you to manipulate the data the server is broadcasting. Click bits to toggle them, or type an integer (0-65535) and press `ENTER` to simulate analog sensor changes.
5. **Stop the Server:** Click **🔴 GO OFFLINE** to gracefully shut down the async loop and disconnect clients.

## Troubleshooting

* **Firewall Issues:** If external clients cannot connect when using `0.0.0.0`, ensure that you have opened the target port (default `502`) in your Windows/OS Firewall for inbound connections.
* **Address Already in Use / Permission Denied:** If the server fails to start on port `502`, ensure you are not running another Modbus server. On Linux/macOS, binding to ports below `1024` requires `sudo`. Alternatively, change the port to `5020`.