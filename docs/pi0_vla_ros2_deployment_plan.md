# pi0 VLA + ROS2 机械臂部署计划

> 目标：在机械臂上部署 pi0 这类 VLA policy。第一阶段只做浮点部署，优先跑通闭环，不急着做 QNN 量化或端侧极限优化。  
> 计划开始日期：2026-05-26，周二。  
> 每天按 8 小时规划。

## 1. 总体思路

先把任务拆成四层：

```text
Camera / Robot State / Language Prompt
        |
        v
ROS2 Observation Node
        |
        v
Policy Client Node  <---- websocket / RPC ---->  pi0 Policy Server
        |
        v
Action Adapter Node
        |
        v
Safety Filter / Rate Limit / Workspace Limit
        |
        v
ROS2 Controller / MoveIt2 / ros2_control / Vendor SDK
        |
        v
Robot Arm + Gripper
```

第一阶段最重要的不是任务成功率，而是：

- observation 能稳定采集。
- policy server 能稳定返回 action。
- action 能映射成机械臂命令。
- 命令经过安全过滤后能让机械臂小幅运动。
- 全流程可停止、可记录、可回放、可 debug。

## 2. 需要优先确认的问题

1. 机械臂型号、自由度、gripper 型号。
2. ROS2 版本、Ubuntu 版本、已有 bringup package。
3. 控制接口：MoveIt2、ros2_control、厂商 SDK、topic/service/action。
4. 相机：外部 RGB、腕部 RGB、深度相机、topic 名、分辨率、帧率。
5. 计算平台：机器人本体、工作站、Qualcomm 设备、是否有 GPU。
6. pi0 输入格式：图像、机器人状态、语言 prompt。
7. pi0 输出格式：joint delta、end-effector delta、gripper command、action chunk。
8. 是否允许 remote inference，即模型跑在工作站，机器人端只跑 ROS2 client。

## 3. 阶段目标

### Phase 1：闭环打通

- ROS2 能读相机和机器人状态。
- pi0 policy server 能跑 float inference。
- ROS2 client 能收到 action。
- action adapter 能发安全小动作。

### Phase 2：任务最小 demo

- 固定桌面、固定相机、固定 prompt、固定物体。
- 先做 reach / move near object / gripper open-close 这类低风险任务。
- 连续测试并记录失败模式。

### Phase 3：稳定性与性能

- 加 watchdog、timeout、NaN check、rate limit。
- 跑 benchmark 和 rosbag。
- 分析 latency 和失败原因。

### Phase 4：再考虑部署优化

- 是否需要端侧推理。
- 是否需要 ONNX / TorchScript / TensorRT / QNN。
- 是否需要 fine-tuning。
- 是否需要自定义动作空间或数据采集。

## 4. 每日计划

### Day 1：周二 2026-05-26，需求澄清 + 环境摸底

上午 4 小时：

- 确认机械臂型号、gripper、ROS2 版本、OS 版本。
- 梳理已有 ROS2 package：bringup、description、controller、MoveIt2。
- 确认相机 topic、robot state topic、gripper topic。
- 确认计算资源和是否能 remote inference。

下午 4 小时：

- clone openpi / pi0 相关代码。
- 跑通官方最小 inference 或 dummy inference。
- 阅读 remote inference 文档。
- 写 `deployment_notes.md`：记录输入、输出、topic、server/client 位置。

交付物：

- 机器人接口表。
- openpi/pi0 是否能启动的结论。
- 当前 blocker 列表。

### Day 2：周三，ROS2 bringup 和安全运动

上午 4 小时：

- 启动机械臂 bringup。
- `ros2 topic list`、`ros2 service list`、`ros2 action list`。
- 检查 `/joint_states`、TF tree、robot description。
- RViz2 中确认模型和 TF 正常。

下午 4 小时：

- 测试最小安全运动：小幅 joint move、末端小幅移动、gripper open/close。
- 确认急停方式。
- 写安全限制初版：最大速度、最大关节增量、workspace box。

交付物：

- `ros2_robot_interface.md`
- 一个最小安全运动脚本。
- 安全参数初版。

### Day 3：周四，Observation Node

上午 4 小时：

- 写 ROS2 observation node。
- 订阅相机、joint states、gripper state。
- 保存一帧 observation 到本地。

下午 4 小时：

- 图像预处理：resize、RGB/BGR、normalize、timestamp。
- robot state 预处理：joint position、end-effector pose、gripper state。
- 定义 observation dict / JSON / pickle 格式。

交付物：

- `observation_node.py`
- `sample_observation.pkl` 或 `sample_observation.json`
- observation 字段说明。

### Day 4：周五，Policy Server + ROS2 Client

上午 4 小时：

- 启动 pi0 policy server。
- 用官方 client 发 dummy observation。
- 记录返回 action shape、dtype、action chunk 长度。

下午 4 小时：

- 写 ROS2 policy client node。
- 把 observation node 输出转成 policy input。
- 收到 action 后暂时只打印，不控制机械臂。

交付物：

- `policy_client_node.py`
- pi0 输入输出 shape 记录。
- 一次 observation -> action 的完整日志。

### Day 5：Action Adapter

上午 4 小时：

- 确认 action 语义：joint delta、end-effector delta、absolute pose、gripper command。
- 写 action adapter，把 policy action 映射成 robot command。

下午 4 小时：

- 先在 fake controller / RViz / dry-run 模式测试。
- 加安全过滤：NaN check、clip、rate limit、workspace limit、timeout。
- 真机只做极小幅动作。

交付物：

- `action_adapter_node.py`
- `safety_filter.py`
- action mapping 说明。

### Day 6：完整闭环 dry run

上午 4 小时：

- 跑完整链路：camera/state -> observation -> policy -> action adapter -> safety -> robot。
- 不接触物体，只做空中动作。

下午 4 小时：

- 加日志：图像、state、prompt、raw action、clipped action、executed command。
- 录 rosbag。
- 统计 latency：采集、推理、通信、控制。

交付物：

- 第一次闭环视频或日志。
- latency 表。
- rosbag。

### Day 7：最小任务 demo

上午 4 小时：

- 和 mentor 确认第一个 demo task。
- 建议从 reach object / move near object / gripper open-close 开始。
- 固定相机、桌面、物体、光照、prompt。

下午 4 小时：

- 连续测试 10 次。
- 记录失败模式：场景识别、action scale、坐标系、gripper、latency、抖动。

交付物：

- `first_task_eval.md`
- 10 次测试表。
- 失败模式列表。

### Day 8：坐标系和动作尺度

上午 4 小时：

- 检查 camera frame、base frame、end-effector frame。
- 确认 action 坐标系和单位。
- 检查 gripper action 的范围和方向。

下午 4 小时：

- 调 action scale。
- 调 control frequency。
- 调 action chunk 执行策略：执行整段、只执行前 k 步、每次重规划。
- 再做 10 次测试。

交付物：

- 坐标系说明。
- action scale 参数表。
- 改进后测试结果。

### Day 9：稳定性和安全

上午 4 小时：

- 加 watchdog：policy server 断线停止、observation 超时停止、action 异常停止。
- 加 manual enable/disable。
- 加 dry-run 模式。

下午 4 小时：

- 测 policy server 重启。
- 测相机断流。
- 测控制异常。
- 整理安全 checklist。

交付物：

- `safety_checklist.md`
- watchdog 机制。
- 稳定性测试记录。

### Day 10：整理 demo 和汇报

上午 4 小时：

- 整理代码结构。
- 写启动脚本或 launch 文件。
- 写 README。

下午 4 小时：

- 录制 demo。
- 整理结果、blocker、下一步计划。
- 准备 5 分钟 mentor 汇报。

交付物：

- `README.md`
- `demo_launch.md`
- demo 视频。
- mentor 汇报材料。

## 5. 每天固定记录模板

每天结束前记录：

```text
日期：
今天完成了什么：
遇到什么 blocker：
明天第一件事：
需要 mentor 回答的问题：
当前风险等级：
```

## 6. 最高风险点

1. pi0 action space 和机械臂控制接口不一致。
2. 相机视角和模型训练数据差异太大。
3. 没有 fine-tuning 数据，zero-shot 效果不稳定。
4. ROS2 控制频率和模型 inference latency 不匹配。
5. 坐标系错位导致方向反了或尺度错了。
6. gripper 时机不对。
7. float 推理延迟过高。
8. 安全限制不充分，真机测试风险高。

## 7. 对 mentor 的问题

1. 当前项目的目标 backend 是 HTP、GPU、CPU，还是先只在 GPU 工作站 remote inference？
2. 机械臂控制推荐走 MoveIt2、ros2_control，还是厂商 SDK？
3. 第一个 demo task 应该是什么？
4. 是否已有相机标定和 hand-eye calibration？
5. 是否需要采集数据做 pi0 fine-tuning？
6. 是否要求最终跑在 Qualcomm 端侧设备上？
7. 是否允许远程 policy server？
8. 项目中有没有已有的 ROS2 launch、controller config、benchmark template？
