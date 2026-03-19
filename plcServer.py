import tkinter as tk
from tkinter import ttk
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

# --- THEME COLORS ---
BG_MAIN = "#f0f2f5"        
COLOR_ON = "#2ecc71"       
COLOR_OFF = "#e74c3c"      
COLOR_READONLY = "#34495e" 
COLOR_READWRITE = "#8e44ad" 

class ModbusGUISimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Compact Modbus Dashboard")
        self.root.geometry("1050x700") # Reduced default height
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
        self.bind_mouse_wheel()

    # --- UI SETUP ---
    def setup_ui(self):
        # 1. HEADER (Controls) - More compact padding
        hdr = tk.Frame(self.root, bg="#212f3d", pady=5, padx=10)
        hdr.pack(fill="x")
        
        tk.Label(hdr, text="MODBUS SERVER", bg="#212f3d", fg="#f1c40f", font=("Arial", 11, "bold")).pack(side="left", padx=(0, 15))
        
        tk.Label(hdr, text="IP:", bg="#212f3d", fg="white", font=("Arial", 9, "bold")).pack(side="left")
        self.ip_entry = tk.Entry(hdr, width=13, font=("Arial", 9), bd=0, relief="flat")
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack(side="left", padx=(5, 15), ipady=2)
        
        tk.Label(hdr, text="Port:", bg="#212f3d", fg="white", font=("Arial", 9, "bold")).pack(side="left")
        self.port_entry = tk.Entry(hdr, width=5, font=("Arial", 9), bd=0, relief="flat")
        self.port_entry.insert(0, "502")
        self.port_entry.pack(side="left", padx=(5, 15), ipady=2)
        
        self.btn_online = tk.Button(hdr, text="🔌 GO ONLINE", bg="#f39c12", fg="white", font=("Arial", 8, "bold"), 
                                    relief="flat", cursor="hand2", padx=8, command=self.toggle_server)
        self.btn_online.pack(side="left")
        
        self.status_lbl = tk.Label(hdr, text="STATUS: OFFLINE", bg="#212f3d", fg="#e74c3c", font=("Arial", 9, "bold"))
        self.status_lbl.pack(side="right", padx=10)

        # 2. SCROLLING CONTAINER
        cont = tk.Frame(self.root, bg=BG_MAIN)
        cont.pack(fill="both", expand=True, padx=5, pady=5)
        self.canvas = tk.Canvas(cont, bg=BG_MAIN, highlightthickness=0)
        sb = ttk.Scrollbar(cont, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=BG_MAIN)
        
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw", width=self.canvas.winfo_reqwidth())
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas.find_withtag("all")[0], width=e.width))

        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # =========================================================
        # SECTION 1: SnX to PLC (Read Only)
        # =========================================================
        sec1 = tk.Frame(self.scroll_frame, bg="white", bd=1, relief="solid")
        sec1.pack(fill="x", pady=(0, 10))
        
        tk.Label(sec1, text="SnX to PLC", bg=COLOR_READONLY, fg="white", font=("Arial", 11, "bold"), pady=4).pack(fill="x")
        
        ro_bits = [r for r in BIT_MAPPING.keys() if r < 200]
        ro_analogs = [r for r in ANALOG_MAPPING.keys() if r < 200]
        
        self.build_bit_grid(sec1, ro_bits, is_writable=False)
        self.build_analog_grid(sec1, ro_analogs, is_writable=False)

        # =========================================================
        # SECTION 2: PLC to SnX (Writable / Interactive)
        # =========================================================
        sec2 = tk.Frame(self.scroll_frame, bg="white", bd=1, relief="solid")
        sec2.pack(fill="x", pady=(0, 10))
        
        tk.Label(sec2, text="PLC to SnX", bg=COLOR_READWRITE, fg="white", font=("Arial", 11, "bold"), pady=4).pack(fill="x")
        
        rw_bits = [r for r in BIT_MAPPING.keys() if r >= 200]
        rw_analogs = [r for r in ANALOG_MAPPING.keys() if r >= 200]
        
        self.build_bit_grid(sec2, rw_bits, is_writable=True)
        self.build_analog_grid(sec2, rw_analogs, is_writable=True)

    # --- UI COMPONENT BUILDERS ---
    def build_bit_grid(self, parent, registers, is_writable):
        if not registers: return

        for reg in sorted(registers):
            header_color = COLOR_READWRITE if is_writable else COLOR_READONLY
            
            lf = tk.Frame(parent, bg="#f8f9fa", highlightbackground="#e0e0e0", highlightthickness=1)
            lf.pack(fill="x", padx=10, pady=4)
            
            hdr_frame = tk.Frame(lf, bg=header_color)
            hdr_frame.pack(fill="x")
            
            tk.Label(hdr_frame, text=f" Reg {reg}", bg=header_color, fg="white", font=("Arial", 8, "bold"), anchor="w").pack(side="left", fill="x", expand=True, pady=2)
            reg_val_lbl = tk.Label(hdr_frame, text="Current value: 0", bg=header_color, fg="#f1c40f", font=("Courier", 9, "bold"))
            reg_val_lbl.pack(side="right", padx=10)
            
            bit_container = tk.Frame(lf, bg="#f8f9fa")
            bit_container.pack(fill="x", pady=2, padx=4)
            
            row = []
            for b in range(16):
                # Removed "b" prefix, just leave the number if unnamed
                name = BIT_MAPPING[reg].get(b, str(b))
                cursor_type = "hand2" if is_writable else "arrow"
                
                f = tk.Frame(bit_container, bd=0, bg=COLOR_OFF, cursor=cursor_type)
                f.pack(side="right", expand=True, fill="both", padx=1)
                
                # Removed text completely. Fixed width to prevent jittering on click.
                v = tk.Label(f, text="", bg=COLOR_OFF, width=3, height=1, cursor=cursor_type)
                v.pack(pady=(2,0))
                
                tk.Label(f, text=name, font=("Arial", 7), wraplength=45, bg=COLOR_OFF, fg="white", cursor=cursor_type).pack(fill="both", pady=(0,2))
                
                if is_writable:
                    f.bind("<Button-1>", self.make_bit_toggler(reg, b))
                    v.bind("<Button-1>", self.make_bit_toggler(reg, b))
                    for child in f.winfo_children(): child.bind("<Button-1>", self.make_bit_toggler(reg, b))
                
                row.append({"lbl": v, "frame": f, "named": b in BIT_MAPPING[reg], "children": f.winfo_children()})
            
            self.bit_uis[reg] = {"bits": row[::-1], "val_lbl": reg_val_lbl}

    def build_analog_grid(self, parent, registers, is_writable):
        if not registers: return

        grid = tk.Frame(parent, bg="white")
        grid.pack(fill="x", padx=10, pady=(4, 10))
        
        r, c = 0, 0
        for reg in sorted(registers):
            border_color = COLOR_READWRITE if is_writable else COLOR_READONLY
            
            f = tk.Frame(grid, bg="#f8f9fa", highlightbackground=border_color, highlightthickness=1)
            f.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
            grid.grid_columnconfigure(c, weight=1) 
            
            hdr = tk.Frame(f, bg="#eaeded")
            hdr.pack(fill="x")
            tk.Label(hdr, text=f"Reg {reg}", font=("Arial", 7, "bold"), bg="#eaeded", fg="#7f8c8d").pack(side="left", padx=4, pady=1)
            
            tk.Label(f, text=ANALOG_MAPPING[reg], font=("Arial", 8, "bold"), bg="#f8f9fa", fg="#2c3e50", wraplength=110).pack(pady=4)
            
            if is_writable:
                input_frame = tk.Frame(f, bg="#f8f9fa")
                input_frame.pack(pady=(0, 5))
                entry = tk.Entry(input_frame, font=("Courier", 10, "bold"), width=5, justify="center", bd=1, relief="solid")
                entry.pack(side="left", padx=2)
                btn = tk.Button(input_frame, text="SET", bg=COLOR_READWRITE, fg="white", font=("Arial", 7, "bold"), 
                                relief="flat", cursor="hand2", command=lambda reg=reg, e=entry: self.write_analog(reg, e))
                btn.pack(side="left", padx=2)
                self.analog_uis[reg] = {"type": "rw", "entry": entry}
            else:
                l = tk.Label(f, text="0", font=("Courier", 11, "bold"), fg="#2980b9", bg="white", width=6, bd=1, relief="solid", pady=1)
                l.pack(pady=(0, 6))
                self.analog_uis[reg] = {"type": "ro", "lbl": l}
            
            c += 1
            if c > 5: # Fit 6 across now
                c = 0; r += 1

    # --- MOUSE WHEEL SCROLLING ---
    def bind_mouse_wheel(self):
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        if event.num == 4: self.canvas.yview_scroll(-1, "units")
        elif event.num == 5: self.canvas.yview_scroll(1, "units")
        else: self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # --- SERVER START / STOP LOGIC ---
    def toggle_server(self):
        if self.is_online:
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(ServerAsyncStop)
                
            self.is_online = False
            self.ip_entry.config(state="normal")
            self.port_entry.config(state="normal")
            self.btn_online.config(text="🔌 GO ONLINE", bg="#f39c12")
            self.status_lbl.config(text="STATUS: OFFLINE", fg="#e74c3c")
        else:
            self.target_ip = self.ip_entry.get()
            try: self.target_port = int(self.port_entry.get())
            except ValueError:
                self.status_lbl.config(text="ERROR: BAD PORT")
                return

            self.is_online = True
            self.ip_entry.config(state="disabled")
            self.port_entry.config(state="disabled")
            self.btn_online.config(text="🔴 GO OFFLINE", bg="#e74c3c")
            self.status_lbl.config(text="STATUS: RUNNING", fg="#2ecc71")
            
            self.server_thread = threading.Thread(target=self.run_server, daemon=True)
            self.server_thread.start()
            self.update_gui()

    def run_server(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try: self.loop.run_until_complete(StartAsyncTcpServer(context=self.server_context, address=(self.target_ip, self.target_port)))
        except Exception as e: print(f"Server Error: {e}")

    # ========================================================================
    # FIXED: ALIGNED DATA ACCESS METHODS (+1 SHIFT)
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
        except ValueError: pass

    # --- GUI UPDATE LOOP ---
    def update_gui(self):
        if not self.is_online: return
        try:
            vals = self.get_safe_values()
                
            for reg, data in self.bit_uis.items():
                rv = vals[reg]
                
                if data["val_lbl"].cget("text") != f"Current value: {rv}":
                    data["val_lbl"].config(text=f"Current value: {rv}")
                
                for i in range(16):
                    active = (rv >> i) & 1
                    ui = data["bits"][15-i]
                    bg_color = COLOR_ON if active else COLOR_OFF
                    
                    # Check background color instead of text to update, since text is removed
                    if ui["lbl"].cget("bg") != bg_color:
                        ui["lbl"].config(bg=bg_color)
                        ui["frame"].config(bg=bg_color)
                        for child in ui["children"]: child.config(bg=bg_color)
                    
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