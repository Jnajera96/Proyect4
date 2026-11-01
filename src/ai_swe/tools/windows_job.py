"""Owned Windows Job Object; attach a suspended child before running untrusted code."""

from __future__ import annotations

import ctypes as c
import os
import sys
import time
from ctypes import wintypes as w

from pydantic import BaseModel, ConfigDict, Field

CREATE_SUSPENDED = 0x4


class JobLimits(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always",
    )

    max_processes: int = Field(default=16, ge=1, le=128)
    memory_mb: int = Field(default=1024, ge=64, le=8192)
    cpu_seconds: int = Field(default=600, ge=1, le=3600)


class JobError(RuntimeError):
    pass


class _Limits(c.Structure):
    _fields_ = [
        ("process_time", c.c_longlong), ("job_time", c.c_longlong), ("flags", w.DWORD),
        ("min_ws", c.c_size_t), ("max_ws", c.c_size_t), ("max_processes", w.DWORD),
        ("affinity", c.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD),
    ]


class _ExtendedLimits(c.Structure):
    _fields_ = [
        ("basic", _Limits), ("io_counters", c.c_ulonglong * 6),
        ("process_memory", c.c_size_t), ("job_memory", c.c_size_t),
        ("peak_process_memory", c.c_size_t), ("peak_job_memory", c.c_size_t),
    ]


class _Accounting(c.Structure):
    _fields_ = [
        ("times", c.c_longlong * 4), ("page_faults", w.DWORD), ("total", w.DWORD),
        ("active", w.DWORD), ("terminated", w.DWORD),
    ]


class _Thread(c.Structure):
    _fields_ = [
        ("size", w.DWORD), ("usage", w.DWORD), ("tid", w.DWORD), ("owner", w.DWORD),
        ("base_priority", w.LONG), ("delta_priority", w.LONG), ("flags", w.DWORD),
    ]


class _ProcessList(c.Structure):
    _fields_ = [("assigned", w.DWORD), ("count", w.DWORD), ("ids", c.c_size_t * 1024)]


class WindowsJob:
    def __init__(self, limits: JobLimits | None = None):
        policy = JobLimits() if limits is None else JobLimits.model_validate(limits)
        if os.name != "nt":
            raise JobError("El control de grupos Windows no está disponible")
        executable = (
            sys.executable
            if getattr(os.lstat(sys.executable), "st_reparse_tag", 0) == 0
            else sys._base_executable
        )
        if getattr(os.lstat(executable), "st_reparse_tag", 0) == 0x8000001B:
            raise JobError(
                "Usa el intérprete real de Python o el portable; el alias de Microsoft Store "
                "no permite confirmar el confinamiento"
            )
        api = c.WinDLL("kernel32", use_last_error=True)

        def bind(name, result, *arguments):
            function = getattr(api, name)
            function.restype = result
            function.argtypes = list(arguments)
            return function

        self._close = bind("CloseHandle", w.BOOL, w.HANDLE)
        self._create = bind("CreateJobObjectW", w.HANDLE, c.c_void_p, w.LPCWSTR)
        self._set = bind("SetInformationJobObject", w.BOOL, w.HANDLE, c.c_int, c.c_void_p, w.DWORD)
        self._assign = bind("AssignProcessToJobObject", w.BOOL, w.HANDLE, w.HANDLE)
        self._query = bind("QueryInformationJobObject", w.BOOL, w.HANDLE, c.c_int,
                           c.c_void_p, w.DWORD, c.c_void_p)
        self._terminate = bind("TerminateJobObject", w.BOOL, w.HANDLE, w.UINT)
        self._snapshot = bind("CreateToolhelp32Snapshot", w.HANDLE, w.DWORD, w.DWORD)
        self._first = bind("Thread32First", w.BOOL, w.HANDLE, c.POINTER(_Thread))
        self._next = bind("Thread32Next", w.BOOL, w.HANDLE, c.POINTER(_Thread))
        self._open_thread = bind("OpenThread", w.HANDLE, w.DWORD, w.BOOL, w.DWORD)
        self._resume = bind("ResumeThread", w.DWORD, w.HANDLE)
        self._open_process = bind("OpenProcess", w.HANDLE, w.DWORD, w.BOOL, w.DWORD)
        self._in_job = bind("IsProcessInJob", w.BOOL, w.HANDLE, w.HANDLE, c.POINTER(w.BOOL))
        self._wait = bind("WaitForSingleObject", w.DWORD, w.HANDLE, w.DWORD)
        self.handle = self._check(self._create(None, None), "Crear grupo de procesos")
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000 | 0x200 | 0x8 | 0x4
        limits.basic.max_processes = policy.max_processes
        limits.job_memory = policy.memory_mb * 1024 * 1024
        limits.basic.job_time = policy.cpu_seconds * 10_000_000
        self._limits = limits
        try:
            self._check(self._set(self.handle, 9, c.byref(limits), c.sizeof(limits)),
                        "Configurar cierre del grupo")
        except JobError:
            self.close()
            raise

    @staticmethod
    def _check(value, operation):
        if not value:
            raise JobError(f"{operation}: Windows {c.get_last_error()}")
        return value

    def assign_and_resume(self, process, deadline=None):
        # shortcut: CPython's owned Windows process handle; revisit for other interpreters.
        handle = getattr(process, "_handle", None)
        if handle is None:
            raise JobError("No se pudo identificar el proceso suspendido propio")
        self._check(self._assign(self.handle, int(handle)), "Asignar proceso al grupo")
        if deadline is not None and time.monotonic() >= deadline:
            return False
        snapshot = self._snapshot(0x4, 0)  # TH32CS_SNAPTHREAD, read-only system snapshot.
        if not snapshot or snapshot == c.c_void_p(-1).value:
            raise JobError(f"Consultar hilo suspendido: Windows {c.get_last_error()}")
        try:
            entry = _Thread()
            entry.size = c.sizeof(entry)
            threads = []
            more = self._first(snapshot, c.byref(entry))
            while more:
                if entry.owner == process.pid:
                    threads.append(entry.tid)
                more = self._next(snapshot, c.byref(entry))
            if c.get_last_error() != 18 or len(threads) != 1:  # ERROR_NO_MORE_FILES.
                raise JobError("No se confirmó un único hilo inicial suspendido")
            thread = self._check(self._open_thread(0x2, False, threads[0]), "Abrir hilo propio")
            try:
                if deadline is not None and time.monotonic() >= deadline:
                    return False
                if self._resume(thread) != 1:
                    raise JobError("No se confirmó la reanudación del hilo inicial suspendido")
            finally:
                self._check(self._close(thread), "Cerrar handle del hilo")
        finally:
            self._check(self._close(snapshot), "Cerrar snapshot de hilos")
        return True

    def active(self) -> int:
        accounting = _Accounting()
        self._check(self._query(self.handle, 1, c.byref(accounting), c.sizeof(accounting), None),
                    "Consultar procesos activos del grupo")
        return accounting.active

    def wait_empty(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while self.active():
            if time.monotonic() >= deadline:
                return False
            time.sleep(.01)
        return True

    def terminate_and_wait(self):
        handles = []
        try:
            # Stop new descendants before taking the job-owned PID snapshot.
            limits = _ExtendedLimits.from_buffer_copy(self._limits)
            # Preserve elapsed job CPU time instead of restarting its quota during cleanup.
            limits.basic.flags = (limits.basic.flags & ~0x4) | 0x40
            limits.basic.max_processes = 1
            self._check(self._set(self.handle, 9, c.byref(limits), c.sizeof(limits)),
                        "Impedir nuevos descendientes durante el cierre")
            processes = _ProcessList()
            self._check(self._query(self.handle, 3, c.byref(processes), c.sizeof(processes), None),
                        "Consultar procesos propios para cierre")
            if processes.count > len(processes.ids):
                raise JobError("Demasiados procesos para verificar el cierre")
            for pid in processes.ids[:processes.count]:
                handle = self._open_process(0x100000 | 0x1000, False, pid)
                if not handle and c.get_last_error() == 87:
                    continue  # The process already exited.
                self._check(handle, "Abrir proceso propio para verificar cierre")
                handles.append(handle)
                belongs = w.BOOL()
                self._check(self._in_job(handle, self.handle, c.byref(belongs)),
                            "Verificar pertenencia al grupo")
                if not belongs.value:
                    raise JobError("No se confirmó la identidad del proceso del grupo")
            self._check(self._terminate(self.handle, 124), "Terminar grupo de procesos")
            deadline = time.monotonic() + 5
            for handle in handles:
                remaining = max(0, int((deadline - time.monotonic()) * 1000))
                if self._wait(handle, remaining) != 0:
                    raise JobError("No se confirmó la terminación de un proceso propio")
            if not self.wait_empty(max(0, deadline - time.monotonic())):
                raise JobError("El grupo aún contiene procesos activos después del cierre")
        finally:
            for handle in handles:
                self._close(handle)

    def close(self):
        if self.handle is not None:
            self._check(self._close(self.handle), "Cerrar handle del grupo")
            self.handle = None
