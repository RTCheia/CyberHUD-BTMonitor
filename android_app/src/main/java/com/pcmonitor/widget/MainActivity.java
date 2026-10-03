package com.pcmonitor.widget;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothServerSocket;
import android.bluetooth.BluetoothSocket;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.widget.ProgressBar;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.Locale;
import java.util.UUID;

public class MainActivity extends Activity {
    private static final String TAG = "PCMonitor";

    // 标准蓝牙串口服务 SPP UUID
    private static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");
    private static final String SERVICE_NAME = "PC_MONITOR";

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private BluetoothServerThread serverThread;

    // 模块 01: TELEMETRY (FPS / 1% LOW / NET / RAM)
    private TextView tvFps, tvFpsLow;
    private TextView tvNetDown, tvNetUp;
    private TextView tvRamUsed;
    private ProgressBar pbRam;

    // 模块 02: CPU
    private TextView tvCpuTemp, tvCpuPower, tvCpuVolt;
    private TextView tvPCoreFreq, tvPCoreLoad;
    private ProgressBar pbPCore;
    private TextView tvECoreFreq, tvECoreLoad;
    private ProgressBar pbECore;

    // 模块 03: GPU
    private TextView tvGpuHotspot, tvGpuCoreTemp, tvGpuPower, tvGpuClock;
    private TextView tvGpuLoad;
    private ProgressBar pbGpuLoad;
    private TextView tvVramText;
    private ProgressBar pbVram;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 保持屏幕常亮
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        // 铺满物理屏幕，允许内容延伸到摄像头挖孔/刘海区域（不留黑边）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            try {
                WindowManager.LayoutParams lp = getWindow().getAttributes();
                lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
                getWindow().setAttributes(lp);
            } catch (Exception ignored) {}
        }

        setContentView(R.layout.activity_main);

        applyFullScreen();

        initViews();
        checkPermissionsAndStart();
    }

    private void applyFullScreen() {
        try {
            View decorView = getWindow().getDecorView();
            if (decorView == null) return;

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                getWindow().setDecorFitsSystemWindows(false);
                WindowInsetsController controller = decorView.getWindowInsetsController();
                if (controller != null) {
                    controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                    controller.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                }
            }
            decorView.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            );
        } catch (Exception e) {
            Log.e(TAG, "Error applying fullscreen", e);
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            applyFullScreen();
        }
    }

    private void initViews() {
        // 模块 01
        tvFps = findViewById(R.id.tv_fps);
        tvFpsLow = findViewById(R.id.tv_fps_low);
        tvNetDown = findViewById(R.id.tv_net_down);
        tvNetUp = findViewById(R.id.tv_net_up);
        tvRamUsed = findViewById(R.id.tv_ram_used);
        pbRam = findViewById(R.id.pb_ram);

        // 模块 02
        tvCpuTemp = findViewById(R.id.tv_cpu_temp);
        tvCpuPower = findViewById(R.id.tv_cpu_power);
        tvCpuVolt = findViewById(R.id.tv_cpu_volt);
        tvPCoreFreq = findViewById(R.id.tv_p_core_freq);
        tvPCoreLoad = findViewById(R.id.tv_p_core_load);
        pbPCore = findViewById(R.id.pb_p_core);
        tvECoreFreq = findViewById(R.id.tv_e_core_freq);
        tvECoreLoad = findViewById(R.id.tv_e_core_load);
        pbECore = findViewById(R.id.pb_e_core);

        // 模块 03
        tvGpuHotspot = findViewById(R.id.tv_gpu_hotspot);
        tvGpuCoreTemp = findViewById(R.id.tv_gpu_core_temp);
        tvGpuPower = findViewById(R.id.tv_gpu_power);
        tvGpuClock = findViewById(R.id.tv_gpu_clock);
        tvGpuLoad = findViewById(R.id.tv_gpu_load);
        pbGpuLoad = findViewById(R.id.pb_gpu_load);
        tvVramText = findViewById(R.id.tv_vram_text);
        pbVram = findViewById(R.id.pb_vram);
    }

    private void checkPermissionsAndStart() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{
                        Manifest.permission.BLUETOOTH_CONNECT,
                        Manifest.permission.BLUETOOTH_SCAN
                }, 100);
                return;
            }
        }
        startBluetoothServer();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == 100) {
            startBluetoothServer();
        }
    }

    private synchronized void startBluetoothServer() {
        if (serverThread != null) {
            serverThread.stopServer();
        }
        serverThread = new BluetoothServerThread();
        serverThread.start();
    }

    private void updateMetrics(final JSONObject data) {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                try {
                    // 1. Overview (FPS / NET / RAM)
                    if (data.has("overview")) {
                        JSONObject ov = data.getJSONObject("overview");

                        if (ov.has("fps") && !ov.isNull("fps")) {
                            tvFps.setText(String.valueOf(ov.getInt("fps")));
                        } else {
                            tvFps.setText("--");
                        }

                        if (ov.has("fps_low") && !ov.isNull("fps_low")) {
                            tvFpsLow.setText(String.valueOf(ov.getInt("fps_low")));
                        } else {
                            tvFpsLow.setText("--");
                        }

                        tvNetDown.setText(ov.optString("net_down_str", "0 KB/s"));
                        tvNetUp.setText(ov.optString("net_up_str", "0 KB/s"));

                        double ramUsed = ov.optDouble("ram_used_gb", 0.0);
                        double ramPct = ov.optDouble("ram_percent", 0.0);
                        tvRamUsed.setText(String.format(Locale.US, "%.1fG (%.0f%%)", ramUsed, ramPct));
                        pbRam.setProgress((int) Math.round(ramPct));
                    }

                    // 2. CPU
                    if (data.has("cpu")) {
                        JSONObject cpu = data.getJSONObject("cpu");
                        double tempHotspot = cpu.optDouble("temp_hotspot", 0.0);
                        if (tempHotspot > 0) {
                            tvCpuTemp.setText(String.format(Locale.US, "%.1f°C", tempHotspot));
                        } else {
                            tvCpuTemp.setText("--");
                        }

                        double power = cpu.optDouble("power_package_w", 0.0);
                        if (power > 0) {
                            tvCpuPower.setText(String.format(Locale.US, "%.0fW", power));
                        } else {
                            tvCpuPower.setText("--");
                        }

                        if (cpu.has("volt_core_v") && !cpu.isNull("volt_core_v")) {
                            tvCpuVolt.setText(String.format(Locale.US, "%.2fV", cpu.getDouble("volt_core_v")));
                        } else {
                            tvCpuVolt.setText("--");
                        }

                        double pLoad = cpu.optDouble("p_core_avg_load", 0.0);
                        double pClock = cpu.optDouble("p_core_avg_clock_ghz", 0.0);
                        tvPCoreLoad.setText(String.format(Locale.US, "%.0f%%", pLoad));
                        tvPCoreFreq.setText(pClock > 0 ? String.format(Locale.US, "%.2f GHz", pClock) : "-- GHz");
                        pbPCore.setProgress((int) Math.round(pLoad));

                        double eLoad = cpu.optDouble("e_core_avg_load", 0.0);
                        double eClock = cpu.optDouble("e_core_avg_clock_ghz", 0.0);
                        tvECoreLoad.setText(String.format(Locale.US, "%.0f%%", eLoad));
                        tvECoreFreq.setText(eClock > 0 ? String.format(Locale.US, "%.2f GHz", eClock) : "-- GHz");
                        pbECore.setProgress((int) Math.round(eLoad));
                    }

                    // 3. GPU
                    if (data.has("gpu")) {
                        JSONObject gpu = data.getJSONObject("gpu");
                        double hotspot = gpu.optDouble("temp_hotspot", 0.0);
                        tvGpuHotspot.setText(hotspot > 0 ? String.format(Locale.US, "%.0f°C", hotspot) : "--");

                        double coreTemp = gpu.optDouble("temp_core", 0.0);
                        tvGpuCoreTemp.setText(coreTemp > 0 ? String.format(Locale.US, "%.0f°C", coreTemp) : "--");

                        double power = gpu.optDouble("power_package_w", 0.0);
                        tvGpuPower.setText(power > 0 ? String.format(Locale.US, "%.0fW", power) : "--");

                        int clock = gpu.optInt("clock_core_mhz", 0);
                        tvGpuClock.setText(clock > 0 ? String.format(Locale.US, "%d MHz", clock) : "-- MHz");

                        double gpuLoad = gpu.optDouble("load_core", 0.0);
                        tvGpuLoad.setText(String.format(Locale.US, "%.0f%%", gpuLoad));
                        pbGpuLoad.setProgress((int) Math.round(gpuLoad));

                        double vramUsed = gpu.optDouble("vram_used_gb", 0.0);
                        double vramPct = gpu.optDouble("vram_percent", 0.0);
                        tvVramText.setText(String.format(Locale.US, "%.1fG (%.0f%%)", vramUsed, vramPct));
                        pbVram.setProgress((int) Math.round(vramPct));
                    }

                } catch (Exception e) {
                    Log.e(TAG, "Error updating UI metrics", e);
                }
            }
        });
    }

    private class BluetoothServerThread extends Thread {
        private BluetoothServerSocket serverSocket;
        private volatile boolean isRunning = true;

        @Override
        public void run() {
            BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
            if (adapter == null || !adapter.isEnabled()) {
                Log.w(TAG, "Bluetooth not available or not enabled");
                return;
            }

            try {
                serverSocket = adapter.listenUsingRfcommWithServiceRecord(SERVICE_NAME, SPP_UUID);
            } catch (IOException e) {
                Log.e(TAG, "listen() failed", e);
                return;
            }

            while (isRunning) {
                BluetoothSocket socket = null;
                try {
                    socket = serverSocket.accept();
                } catch (IOException e) {
                    if (!isRunning) break;
                    continue;
                }

                if (socket != null) {
                    BluetoothDevice dev = socket.getRemoteDevice();
                    String devName = dev != null ? dev.getName() : "PC";
                    Log.i(TAG, "Connected to PC: " + devName);

                    try {
                        BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), "UTF-8"));
                        String line;
                        while (isRunning && (line = reader.readLine()) != null) {
                            line = line.trim();
                            if (!line.isEmpty()) {
                                try {
                                    JSONObject json = new JSONObject(line);
                                    updateMetrics(json);
                                } catch (Exception parseEx) {
                                    Log.w(TAG, "Invalid json frame: " + line);
                                }
                            }
                        }
                    } catch (IOException e) {
                        Log.i(TAG, "Client disconnected: " + e.getMessage());
                    } finally {
                        try {
                            socket.close();
                        } catch (Exception ignored) {}
                    }
                }
            }

            if (serverSocket != null) {
                try { serverSocket.close(); } catch (Exception ignored) {}
            }
        }

        public void stopServer() {
            isRunning = false;
            if (serverSocket != null) {
                try { serverSocket.close(); } catch (Exception ignored) {}
            }
            interrupt();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (serverThread != null) {
            serverThread.stopServer();
        }
    }
}
