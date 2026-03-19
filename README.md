# Modern Modbus Server Simulator

A Python-based Modbus TCP server simulator with a live graphical interface. Built to perfectly mirror the aesthetics of the Client Dashboard, this tool allows developers and integrators to test Modbus communications locally without needing physical PLC hardware.

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
2. **Start the Server:** Ensure the IP and Port are set (defaults to `127.0.0.1:502`), then click **🔌 GO ONLINE**. The status will change to `RUNNING`.
3. **Connect Clients:** You can now connect your SCADA client, HMI, or the companion Client Dashboard to this IP and Port.
4. **Simulate PLC Logic:**
   * The top section allows you to view incoming commands from connected clients.
   * The bottom section ("Server Override") allows you to manipulate the data the server is broadcasting. Click bits to toggle them, or type an integer (0-65535) and press `ENTER` to simulate analog sensor changes.
5. **Stop the Server:** Click **🔴 GO OFFLINE** to gracefully shut down the async loop and disconnect clients.

## Troubleshooting

* **Address Already in Use / Permission Denied:** If the server fails to start on port `502`, ensure you are not running another Modbus server. Note: On Linux/macOS, binding to ports below `1024` (like 502) requires `sudo` privileges. Alternatively, change the port to `5020` for local testing.