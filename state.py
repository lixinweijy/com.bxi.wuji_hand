from bxi_example_py_elf3.framework.mod_api import RobotControlState


class WujiHandState(RobotControlState):
    """让独立的 Wuji 进程控制灵巧手，同时保持机器人本体上一帧命令。"""

    def on_update(self, ctx, dt: float) -> None:
        # ponytail: hold one resolved body frame; compose with normal policy
        # only when concurrent locomotion becomes a real requirement.
        ctx.set_motor_target(ctx.last_motor_frame)
