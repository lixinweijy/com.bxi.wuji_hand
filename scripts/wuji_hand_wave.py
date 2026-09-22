#!/usr/bin/env python3
"""在 Wuji Hand 2 上平滑循环执行 wave.npy 动作。"""

import argparse
import time
from pathlib import Path

import numpy as np
from wuji_sdk import JointCommand, SdkManager


NIDS = (1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 24)


def next_frame(sub, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = sub.recv()
        if frame is not None:
            return frame
        time.sleep(0.005)
    raise TimeoutError("等待关节数据超时")


def positions(sub):
    frame = next_frame(sub)
    values = {joint.nid: float(joint.position) for joint in frame.joints}
    if set(values) != set(NIDS):
        raise RuntimeError(f"在线关节不完整: {sorted(values)}")
    return [values[nid] for nid in NIDS]


def wait_enabled(sub, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = sub.recv()
        if frame is not None and len(frame.joints) == 20:
            if all(getattr(joint.status_word, "ext_state", None) == 2 for joint in frame.joints):
                return
        time.sleep(0.01)
    raise TimeoutError("关节使能超时")


def load_deltas(path, scale):
    trajectory = np.asarray(np.load(path), dtype=float)
    if trajectory.ndim != 2 or trajectory.shape[1] != len(NIDS) or len(trajectory) < 2:
        raise ValueError(f"轨迹必须是 N×20 且至少有两帧，实际为 {trajectory.shape}")
    if not np.isfinite(trajectory).all():
        raise ValueError("轨迹包含 NaN 或无穷值")
    return (trajectory - trajectory[0]) * scale


def play_wave(publisher, base, deltas, source_rate, rate, cycles):
    """对相邻轨迹点插值，并平滑连接最后一帧和第一帧。"""
    steps = max(1, round(len(deltas) * rate / source_rate))
    points = np.vstack((deltas, deltas[0]))
    deadline = time.monotonic()
    cycle = 0
    while cycles == 0 or cycle < cycles:
        for step in range(steps):
            position = step * len(deltas) / steps
            index = int(position)
            ratio = position - index
            delta = points[index] * (1.0 - ratio) + points[index + 1] * ratio
            publisher.send(
                [JointCommand(a + float(d), 0.0, 0.0) for a, d in zip(base, delta)]
            )
            deadline += 1.0 / rate
            time.sleep(max(0.0, deadline - time.monotonic()))
        cycle += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default="192.168.1.111:7447")
    parser.add_argument("--trajectory", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "wave.npy")
    parser.add_argument("--scale", type=float, default=1.5, help="wave 轨迹增量缩放倍数")
    parser.add_argument("--source-rate", type=float, default=100.0, help="开源轨迹频率，单位 Hz")
    parser.add_argument("--rate", type=float, default=200.0, help="命令发送频率，单位 Hz")
    parser.add_argument("--cycles", type=int, default=0, help="循环次数，0 表示一直循环")
    args = parser.parse_args()
    if args.rate <= 0 or args.source_rate <= 0 or args.cycles < 0:
        parser.error("--rate、--source-rate 必须大于 0，--cycles 不能小于 0")
    deltas = load_deltas(args.trajectory, args.scale)

    manager = SdkManager.instance()
    hand = manager.connect(address=args.address, device_name="wuji_hand_2")
    diagnostics = states = publisher = None
    old_mit = old_effort = None
    try:
        if hand.online_joints_count().get() != 20:
            raise RuntimeError("未检测到完整的 20 个在线关节")
        old_mit = hand.mit_params().get()
        old_effort = hand.effort_limit().get()
        hand.mit_params().set((3.0, 0.05))
        hand.effort_limit().set(1.5)
        diagnostics = hand.joint_diagnostics().subscribe()
        hand.enable()
        wait_enabled(diagnostics)
        states = hand.joint_states().subscribe()
        base = positions(states)
        publisher = hand.joint_command().publish()
        print(f"执行 {args.trajectory} ({len(deltas)} 帧)", flush=True)
        play_wave(publisher, base, deltas, args.source_rate, args.rate, args.cycles)
    except BaseException:
        try:
            hand.emergency_stop()
        finally:
            raise
    finally:
        if publisher is not None:
            publisher.close()
        if states is not None:
            states.close()
        if diagnostics is not None:
            diagnostics.close()
        try:
            hand.disable()
        finally:
            try:
                if old_mit is not None:
                    hand.mit_params().set([(item.kp, item.kd) for item in old_mit])
                if old_effort is not None:
                    hand.effort_limit().set(old_effort)
            finally:
                manager.disconnect(device_name="wuji_hand_2")


if __name__ == "__main__":
    main()
