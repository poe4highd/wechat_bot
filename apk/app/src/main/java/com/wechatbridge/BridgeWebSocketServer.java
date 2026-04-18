package com.wechatbridge;

import android.util.Log;
import org.java_websocket.WebSocket;
import org.java_websocket.handshake.ClientHandshake;
import org.java_websocket.server.WebSocketServer;

import java.net.InetSocketAddress;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

public class BridgeWebSocketServer extends WebSocketServer {
    private static final String TAG = "BridgeWS";
    private final Set<WebSocket> clients = Collections.synchronizedSet(new HashSet<>());

    public BridgeWebSocketServer(int port) {
        super(new InetSocketAddress("0.0.0.0", port));
        setReuseAddr(true);
        setConnectionLostTimeout(30);
    }

    @Override
    public void onOpen(WebSocket conn, ClientHandshake handshake) {
        clients.add(conn);
        Log.i(TAG, "Client connected: " + conn.getRemoteSocketAddress());
    }

    @Override
    public void onClose(WebSocket conn, int code, String reason, boolean remote) {
        clients.remove(conn);
        Log.i(TAG, "Client disconnected: " + reason);
    }

    @Override
    public void onMessage(WebSocket conn, String message) {
        // 暂不处理来自 Python 的指令（预留扩展）
        Log.d(TAG, "Received from client: " + message);
    }

    @Override
    public void onError(WebSocket conn, Exception ex) {
        Log.e(TAG, "WebSocket error", ex);
    }

    @Override
    public void onStart() {
        Log.i(TAG, "WebSocket server started on port " + getPort());
    }

    public void pushMessage(String json) {
        synchronized (clients) {
            for (WebSocket client : clients) {
                if (client.isOpen()) {
                    client.send(json);
                }
            }
        }
    }
}
