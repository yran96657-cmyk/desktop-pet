def pre_find_module_path(hook_api):
    # Override PyInstaller's default tkinter pre-find hook.
    # Our local Python can import tkinter, but PyInstaller's probe marks it
    # unavailable because Tcl initialization is broken in the build env.
    # We package Tcl/Tk manually in the spec and fix paths at runtime.
    return
