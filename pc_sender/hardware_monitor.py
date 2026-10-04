import os
import sys
import time
from collections import deque

# 引入 pythonnet CLR
import clr

DLL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lhm", "LibreHardwareMonitorLib.dll"))
if not os.path.exists(DLL_PATH):
    raise FileNotFoundError(f"未找到 LibreHardwareMonitorLib.dll: {DLL_PATH}")

clr.AddReference(DLL_PATH)
from LibreHardwareMonitor.Hardware import Computer

class HardwareMonitor:
    def __init__(self):
        self.computer = Computer()
        self.computer.IsCpuEnabled = True
        self.computer.IsGpuEnabled = True
        self.computer.IsMemoryEnabled = True
        self.computer.IsNetworkEnabled = True
        self.computer.Open()

        # 帧时间滑动窗口 (用于计算 1% Low FPS)
        self.fps_history = deque(maxlen=100)

        # 网速滑动计算兜底
        self.last_net_time = time.time()
        self.last_net_bytes_sent = 0
        self.last_net_bytes_recv = 0

        # 初始化 Windows 性能计数器 (免管理员权限获取 Intel P核/E核 实时真实睿频)
        # Intel Core Ultra 7 265KF (Arrow Lake):
        # 8 个 P核 (0-indexed: 0, 1, 6, 7, 8, 9, 18, 19)
        # 12 个 E核 (0-indexed: 2, 3, 4, 5, 10, 11, 12, 13, 14, 15, 16, 17)
        self.P_CORE_IDS_0 = {0, 1, 6, 7, 8, 9, 18, 19}
        self.E_CORE_IDS_0 = {i for i in range(20) if i not in self.P_CORE_IDS_0}
        self.P_CORE_IDS_1 = {i + 1 for i in self.P_CORE_IDS_0}
        self.E_CORE_IDS_1 = {i + 1 for i in self.E_CORE_IDS_0}

        self.pdh_query = None
        self.p_pdh_handles = []
        self.e_pdh_handles = []
        try:
            import win32pdh
            self.pdh_query = win32pdh.OpenQuery()
            for i in sorted(self.P_CORE_IDS_0):
                h = win32pdh.AddCounter(self.pdh_query, f"\\Processor Information(0,{i})\\% Processor Performance")
                self.p_pdh_handles.append(h)
            for i in sorted(self.E_CORE_IDS_0):
                h = win32pdh.AddCounter(self.pdh_query, f"\\Processor Information(0,{i})\\% Processor Performance")
                self.e_pdh_handles.append(h)
            win32pdh.CollectQueryData(self.pdh_query)
        except Exception:
            self.pdh_query = None

        # 一阶低通滤波器配置 (方案 B: 历史权重 0.85 + 当前实测权重 0.15)
        self.alpha_current = 0.15
        self.alpha_history = 0.85
        self.ema_history = {}

    def _filter_val(self, key: str, val, precision: int = 1, is_int: bool = False):
        if val is None:
            return None
        try:
            val = float(val)
        except (ValueError, TypeError):
            return val

        if key not in self.ema_history or self.ema_history[key] is None:
            # 第一帧冷启动：直接以当前第一帧作为初始历史值
            self.ema_history[key] = val
            return int(round(val)) if is_int else round(val, precision)

        # 方案 B: 滤波值 = 历史滤波值 * 0.9 + 当前实测值 * 0.1
        smoothed = self.alpha_history * self.ema_history[key] + self.alpha_current * val
        self.ema_history[key] = smoothed
        return int(round(smoothed)) if is_int else round(smoothed, precision)

    def _apply_ema(self, data: dict) -> dict:
        # CPU 核心指标滤波
        cpu = data.get("cpu", {})
        if "p_core_avg_load" in cpu:
            cpu["p_core_avg_load"] = self._filter_val("cpu_p_load", cpu["p_core_avg_load"], 1)
        if "e_core_avg_load" in cpu:
            cpu["e_core_avg_load"] = self._filter_val("cpu_e_load", cpu["e_core_avg_load"], 1)
        if "p_core_avg_clock_ghz" in cpu:
            cpu["p_core_avg_clock_ghz"] = self._filter_val("cpu_p_clock", cpu["p_core_avg_clock_ghz"], 2)
        if "e_core_avg_clock_ghz" in cpu:
            cpu["e_core_avg_clock_ghz"] = self._filter_val("cpu_e_clock", cpu["e_core_avg_clock_ghz"], 2)
        if "temp_hotspot" in cpu and cpu["temp_hotspot"] is not None:
            cpu["temp_hotspot"] = self._filter_val("cpu_temp", cpu["temp_hotspot"], 1)
        if "power_package_w" in cpu and cpu["power_package_w"] is not None:
            cpu["power_package_w"] = self._filter_val("cpu_power", cpu["power_package_w"], 1)
        if "volt_core_v" in cpu and cpu["volt_core_v"] is not None:
            cpu["volt_core_v"] = self._filter_val("cpu_volt", cpu["volt_core_v"], 3)

        # GPU 核心指标滤波
        gpu = data.get("gpu", {})
        if "load_core" in gpu:
            gpu["load_core"] = self._filter_val("gpu_load", gpu["load_core"], 1)
        if "temp_hotspot" in gpu and gpu["temp_hotspot"] is not None:
            gpu["temp_hotspot"] = self._filter_val("gpu_temp_hotspot", gpu["temp_hotspot"], 1)
        if "temp_core" in gpu and gpu["temp_core"] is not None:
            gpu["temp_core"] = self._filter_val("gpu_temp_core", gpu["temp_core"], 1)
        if "power_package_w" in gpu and gpu["power_package_w"] is not None:
            gpu["power_package_w"] = self._filter_val("gpu_power", gpu["power_package_w"], 1)
        if "clock_core_mhz" in gpu and gpu["clock_core_mhz"] is not None:
            gpu["clock_core_mhz"] = self._filter_val("gpu_clock_core", gpu["clock_core_mhz"], 0, is_int=True)
        if "clock_mem_mhz" in gpu and gpu["clock_mem_mhz"] is not None:
            gpu["clock_mem_mhz"] = self._filter_val("gpu_clock_mem", gpu["clock_mem_mhz"], 0, is_int=True)
        if "vram_used_gb" in gpu:
            gpu["vram_used_gb"] = self._filter_val("gpu_vram_used", gpu["vram_used_gb"], 1)
        if "vram_percent" in gpu:
            gpu["vram_percent"] = self._filter_val("gpu_vram_percent", gpu["vram_percent"], 1)

        # Overview (FPS / NET / RAM) 滤波
        overview = data.get("overview", {})
        if overview.get("fps") is not None:
            overview["fps"] = self._filter_val("fps", overview["fps"], 0, is_int=True)
        if overview.get("fps_low") is not None:
            overview["fps_low"] = self._filter_val("fps_low", overview["fps_low"], 0, is_int=True)

        # 网络上下行速度平滑
        def _smooth_net(net_str, key):
            if not net_str: return "0 KB/s"
            try:
                s = net_str.strip()
                kb = 0.0
                if s.endswith("MB/s"):
                    kb = float(s.replace("MB/s", "").trim()) * 1024.0
                elif s.endswith("KB/s"):
                    kb = float(s.replace("KB/s", "").trim())
                elif s.endswith("B/s"):
                    kb = float(s.replace("B/s", "").trim()) / 1024.0
                smoothed_kb = self._filter_val(key, kb, 1)
                if smoothed_kb >= 1024.0:
                    return f"{smoothed_kb / 1024.0:.1f} MB/s"
                else:
                    return f"{max(0.0, smoothed_kb):.0f} KB/s"
            except Exception:
                return net_str

        if "net_down_str" in overview:
            overview["net_down_str"] = _smooth_net(overview["net_down_str"], "net_down_kb")
        if "net_up_str" in overview:
            overview["net_up_str"] = _smooth_net(overview["net_up_str"], "net_up_kb")

        if "ram_used_gb" in overview:
            overview["ram_used_gb"] = self._filter_val("ram_used", overview["ram_used_gb"], 1)
        if "ram_percent" in overview:
            overview["ram_percent"] = self._filter_val("ram_percent", overview["ram_percent"], 1)

        return data

    def update(self) -> dict:
        """
        全量更新硬件传感器并提取 ui思路.txt 中指定的固定指标
        """
        for hw in self.computer.Hardware:
            hw.Update()
            for sub in hw.SubHardware:
                sub.Update()

        # 提取指标结构
        data = {
            "overview": {
                "is_gaming": False,
                "fps": None,
                "fps_low": None,
                "net_down_str": "0 KB/s",
                "net_up_str": "0 KB/s",
                "ram_used_gb": 0.0,
                "ram_total_gb": 32.0,
                "ram_percent": 0.0
            },
            "cpu": {
                "name": "Ultra 7 265KF",
                "temp_hotspot": None,      # Core Max 或 CPU Package
                "power_package_w": None,   # CPU Package Power
                "volt_core_v": None,       # VCore
                "p_core_avg_load": 0.0,
                "p_core_avg_clock_ghz": 0.0,
                "e_core_avg_load": 0.0,
                "e_core_avg_clock_ghz": 0.0
            },
            "gpu": {
                "name": "RX 7800 XT",
                "temp_hotspot": None,      # GPU Hot Spot
                "temp_core": None,         # GPU Core Temp
                "power_package_w": None,   # GPU Package Power
                "clock_core_mhz": None,    # GPU Core Clock
                "clock_mem_mhz": None,     # GPU Memory Clock
                "load_core": 0.0,          # GPU Core Load
                "vram_used_gb": 0.0,
                "vram_total_gb": 16.0,
                "vram_percent": 0.0
            },
            "timestamp": int(time.time() * 1000)
        }

        # 临时聚合变量
        p_loads = []
        e_loads = []
        p_clocks = []
        e_clocks = []

        for hw in self.computer.Hardware:
            all_hw = [hw] + list(hw.SubHardware)
            for h in all_hw:
                htype = str(h.HardwareType)

                # ==========================
                # CPU 传感器解析 (Intel Ultra 7 265KF)
                # ==========================
                if htype == "Cpu":
                    for s in h.Sensors:
                        sname = s.Name
                        stype = str(s.SensorType)
                        val = s.Value if s.Value is not None else 0.0

                        # 温度: Core Max 优先
                        if stype == "Temperature":
                            if sname == "Core Max":
                                data["cpu"]["temp_hotspot"] = round(val, 1)
                            elif sname == "CPU Package" and data["cpu"]["temp_hotspot"] is None:
                                data["cpu"]["temp_hotspot"] = round(val, 1)

                        # 功耗: CPU Package Power
                        elif stype == "Power" and sname == "CPU Package":
                            data["cpu"]["power_package_w"] = round(val, 1)

                        # 电压: CPU Core
                        elif stype == "Voltage" and "CPU Core" in sname:
                            data["cpu"]["volt_core_v"] = round(val, 3)

                        # 占用率: P核 与 E核 (1-indexed: P核为 1,2,7,8,9,10,19,20，其余为 E核)
                        elif stype == "Load" and sname.startswith("CPU Core #"):
                            try:
                                core_idx = int(sname.replace("CPU Core #", ""))
                                if core_idx in self.P_CORE_IDS_1:
                                    p_loads.append(val)
                                elif core_idx in self.E_CORE_IDS_1:
                                    e_loads.append(val)
                            except ValueError:
                                pass

                        # 频率: P-Core #1..#8 与 E-Core #1..#12
                        elif stype == "Clock":
                            if val > 0:
                                if sname.startswith("P-Core #"):
                                    p_clocks.append(val)
                                elif sname.startswith("E-Core #"):
                                    e_clocks.append(val)

                # ==========================
                # GPU 传感器解析 (AMD RX 7800 XT)
                # ==========================
                elif "Gpu" in htype:
                    for s in h.Sensors:
                        sname = s.Name
                        stype = str(s.SensorType)
                        val = s.Value if s.Value is not None else 0.0

                        if stype == "Factor" and sname == "Fullscreen FPS":
                            if val > 0:
                                val = min(200.0, val)
                                data["overview"]["is_gaming"] = True
                                data["overview"]["fps"] = int(val)
                                self.fps_history.append(val)
                                # 计算 1% Low FPS
                                sorted_fps = sorted(self.fps_history)
                                low_idx = max(1, int(len(sorted_fps) * 0.01))
                                low_val = int(sum(sorted_fps[:low_idx]) / low_idx)
                                data["overview"]["fps_low"] = min(200, low_val)

                        elif stype == "Temperature":
                            if sname == "GPU Hot Spot":
                                data["gpu"]["temp_hotspot"] = round(val, 1)
                            elif sname == "GPU Core":
                                data["gpu"]["temp_core"] = round(val, 1)

                        elif stype == "Power" and sname == "GPU Package":
                            data["gpu"]["power_package_w"] = round(val, 1)

                        elif stype == "Clock":
                            if sname == "GPU Core":
                                data["gpu"]["clock_core_mhz"] = int(val)
                            elif sname == "GPU Memory":
                                data["gpu"]["clock_mem_mhz"] = int(val)

                        elif stype == "Load" and sname == "GPU Core":
                            data["gpu"]["load_core"] = round(val, 1)

                        elif sname == "D3D Dedicated Memory Used":
                            data["gpu"]["vram_used_gb"] = round(val / 1024.0, 1)
                            data["gpu"]["vram_percent"] = round((data["gpu"]["vram_used_gb"] / 16.0) * 100, 1)

                # ==========================
                # 内存解析
                # ==========================
                elif htype == "Memory" and h.Name == "Total Memory":
                    for s in h.Sensors:
                        val = s.Value if s.Value is not None else 0.0
                        if s.Name == "Memory Used":
                            data["overview"]["ram_used_gb"] = round(val, 1)
                        elif s.Name == "Memory":
                            data["overview"]["ram_percent"] = round(val, 1)
                    data["overview"]["ram_total_gb"] = 32.0

                # ==========================
                # 网络流速解析 (WLAN 3)
                # ==========================
                elif htype == "Network" and "WLAN" in h.Name:
                    for s in h.Sensors:
                        val = s.Value if s.Value is not None else 0.0
                        if s.Name == "Download Speed":
                            kb = val / 1024.0
                            data["overview"]["net_down_str"] = f"{kb/1024.0:.1f} MB/s" if kb >= 1024 else f"{kb:.0f} KB/s"
                        elif s.Name == "Upload Speed":
                            kb = val / 1024.0
                            data["overview"]["net_up_str"] = f"{kb/1024.0:.1f} MB/s" if kb >= 1024 else f"{kb:.0f} KB/s"

        # 计算 P/E 核平均值
        if p_loads:
            data["cpu"]["p_core_avg_load"] = round(sum(p_loads) / len(p_loads), 1)
        if e_loads:
            data["cpu"]["e_core_avg_load"] = round(sum(e_loads) / len(e_loads), 1)
            
        if p_clocks:
            data["cpu"]["p_core_avg_clock_ghz"] = round((sum(p_clocks) / len(p_clocks)) / 1000.0, 2)
        elif self.pdh_query:
            try:
                import win32pdh
                win32pdh.CollectQueryData(self.pdh_query)
                p_vals = [win32pdh.GetFormattedCounterValue(h, win32pdh.PDH_FMT_DOUBLE)[1] for h in self.p_pdh_handles]
                data["cpu"]["p_core_avg_clock_ghz"] = round(3.9 * (sum(p_vals) / len(p_vals) / 100.0), 2)
            except Exception:
                pass

        if e_clocks:
            data["cpu"]["e_core_avg_clock_ghz"] = round((sum(e_clocks) / len(e_clocks)) / 1000.0, 2)
        elif self.pdh_query:
            try:
                import win32pdh
                e_vals = [win32pdh.GetFormattedCounterValue(h, win32pdh.PDH_FMT_DOUBLE)[1] for h in self.e_pdh_handles]
                data["cpu"]["e_core_avg_clock_ghz"] = round(3.3 * (sum(e_vals) / len(e_vals) / 100.0), 2)
            except Exception:
                pass

        # 应用一阶低通滤波 (EMA 平滑)
        return self._apply_ema(data)

    def close(self):
        self.computer.Close()

if __name__ == "__main__":
    monitor = HardwareMonitor()
    try:
        for _ in range(3):
            d = monitor.update()
            import json
            print(json.dumps(d, ensure_ascii=False, indent=2))
            time.sleep(1)
    finally:
        monitor.close()
