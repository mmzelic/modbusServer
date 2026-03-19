import tkinter as tk
import threading
import asyncio
import sys

# ============================================================================
# DYNAMIC PYMODBUS IMPORTS (Universal Adapter)
# ============================================================================
try:
    from pymodbus.server import StartAsyncTcpServer, ServerAsyncStop
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext
    try:
        from pymodbus.datastore import ModbusDeviceContext as ContextClass
    except ImportError:
        try:
            from pymodbus.datastore import ModbusSlaveContext as ContextClass
        except ImportError:
            from pymodbus.datastore.context import ModbusSlaveContext as ContextClass
except ImportError as e:
    print(f"FATAL IMPORT ERROR: {e}")
    sys.exit(1)

# --- DATA MAPPING ---
BIT_MAPPING = {
    0: {0: "Err Reset", 1: "Proc Reset"},
    1: {0: "Heartbeat", 9: "GunTrigger"},
    2: {0: "Mix Mode", 1: "Color Req"},
    3: {0: "Est En", 1: "Est Rst", 2: "Est Rem"},
    200: {0: "Safety ESTOP"},
    201: {0: "Gun Open"},
    203: {0: "Safe Move", 1: "Estat Error"}
}

ANALOG_MAPPING = {
    10: "Atom Air", 11: "Fan Air", 12: "Flow SP", 13: "Volt SP", 20: "Recipe",
    210: "PLC Step", 211: "Err[0]", 212: "Err[1]", 213: "Err[2]", 214: "Err[3]",
    220: "Atom Ret", 221: "Fan Ret", 222: "Flow Ret", 223: "Volt FB", 231: "Act Recp"
}

# --- UNIFIED MODERN "TECH" COLOR PALETTE ---
BG_MAIN = "#ecf0f1"          
COLOR_ON = "#00b894"         
COLOR_OFF = "#d63031"        
COLOR_READONLY = "#2c3e50"   # Midnight Blue
COLOR_READWRITE = "#2c3e50"  # Unified Midnight Blue

class ModbusGUISimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Modern Modbus Server Dashboard")
        self.root.geometry("1280x800") 
        self.root.configure(bg=BG_MAIN)
        
        # Internal Data Store
        self.store = ModbusSequentialDataBlock(0, [0] * 300)
        self.device_context = ContextClass(hr=self.store)
        
        try: self.server_context = ModbusServerContext(slaves=self.device_context, single=True)
        except TypeError:
            try: self.server_context = ModbusServerContext(device_ids=self.device_context, single=True)
            except TypeError: self.server_context = ModbusServerContext(devices=self.device_context, single=True)

        self.is_online = False
        self.loop = None 
        
        self.bit_uis = {}
        self.analog_uis = {}
        
        self.setup_ui()

    # --- UI SETUP ---
    def setup_ui(self):
        # 1. HEADER
        hdr = tk.Frame(self.root, bg="#1e272e", pady=8, padx=15)
        hdr.pack(fill="x")
        
        tk.Label(hdr, text="MODBUS SERVER", bg="#1e272e", fg="#00b894", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 20))
        
        tk.Label(hdr, text="IP:", bg="#1e272e", fg="white", font=("Arial", 9, "bold")).pack(side="left")
        self.ip_entry = tk.Entry(hdr, width=14, font=("Arial", 10), bd=0, relief="flat")
        self.ip_entry.insert(0, "0.0.0.0")
        self.ip_entry.pack(side="left", padx=(5, 15), ipady=3)
        
        tk.Label(hdr, text="Port:", bg="#1e272e", fg="white", font=("Arial", 9, "bold")).pack(side="left")
        self.port_entry = tk.Entry(hdr, width=6, font=("Arial", 10), bd=0, relief="flat")
        self.port_entry.insert(0, "502")
        self.port_entry.pack(side="left", padx=(5, 15), ipady=3)
        
        self.btn_online = tk.Button(hdr, text="🔌 GO ONLINE", bg="#f39c12", fg="white", font=("Arial", 9, "bold"), 
                                    relief="flat", cursor="hand2", padx=10, pady=2, command=self.toggle_server)
        self.btn_online.pack(side="left")
        
        self.status_lbl = tk.Label(hdr, text="STATUS: OFFLINE", bg="#1e272e", fg="#e84118", font=("Arial", 10, "bold"))
        self.status_lbl.pack(side="right", padx=10)

        # 2. MAIN STATIC CONTAINER (Replaced Scrollbar logic)
        self.main_frame = tk.Frame(self.root, bg=BG_MAIN)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # =========================================================
        # SECTION 1: SnX to PLC (Server Monitor)
        # =========================================================
        sec1 = tk.Frame(self.main_frame, bg="white", bd=1, relief="solid")
        sec1.pack(fill="x", pady=(0, 10))
        tk.Label(sec1, text="SnX to PLC (Server Read-Only)", bg=COLOR_READONLY, fg="white", font=("Arial", 11, "bold"), pady=6).pack(fill="x")
        
        ro_bits = [r for r in BIT_MAPPING.keys() if r < 200]
        ro_analogs = [r for r in ANALOG_MAPPING.keys() if r < 200]
        self.build_bit_grid(sec1, ro_bits, is_writable=False)
        self.build_analog_grid(sec1, ro_analogs, is_writable=False)

        # =========================================================
        # SECTION 2: PLC to SnX (Server Override Control)
        # =========================================================
        sec2 = tk.Frame(self.main_frame, bg="white", bd=1, relief="solid")
        sec2.pack(fill="x", pady=(0, 10))
        
        # Added a helpful hint for the new "Enter to Save" analog feature
        hdr2 = tk.Frame(sec2, bg=COLOR_READWRITE)
        hdr2.pack(fill="x")
        tk.Label(hdr2, text="PLC to SnX (Server Override)", bg=COLOR_READWRITE, fg="white", font=("Arial", 11, "bold"), pady=6).pack(side="left", padx=10)
        tk.Label(hdr2, text="💡 Tip: Press ENTER to apply analog values", bg=COLOR_READWRITE, fg="#dcdde1", font=("Arial", 8, "italic")).pack(side="right", padx=10)

        rw_bits = [r for r in BIT_MAPPING.keys() if r >= 200]
        rw_analogs = [r for r in ANALOG_MAPPING.keys() if r >= 200]
        self.build_bit_grid(sec2, rw_bits, is_writable=True)
        self.build_analog_grid(sec2, rw_analogs, is_writable=True)

    # --- UI COMPONENT BUILDERS ---
    def build_bit_grid(self, parent, registers, is_writable):
        if not registers: return
        
        grid_frame = tk.Frame(parent, bg="white")
        grid_frame.pack(fill="x", padx=10, pady=5)
        
        cols = 2 
        r, c = 0, 0
        
        for reg in sorted(registers):
            header_color = COLOR_READWRITE if is_writable else COLOR_READONLY
            
            lf = tk.Frame(grid_frame, bg="#f8f9fa", highlightbackground="#dcdde1", highlightthickness=1)
            lf.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
            grid_frame.grid_columnconfigure(c, weight=1) 
            
            hdr_frame = tk.Frame(lf, bg=header_color)
            hdr_frame.pack(fill="x")
            
            tk.Label(hdr_frame, text=f" Reg {reg}", bg=header_color, fg="white", font=("Arial", 9, "bold"), anchor="w").pack(side="left", fill="x", expand=True, pady=3)
            reg_val_lbl = tk.Label(hdr_frame, text="Current: 0", bg=header_color, fg="#ffffff", font=("Courier", 9, "bold"))
            reg_val_lbl.pack(side="right", padx=8)
            
            bit_container = tk.Frame(lf, bg="#f8f9fa")
            bit_container.pack(fill="x", pady=4, padx=4)
            
            row_items = []
            for b in range(16):
                name = BIT_MAPPING[reg].get(b, str(b))
                cursor_type = "hand2" if is_writable else "arrow"
                
                f = tk.Frame(bit_container, bd=0, bg=COLOR_OFF, cursor=cursor_type)
                f.pack(side="right", expand=True, fill="both", padx=1)
                
                lbl = tk.Label(f, text=name, font=("Arial", 7, "bold"), bg=COLOR_OFF, fg="white", 
                               height=2, wraplength=55, cursor=cursor_type)
                lbl.pack(fill="both", expand=True, pady=1)
                
                if is_writable:
                    f.bind("<Button-1>", self.make_bit_toggler(reg, b))
                    lbl.bind("<Button-1>", self.make_bit_toggler(reg, b))
                
                row_items.append({"lbl": lbl, "frame": f, "named": b in BIT_MAPPING[reg]})
            
            self.bit_uis[reg] = {"bits": row_items[::-1], "val_lbl": reg_val_lbl}
            
            c += 1
            if c >= cols:
                c = 0
                r += 1

    def build_analog_grid(self, parent, registers, is_writable):
        if not registers: return
        grid = tk.Frame(parent, bg="white")
        grid.pack(fill="x", padx=10, pady=(4, 10))
        r, c = 0, 0
        for reg in sorted(registers):
            border_color = COLOR_READWRITE if is_writable else COLOR_READONLY
            
            f = tk.Frame(grid, bg="#f5f6fa", highlightbackground=border_color, highlightthickness=1)
            f.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            grid.grid_columnconfigure(c, weight=1) 
            
            hdr = tk.Frame(f, bg="#dcdde1")
            hdr.pack(fill="x")
            tk.Label(hdr, text=f"Reg {reg}", font=("Arial", 8, "bold"), bg="#dcdde1", fg="#2f3640").pack(side="left", padx=5, pady=2)
            
            tk.Label(f, text=ANALOG_MAPPING[reg], font=("Arial", 9, "bold"), bg="#f5f6fa", fg="#2f3640", wraplength=110).pack(pady=6)
            
            if is_writable:
                entry = tk.Entry(f, font=("Courier", 12, "bold"), fg=COLOR_READWRITE, width=8, justify="center", bd=1, relief="solid")
                entry.pack(pady=(0, 8))
                
                # Bind the ENTER key to save the analog value seamlessly
                entry.bind("<Return>", lambda e, r=reg, ent=entry: self.write_analog(r, ent))
                self.analog_uis[reg] = {"type": "rw", "entry": entry}
            else:
                l = tk.Label(f, text="0", font=("Courier", 12, "bold"), fg=COLOR_READONLY, bg="white", width=7, bd=1, relief="solid", pady=2)
                l.pack(pady=(0, 8))
                self.analog_uis[reg] = {"type": "ro", "lbl": l}
            
            c += 1
            if c > 5: 
                c = 0; r += 1

    # --- SERVER START / STOP LOGIC ---
    def toggle_server(self):
        if self.is_online:
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(ServerAsyncStop)
                
            self.is_online = False
            self.ip_entry.config(state="normal")
            self.port_entry.config(state="normal")
            self.btn_online.config(text="🔌 GO ONLINE", bg="#f39c12")
            self.status_lbl.config(text="STATUS: OFFLINE", fg="#e84118")
        else:
            self.target_ip = self.ip_entry.get()
            try: self.target_port = int(self.port_entry.get())
            except ValueError:
                self.status_lbl.config(text="ERROR: BAD PORT", fg="#e84118")
                return

            self.is_online = True
            self.ip_entry.config(state="disabled")
            self.port_entry.config(state="disabled")
            self.btn_online.config(text="🔴 GO OFFLINE", bg="#e84118")
            self.status_lbl.config(text="STATUS: RUNNING", fg="#00b894")
            
            self.server_thread = threading.Thread(target=self.run_server, daemon=True)
            self.server_thread.start()
            self.update_gui()

    def run_server(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try: self.loop.run_until_complete(StartAsyncTcpServer(context=self.server_context, address=(self.target_ip, self.target_port)))
        except Exception as e: print(f"Server Error: {e}")

    # ========================================================================
    # DATA ACCESS METHODS 
    # ========================================================================
    def get_safe_values(self):
        if hasattr(self.store, 'getValues'): return self.store.getValues(1, 250) 
        offset = 1 if len(self.store.values) > 300 else 0
        return self.store.values[offset + 1 : offset + 251]

    def read_register(self, reg):
        target = reg + 1
        if hasattr(self.store, 'getValues'): return self.store.getValues(target, 1)[0]
        offset = 1 if len(self.store.values) > 300 else 0
        return self.store.values[target + offset]

    def write_register(self, reg, val):
        target = reg + 1
        if hasattr(self.store, 'setValues'): self.store.setValues(target, [val])
        else:
            offset = 1 if len(self.store.values) > 300 else 0
            self.store.values[target + offset] = val

    # --- INTERACTION METHODS ---
    def make_bit_toggler(self, reg, bit):
        def toggle(event):
            if not self.is_online: return 
            current_val = self.read_register(reg)
            new_val = current_val ^ (1 << bit)
            self.write_register(reg, new_val)
        return toggle

    def write_analog(self, reg, entry_widget):
        if not self.is_online: return
        try:
            val = int(entry_widget.get())
            if val < 0: val = 0 
            if val > 65535: val = 65535
            self.write_register(reg, val)
            
            # Remove focus so the UI updates and flashes instantly to prove it saved
            self.root.focus_set()
        except ValueError: pass

    # --- GUI UPDATE LOOP ---
    def update_gui(self):
        if not self.is_online: 
            return
            
        try:
            vals = self.get_safe_values()
                
            for reg, data in self.bit_uis.items():
                rv = vals[reg]
                
                if data["val_lbl"].cget("text") != f"Current: {rv}":
                    data["val_lbl"].config(text=f"Current: {rv}")
                
                for i in range(16):
                    active = (rv >> i) & 1
                    ui = data["bits"][15-i]
                    bg_color = COLOR_ON if active else COLOR_OFF
                    
                    if ui["lbl"].cget("bg") != bg_color:
                        ui["lbl"].config(bg=bg_color)
                        ui["frame"].config(bg=bg_color)
                    
            for reg, ui in self.analog_uis.items():
                current_val = vals[reg]
                if ui["type"] == "ro":
                    ui["lbl"].config(text=str(current_val))
                elif ui["type"] == "rw":
                    entry = ui["entry"]
                    if self.root.focus_get() != entry:
                        if entry.get() != str(current_val):
                            entry.delete(0, tk.END)
                            entry.insert(0, str(current_val))
        except Exception:
            pass
            
        self.root.after(150, self.update_gui)

if __name__ == "__main__":
    root = tk.Tk()
    app = ModbusGUISimulator(root)
    root.mainloop()