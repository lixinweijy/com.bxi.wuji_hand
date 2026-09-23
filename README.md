# Wuji 手波动 Mod

`com.bxi.wuji_hand` 将 `elf3-arm-02` 上验证过的 Wuji Hand 2 `wave.npy` 示例接入 ELF3 状态机。它只控制灵巧手的 20 个关节；机器人本体在该状态中保持进入状态前的最后一帧电机目标，因此当前版本适合原地短时演示，不支持边走边做手部动作。

## 功能概览

- 从 `com.bxi.basic_actions/normal` 进入 `Wuji 手波动` 状态。
- 状态节点独立启动 Wuji SDK 进程，避免把手部 SDK 放进机器人控制热路径。
- 退出状态时发送 `SIGINT`，脚本执行急停、失能、恢复 MIT 参数和力矩限制，然后断开连接。
- 内置 150 帧、20 关节的 `assets/wave.npy`，支持幅度、播放频率和循环次数调整。

## 目录结构

```text
com.bxi.wuji_hand/
├── mod.yaml                         # Mod 清单、事件、状态和节点生命周期
├── state.py                         # 保持机器人本体上一帧目标
├── scripts/wuji_hand_wave.py        # Wuji Hand 2 SDK 播放器
├── assets/wave.npy                  # 150×20 的波动轨迹
└── README.md
```

## 运行前提

### ELF3 控制端

- 已安装并启用 `bxi_example_py_elf3` 状态机。
- `com.bxi.basic_actions` 已加载；本 Mod 的 `requires` 会检查版本范围 `>=1,<2`。
- 控制端使用 Python 3，且运行时能够导入 `numpy` 与 `wuji_sdk`。
- 手部网络可达默认地址 `192.168.1.111:7447`。

### Wuji Hand 2

- 设备为 Wuji Hand 2，20 个关节全部在线。
- 手部已供电，控制端与手部位于可通信网络。
- 同一时间只能有一个程序发布手部关节命令。

在目标设备上先检查 Python 环境：

```bash
python3 -m pip show wuji-sdk numpy
python3 - <<'PY'
import numpy
import wuji_sdk

print("numpy:", numpy.__version__)
print("wuji_sdk:", wuji_sdk.__file__)
PY
```

如果缺少依赖，应在实际运行 Mod 的同一个 Python 环境中安装。SDK 版本需与当前手部固件配套；不要在机器人正在运动时切换 Python 环境或升级 SDK。

### 装到运行节点的那个解释器（常见坑）

状态机启动 Mod 节点时用的是**控制栈自己的解释器**：ELF3 上 example 由 `ros_elf_launch.service`（`User=root`）拉起，节点即 `/usr/bin/python3`。`pip install --user` 装进某个普通用户 `~/.local` 的 SDK 对它不可见，状态机会报：

```text
Mod node 'com.bxi.wuji_hand/wave_driver' is unavailable:
Python module 'wuji_sdk' is not importable with '/usr/bin/python3': ModuleNotFoundError: No module named 'wuji_sdk'
```

装到系统级并用同一个解释器验证：

```bash
sudo -H /usr/bin/python3 -m pip install wuji-sdk
sudo /usr/bin/python3 -c "import wuji_sdk, numpy; print(wuji_sdk.__file__, numpy.__version__)"
```

离线环境或已有用户级安装时，可把三份目录一起复制到系统 site-packages（漏掉 `wuji_sdk.libs` 会让 `.so` 加载失败）：

```bash
SP=~/.local/lib/python3.10/site-packages
sudo cp -r "$SP/wuji_sdk" "$SP/wuji_sdk.libs" "$SP"/wuji_sdk-*.dist-info \
  /usr/local/lib/python3.10/dist-packages/
```

装好后必须重启 example（遥控器 Stop → Start），状态机才会重新计算节点可用性。

## 部署

> [!warning] 两种部署方式互斥，只能选一种
> 同一个 Mod 不能同时存在于两个 Mod 根目录。工作区内置根目录（`src/bxi_example_py_elf3/mods/`，安装后为 `install/share/bxi_example_py_elf3/mods/`）和外部根目录（状态机配置 `mod_paths`，默认示例 `/opt/bxi/mods`）各放一份时，状态机启动会直接失败，控制进程随之退出：
>
> ```text
> ValueError: duplicate Mod 'com.bxi.wuji_hand': <install>/share/bxi_example_py_elf3/mods/com.bxi.wuji_hand and /opt/bxi/mods/com.bxi.wuji_hand
> ```
>
> 部署前先检查另一处是否已有同名目录，只保留一份：
>
> ```bash
> ls -d ./src/bxi_example_py_elf3/mods/com.bxi.wuji_hand \
>       ./install/share/bxi_example_py_elf3/mods/com.bxi.wuji_hand \
>       /opt/bxi/mods/com.bxi.wuji_hand 2>/dev/null
> ```

### 作为外部 Mod 部署

将仓库目录放到状态机配置中的 Mod 根目录（默认示例为 `/opt/bxi/mods`）：

```bash
sudo mkdir -p /opt/bxi/mods
sudo git clone git@github.com:lixinweijy/com.bxi.wuji_hand.git \
  /opt/bxi/mods/com.bxi.wuji_hand
```

已有目录更新时使用快进更新：

```bash
sudo git -C /opt/bxi/mods/com.bxi.wuji_hand pull --ff-only
```

确认以下文件存在：

```bash
test -f /opt/bxi/mods/com.bxi.wuji_hand/mod.yaml
test -f /opt/bxi/mods/com.bxi.wuji_hand/assets/wave.npy
```

### 集成到 `bxi_example_py_elf3` 源码

把整个 `com.bxi.wuji_hand` 目录放入包的 `mods/` 目录，然后重新构建安装空间（**不要再按上一节 clone 到 `/opt/bxi/mods`**）：

```bash
colcon build --packages-select bxi_example_py_elf3 --symlink-install
source install/setup.bash
```

不要只复制 `scripts/wuji_hand_wave.py`；`mod.yaml`、`state.py` 和 `assets/wave.npy` 也必须保留，否则状态机无法发现完整 Mod。

## 遥控器操作

| 操作 | 事件 | 状态机行为 |
| --- | --- | --- |
| `LB + RB + A` | `btn_10=13` | `normal` → `com.bxi.wuji_hand/wave` |
| 普通状态键 | `btn_1=1` | `wave` → `com.bxi.basic_actions/normal` |
| 零力矩键 | `btn_2=1` | `wave` → `com.bxi.basic_actions/zero_torque` |

组合键需要同时按下。进入状态前清空灵巧手周围空间，并确认状态机弹出的安全确认提示。进入 `wave` 后，机器人本体不会跟随行走指令；需要移动机器人时先退出该状态。

## 直接运行播放器

直接运行适合调试手部连接和轨迹，不经过 ELF3 状态机：

```bash
cd /opt/bxi/mods/com.bxi.wuji_hand
python3 scripts/wuji_hand_wave.py \
  --trajectory assets/wave.npy \
  --scale 0.3 \
  --cycles 1
```

首次运行建议使用较小幅度和单次循环。常用参数：

| 参数 | 默认值 | 说明 |
| --- | ---: | --- |
| `--address` | `192.168.1.111:7447` | Wuji Hand 2 的 UDP 地址 |
| `--trajectory` | `assets/wave.npy` | `N×20` 的 NumPy 轨迹文件 |
| `--scale` | `1.5` | 相对首帧的增量缩放倍数 |
| `--source-rate` | `100` | 原始轨迹频率，单位 Hz |
| `--rate` | `200` | 实际命令发送频率，单位 Hz |
| `--cycles` | `0` | 循环次数；`0` 表示持续循环 |

例如指定手部地址并播放两次：

```bash
python3 scripts/wuji_hand_wave.py \
  --address 192.168.1.111:7447 \
  --scale 0.3 \
  --cycles 2
```

按 `Ctrl-C` 会触发 `KeyboardInterrupt`：脚本先调用 `emergency_stop()`，再关闭发布器、失能关节、恢复原来的 MIT 参数和力矩限制，最后断开 SDK 连接。

## 轨迹格式

`wave.npy` 必须满足：

- 二维数组，形状为 `N×20`，且至少包含两帧；
- 所有元素都是有限浮点数；
- 列顺序固定为 Wuji 关节 NID：
  `1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 24`。

播放器以第一帧为基准，只发送 `第一帧位置 + (当前帧 - 第一帧) × scale`，不会直接覆盖设备当前姿态。每个相邻轨迹点之间会插值，循环边界也会平滑连接。

## 安全与退出

1. 首次运行使用 `--scale 0.1`～`0.3`、`--cycles 1`，并让手指远离人员、桌面和线缆。
2. 启动前确认没有其他 Wuji SDK 程序、示例脚本或调试工具占用命令发布通道。
3. 运行中发现异常姿态、异响、通信告警或手部失控时，立即按 `Ctrl-C`；必要时断开手部电源。
4. 不要在 `wave` 状态中同时启动行走、全身动作或另一套灵巧手控制器。
5. 如果进程被 `SIGKILL` 强制终止，清理代码可能来不及恢复参数；重新连接前应检查 MIT 参数、力矩限制和关节使能状态。

## 故障排查

| 现象 | 检查项 |
| --- | --- |
| `ValueError: duplicate Mod 'com.bxi.wuji_hand'` | 同一个 Mod 被部署到了两个根目录（内置 `install/share/bxi_example_py_elf3/mods/` 与 `/opt/bxi/mods`）。按“部署”一节的检查命令确认两处都在后，删除或移走多余的一份再启动；不要靠改 `mod_paths` 绕过。 |
| `No module named wuji_sdk` | 用运行状态机的同一个 `python3` 检查 `python3 -m pip show wuji-sdk`。 |
| 状态机报 `Mod node 'com.bxi.wuji_hand/wave_driver' is unavailable: ... 'wuji_sdk' is not importable with '/usr/bin/python3'` | SDK 装在别的解释器/用户目录（典型是普通用户 `~/.local`，而节点以 root + `/usr/bin/python3` 运行）。按“安装 SDK”一节装到系统级，然后重启 example。 |
| `未检测到完整的 20 个在线关节` | 检查手部供电、网络地址、内部总线和设备型号。 |
| `在线关节不完整` | 确认 20 个 NID 都能在诊断帧中读到，不要修改列顺序来绕过检查。 |
| `等待关节数据超时` | 检查 SDK 连接、UDP 地址和是否已有其他订阅/发布程序。 |
| `关节使能超时` | 读取手部诊断状态，排除电机故障后再重试。 |
| 动作幅度过大或抖动 | 立即停止，降低 `--scale`，确认只有一个发布者并检查网络丢包。 |
| 退出后参数未恢复 | 检查进程是否被强制杀死；重新运行前手动核对 MIT 参数和力矩限制。 |

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

- 当前示例轨迹来自 Wuji Technology `isaaclab-sim` 提交 `67c8a36743ef12e341b9c814126aafbbd1167ac8`，上游采用 MIT License。

## 相关资料

- [Wuji Hand 2 官方文档](https://docs.wuji.tech/docs/zh/wuji-hand/latest/overview/)
- [Wuji SDK Python 示例](https://github.com/wuji-technology/wuji-sdk/tree/main/examples/python/wuji_hand_2)
- [Isaac Lab 示例仓库](https://github.com/wuji-technology/isaaclab-sim)
