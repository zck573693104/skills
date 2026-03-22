// extensions/websocket-channel/index.ts
// WebSocket Channel 插件实现
// 提供基于 WebSocket 的双向通信能力，支持 AI 回复和主动消息

import type { ReplyPayload } from "openclaw/auto-reply/types";
import type { ChannelPlugin, OpenClawConfig } from "openclaw/plugin-sdk";
import { createDefaultChannelRuntimeState } from "openclaw/plugin-sdk";

/** WebSocket 连接实例 */
interface WebSocketChannelConnection {
  ws: any;
  accountId: string;
}

/** WebSocket 账户配置（运行时对象） */
interface WebSocketChannelAccount {
  accountId: string;
  wsUrl: string;
  enabled?: boolean;
  configured?: boolean;
  dmPolicy?: "pairing" | "allowlist" | "open" | "disabled";
  allowFrom?: string[];
  groups?: Record<string, unknown>;
}

// 存储所有活跃的 WebSocket 连接
const connections = new Map<string, WebSocketChannelConnection>();

// 保存完整的 runtime（在 register 中设置）
let pluginRuntime: any = null;

const WebSocketChannel: ChannelPlugin<WebSocketChannelAccount> = {
  id: "websocket-channel",

  /** 通道元数据 */
  meta: {
    id: "websocket-channel",
    label: "Websocket Channel",
    selectionLabel: "Websocket Channel (Custom)",
    docsPath: "/channels/websocket-channel",
    blurb: "WebSocket based messaging channel.",
    aliases: ["ws"],
  },

  /** 通道能力定义 */
  capabilities: {
    chatTypes: ["direct", "group"],
    media: {
      maxSizeBytes: 10 * 1024 * 1024,
      supportedTypes: ["image/jpeg", "image/png", "video/mp4"],
    },
    supports: {
      threads: true,
      reactions: false,
      mentions: true,
    },
  },

  /** 配置 Schema 定义 */
  configSchema: {
    schema: {
      type: "object",
      additionalProperties: false,
      properties: {
        enabled: {
          type: "boolean",
        },
        config: {
          type: "object",
          additionalProperties: false,
          properties: {
            enabled: {
              type: "boolean",
            },
            wsUrl: {
              type: "string",
            },
            groupPolicy: {
              type: "string",
              enum: ["pairing", "allowlist", "open", "disabled"],
            },
          },
          required: ["wsUrl"],
        },
      },
    },
    uiHints: {
      enabled: {
        label: "Enabled",
        description: "Enable WebSocket Channel",
      },
      config: {
        label: "Configuration",
        description: "WebSocket connection configuration",
      },
      "config.enabled": {
        label: "Enabled",
        description: "Enable this configuration",
      },
      "config.wsUrl": {
        label: "WebSocket URL",
        placeholder: "ws://localhost:8765/openclaw",
        help: "WebSocket server URL",
      },
      "config.groupPolicy": {
        label: "Group Policy",
        description: "Message policy for group chats",
      },
    },
  },

  // ... existing code ...

  /** 通道配置适配器 */
  config: {
    /**
     * 列出所有配置的账户 ID
     * @returns 固定返回 ["default"]，因为 websocket-channel 只有一个配置
     */
    listAccountIds: (cfg: OpenClawConfig) => {
      return ["default"];
    },

    /**
     * 解析账户配置
     * @param cfg - OpenClaw 完整配置
     * @param accountId - 账户 ID（固定为 "default"）
     * @returns 账户运行时对象
     */
    resolveAccount: (cfg: OpenClawConfig, accountId: string) => {
      const channelCfg = cfg.channels?.["websocket-channel"];
      if (!channelCfg || !channelCfg.config) {
        return undefined;
      }

      const config = channelCfg.config as any;

      return {
        accountId: "default",
        wsUrl: config.wsUrl || "ws://localhost:8765/openclaw",
        enabled: config.enabled !== false,
        groupPolicy: config.groupPolicy || "open",
      };
    },

    /**
     * 检查账户是否已配置
     * @param account - 账户运行时对象
     * @returns 是否已配置（只需要 wsUrl 非空）
     */
    isConfigured: async (account, cfg) => {
      return Boolean(account.wsUrl && account.wsUrl.trim() !== "");
    },
  },

  /** 状态管理适配器 */
  status: {
    /** 默认运行时状态模板 */
    defaultRuntime: createDefaultChannelRuntimeState("default", {
      wsUrl: null,
      connected: false,
      groupPolicy: null,
    }),

    /**
     * 构建通道摘要（用于 UI 显示）
     * @param snapshot - 运行时快照
     */
    buildChannelSummary: ({ snapshot }) => ({
      wsUrl: snapshot.wsUrl ?? null,
      connected: snapshot.connected ?? null,
      groupPolicy: snapshot.groupPolicy ?? null,
    }),

    /**
     * 构建账户完整快照
     * @param account - 账户配置
     * @param runtime - 运行时状态
     */
    buildAccountSnapshot: ({ account, runtime }) => ({
      accountId: account.accountId,
      enabled: account.enabled,
      configured: account.configured,
      wsUrl: account.wsUrl,
      running: runtime?.running ?? false,
      connected: runtime?.connected ?? false,
      groupPolicy: runtime?.groupPolicy ?? null,
      lastStartAt: runtime?.lastStartAt ?? null,
      lastStopAt: runtime?.lastStopAt ?? null,
      lastError: runtime?.lastError ?? null,
    }),
  },

  /** 出站消息适配器（主动消息） */
  outbound: {
    deliveryMode: "direct",

    /**
     * 发送文本消息（主动消息）
     * @param to - 目标用户 ID
     * @param text - 消息内容
     * @param accountId - 账户 ID
     */
    sendText: async ({ to, text, accountId }) => {
      const conn = connections.get(accountId ?? "default");

      if (!conn || !conn.ws || conn.ws.readyState !== 1) {
        return { ok: false, error: "No connection" };
      }

      conn.ws.send(JSON.stringify({ type: "message", to, content: text }));
      return { ok: true };
    },

    /**
     * 发送媒体消息（主动消息）
     * @param to - 目标用户 ID
     * @param text - 消息文本（可选）
     * @param mediaUrl - 媒体 URL
     * @param accountId - 账户 ID
     */
    sendMedia: async ({ to, text, mediaUrl, accountId }) => {
      const conn = connections.get(accountId ?? "default");

      if (!conn || !conn.ws || conn.ws.readyState !== 1) {
        return { ok: false, error: "No connection" };
      }

      conn.ws.send(JSON.stringify({ type: "media", to, content: text, mediaUrl }));
      return { ok: true };
    },
  },

  /** 网关适配器（长连接管理） */
  gateway: {
    /**
     * 启动 WebSocket 账户连接
     * @param ctx - 网关上下文
     */
    startAccount: async (ctx) => {
      const { log, account, abortSignal, cfg } = ctx;

      log?.info(`[websocket-channel] Starting WebSocket Channel for ${account.accountId}`);

      // 使用在 register 中保存的完整 runtime
      const runtime = pluginRuntime;

      if (!runtime?.channel?.reply?.withReplyDispatcher) {
        log?.error("[websocket-channel] runtime.channel.reply API not available");
        throw new Error("Runtime API not available");
      }

      // 设置初始状态为已连接
      ctx.setStatus({
        accountId: account.accountId,
        wsUrl: account.wsUrl,
        running: true,
        connected: true,
        groupPolicy: account.groupPolicy || "open",
      });
      log?.info(`[websocket-channel] Status set: connected=true, running=true`);

      // 动态导入 ws 库并创建连接
      const WebSocketLib = await import("ws");
      const ws = new (WebSocketLib.default as any)(account.wsUrl);

      // 存储连接
      connections.set(account.accountId, { ws, accountId: account.accountId });

      // 创建 promise 保持连接运行
      const connectionPromise = new Promise<void>((resolve, reject) => {
        ws.on("open", () => {
          log?.info(`[websocket-channel] Connected to ${account.wsUrl}`);
        });

        /** 处理入站消息 */
        ws.on("message", async (data: Buffer) => {
          try {
            const rawData = data.toString();
            const eventData = JSON.parse(rawData);
            const innerData = eventData.data || {};

            // 构造标准消息
            const normalizedMessage = {
              id: `${eventData.source || "websocket"}-${Date.now()}`,
              channel: "websocket-channel",
              accountId: account.accountId,
              senderId: innerData.source || eventData.source || "unknown",
              senderName: innerData.source || eventData.source || "Unknown",
              text: innerData.content || innerData.text || "",
              timestamp: innerData.timestamp || Date.now().toISOString(),
              isGroup: false,
              groupId: undefined,
              attachments: [],
              metadata: {},
            };

            log?.info(
              `[websocket-channel] 📨 Received: "${normalizedMessage.text}" from ${normalizedMessage.senderId}`,
            );

            // 解析路由
            const route = runtime.channel.routing.resolveAgentRoute({
              cfg,
              channel: "websocket-channel",
              accountId: account.accountId,
              peer: {
                kind: "direct",
                id: normalizedMessage.senderId,
              },
            });

            log?.info(
              `[websocket-channel] Route resolved sessionKey:${route.sessionKey}, accountId:${route.accountId}, matchedBy: ${route.matchedBy}`,
            );

            // 构建消息上下文
            const ctxPayload = runtime.channel.reply.finalizeInboundContext({
              Body: normalizedMessage.text,
              BodyForAgent: normalizedMessage.text,
              From: normalizedMessage.senderId,
              To: undefined,
              SessionKey: route.sessionKey,
              AccountId: route.accountId,
              ChatType: "direct",
              SenderName: normalizedMessage.senderName,
              SenderId: normalizedMessage.senderId,
              Provider: "websocket-channel",
              Surface: "websocket-channel",
              MessageSid: normalizedMessage.id,
              Timestamp: Date.now(),
            });

            // 调用框架调度器发送回复
            const result = await runtime.channel.reply.dispatchReplyWithBufferedBlockDispatcher({
              ctx: ctxPayload,
              cfg: cfg,
              dispatcherOptions: {
                deliver: async (payload: ReplyPayload, { kind }) => {
                  log?.info(`[websocket-channel] Delivering ${kind} reply via WebSocket...`);

                  // 直接通过 WebSocket 发送回复
                  const currentConn = connections.get(account.accountId);

                  if (!currentConn || !currentConn.ws || currentConn.ws.readyState !== 1) {
                    throw new Error("No WebSocket connection available");
                  }

                  currentConn.ws.send(
                    JSON.stringify({
                      type: "reply",
                      content: payload.text || "",
                      kind,
                    }),
                  );
                },
                onError: (err, { kind }) => {
                  log?.error(
                    `[websocket-channel] Delivery error for ${kind}: ${err instanceof Error ? err.message : String(err)}`,
                  );
                },
              },
            });

            log?.info(`[websocket-channel] Message dispatched successfully`);
          } catch (err) {
            log?.error(
              `[websocket-channel] Failed to process message: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        });

        /** 处理连接错误 */
        ws.on("error", (err: Error) => {
          log?.error(`[websocket-channel] ❌ WebSocket error: ${err.message}`);
          connections.delete(account.accountId);
          reject(err);
        });

        /** 处理连接关闭 */
        ws.on("close", () => {
          log?.info(`[websocket-channel] 🔴 Connection closed`);
          connections.delete(account.accountId);
          resolve();
        });

        /** 处理中止信号 */
        abortSignal.addEventListener("abort", () => {
          log?.info(`[websocket-channel] ⏹️ Abort requested`);
          ws.close();
          resolve();
        });
      });

      // 等待连接关闭或 abort 信号
      await Promise.race([
        connectionPromise,
        new Promise<void>((resolve) => {
          abortSignal.addEventListener("abort", () => resolve());
        }),
      ]);

      connections.delete(account.accountId);
    },

    /**
     * 停止 WebSocket 账户连接
     * @param ctx - 网关上下文
     */
    stopAccount: async (ctx) => {
      const { log, account } = ctx;
      log?.info(`[websocket-channel] Stopping WebSocket Channel for ${account.accountId}`);
      const conn = connections.get(account.accountId);
      if (conn) {
        conn.ws.close();
        connections.delete(account.accountId);
      }
    },
  },

  /** 安全策略适配器 */
  security: {
    getDmPolicy: (account) => account.dmPolicy ?? "open",
    getAllowFrom: (account) => account.allowFrom ?? [],
    checkGroupAccess: (account, groupId) => {
      const groups = account.groups ?? {};
      return "*" in groups || groupId in groups;
    },
  },
};

/**
 * 注册插件入口
 * @param api - 插件 API
 */
export default function register(api: any) {
  console.log("[websocket-channel] Registering WebSocket Channel plugin");
  pluginRuntime = api.runtime;
  api.registerChannel({ plugin: WebSocketChannel });
}
