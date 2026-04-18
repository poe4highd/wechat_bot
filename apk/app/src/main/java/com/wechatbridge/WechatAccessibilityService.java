package com.wechatbridge;

import android.accessibilityservice.AccessibilityService;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import com.google.gson.JsonObject;

import java.util.List;

public class WechatAccessibilityService extends AccessibilityService {
    private static final String TAG = "WechatBridge";
    private static final int WS_PORT = 8765;
    private static final String WECHAT_PKG = "com.tencent.mm";

    private BridgeWebSocketServer wsServer;

    // 过滤掉非消息界面（防止刷屏）
    private static final String[] IGNORED_ACTIVITIES = {
            "com.tencent.mm.ui.LauncherUI",    // 会话列表
            "com.tencent.mm.ui.contact.AddContactUI",
    };

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        wsServer = new BridgeWebSocketServer(WS_PORT);
        try {
            wsServer.start();
            Log.i(TAG, "WechatBridge service connected, WS started on " + WS_PORT);
        } catch (Exception e) {
            Log.e(TAG, "Failed to start WebSocket server", e);
        }
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (!WECHAT_PKG.equals(event.getPackageName())) return;
        if (event.getEventType() != AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED
                && event.getEventType() != AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED) return;

        // 只在聊天界面（有输入框的窗口）处理
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return;

        String chatName = extractChatName(root);
        if (chatName == null || chatName.isEmpty()) {
            root.recycle();
            return;
        }

        List<AccessibilityNodeInfo> messageNodes = root.findAccessibilityNodeInfosByViewId(
                "com.tencent.mm:id/b7z"  // 消息列表容器（WeChat 8.0.47，需按版本调整）
        );

        if (messageNodes.isEmpty()) {
            root.recycle();
            return;
        }

        // 取最后一条消息
        AccessibilityNodeInfo lastNode = findLastMessage(messageNodes.get(0));
        if (lastNode == null) {
            root.recycle();
            return;
        }

        String sender = extractSender(lastNode);
        String content = extractContent(lastNode);

        if (content == null || content.trim().isEmpty()) {
            root.recycle();
            return;
        }

        pushEvent(chatName, sender, content);
        root.recycle();
    }

    private String extractChatName(AccessibilityNodeInfo root) {
        // 标题栏 resource-id（WeChat 8.0.47）
        List<AccessibilityNodeInfo> nodes = root.findAccessibilityNodeInfosByViewId(
                "com.tencent.mm:id/j7"
        );
        if (nodes.isEmpty()) return null;
        CharSequence text = nodes.get(0).getText();
        return text != null ? text.toString() : null;
    }

    private AccessibilityNodeInfo findLastMessage(AccessibilityNodeInfo container) {
        int count = container.getChildCount();
        for (int i = count - 1; i >= 0; i--) {
            AccessibilityNodeInfo child = container.getChild(i);
            if (child != null) return child;
        }
        return null;
    }

    private String extractSender(AccessibilityNodeInfo node) {
        // 群消息有发送者节点
        List<AccessibilityNodeInfo> senderNodes = node.findAccessibilityNodeInfosByViewId(
                "com.tencent.mm:id/b83"
        );
        if (!senderNodes.isEmpty()) {
            CharSequence t = senderNodes.get(0).getText();
            return t != null ? t.toString() : "";
        }
        return "";
    }

    private String extractContent(AccessibilityNodeInfo node) {
        List<AccessibilityNodeInfo> contentNodes = node.findAccessibilityNodeInfosByViewId(
                "com.tencent.mm:id/b7w"  // 消息文本 view
        );
        if (!contentNodes.isEmpty()) {
            CharSequence t = contentNodes.get(0).getText();
            return t != null ? t.toString() : null;
        }
        // fallback：取节点全部文本
        List<CharSequence> texts = new java.util.ArrayList<>();
        collectTexts(node, texts);
        return texts.isEmpty() ? null : texts.get(texts.size() - 1).toString();
    }

    private void collectTexts(AccessibilityNodeInfo node, List<CharSequence> out) {
        if (node.getText() != null) out.add(node.getText());
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) collectTexts(child, out);
        }
    }

    private void pushEvent(String chatName, String sender, String content) {
        if (wsServer == null) return;
        JsonObject obj = new JsonObject();
        obj.addProperty("type", "message");
        obj.addProperty("chat_id", chatName);   // 暂用 chat_name 作 id
        obj.addProperty("chat_name", chatName);
        obj.addProperty("sender", sender);
        obj.addProperty("content", content);
        obj.addProperty("ts", System.currentTimeMillis() / 1000L);
        obj.addProperty("is_group", !sender.isEmpty());
        wsServer.pushMessage(obj.toString());
        Log.d(TAG, "Event pushed: [" + chatName + "] " + sender + ": " + content);
    }

    @Override
    public void onInterrupt() {
        Log.w(TAG, "Service interrupted");
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (wsServer != null) {
            try { wsServer.stop(); } catch (Exception ignored) {}
        }
    }
}
