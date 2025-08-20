import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ICTParserBackend import aggregate_results, write_csv, write_failures_log

class ICTParser(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ICT Parser")
        self.geometry("800x500")
        self.log_folder_path = ""
        self.tests = []
        self.selected_tests = []
        self.rows = []
        self.limits = {}
        self.failures = []
        self.export_failures = tk.BooleanVar(value=True)
        self._show_folder_picker()

    def _show_folder_picker(self):
        for w in self.winfo_children():
            w.destroy()
        picker_frame = ttk.Frame(self)
        picker_frame.pack(pady=(40,10), expand=True)

        instruction = ttk.Label(
            picker_frame,
            text="Select the folder containing your ICT log files.\nAll log files to be parsed should be stored in this folder.",
            wraplength=300,
            justify="left"
        )
        instruction.pack(side="top", pady=(0,10))

        # Choose Folder button (below)
        choose_btn = ttk.Button(picker_frame, text="Choose Folder", command=self._on_choose_folder)
        choose_btn.pack(side="top")

    def _on_choose_folder(self):
        path = filedialog.askdirectory(title="Select folder with log files")
        if not path or not any(os.scandir(path)):
            messagebox.showerror("Error", "Folder cannot be empty. Please select another.")
            return
        self.log_folder_path = path
        filepaths = [os.path.join(path, fn) for fn in os.listdir(path) if not fn.startswith('.')]
        try:
            cols, rows, limits, failures = aggregate_results(filepaths)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to aggregate: {e}")
            return
        self.tests = cols[2:]
        self.rows = rows
        self.limits = limits
        self.failures = failures
        self.selected_tests = []
        self._build_listbox_ui()

    def _build_listbox_ui(self):
        for w in self.winfo_children():
            w.destroy()

        # Search bars with placeholders (unchanged)
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=5)

        self.search_left = tk.StringVar()
        self.search_right = tk.StringVar()

        left_search = ttk.Entry(top_frame, textvariable=self.search_left)
        right_search = ttk.Entry(top_frame, textvariable=self.search_right)

        left_search.insert(0, "Search Available...")
        right_search.insert(0, "Search Selected...")

        def on_focus_in(event, placeholder):
            if event.widget.get() == placeholder:
                event.widget.delete(0, tk.END)

        def on_focus_out(event, placeholder):
            if not event.widget.get():
                event.widget.insert(0, placeholder)
                event.widget.configure(foreground='grey')

        left_search.bind("<FocusIn>",  lambda e: on_focus_in(e, "Search Available..."))
        left_search.bind("<FocusOut>", lambda e: on_focus_out(e, "Search Available..."))
        right_search.bind("<FocusIn>", lambda e: on_focus_in(e, "Search Selected..."))
        right_search.bind("<FocusOut>",lambda e: on_focus_out(e, "Search Selected..."))

        left_search.pack(side="left", fill="x", expand=True, padx=(0,5))
        right_search.pack(side="left", fill="x", expand=True, padx=(5,0))

        self.search_left.trace_add("write", self._filter_left)
        self.search_right.trace_add("write", self._filter_right)

        # Content frame
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True, padx=10, pady=(0,5))

        # Available Tests listbox
        left_frame = ttk.Frame(content)
        left_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(left_frame, text="Available Tests").pack(anchor="w", padx=2, pady=(0,2))
        self.lb_available = tk.Listbox(
            left_frame,
            selectmode=tk.EXTENDED,
            exportselection=False
        )

        self.lb_available.bind("<Button-1>", lambda e: self.lb_available.focus_set())

        scrollbar_av = ttk.Scrollbar(left_frame, orient="vertical", command=self.lb_available.yview)
        self.lb_available.config(yscrollcommand=scrollbar_av.set)
        self.lb_available.pack(side="left", fill="both", expand=True)
        scrollbar_av.pack(side="left", fill="y")

        # Move-buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(side="left", padx=5)
        ttk.Button(btn_frame, text=">",   width=3, command=self._move_one_right).pack(pady=5)
        ttk.Button(btn_frame, text=">>",  width=3, command=self._move_all_right).pack(pady=5)
        ttk.Button(btn_frame, text="<",   width=3, command=self._move_one_left).pack(pady=5)
        ttk.Button(btn_frame, text="<<",  width=3, command=self._move_all_left).pack(pady=5)

        # Selected Tests listbox
        right_frame = ttk.Frame(content)
        right_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(right_frame, text="Selected Tests").pack(anchor="w", padx=2, pady=(0,2))
        self.lb_selected = tk.Listbox(
            right_frame,
            selectmode=tk.EXTENDED,
            exportselection=False
        )
        self.lb_selected.bind("<Button-1>", lambda e: self.lb_selected.focus_set())

        scrollbar_sel = ttk.Scrollbar(right_frame, orient="vertical", command=self.lb_selected.yview)
        self.lb_selected.config(yscrollcommand=scrollbar_sel.set)
        self.lb_selected.pack(side="left", fill="both", expand=True)
        scrollbar_sel.pack(side="left", fill="y")

        # Populate and Export
        self._populate_listboxes()

        # warn if any failed tests were detected in the files parsed
        if getattr(self, 'failures', []):
            n = len(self.failures)
            msg = f"There are {n} failed tests.\nFailed tests can be optionally exported to another CSV."
            messagebox.showwarning("Failed Tests Found", msg)

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=5)

        fail_checkbox = ttk.Checkbutton(
            footer,
            text="Export failures to CSV",
            variable=self.export_failures
        )
        fail_checkbox.pack(side="left", padx=5)

        ttk.Button(footer, text="Export CSV", command=self._on_export).pack(side="right")

    def _populate_listboxes(self):
        available = sorted(set(self.tests) - set(self.selected_tests))
        selected  = sorted(self.selected_tests)
        self.lb_available.delete(0, tk.END)
        for item in available:
            self.lb_available.insert(tk.END, item)
        self.lb_selected.delete(0, tk.END)
        for item in selected:
            self.lb_selected.insert(tk.END, item)

        # Clear stale selections
        self.lb_available.selection_clear(0, tk.END)
        self.lb_selected.selection_clear(0, tk.END)
        self.lb_available.update_idletasks()
        self.lb_selected.update_idletasks()

    def _filter_left(self, *args):
        kw = self.search_left.get()
        if kw == "Search Available...":
            kw = ""
        else:
            kw = kw.lower()

        self.lb_available.delete(0, tk.END)
        for t in sorted(set(self.tests) - set(self.selected_tests)):
            if not kw or kw in t.lower():
                self.lb_available.insert(tk.END, t)

    def _filter_right(self, *args):
        kw = self.search_right.get()
        if kw == "Search Selected...":
            kw = ""
        else:
            kw = kw.lower()

        self.lb_selected.delete(0, tk.END)
        for t in sorted(self.selected_tests):
            if not kw or kw in t.lower():
                self.lb_selected.insert(tk.END, t)

    def _move_one_right(self):
        # Move selected and refresh
        for idx in self.lb_available.curselection():
            self.selected_tests.append(self.lb_available.get(idx))
        self._populate_listboxes()

    def _move_all_right(self):
        self.selected_tests = list(self.tests)
        self._populate_listboxes()

    def _move_one_left(self):
        for idx in self.lb_selected.curselection():
            item = self.lb_selected.get(idx)
            if item in self.selected_tests:
                self.selected_tests.remove(item)
        self._populate_listboxes()

    def _move_all_left(self):
        self.selected_tests.clear()
        self._populate_listboxes()

    def _on_export(self):
        if not self.selected_tests:
            messagebox.showwarning("No Selection", "Please select at least one test.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV files","*.csv")],
                                            title="Save CSV as...")
        if path:
            cols = ['Tester', 'Serial'] + self.selected_tests
            try:
                write_csv(path, cols, self.rows, self.limits)
                messagebox.showinfo("Export Successful", "CSV exported successfully!")
            except Exception as e:
                messagebox.showerror("Passing-tests Export Failed", str(e))
        
        if self.export_failures.get() and getattr(self, 'failures', []):
            base, _ = os.path.splitext(path)
            fail_path = base + "_failures.csv"
            try:
                write_failures_log(fail_path, self.failures)
            except Exception as e:
                messagebox.showerror("Failed-tests Export Failed", str(e))
                return
            messagebox.showinfo("Export Complete",
                                f"Failures logged to:\n  {fail_path}")
        else:
            messagebox.showinfo("Export Successful", f"CSV exported to:\n  {path}")

if __name__ == "__main__":
    ICTParser().mainloop()