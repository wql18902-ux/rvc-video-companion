// RVC 后台服务：点击扩展图标时，在当前页面显示/隐藏嵌入式播放器

// A1 权限收窄（v3.2.0）：只支持 aim-read.top 阅读站 + 本地 server 端口
function isSupportedUrl(url) {
  if (!url) return false;
  // 受限协议一律不支持
  if (url.startsWith('chrome://') ||
    url.startsWith('chrome-extension://') ||
    url.startsWith('https://chrome.google.com/webstore') ||
    url.startsWith('https://chromewebstore.google.com') ||
    url.startsWith('about:') ||
    url.startsWith('devtools://')) {
    return false;
  }
  // 仅 aim-read.top（content_scripts matches 与 host_permissions 同步收窄）
  return url.startsWith('https://aim-read.top/') || url.startsWith('http://aim-read.top/');
}

// 点击扩展图标
chrome.action.onClicked.addListener(async (tab) => {
  console.log('[RVC] 图标被点击，当前标签页:', tab.id, 'URL:', tab.url);

  // 不支持页面：弹出提示而不是静默跳过（A1：仅 aim-read.top）
  if (!isSupportedUrl(tab.url)) {
    console.log('[RVC] 当前页面不支持注入:', tab.url);
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title: 'RVC 视频伴侣',
      message: '当前页面不支持播放器，仅支持 aim-read.top（Reader 阅读站）'
    });
    return;
  }

  // 尝试与已注入的内容脚本通信
  try {
    await chrome.tabs.sendMessage(tab.id, { action: 'rvc-toggle' });
    console.log('[RVC] 播放器切换成功');
    return;
  } catch (err) {
    console.log('[RVC] 内容脚本未响应，准备重新注入:', err.message);
  }

  // 内容脚本未注入或已失效，先清理旧 DOM 再重新注入
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const old = document.getElementById('rvc-player');
        if (old) {
          console.log('[RVC] 清理旧播放器 DOM');
          old.remove();
        }
        document.querySelectorAll('.rvc-folder-overlay, .rvc-tree-overlay').forEach((el) => el.remove());
      }
    });

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['mpegts.min.js', 'content.js']
    });
    console.log('[RVC] 内容脚本注入成功');

    // 等待内容脚本初始化完成，然后重试发送消息
    let sent = false;
    for (let i = 0; i < 5; i++) {
      await new Promise(r => setTimeout(r, 150));
      try {
        await chrome.tabs.sendMessage(tab.id, { action: 'rvc-toggle' });
        console.log('[RVC] 播放器切换成功');
        sent = true;
        break;
      } catch (e) {
        // 内容脚本还没准备好，继续重试
      }
    }
    if (!sent) {
      console.warn('[RVC] 内容脚本已注入但消息发送失败，请点击图标重试');
    }
  } catch (err2) {
    console.error('[RVC] 内容脚本注入失败:', err2.message);
  }
});
