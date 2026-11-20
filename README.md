# single-loop

一个最小的单循环 Agent 实现：一个模型、一个上下文窗口，所有工作都在同一份上下文里完成。

能力不预先塞进系统提示词，而是分四类挂在外面，靠索引和按需加载进入上下文：

- **技能**管流程：团队的工作方式，步骤、规则、判断标准。
- **工具**管动作：执行操作、读实时数据、返回固定格式结果。
- **知识**管事实：偶尔查阅的参考资料。
- **代码**管预处理：实体解析这类成本低且几乎总是相关的内容。

工具自己检查前置条件和权限，拒绝以结构化结果返回，模型读得懂就能改路。门控在循环外，只回答一个问题：还该不该继续。

## 四条不变式

代码里能断言的只有四条，其余都是实现细节。

1. **上下文单例**：任何时刻只有一份 `messages`，没有第二个窗口。
2. **资产四分**：技能、工具、知识、代码各有各的通道，不混用。
3. **索引常驻、正文按需**：默认上下文里只有类别和数量，正文必须经过一次检索才进来。
4. **结果不摘要**：工具返回原样回灌，不做压缩。

## 快速开始

```bash
python examples/demo.py     # 离线演示，不需要 key
python -m pytest            # 测试
```

演示输出里能看到四个机制依次生效：直接调用被挡、检索后工具出现、前置条件拒绝、补齐依赖后成功。

```
第 1 轮 模型可见工具：['discover', 'update_plan']
call_update_address not_loaded           update_address 还没有被检索加载，先调用 discover
第 3 轮 模型可见工具：['discover', 'update_plan', 'update_address']
call_update_address precondition_failed  update_address 需要先成功调用 ['get_order']
第 5 轮 模型可见工具：['discover', 'update_plan', 'get_order', 'update_address']
call_update_address ok
```

## 接入真实模型

```python
from single_loop import Budget, MainLoop, Registry
from single_loop.clients import OpenAICompatClient

model = OpenAICompatClient(
    api_key="sk-xxx",
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
)
loop = MainLoop(model, Registry(), budget=Budget(max_turns=12))
loop.register_tool(my_tool)          # 业务工具，注册后仍然对模型不可见
result = loop.run("用户的请求")
```

`openai` 是可选依赖：`pip install single-loop[openai]`。

## 结构

```
single_loop/
├── spec.py        四类资产与不变式
├── gate.py        轮次、预算、重复拒绝止损
├── registry.py    资产注册
├── disclosure.py  二级索引、检索、按需加载
├── runtime.py     前置条件、权限、机械部分
├── loop.py        主循环
├── verify.py      形式检查 + 语义验证接口
├── clients.py     OpenAI 兼容适配
└── testing.py     脚本化模型
```

## 两个关键设计

**验证分两层。** 形式检查和语义验证不是一回事。前者比对可核对的事实（空答案、超长、代码块未闭合、禁用字面量），和回答者在同一个上下文里做没有问题；后者判断答案对不对，必须换一个执行体，否则就是让回答者给自己打分。所以 `verify.py` 里 `FormalVerifier` 在循环内跑，`SemanticVerifier` 只给协议。

**门控多一条止损。** 轮次和成本只能兜底。工具拒绝之后模型很可能换个参数再试，来回几次就把轮次耗光。`Gate` 因此记录同一个调用签名被拒的次数，满 N 次直接停。

## 边界

这是最小实现，不是生产框架。

- 检索是本地关键词加中文二元组，不是向量检索。工具规模上千时需要换掉 `disclosure.search`。
- 没有会话持久化，进程退出即丢失。长任务要分段恢复得自己接。
- `SemanticVerifier` 只给了协议，没有实现，也没有防止误用同一上下文的机制。
- 代码资产目前只做登记，没有执行沙箱。

## License

MIT
