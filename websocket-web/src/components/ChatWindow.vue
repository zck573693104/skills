<template>
  <div class="chat-container">
    <!-- 头部 -->
    <header class="chat-header">
      <h2>🤖 OpenClaw AI 助手</h2>
      <div class="status-indicator" :class="connectionStatus">
        <span class="dot"></span>
        {{ statusText }}
      </div>
    </header>

    <!-- 消息列表 -->
    <div class="message-list" ref="messageListRef">
      <div v-if="messages.length === 0" class="empty-state">
        <p>👋 您好！连接成功后，请输入消息开始对话。</p>
        <p class="hint">后端：Python WebSocket Hub | AI：OpenClaw</p>
      </div>

      <div 
        v-for="(msg, index) in messages" 
        :key="index" 
        class="message-item" 
        :class="msg.role"
      >
        <div class="avatar">
          {{ msg.role === 'user' ? '🧑‍💻' : '🤖' }}
        </div>
        <div class="bubble">
          <div class="content">{{ msg.content }}</div>
          <div class="timestamp">{{ msg.time }}</div>
        </div>
      </div>
      
      <!-- 加载中状态 -->
      <div v-if="isThinking" class="message-item ai thinking">
        <div class="avatar">🤖</div>
        <div class="bubble">
          <span class="typing-indicator">AI 正在思考...</span>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <input 
        v-model="inputMessage" 
        @keyup.enter="sendMessage" 
        placeholder="输入消息并回车发送..." 
        :disabled="connectionStatus !== 'connected'"
        class="chat-input"
      />
      <button 
        @click="sendMessage" 
        :disabled="connectionStatus !== 'connected' || !inputMessage.trim()"
        class="send-btn"
      >
        发送
      </button>
      <button @click="toggleConnection" class="control-btn">
        {{ connectionStatus === 'connected' ? '断开' : '重连' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, computed, onMounted, onUnmounted } from 'vue';

// --- 状态定义 ---
const inputMessage = ref('');
const messages = reactive([]);
const isThinking = ref(false);
const ws = ref(null);
const messageListRef = ref(null);

// 连接状态: 'disconnected', 'connecting', 'connected'
const connectionStatus = ref('disconnected');

const statusText = computed(() => {
  switch(connectionStatus.value) {
    case 'connected': return '已连接';
    case 'connecting': return '连接中...';
    default: return '未连接';
  }
});

// --- WebSocket 逻辑 ---

const connectWebSocket = () => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) return;

  connectionStatus.value = 'connecting';
  
  // 【关键】连接 Python 服务的根路径 '/'
  // Python 会根据路径识别此为 'frontend' 客户端
  const wsUrl = 'ws://localhost:8765/'; 
  
  console.log(`正在连接: ${wsUrl}`);
  ws.value = new WebSocket(wsUrl);

  ws.value.onopen = () => {
    connectionStatus.value = 'connected';
    addSystemMessage('✅ 已连接到 Python 服务，可以开始对话了！');
    scrollToBottom();
  };

  ws.value.onmessage = (event) => {
    try {
      const packet = JSON.parse(event.data);
      
      // 【核心协议】处理来自 OpenClaw 的转发消息
      if (packet.type === 'from_openclaw') {
        // 停止思考动画
        isThinking.value = false;
        
        // 提取内容：兼容多种数据结构
        const content = packet.data?.content 
                     || packet.data?.text 
                     || packet.data?.reply 
                     || JSON.stringify(packet.data);
        
        addMessage('ai', content);
      } 
      // 处理错误消息
      else if (packet.type === 'error') {
        addSystemMessage(`⚠️ 服务器错误: ${packet.message}`);
        isThinking.value = false;
      }
      // 处理确认消息 (可选)
      else if (packet.type === 'message_received') {
        console.log('服务器已接收:', packet);
      }
      // 兼容旧格式或非 JSON 字符串
      else {
        addMessage('ai', event.data);
        isThinking.value = false;
      }
      
      scrollToBottom();
    } catch (e) {
      console.error('解析消息失败:', e);
      addSystemMessage('收到无法解析的消息格式');
      isThinking.value = false;
    }
  };

  ws.value.onclose = () => {
    connectionStatus.value = 'disconnected';
    addSystemMessage('❌ 连接已断开，请检查 Python 服务是否运行。');
    isThinking.value = false;
  };

  ws.value.onerror = (err) => {
    console.error('WS Error:', err);
    // 错误通常伴随 close 事件
  };
};

const disconnectWebSocket = () => {
  if (ws.value) {
    ws.value.close();
    ws.value = null;
  }
};

const toggleConnection = () => {
  if (connectionStatus.value === 'connected') {
    disconnectWebSocket();
  } else {
    connectWebSocket();
  }
};

const sendMessage = () => {
  const text = inputMessage.value.trim();
  if (!text || connectionStatus.value !== 'connected') return;

  // 1. 显示用户消息
  addMessage('user', text);
  inputMessage.value = '';
  isThinking.value = true; // 显示 AI 思考中
  scrollToBottom();

  // 2. 构造发送给 Python 的协议包
  const payload = {
    type: 'chat',          // 消息类型
    content: text,         // 实际内容
    timestamp: new Date().toISOString(),
    source: 'vue_frontend'
  };

  // 3. 发送
  ws.value.send(JSON.stringify(payload));
  console.log('已发送:', payload);
};

// --- 辅助函数 ---

const addMessage = (role, content) => {
  messages.push({
    role, // 'user' or 'ai'
    content,
    time: new Date().toLocaleTimeString()
  });
};

const addSystemMessage = (content) => {
  messages.push({
    role: 'system',
    content,
    time: new Date().toLocaleTimeString()
  });
};

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight;
    }
  });
};

// --- 生命周期 ---
onMounted(() => {
  connectWebSocket();
});

onUnmounted(() => {
  disconnectWebSocket();
});
</script>

<style scoped>
/* 容器样式 */
.chat-container {
  width: 100%;
  max-width: 600px;
  height: 80vh;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e0e0e0;
}

/* 头部 */
.chat-header {
  padding: 15px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chat-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: #333;
}
.status-indicator {
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  background: #eee;
  color: #666;
}
.status-indicator.connected {
  background: #e6f4ea;
  color: #1e8e3e;
}
.status-indicator.connecting {
  background: #e8f0fe;
  color: #1967d2;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

/* 消息列表 */
.message-list {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.empty-state {
  text-align: center;
  color: #999;
  margin-top: 50px;
}
.hint {
  font-size: 0.8rem;
  margin-top: 5px;
  opacity: 0.7;
}

/* 消息气泡 */
.message-item {
  display: flex;
  gap: 10px;
  max-width: 85%;
}
.message-item.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.message-item.system {
  align-self: center;
  max-width: 100%;
  justify-content: center;
  font-size: 0.85rem;
  color: #888;
  font-style: italic;
}
.message-item.ai.thinking .bubble {
  background: #f0f0f0;
  color: #666;
  font-style: italic;
}

.avatar {
  font-size: 1.5rem;
  line-height: 1;
}

.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  position: relative;
  word-wrap: break-word;
}
.message-item.user .bubble {
  background: #1967d2;
  color: white;
  border-bottom-right-radius: 2px;
}
.message-item.ai .bubble {
  background: #f1f3f4;
  color: #333;
  border-bottom-left-radius: 2px;
}
.timestamp {
  font-size: 0.7rem;
  margin-top: 4px;
  opacity: 0.7;
  text-align: right;
}

/* 输入区 */
.input-area {
  padding: 15px;
  background: #f8f9fa;
  border-top: 1px solid #eee;
  display: flex;
  gap: 10px;
}
.chat-input {
  flex: 1;
  padding: 10px 15px;
  border: 1px solid #ddd;
  border-radius: 20px;
  outline: none;
  transition: border-color 0.2s;
}
.chat-input:focus {
  border-color: #1967d2;
}
.send-btn {
  padding: 0 20px;
  background: #1967d2;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.2s;
}
.send-btn:hover:not(:disabled) {
  background: #1557b0;
}
.send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}
.control-btn {
  padding: 0 15px;
  background: transparent;
  border: 1px solid #ccc;
  border-radius: 20px;
  cursor: pointer;
  color: #666;
  font-size: 0.9rem;
}
.control-btn:hover {
  background: #eee;
}
</style>