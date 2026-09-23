# Wuji 手波动 Mod

`com.bxi.wuji_hand` 把 Wuji Hand 2 的 `wave.npy` 波动动作接入 ELF3 状态机。它只控制灵巧手的 20 个关节，机器人本体在 `wave` 状态中保持进入前的最后一帧电机目标，因此只适合原地短时演示，不支持边走边做手部动作。

## 目录结构

```text
com.bxi.wuji_hand/
├── mod.yaml                         # Mod 清单、事件、状态和节点生命周期
├── state.py                         # 保持机器人本体上一帧目标
├── scripts/wuji_hand_wave.py        # Wuji Hand 2 SDK 播放器
├── assets/wave.npy                  # 150×20 的波动轨迹
└── README.md
```

## 环境要求

| 项 | 要求 |
| --- | --- |
| ELF3 控制端 | 已部署并启用 `bxi_example_py_elf3` 状态机；`com.bxi.basic_actions`（`>=1,<2`）已加载 |
| Python | 控制端 Python 3 能导入 `numpy` 与 `wuji_sdk`。ELF3 上 Mod 节点由 `ros_elf_launch.service`（`User=root`）以 `/usr/bin/python3` 运行，SDK 必须装到该解释器可见的位置 |
| 灵巧手 | Wuji Hand 2，20 个关节在线、已供电；同一时间只能有一个程序发布手部关节命令 |
| 网络 | 主机有一块网卡处在 `192.168.1.0/24`（约定主机侧 `192.168.1.100/24`），手部默认 `192.168.1.111:7447` |

## 操作步骤

按顺序执行，每步都给出验证方法。

### 步骤 1：把 wuji_sdk 装到运行节点的解释器

ELF3 上 Mod 节点由 `ros_elf_launch.service`（`User=root`）以 `/usr/bin/python3` 启动，所以 SDK 要装到系统级；`pip install --user` 装进普通用户 `~/.local` 的 SDK 对该进程不可见。

联网安装：

```bash
sudo -H /usr/bin/python3 -m pip install wuji-sdk
```

离线安装（已有用户级安装时，把三份目录一起复制到系统 site-packages；缺 `wuji_sdk.libs` 会导致 `.so` 加载失败）：

```bash
SP=~/.local/lib/python3.10/site-packages
sudo cp -r "$SP/wuji_sdk" "$SP/wuji_sdk.libs" "$SP"/wuji_sdk-*.dist-info \
  /usr/local/lib/python3.10/dist-packages/
```

验证（必须用 root + `/usr/bin/python3`）：

```bash
sudo /usr/bin/python3 -c "import wuji_sdk, numpy; print(wuji_sdk.__file__, numpy.__version__)"
```

### 步骤 2：给直连网口配置手部网段

```bash
# 临时（重启失效）
sudo ip addr add 192.168.1.100/24 dev <直连网口>

# 持久（NetworkManager；never-default 保证不顶掉默认路由）
sudo nmcli con add type ethernet ifname <直连网口> con-name bxi-hand \
  ipv4.method manual ipv4.addresses 192.168.1.100/24 \
  ipv4.never-default yes ipv6.method disabled
sudo nmcli con up bxi-hand
```

验证路由、连通性和设备发现（扫描只发现设备，不使能关节）：

```bash
ip route get 192.168.1.111          # 应指向直连网口
ping -c 2 192.168.1.111
python3 - <<'PY'
from wuji_sdk import SdkManager
for d in SdkManager.instance().scan():
    print(d.sn, d.address, d.transport_type, d.device_type)
PY
```

期望输出形如 `WH2KA01260807012 192.168.1.111:7447 TransportType.Udp DeviceType.WujiHand2`。

### 步骤 3：部署 Mod（两种方式二选一）

同一个 Mod 只能存在于一个 Mod 根目录。部署前先确认另一处没有同名目录：

```bash
ls -d ./src/bxi_example_py_elf3/mods/com.bxi.wuji_hand \
      ./install/share/bxi_example_py_elf3/mods/com.bxi.wuji_hand \
      /opt/bxi/mods/com.bxi.wuji_hand 2>/dev/null
```

**方式 A：外部 Mod 根目录**（不改工作区，适合独立升级）

```bash
sudo mkdir -p /opt/bxi/mods
sudo git clone git@github.com:lixinweijy/com.bxi.wuji_hand.git \
  /opt/bxi/mods/com.bxi.wuji_hand

# 之后更新
sudo git -C /opt/bxi/mods/com.bxi.wuji_hand pull --ff-only
```

**方式 B：集成到 `bxi_example_py_elf3` 源码**

```bash
cp -r com.bxi.wuji_hand src/bxi_example_py_elf3/mods/
colcon build --merge-install --packages-select bxi_example_py_elf3
source install/setup.bash
```

两种方式都要保留 `mod.yaml`、`state.py`、`scripts/wuji_hand_wave.py`、`assets/wave.npy` 四个文件，只复制播放器脚本状态机无法发现完整 Mod。

验证文件齐全（路径按所选方式替换）：

```bash
M=/opt/bxi/mods/com.bxi.wuji_hand
test -f $M/mod.yaml && test -f $M/state.py \
  && test -f $M/scripts/wuji_hand_wave.py && test -f $M/assets/wave.npy \
  && echo "Mod 文件齐全"
```

### 步骤 4：重启 example 让状态机重新加载

用遥控器 **Stop → Start**（或 `sudo systemctl restart ros_elf_launch.service`）。Mod 可用性在加载时计算，不会热更新。

验证启动日志（`/var/log/bxi_log/<时间>_elf.log`）里出现：

```text
[fw.controller]: loaded 5 Mods, 0 unavailable, 0 disabled, ...
[com.bxi.wuji_hand]: loaded v1.0.0: .../mods/com.bxi.wuji_hand; requires=com.bxi.basic_actions
```

### 步骤 5：上电后做只读自检

连接、订阅诊断，不使能、不发布命令：

```bash
cd <Mod 目录>
python3 - <<'PY'
import time
from wuji_sdk import SdkManager

m = SdkManager.instance()
hand = m.connect(address="192.168.1.111:7447", device_name="wuji_diag")
sub = None
try:
    print("online joints:", hand.online_joints_count().get())
    sub = hand.joint_diagnostics().subscribe()
    deadline = time.monotonic() + 5
    frame = None
    while time.monotonic() < deadline:
        frame = sub.recv()
        if frame is not None and len(frame.joints) == 20:
            break
        time.sleep(0.01)
    for j in sorted(frame.joints, key=lambda x: x.nid):
        code = j.error_code_current
        info = hand.describe_error(code) if code else None
        tag = "" if info is None else " | %s/%s" % (info["severity"], info["clear_policy"])
        print("nid=%2d ext_state=%s vbus=%.1fV err=0x%04X%s"
              % (j.nid, getattr(j.status_word, "ext_state", None), j.vbus_v_fb, code, tag))
finally:
    if sub is not None:
        sub.close()
    m.disconnect(device_name="wuji_diag")
PY
```

期望：`online joints: 20`，每个关节 `err=0x0000`（个别 `0x0006 BusFrameLossHigh` 是可自动清除的总线告警，可忽略），**没有** `ext_state=3` 的关节。自检不通过时先处理手部侧再继续，不要进入运动步骤。

### 步骤 6：进入 wave 状态操作

| 操作 | 事件 | 状态机行为 |
| --- | --- | --- |
| `LB + RB + A` | `btn_10=13` | `com.bxi.basic_actions/normal` → `com.bxi.wuji_hand/wave` |
| 普通状态键 | `btn_1=1` | `wave` → `com.bxi.basic_actions/normal` |
| 零力矩键 | `btn_2=1` | `wave` → `com.bxi.basic_actions/zero_torque` |

组合键需同时按下。进入前清空灵巧手周围空间，并确认状态机弹出的安全确认提示。进入后机器人本体不跟随行走指令；需要移动机器人时先退出该状态。退出状态时节点发送 `SIGINT`，脚本执行急停、失能、恢复 MIT 参数与力矩限制后断开连接。

验证：日志出现 `state transition: from=com.bxi.basic_actions/normal, to=com.bxi.wuji_hand/wave`，且 `[com.bxi.wuji_hand.node.wave_driver]: started process Mod node`。

### 步骤 7：不经状态机直接运行播放器

适合单独调试手部连接和轨迹：

```bash
cd <Mod 目录>
python3 scripts/wuji_hand_wave.py \
  --address 192.168.1.111:7447 \
  --trajectory assets/wave.npy \
  --scale 0.3 \
  --cycles 1
```

首次运行使用较小幅度和单次循环，确认动作正常后再加大。常用参数：

| 参数 | 默认值 | 说明 |
| --- | ---: | --- |
| `--address` | `192.168.1.111:7447` | Wuji Hand 2 的 UDP 地址 |
| `--trajectory` | 必填 | `N×20` 的 NumPy 轨迹文件 |
| `--scale` | `1.5` | 相对首帧的增量缩放倍数 |
| `--source-rate` | `100` | 原始轨迹频率，单位 Hz |
| `--rate` | `200` | 实际命令发送频率，单位 Hz |
| `--cycles` | `0` | 循环次数；`0` 表示持续循环 |

### 步骤 8：停止与退出

- 脚本运行中按 `Ctrl-C`：先 `emergency_stop()`，再关闭发布器、失能关节、恢复 MIT 参数和力矩限制，最后断开 SDK 连接。
- 状态机中退出：按 `btn_1=1` 回 `normal`（或 `btn_2=1` 进 `zero_torque`）。
- 异常中断（如 `SIGKILL`）后清理可能不完整，重新连接前核对 MIT 参数、力矩限制和关节使能状态。

## 轨迹格式

`wave.npy` 必须满足：

- 二维数组，形状为 `N×20`，且至少包含两帧；
- 所有元素都是有限浮点数；
- 列顺序固定为 Wuji 关节 NID：
  `1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 24`。

播放器以第一帧为基准，只发送 `第一帧位置 + (当前帧 - 第一帧) × scale`，不会直接覆盖设备当前姿态；相邻轨迹点之间插值，循环边界也平滑连接。

## 安全要求

1. 首次运行使用 `--scale 0.1`～`0.3`、`--cycles 1`，并让手指远离人员、桌面和线缆。
2. 启动前确认没有其他 Wuji SDK 程序、示例脚本或调试工具占用命令发布通道。
3. 运行中出现异常姿态、异响、通信告警或手部失控时立即 `Ctrl-C`，必要时断开手部电源。
4. 不要在 `wave` 状态中同时启动行走、全身动作或另一套灵巧手控制器。
5. 不要用 `clear_fault()` / `clear_all_faults()` 绕过不可自动清除的关节故障码，也不要修改 20 关节在线校验。

## 开发与验证

- 修改 `mod.yaml` 时同步检查事件值、状态路由和节点 `shutdown` 策略。
- 修改播放器时保持 20 关节校验、有限值校验和异常路径急停逻辑。
- 本地静态检查：

  ```bash
  python3 -m py_compile scripts/wuji_hand_wave.py state.py
  python3 - <<'PY'
  import numpy as np
  print(np.load("assets/wave.npy").shape)
  PY
  ```

- 示例轨迹来自 Wuji Technology `isaaclab-sim` 提交 `67c8a36743ef12e341b9c814126aafbbd1167ac8`，上游采用 MIT License。

## 相关资料

- [Wuji Hand 2 官方文档](https://docs.wuji.tech/docs/zh/wuji-hand/latest/overview/)
- [Wuji SDK Python 示例](https://github.com/wuji-technology/wuji-sdk/tree/main/examples/python/wuji_hand_2)
- [Isaac Lab 示例仓库](https://github.com/wuji-technology/isaaclab-sim)
