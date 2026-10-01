---
title: AI 的缓存会“凉”，凉了你就在按全价付钱
date: 2026-10-01 11:40:00
tags: [缓存, KV缓存, 缓存保温, agent, 省钱, 工程]
categories: [技术]
---

**——我们给它留了盏灯，顺手把 98.2% 的 token 变成了打折价（附可复制的 prompt 和复现命令）**

写于 2026-10-01 · 数据全部来自本机 pi 0.99.2（Windows）真实会话，命令在文末，可自己跑一遍

---

## 0. 30 秒版

- 你每次向 AI 提问，它都要把**从系统提示到当前这句话的完整前缀**重读一遍。读的结果会存进缓存。
- 缓存有**保质期**。你走开一会儿（想事情、等工具跑完），缓存到期被清掉。你回来时，它把你之前所有的话按**全价**重读一遍。
- 我们做的事很小很土：**在你还没回来的时候，替你把缓存续上**——把上一次请求原样再发一遍，只让它吐 1 个 token。
- 效果（我们自己的机器，2026-09 全月）：

| 指标 | 实测值 |
|---|---|
| 有 usage 的对话轮次 | 3949 轮 / 78 个会话 |
| 输入 token 里走缓存的比例 | **98.2%**（缓存读 545.35M vs 真输入 9.75M） |
| 保温续温次数 | 59 次（跨 20 段空闲期，5 天） |
| 59 次续温总花费 | **$0.0352** |
| **一次冷重读**（21.9 万 token 前缀） | **$0.0300** |
| 续温 vs 重读 单价 | **1 : 49**（账本实测中位数） |

**记住这个数**：续温 59 次的钱 ≈ 重读 1 次的钱。
所以整个策略的经济学只有一句话——**那是个极便宜的期权：接住一次“你回来了”，就回本了。**

---

## 1. 为什么缓存会凉（人话版）

打个比方：**你让一个抄书的人，把你之前说的话全抄一遍才能回答你这一句。**

- 他抄完会留个底稿（**KV 缓存**），下次接着抄，就不必从头。
- 底稿占桌子，所以他只留 **5 分钟**（千问显式缓存 TTL = 5 分钟），过时就扔。
- 你出去喝了杯水回来接着问 —— 底稿没了 —— **他又从头抄一遍，这一遍按原价收钱。**

而 AI agent 的工作节奏，恰好**每一步都卡在这个 5 分钟上**：写代码、跑测试、等你读输出、等你打字，动不动就几分钟。

**打折有多狠**（各家公开价，2026-10-01 核过官方页）：

| 家 | 未命中（全价） | 缓存命中 | 折扣 |
|---|---|---|---|
| 千问（百炼）显式缓存 | 100% | **10%**（创建时另收 125% 一次） | 打 1 折 |
| 千问 隐式缓存 | 100% | 20% | 打 2 折 |
| 智谱 GLM-5.3 | 8 元/M | 2 元/M | 25% |
| DeepSeek 硬盘缓存 | 100% | 官方说法“再降一个数量级” | ~10% |
| 我们自己的小米 mimo 实测 | 100% | 账本实测 **1/49** | ~2% |

> 也就是说：**缓存活着的时候，你在打 2~5 折；缓存一凉，你立刻回到原价。** 中间没有任何提示，账单上也不写“你的缓存凉了”。

---

## 2. 我们量出来的那道“悬崖”

这是全文最直观的一张表（本机实测，复现命令见文末）。把相邻两次对话的**时间间隔**分桶，看这一次的输入有多少是走了缓存的：

| 距上一次说话的间隔 | 轮数 | 真输入（全价） | 读缓存（打折） | 复用率 |
|---|---|---|---|---|
| < 1 分钟 | 3196 | 6.75M | 434.59M | 98.5% |
| 1–5 分钟 | 453 | 1.00M | 70.67M | 98.6% |
| 5–30 分钟 | 195 | 0.86M | 33.71M | 97.5% |
| 30 分钟–2 小时 | 20 | 0.39M | 4.79M | **92.5%** |
| 2–24 小时 | 7 | 0.38M | 1.43M | **79.0%** |

再把千问单独拎出来（它用的是**显式缓存，TTL 正好 5 分钟**）：

| 距上一次说话的间隔 | 轮数 | 复用率 |
|---|---|---|
| < 5 分钟 | 313 | **99.1%** |
| 5–30 分钟 | 13 | **32.5%** ← 悬崖 |

**读法**：
- **5 分钟是显式缓存的悬崖**：超过 5 分钟，命中率从 99.1% 掉到 32.5%。
- **半小时是隐式缓存的斜坡**：隐式缓存 TTL 更长，半小时后开始劣化，隔夜只剩 79%。

那 13 轮 5–30 分钟的请求，真输入 636.6k token —— **全部按全价付了**。这不是 bug，这是没人管的缓存寿命。

---

## 3. 你能做什么：先分清情况

| 你的 AI 是 | 缓存归谁管 | 你能做的动作 |
|---|---|---|
| **自建推理**（vLLM / 自己显卡） | 你自己的引擎 | 能**钉住**（pin）：直接不让它驱逐，TTL 到期自动放 |
| **用 API**（我们的情况） | 服务商 | 只能**续温**（warm）：定时拿同一份请求重放一次，把寿命顶下去 |
| **订阅制**（token-plan / 包月） | 服务商 | 同上，但**账单不显示钱，只显示额度** → 更容易被忽略 |

> 顺便说清一件事：有一篇很漂亮的论文（UC Berkeley，arXiv 2511.02230，*Continnum*）做的是第一格——在**显卡里**把 KV 缓存钉住，用工具耗时的经验分布算出最优过期时间 τ\*，多轮任务完成时间最高降到 1/8。
> 我们在做第二格——在**账单里**续温。**同一道数学题，两枚币**（他们的是显存，我们的是美元）。
> 而且我们核过它的开源仓库：**论文里的 τ\* 估计器并没有放出来**（仓库 README 自己写着 “without the estimation in the paper”，代码里只有一颗写死的 2 秒阈值）。所以下面这套判据是我们自己推的，不是抄来的。

---

## 4. 怎么做：5 步

### Step 0 · 先测：这家有没有缓存折扣（1 分钟）

同一个请求连发两次，看**第二次**返回的 `usage`：

```bash
# 换 key / 换 base_url 即可测任意 OpenAI 兼容端点
curl -s https://<你的端点>/chat/completions \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"<模型>","messages":[{"role":"system","content":"<一段长系统提示>"},{"role":"user","content":"hi"}],"max_tokens":1}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["usage"])'
```

你要看的字段（各家名字不同，见到就算有）：
`prompt_tokens_details.cached_tokens`（千问/OpenAI 系）、`prompt_cache_hit_tokens`（DeepSeek）、`cache_type:"ephemeral"`、`cache_creation`（千问显式路径的标志）。

**第二次 `cached` 显著大于 0，才值得往下做。** 全是 0 就停手——这家没有缓存折扣，后面所有事都没意义。

### Step 1 · 开显式缓存（以 pi 为例，3 处配置 + 2 个坑）

改 `~/.pi/agent/models.json` 的对应 provider：

1. `baseUrl` 指向带缓存能力的端点；
2. `compat` 里加 `"cacheControlFormat": "anthropic"`（pi 会照着 Anthropic 的写法，自动在系统提示、最后一个工具、最后一条消息上打 `cache_control: {type:"ephemeral"}`）；
3. **删掉** `compat.thinkingTokenBudgetField`——否则 pi 会同时发 `reasoning_effort` 和 `thinking_budget`，端点直接 400。

坑：① 有些端点只认官方目录里的模型名（不在 pi 目录里的名字要先补进去）；② 显式缓存的 TTL 只有 **5 分钟**，比隐式缓存短得多——**开了显式缓存，保温就从“可选”变成“必须”**。

### Step 2 · 装保温器

保温器只做两件事：

1. **抓一份完整的真实请求**（messages / tools / 系统提示 / 思考参数，一字不改，工具定义顺序也不能动）；
2. **空闲后**，按 `TTL × 0.9` 的间隔把这份请求原样重发，只改两个字段：`stream=false`、`max_completion_tokens=1`，然后把每次响应的 usage 记进账本。

我们的实现是一个 pi 扩展（`cache-keeper.ts`），在 pi 的事件上挂钩子：`before_provider_request` 抓请求快照，`agent_settled` 开始计时，空闲时自行重放，`agent_start / turn_start` 一有真实请求就立刻停。

> **为什么不能靠 pi 自带的保温？** 它的判据是**绝对金额**：预期省钱 ≥ $0.05 才保温。而 10 万 token 前缀的 miss 成本只有 $0.014，订阅制模型记账全是 0 —— 数学上永远不触发。（这个坑我们踩过，写在这里免得你再踩。）

### Step 3 · 判断该不该续（人话版判据）

用不着公式也能想明白：

- 续一次的价钱 ≈ **命中价 × 前缀长度**
- 重读一次的价钱 ≈ **（全价 − 命中价）× 前缀长度** ≈ 续温价的 **4 ~ 49 倍**

所以：**只要我可能回来，就值得续一次**（一次回本）。护栏只有一条——

> 连续续到 **(已续次数 + 1) × 单次续温价 ≥ 单次重读价**，就停。

因为我们并不知道你还会不会回来；这条线保证了“最坏情况也只是白花一次重读的钱，绝不会白花两次”。

真实数字（账本原文，21.9 万 token 前缀）：
- 单次续温 **$0.000613**
- 单次冷重读 **$0.0300**
- 比值 **49×**

### Step 4 · 设边界（三条，缺一不可）

1. **一有真实请求立刻停**（否则和用户自己的请求抢流量、还白花钱）；
2. **空闲上限**（我们设 4 小时，到点就停）；
3. **报错只停不救**：服务端返回 400/401 就停这一段，不重试、不改请求体重试（改了就换了前缀，等于白保）。

---

## 5. 三段可以直接照抄的 prompt

### Prompt A · 给 agent 的“自保温”实现指令

粘贴给你自己的编码 agent（pi / Claude Code / Cursor / hermes 都行）：

```text
你现在要给自己加一个能力：空闲时给自己的 prompt 缓存续温。

背景：我每次请求都会把「系统提示 + 全部历史 + 工具定义」作为完整前缀发给模型。
服务端会缓存这段前缀的 KV，但有过期时间（TTL，例如显式缓存 5 分钟）。
我离开几分钟再回来，缓存通常已经没了，同样的前缀要按未命中价重读一遍。

请实现：
1) 每次真实请求发出前，把这次请求的完整 body 原样存一份快照。
   messages / tools / 系统提示一字不改，工具定义顺序也不能变。
2) 本回合结束、我进入空闲后，每个 TTL×0.9 秒，把这份快照原样重发一次；
   只允许改两个字段：stream=false、max_completion_tokens=1。
3) 每次重发后读响应 usage：cached_tokens / prompt_tokens。
   cached_tokens > 0 才算真的续上了，把它记下来。
4) 维护一份账本（JSONL，一次一行）：时间、模型、prompt token 数、
   cached token 数、本次续温花费、以及「若没续上而重读一遍」的花费。
5) 停止条件（三条都要）：
   a. 我发出真实请求 → 立刻停；
   b. (已续次数 + 1) × 单次续温价 ≥ 单次重读价 → 停；
   c. 空闲超过 4 小时 → 停。
6) 禁止：不要修改 messages/tools；不要在报 400 后重试；不要在我说话时续温。

先把你的实现计划和账本字段列给我看，我说可以再动手。
```

### Prompt B · a2a 唤醒消息（一个 agent 发给另一个 agent）

**先说清一个我们踩过的坑：保温是“自证”动作，不是“代劳”动作。** 你不能替对方保温，因为缓存匹配的是**从第 0 个 token 开始的完整前缀**——你的历史和他的历史不可能逐字节相同。所以 a2a 能做的只是**唤醒对方、让对方自己续**：

```text
【保温协商 · a2a】
我方：<agent-A> / session <id> / 模型 <model> / 前缀 <N> tokens / TTL <T> 秒 / 当前空闲
请你方（<agent-B>）做：
  在你方自己进入空闲时，用「你方自己那份完整请求 body」原样重发一次
  （stream=false, max_completion_tokens=1），把 usage 记进你方账本。
请不要做：
  不要用我方的历史消息替我发请求——前缀必然对不上，实测命中率仅 1.4%；
  也不要指望我替你续——同理。
回报格式：
  {"agent":"...","session_id":"...","prompt_tokens":N,"cached_tokens":M,"cost":X}
```

### Prompt C · **不存在**（这条比前两条更重要）

我们真的试过让 pi 侧替 hermes 侧的会话保温（扩展名 `external-keeper`），**7 次尝试全部不合格**：

| 结果 | 次数 | 原因 |
|---|---|---|
| HTTP 400 | 3 | 重建历史时 `assistant.tool_calls` 没有配对到对应的 tool 结果消息，服务端直接拒 |
| 命中率 1.4% / 8.6% / 0% | 3 | 请求合法了，但前缀不是同一份 bytes（系统提示 14433 字符、12 个工具、390 条消息，任何一处差异，缓存从差异那一点起全部作废） |
| 无命中 | 1 | 同上 |

**结论：跨 agent 保温不成立，除非两侧共用同一份字节级前缀。** 每一个 agent 只能保自己的缓存 —— 这不是实现问题，是缓存的定义。

---

## 6. 我们在哪些 agent 上试过（诚实清单）

| 对象 | 状态 | 证据 |
|---|---|---|
| **pi 0.99.2**（Windows，本机） | ✅ 跑通，有账本 | 59 次续温 / 20 段空闲期 / 98.2% 命中 / 单次 49× |
| **hermes**（WSL，`/mnt/i/hermes`） | ⚠️ 失败，已留证 | `external-keeper-ledger.jsonl`：3×400 + 命中率 1.4%/8.6%/0% |
| 自建 vLLM 推理栈 | ⬜ 没做 | 那是论文的战场（pin），我们只做 API 侧续温 |
| Claude Code / Cursor / Codex | ⬜ **没实测** | 原理相同（Anthropic 系的 prompt cache 也是 TTL 档位），但**我们没有在它们上验证过，所以不吹**。做法可以直接照搬 Prompt A |

**边界**（不写这三条就不诚实）：
1. 我们**只在一台机器、一个 agent（pi）上拿到完整数据**；
2. 59 次续温里，被用户真实“兑现”的只有 2 段（`real request arrived`）——其余是撞上 4 小时上限停止（11 段）、session 关机（1 段）、报 400（6 段）。所以 **$1.72 是“被覆盖前缀若重读的全价”，不是“已经省下的钱”**；已经省下的钱 ≤ $1.72，但 $0.0352 是**确定花掉的**，这就是全部风险敞口；
3. 保温**只对“你还会回来”有效**，不回来就是白花——所以我们才要设上限。

---

## 7. 复现（自己跑一遍）

全部命令在 WSL 里执行，数据是 pi 自己写的会话文件，不依赖任何私有服务：

```bash
# ① 汇总：缓存读 / 真输入 / 复用率 / 间隔分桶（含千问 5 分钟悬崖）
python3 - <<'PY'
import json,glob,collections,datetime as dt
files=glob.glob('/mnt/c/Users/Administrator/.pi/agent/sessions/**/*.jsonl',recursive=True)
S=collections.defaultdict(list)
for f in files:
    sid=f.split('/')[-1][:36]; prov=model=None
    for l in open(f,encoding='utf-8',errors='replace'):
        l=l.strip()
        if not l: continue
        try: d=json.loads(l)
        except: continue
        if d.get('type')=='model_change': prov,model=d.get('provider'),d.get('modelId')
        elif d.get('type')=='message' and (d.get('message') or {}).get('role')=='assistant':
            u=d['message'].get('usage') or {}
            if 'cacheRead' not in u: continue
            try: ts=dt.datetime.fromisoformat(d['timestamp'].replace('Z','+00:00'))
            except: continue
            S[sid].append(dict(ts=ts,ci=u.get('input',0),cr=u.get('cacheRead',0),prov=prov))
CI=sum(r['ci'] for v in S.values() for r in v); CR=sum(r['cr'] for v in S.values() for r in v)
print(f'会话 {len(S)} · 轮次 {sum(len(v) for v in S.values())} · 真输入 {CI/1e6:.2f}M · 缓存读 {CR/1e6:.2f}M · 复用率 {100*CR/(CI+CR):.1f}%')
B=[(0,60,'<1分钟'),(60,300,'1-5分钟'),(300,1800,'5-30分钟'),(1800,7200,'30分钟-2小时'),(7200,86400,'2-24小时')]
for name,pred in (('全部模型',lambda r:True),('千问(显式5分钟)',lambda r:(r['prov'] or '').startswith('qwen'))):
    print('--',name)
    for lo,hi,lab in B:
        n=ci=cr=0
        for v in S.values():
            v.sort(key=lambda r:r['ts'])
            for i in range(1,len(v)):
                g=(v[i]['ts']-v[i-1]['ts']).total_seconds()
                if lo<=g<hi and pred(v[i]): n+=1; ci+=v[i]['ci']; cr+=v[i]['cr']
        if n: print(f'   {lab:14} {n:5d}轮  复用率 {100*cr/(ci+cr):5.1f}%')
PY

# ② 保温账本：每次续温花了多少、命中没有、什么时候停
python3 -c "
import json,collections
rows=[json.loads(l) for l in open('/mnt/c/Users/Administrator/.pi/agent/cache-keeper-ledger.jsonl',encoding='utf-8') if l.strip()]
w=[r for r in rows if r['event']=='long_warm']
print('续温',len(w),'次 · 总花费 \$%.4f'%sum(r['warmCost'] for r in w),'· 潜在重读价值 \$%.4f'%sum(r['missCost'] for r in w))
print('结束原因',collections.Counter(r['reason'] for r in rows if r['event']=='long_warming_end').most_common())
"

# ③ 文件位置
#   会话与账本： /mnt/c/Users/Administrator/.pi/agent/{sessions,cache-keeper-ledger.jsonl,external-keeper-ledger.jsonl}
#   保温器源码： /mnt/c/Users/Administrator/.pi/agent/extensions/cache-keeper.ts
```

---

## 8. 别踩的坑（都是我们踩过的）

1. **自带保温可能永不触发**：绝对金额阈值（如 `$0.05`）对国产订阅制模型永远不成立（成本记 0）。
2. **别双重保温**：跑了自己的扩展就把配置文件里的原生保温关掉，否则同一份前缀被续两遍。
3. **400 大多来自“重建历史”**：续温一定用**真实请求快照**，不要自己拼消息；`tool_calls` 必须配对。
4. **前缀一变，缓存全废**：改系统提示、加减工具、换模型、甚至工具定义顺序变了，缓存从差异点起全部作废。
5. **别把“续上的次数”当“省下的钱”**：续温费是确定支出，省下的钱取决于你回不回来。所以上限必须有。
6. **注意 TTL 长短与策略的配套**：显式缓存 TTL 短（5 分钟）→ 必须保温；隐式缓存 TTL 长（半小时以上）→ 可以少管。**先测出你家的 TTL，再决定保不保。**

---

## 9. 收尾

缓存是 AI 时代最便宜的一张期权：**续一次的钱是重读的 1/49，续 59 次的钱是一次重读的钱。**

你要做的只有一件事：**离开的时候，留一盏灯。**

---

*配套材料：保温器源码 `cache-keeper.ts`；保温账本 `cache-keeper-ledger.jsonl`（59 条）；跨 agent 失败记录 `external-keeper-ledger.jsonl`。*
*价格来源：阿里云百炼上下文缓存文档 / DeepSeek 定价页 / 智谱 BigModel 定价页（2026-10-01 核对）。论文对照：arXiv 2511.02230v7 + 官方仓库 Hanchenli/vllm-continuum。*
