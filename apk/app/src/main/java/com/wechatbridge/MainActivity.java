package com.wechatbridge;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.TextView;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView tv = new TextView(this);
        tv.setText("WechatBridge 已安装。\n\n请前往「无障碍」设置开启 WechatBridge 服务，\n或通过 ADB 命令启用：\n\nadb shell settings put secure enabled_accessibility_services com.wechatbridge/.WechatAccessibilityService");
        tv.setPadding(48, 48, 48, 48);
        setContentView(tv);

        // 跳转到无障碍设置页
        startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
    }
}
