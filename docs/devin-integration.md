# Devin Bot 接入方案：选 GitHub Actions / CI，不选 Slack / Discord 常驻 Bot

选择：**方案 1，GitHub Actions / CI 自动开 Devin session 修代码提 PR。**

不选方案 2 的原因：Slack / Discord 常驻 Bot 要另搭日志采集、实时监听、常驻进程和打补丁通道，链路长、没有仓库内的审计痕迹、成本一直在线，审核时很难证明“一次异常到底走了哪一步”。Actions 是事件驱动的，一次失败对应一次可查的 run、一次 artifact、一次 Devin session、一次 PR，全部留在仓库里。

## 闭环链路

```
agent_tool_wrapper.py 复现失败
  -> tests/test_tool_wrapper.py 在 CI 里跑，断言失败
  -> .github/workflows/devin-auto-fix.yml 捕获失败日志
  -> 按失败签名去重，调用 Devin API v1 创建 session
  -> Devin 在仓库里修代码、加回归测试、开 PR
  -> 同一个 CI 在 PR 上重跑测试，通过才允许合
  -> 人工 review 后合并，失败签名关闭
```

公开 Gist 是同一份复现脚本的只读副本，方便审核直接跑：
https://gist.github.com/cbkzc28tp2-png/7aff125fc3cdb2389d7bda25bd72ace5

## 触发条件

- push 到 main、PR、手动 workflow_dispatch 时跑测试。
- 只有 `tests/test_tool_wrapper.py` 失败才触发 Devin，正常通过不触发。
- 失败签名 = pytest 失败输出去掉时间戳、路径和行号抖动后取 SHA-256 前 16 位。
- 同一签名 24 小时内只开一个 session，靠 Devin API 的 `idempotency_key` 去重。

## Devin session 怎么开

官方 API，实测文档在 https://docs.devin.ai/api-reference/v1/sessions/create-a-new-devin-session ：

```
POST https://api.devin.ai/v1/sessions
Authorization: Bearer $DEVIN_API_KEY
Content-Type: application/json

{
  "prompt": "<见下>",
  "idempotency_key": "<failure-signature>",
  "max_acu_limit": 10
}
```

返回 `session_id` 和 `url`，workflow 把这两个值写进 run 的 summary 和 artifact，
同时在失败 issue 里贴出 session 链接。

Devin 侧的官方能力也支持这个闭环：Devin 接入 GitHub 后可以在 PR 上自动响应
评论和 CI 失败，`/devin` 评论可以在已开的 PR 上再开一个 session。issue 评论本身
不会直接触发 Devin，所以这里不靠 issue 评论触发，靠 Actions 直接调 API。

`DEVIN_API_KEY` 只放在 GitHub Actions Secrets 里，不进仓库、不进日志。
没有这个 secret 时，workflow 不静默跳过，而是建一个带 `devin-fix` 标签的
issue，把失败日志和复现步骤贴进去，等人工补 secret 后手动重跑。

## 发给 Devin 的 prompt 模板

```
仓库：cbkzc28tp2-png/linalianan，分支 main，提交 <sha>
失败测试：tests/test_tool_wrapper.py
失败签名：<signature>
失败日志（截断到 8000 字符）：
<log>

任务：只修 agent_tool_wrapper.py 里的重试逻辑。
1. 重试时不要把幻觉参数再喂回去，不要往 params 里写 hallucinated_key。
2. 每次重试用清洗过的原始 params，retry_count 只做计数，不进 params。
3. 保留原有行为：缺 query 报错、force_fail 最终报 ToolCallError。
4. 加回归测试，证明重试 5 次后 params 没有被污染。
不要做：不要改 index.html，不要改 workflow，不要加新依赖，不要自动合并。
验收：pytest tests/test_tool_wrapper.py 全过，python agent_tool_wrapper.py 能跑完。
```

## 防死循环护栏

- 同一失败签名最多开 3 个 session，第 3 个仍失败就停下来，改走人工 issue，不再自动开。
- Devin 的 PR 不自动合并，必须人工 review + CI 全绿。
- Devin 不碰 secrets、不改 workflow 文件、不改部署配置。
- 每次 session 设 `max_acu_limit: 10`，超了就停，不无限烧额度。
- 日志只截断贴出，不贴密钥、不贴用户隐私。

## 审核时能查到的证据

1. Gist 里的复现脚本，本地 `python agent_tool_wrapper.py` 就能跑出失败。
2. 仓库里 `tests/test_tool_wrapper.py` 现在有一条会失败的测试，就是这个 bug 的回归测试。
3. Actions 的一次失败 run 里有 failure-log artifact、失败签名、Devin session 链接。
4. Devin 开的 PR 上有 CI 结果，合并不合由人决定。

## 现在的状态

- 复现脚本、回归测试、workflow、本文档都已进仓库 main。
- 还没接通的是 `DEVIN_API_KEY` 这个 secret，和 Devin 的 GitHub App 授权，
  这两步只能由仓库所有者在 GitHub 上做，代码里不放密钥。
- 接通后第一次触发就能走完整条链路，不需要再改代码。
