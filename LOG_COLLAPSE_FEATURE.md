# WebUI 日志折叠功能说明

## ✨ 新功能

运行时日志（Runtime Log）现在会**嵌入到每条聊天消息中**，并支持**点击展开/收起**。

---

## 🎯 效果展示

### 之前
- ❌ 日志显示在右侧独立的 "RUNTIME LOG" 面板
- ❌ 日志与对话内容分离，难以对应
- ❌ 无法折叠，占用大量空间

### 现在
- ✅ 日志嵌入到每条 Bot 回复下方
- ✅ 默认收起，不占用空间
- ✅ 点击展开查看详细执行过程
- ✅ 再次点击收起，保持界面整洁

---

## 📋 使用方式

### 1. 发送消息
```
用户: 帮我查一下从上海到北京的运价，300kg
```

### 2. Agent 回复
```
🤖 DEEPAGENT
─────────────────────
📦 上海→北京 报价单
...

▼ Runtime Log (42 lines)    [点击展开]
```

### 3. 点击展开
```
🤖 DEEPAGENT
─────────────────────
📦 上海→北京 报价单
...

▼ Runtime Log (42 lines)
─────────────────────
[DeepAgent] 启动中...
[SkillRegistry] ✓ logistics-sales-agent
[ReAct] 步骤 1 | action=use_skill
[SkillTool] 调用 skill=logistics-sales-agent
[ScriptRunner] 执行: python quote.py --from 上海 --to 北京 --weight 300
[ScriptRunner] 原始输出:
{"ltl_quote": {...}, "ftl_quote": {...}}
...
```

### 4. 再次点击收起
```
🤖 DEEPAGENT
─────────────────────
📦 上海→北京 报价单
...

▶ Runtime Log (42 lines) - 已收起    [点击展开]
```

---

## 🎨 视觉设计

### 折叠按钮样式
- **背景**: 深色 (#0a1628)
- **边框**: 青色高亮 (hover 时)
- **图标**: ▼ 展开 / ▶ 收起（带旋转动画）
- **文字**: 显示日志行数
- **提示**: "点击展开/收起"

### 日志内容区域
- **背景**: 极深色 (#030b17)
- **最大高度**: 400px（超出滚动）
- **动画**: 平滑展开/收起（0.3s）
- **着色**: 根据日志类型自动着色
  - 绿色: 成功/完成
  - 黄色: 警告
  - 红色: 错误
  - 青色: 动作/Skill 调用
  - 紫色: Skill 选择
  - 橙色: 参数提取

---

## 🔧 技术实现

### 1. 日志收集
```javascript
let currentMsgLogs = [];  // 当前消息的日志集合

function appendLog(text) {
  // ... 原有逻辑 ...
  
  // 同时收集到当前消息的日志中
  if (isProcessing) {
    currentMsgLogs.push({ text, className: logClass(text) });
  }
}
```

### 2. 渲染折叠区域
```javascript
function appendLogsToMessage(bubble, logs) {
  const msgEl = bubble.closest('.msg');
  
  // 创建折叠按钮
  const toggle = document.createElement('div');
  toggle.className = 'msg-log-toggle';
  toggle.innerHTML = `
    <span class="toggle-icon">▼</span>
    <span class="toggle-text">Runtime Log (${logs.length} lines)</span>
    <span class="toggle-count">点击展开/收起</span>
  `;
  
  // 创建日志内容区域（默认收起）
  const logContent = document.createElement('div');
  logContent.className = 'msg-log-content collapsed';
  
  // ... 添加日志行 ...
  
  // 点击切换
  toggle.addEventListener('click', () => {
    logContent.classList.toggle('collapsed');
    toggle.classList.toggle('collapsed');
  });
  
  msgEl.appendChild(toggle);
  msgEl.appendChild(logContent);
}
```

### 3. 工作流程
```
用户发送消息
  ↓
清空 currentMsgLogs
  ↓
开始 SSE 流式接收
  ↓
收到 log 事件 → 添加到 currentMsgLogs
  ↓
收到 answer 事件 → 渲染答案
  ↓
调用 appendLogsToMessage() → 添加折叠区域
  ↓
清空 currentMsgLogs（准备下一条消息）
```

---

## 💡 优势

### 1. **上下文关联**
- ✅ 每条消息的日志紧跟在消息下方
- ✅ 清晰看到哪条日志对应哪个回答
- ✅ 多轮对话时不会混淆

### 2. **节省空间**
- ✅ 默认收起，不占用聊天区域
- ✅ 需要时才展开查看
- ✅ 可以独立展开多条消息的日志进行对比

### 3. **用户体验**
- ✅ 平滑动画过渡
- ✅ 清晰的视觉反馈
- ✅ 显示日志行数，预判内容量
- ✅ 保留右侧全局日志面板（调试用）

### 4. **灵活性**
- ✅ 可以同时展开多条消息的日志
- ✅ 可以单独收起某条消息的日志
- ✅ 不影响右侧全局日志面板

---

## 🎓 使用场景

### 场景 1: 快速查看结果
```
用户: 查询运价
  ↓
Agent: 返回报价（日志默认收起）
  ↓
用户: 直接看结果，无需关心执行细节
```

### 场景 2: 调试问题
```
用户: 为什么报价这么贵？
  ↓
Agent: 返回报价
  ↓
用户: 点击展开日志，查看计算过程
  ↓
发现: 燃油附加费 8%，旺季加价等
```

### 场景 3: 学习系统工作原理
```
用户: 想了解 DeepAgent 如何工作
  ↓
发送多个请求，展开每条消息的日志
  ↓
观察: ReAct 循环、Skill 选择、参数提取等完整流程
```

### 场景 4: 对比不同请求
```
用户: 对比上海→北京 vs 上海→广州
  ↓
发送两个请求
  ↓
分别展开两条消息的日志
  ↓
对比: 不同的车型选项、价格差异
```

---

## 🔄 与右侧日志面板的关系

| 特性 | 消息内日志 | 右侧日志面板 |
|------|-----------|-------------|
| **位置** | 每条消息下方 | 固定右侧面板 |
| **范围** | 仅当前消息 | 所有历史日志 |
| **默认状态** | 收起 | 展开 |
| **用途** | 查看单次执行 | 全局调试监控 |
| **清除** | 随消息存在 | 可手动清除 |
| **持久性** | 永久保留 | 可清空 |

**建议**：
- 日常使用：关注消息内日志
- 开发调试：同时查看右侧日志面板

---

## 🚀 未来优化方向

1. **搜索过滤**: 在日志区域内搜索关键词
2. **导出功能**: 导出某条消息的完整日志
3. **时间戳**: 显示每条日志的时间
4. **性能优化**: 日志过多时虚拟滚动
5. **快捷键**: Ctrl+L 展开/收起所有日志

---

**最后更新**: 2026-04-11  
**版本**: v2.2  
**作者**: DeepAgent Team
