<template>
  <div class="main-container">
    <div class="chat-container">
      <!-- 主头部 -->
      <header class="chat-header">
        <h2>🤖 OpenClaw AI 助手</h2>
        <div class="status-indicator" :class="connectionStatus">
          <span class="dot"></span>
          {{ statusText }}
        </div>
      </header>

      <!-- 主消息列表 -->
      <div class="message-list" ref="messageListRef">
        <div v-if="messages.length === 0" class="empty-state">
          <p>👋 您好！连接成功后，请输入消息开始对话。</p>
          <p class="hint">后端：Python WebSocket Hub | AI：OpenClaw</p>
        </div>

        <div 
          v-for="(msg, index) in messages" 
          :key="`main-${index}`" 
          class="message-item" 
          :class="msg.role"
        >
          <div class="avatar">
            {{ msg.role === 'user' ? '🧑💻' : '🤖' }}
          </div>
          <div class="bubble">
            <div class="content">{{ msg.content }}</div>
            <div class="timestamp">{{ msg.time }}</div>
          </div>
        </div>
        
        <!-- 主加载中状态 -->
        <div v-if="isThinking" class="message-item ai thinking">
          <div class="avatar">🤖</div>
          <div class="bubble">
            <span class="typing-indicator">AI 正在思考...</span>
          </div>
        </div>
      </div>

      <!-- 主输入区域 -->
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

    <!-- 新增的第二个聊天框 -->
    <div class="chat-container">
      <!-- 第二个头部 -->
      <header class="chat-header">
        <h2>🔧 服务调试助手</h2>
        <div class="status-indicator" :class="debugConnectionStatus">
          <span class="dot"></span>
          {{ debugStatusText }}
        </div>
      </header>

      <!-- 第二个消息列表 -->
      <div class="message-list" ref="debugMessageListRef">
        <div v-if="debugMessages.length === 0" class="empty-state">
          <p>🔧 连接到调试服务，用于发送控制命令或测试。</p>
          <p class="hint">WebSocket: ws://localhost:8765/openclaw</p>
        </div>

        <div 
          v-for="(msg, index) in debugMessages" 
          :key="`debug-${index}`" 
          class="message-item" 
          :class="msg.role"
        >
          <div class="avatar">
            {{ msg.role === 'user' ? '🧑💻' : '🔧' }}
          </div>
          <div class="bubble">
            <div class="content">{{ msg.content }}</div>
            <div class="timestamp">{{ msg.time }}</div>
          </div>
        </div>
        
        <!-- 调试加载中状态 -->
        <div v-if="isDebugThinking" class="message-item ai thinking">
          <div class="avatar">🔧</div>
          <div class="bubble">
            <span class="typing-indicator">服务处理中...</span>
          </div>
        </div>
      </div>

      <!-- 第二个输入区域 -->
      <div class="input-area">
        <input 
          v-model="debugInputMessage" 
          @keyup.enter="sendDebugMessage" 
          placeholder="向调试服务发送消息..." 
          :disabled="debugConnectionStatus !== 'connected'"
          class="chat-input"
        />
        <button 
          @click="sendDebugMessage" 
          :disabled="debugConnectionStatus !== 'connected' || !debugInputMessage.trim()"
          class="send-btn"
        >
          发送
        </button>
        <button @click="toggleDebugConnection" class="control-btn">
          {{ debugConnectionStatus === 'connected' ? '断开' : '重连' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, computed, onMounted, onUnmounted } from 'vue';

// --- 主聊天框状态定义 ---
const inputMessage = ref('');
const messages = reactive([]);
const isThinking = ref(false);
const ws = ref(null);
const messageListRef = ref(null);

// 主聊天框连接状态
const connectionStatus = ref('disconnected');

const statusText = computed(() => {
  switch(connectionStatus.value) {
    case 'connected': return '已连接';
    case 'connecting': return '连接中...';
    default: return '未连接';
  }
});

// --- 第二个聊天框状态定义 ---
const debugInputMessage = ref('');
const debugMessages = reactive([]);
const isDebugThinking = ref(false);
const debugWs = ref(null);
const debugMessageListRef = ref(null);

// 第二个聊天框连接状态
const debugConnectionStatus = ref('disconnected');

const debugStatusText = computed(() => {
  switch(debugConnectionStatus.value) {
    case 'connected': return '已连接';
    case 'connecting': return '连接中...';
    default: return '未连接';
  }
});

// --- 主聊天框 WebSocket 逻辑 ---
const connectMainWebSocket = () => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) return;

  connectionStatus.value = 'connecting';
  const wsUrl = 'ws://localhost:8765/'; // 连接到 /
  
  console.log(`主聊天框正在连接: ${wsUrl}`);
  ws.value = new WebSocket(wsUrl);

  ws.value.onopen = () => {
    connectionStatus.value = 'connected';
    addMainSystemMessage('✅ 已连接到 OpenClaw 服务！');
    scrollToBottom(messageListRef.value);
  };

  ws.value.onmessage = (event) => {
    try {
      const packet = JSON.parse(event.data);
      
      if (packet.type === 'from_openclaw') {
        isThinking.value = false;
        const content = packet.data?.content 
                     || packet.data?.text 
                     || packet.data?.reply 
                     || JSON.stringify(packet.data);
        
        addMainMessage('ai', content);
      } 
      else if (packet.type === 'error') {
        addMainSystemMessage(`⚠️ 服务器错误: ${packet.message}`);
        isThinking.value = false;
      }
      else if (packet.type === 'message_received') {
        console.log('主服务器已接收:', packet);
      }
      else {
        addMainMessage('ai', event.data);
        isThinking.value = false;
      }
      scrollToBottom(messageListRef.value);
    } catch (e) {
      console.error('解析主聊天框消息失败:', e);
      addMainSystemMessage('收到无法解析的消息格式');
      isThinking.value = false;
    }
  };

  ws.value.onclose = () => {
    connectionStatus.value = 'disconnected';
    addMainSystemMessage('❌ 主聊天框连接已断开。');
    isThinking.value = false;
  };

  ws.value.onerror = (err) => {
    console.error('主 WS Error:', err);
  };
};

const disconnectMainWebSocket = () => {
  if (ws.value) {
    ws.value.close();
    ws.value = null;
  }
};

const toggleConnection = () => {
  if (connectionStatus.value === 'connected') {
    disconnectMainWebSocket();
  } else {
    connectMainWebSocket();
  }
};

const sendMessage = () => {
  const text = inputMessage.value.trim();
  if (!text || connectionStatus.value !== 'connected') return;

  addMainMessage('user', text);
  inputMessage.value = '';
  isThinking.value = true;
  scrollToBottom(messageListRef.value);

  const payload = {
    type: 'chat',
    content: text,
    timestamp: new Date().toISOString(),
    source: 'vue_main_chat'
  };

  ws.value.send(JSON.stringify(payload));
  console.log('主聊天框已发送:', payload);
};

// --- 第二个聊天框 WebSocket 逻辑 ---
const connectDebugWebSocket = () => {
  if (debugWs.value && debugWs.value.readyState === WebSocket.OPEN) return;

  debugConnectionStatus.value = 'connecting';
  const wsUrl = 'ws://localhost:8765/openclaw'; // 连接到 /openclaw
  
  console.log(`调试聊天框正在连接: ${wsUrl}`);
  debugWs.value = new WebSocket(wsUrl);

  debugWs.value.onopen = () => {
    debugConnectionStatus.value = 'connected';
    addDebugSystemMessage('✅ 已连接到调试服务！');
    scrollToBottom(debugMessageListRef.value);
  };

  debugWs.value.onmessage = (event) => {
    try {
      const packet = JSON.parse(event.data);
      // 根据实际协议处理调试服务返回的数据
      // 这里假设它也返回类似的内容
      const content = packet.data?.content 
                   || packet.data?.text 
                   || packet.message 
                   || event.data;

      isDebugThinking.value = false;
      addDebugMessage('ai', content);
      scrollToBottom(debugMessageListRef.value);
    } catch (e) {
      console.error('解析调试聊天框消息失败:', e);
      addDebugSystemMessage('收到无法解析的消息格式');
      isDebugThinking.value = false;
    }
  };

  debugWs.value.onclose = () => {
    debugConnectionStatus.value = 'disconnected';
    addDebugSystemMessage('❌ 调试聊天框连接已断开。');
    isDebugThinking.value = false;
  };

  debugWs.value.onerror = (err) => {
    console.error('调试 WS Error:', err);
    addDebugSystemMessage('连接调试服务时发生错误');
    isDebugThinking.value = false;
  };
};

const disconnectDebugWebSocket = () => {
  if (debugWs.value) {
    debugWs.value.close();
    debugWs.value = null;
  }
};

const toggleDebugConnection = () => {
  if (debugConnectionStatus.value === 'connected') {
    disconnectDebugWebSocket();
  } else {
    connectDebugWebSocket();
  }
};

const sendDebugMessage = () => {
  const text = debugInputMessage.value.trim();
  if (!text || debugConnectionStatus.value !== 'connected') return;

  addDebugMessage('user', text);
  debugInputMessage.value = '';
  isDebugThinking.value = true;
  scrollToBottom(debugMessageListRef.value);

  // 可以构造特定于调试服务的协议包
  const payload = {
    type: 'debug_command', // 或其他自定义类型
    command: text,
    timestamp: new Date().toISOString()
  };

  debugWs.value.send(JSON.stringify(payload));
  console.log('调试聊天框已发送:', payload);
};

// --- 辅助函数 ---

// 主聊天框辅助函数
const addMainMessage = (role, content) => {
  messages.push({
    role,
    content,
    time: new Date().toLocaleTimeString()
  });
};

const addMainSystemMessage = (content) => {
  messages.push({
    role: 'system',
    content,
    time: new Date().toLocaleTimeString()
  });
};

// 调试聊天框辅助函数
const addDebugMessage = (role, content) => {
  debugMessages.push({
    role,
    content,
    time: new Date().toLocaleTimeString()
  });
};

const addDebugSystemMessage = (content) => {
  debugMessages.push({
    role: 'system',
    content,
    time: new Date().toLocaleTimeString()
  });
};

const scrollToBottom = (element) => {
  nextTick(() => {
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  });
};

// --- 生命周期 ---
onMounted(() => {
  connectMainWebSocket();
  // 可以选择性地自动连接第二个聊天框
  // connectDebugWebSocket();
});

onUnmounted(() => {
  disconnectMainWebSocket();
  disconnectDebugWebSocket();
});
</script>

<style scoped>
/* 容器样式 */
.main-container {
  display: flex;
  gap: 20px;
  padding: 20px;
  justify-content: center;
  min-height: 100vh;
  background-color: #f5f5f5;
}

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