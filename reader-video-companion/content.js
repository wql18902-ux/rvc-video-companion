// RVC 视频伴侣 · 播放器浮层（content script，MV3 单文件）
// 架构：单 IIFE 内按区组织 —— 状态(state) / 元素(elements) / 文件夹浮层 / 固定目录 /
//       目录树 / 播放加载(loadFile) / 转码错误(fetchTranscodeError) / 控制按钮 / 拖拽。
// 交互入口：header 文件夹图标 + 「加载视频」按钮 -> showFolderOverlay()（浮层内选
//   Web 树 / 手动路径 / 访达），不再自动弹 Finder（见 engineering 审查 2026-08-02）。
(function() {
  'use strict';

  // 防止重复注入
  if (document.getElementById('rvc-player')) {
    return;
  }

  const SERVER = 'http://127.0.0.1:8765';

  // ========== API 命名空间：封装所有对本地服务器的 fetch 调用 ==========
  const api = {
    health: () => fetch(SERVER + '/api/health').then(r => r.json()),
    files: (dir) => fetch(SERVER + '/api/files?dir=' + encodeURIComponent(dir)).then(r => r.json()),
    tree: (dir) => fetch(SERVER + '/api/tree?dir=' + encodeURIComponent(dir)).then(r => r.json()),
    pickFolder: () => fetch(SERVER + '/api/pick-folder').then(r => r.json()),
    fileUrl: (file, dir) => SERVER + '/api/file?file=' + encodeURIComponent(file) + '&dir=' + encodeURIComponent(dir),
    streamUrl: (file, dir, reqId, start) => {
      let url = SERVER + '/api/stream?file=' + encodeURIComponent(file) + '&dir=' + encodeURIComponent(dir) + '&req=' + reqId;
      if (start && start > 0) url += '&start=' + start;
      return url;
    },
    streamError: (reqId) => fetch(SERVER + '/api/stream-error?req=' + encodeURIComponent(reqId)).then(r => r.json()),
    setKeybindings: (kb) => fetch(SERVER + '/api/set-keybindings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(kb)
    }).catch(() => {}),
  };

  // Lucide 风格 inline SVG（stroke 1.8、14px、currentColor），替代所有 emoji/字形符号
  const ICON = {
    video: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m22 8-6 4 6 4V8Z"/><rect x="2" y="6" width="14" height="12" rx="2"/></svg>',
    folder: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>',
    frame: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/></svg>',
    keyboard: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h.01M18 14h.01"/><path d="M11 14h2"/></svg>',
    close: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>',
    play: '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" stroke="none"><polygon points="6 3 20 12 6 21 6 3"/></svg>',
    pause: '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>',
    skipBack: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" x2="5" y1="19" y2="5"/></svg>',
    skipForward: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" x2="19" y1="5" y2="19"/></svg>',
    package: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>',
    film: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 7.5h4M3 12h4M3 16.5h4M17 7.5h4M17 12h4M17 16.5h4"/></svg>',
    alert: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>',
    hourglass: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 22h14M5 2h14M17 22v-4.17a2 2 0 0 0-.59-1.41L12 12 7.59 16.42A2 2 0 0 0 7 17.83V22M7 2v4.17a2 2 0 0 0 .59 1.41L12 12l4.41-4.42A2 2 0 0 0 17 6.17V2"/></svg>',
    pin: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1Z"/></svg>'
  };

  // HTML 转义：所有用户可控字符串（文件名/目录名/服务器错误信息）插入 innerHTML 前必须经过此函数
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // 状态
  const state = {
    isPlaying: false,
    isResizing: false,
    resizeStart: { x: 0, y: 0, width: 0, height: 0, left: 0, top: 0 },
    player: null,           // mpegts.js 播放器实例
    currentReqId: null,     // 当前转码请求 ID（时间戳+随机），服务器据此命名日志、供错误查询
    transcodeTimer: null,        // 转码 loading 超时兜底定时器
    transcodeErrorShown: false,  // 错误已展示（mpegts ERROR / video error / 超时 三路去重）
    serverOnline: false,
    currentFile: null,
    currentDir: null,      // 当前播放文件所在目录（seek 重新加载时用，避免 dirInput 已被修改）
    pinnedDirs: [],         // 固定目录列表（LRU，最前为最近使用，上限 8）
    videoRatio: null,       // 视频宽高比 w/h（loadedmetadata 时更新，null 表示无视频）
    keybindings: { toggle_play: 's', back: 'a', forward: 'd' }  // 自定义按键（chrome.storage.local 持久化）
  };

  // 布局尺寸由 saveLayout/restoreLayout 持久化（rvc-layout），
  // restoreLayout 自带宽度下限守卫（<360 的 fixed 时代脏数据会被忽略）。
  // v3.0.x 的 rvc-layout-schema 一次性迁移已于 v3.2.2 完成，此处移除。

  // ========== 查找文章内容容器 ==========
  // 跳过 flex/grid 容器：float:right 在 flex/grid 下被忽略，会导致播放器挤开文字。
  // 优先找 block-level 容器（article / p / div block），确保 float 生效。
  function findArticleContainer() {
    const selectors = [
      'article',
      '.article-content', '.reader-content',
      '[class*="article"]', '[class*="content"]',
      '.content', 'main'
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (!el || el.offsetHeight <= 300) continue;
      const display = getComputedStyle(el).display;
      // flex/grid 容器：float 不生效，尝试在子元素中找 block 容器
      if (display === 'flex' || display === 'grid') {
        // 找第一个足够高的 block-level 子元素
        for (const child of el.children) {
          const childDisplay = getComputedStyle(child).display;
          if ((childDisplay === 'block' || childDisplay === 'list-item' || childDisplay === 'flow-root')
              && child.offsetHeight > 300) {
            return child;
          }
        }
        // 没找到合适的 block 子元素，退而求其次用原容器
      }
      return el;
    }
    return document.body;
  }

  // ========== 修复祖先 overflow（sticky 需要祖先无 overflow 限制） ==========
  function fixAncestorOverflow(el) {
    let parent = el.parentElement;
    while (parent && parent !== document.body) {
      const style = getComputedStyle(parent);
      if (['hidden', 'auto', 'scroll'].includes(style.overflow) ||
          ['hidden', 'auto', 'scroll'].includes(style.overflowY)) {
        parent.style.overflow = 'visible';
        parent.style.overflowY = 'visible';
      }
      parent = parent.parentElement;
    }
  }

  // 创建播放器DOM
  function createPlayer() {
    const player = document.createElement('div');
    player.id = 'rvc-player';
    player.className = 'rvc-player rvc-empty';

    player.innerHTML = `
      <div class="rvc-header">
        <span class="rvc-title">${ICON.video} RVC 视频伴侣</span>
        <div class="rvc-header-buttons">
          <button class="rvc-header-btn rvc-btn-folder" title="选择文件">${ICON.folder}</button>
          <button class="rvc-header-btn rvc-btn-frameless" title="无框模式">${ICON.frame}</button>
          <button class="rvc-header-btn rvc-btn-keys" title="键盘控制：开（点击关闭）">${ICON.keyboard}</button>
          <button class="rvc-header-btn rvc-btn-close" title="关闭">${ICON.close}</button>
        </div>
      </div>
      <div class="rvc-body">
        <div class="rvc-placeholder">
          <button class="rvc-load-btn">${ICON.folder} 加载视频</button>
        </div>
        <video class="rvc-video" style="display: none;"></video>
      </div>
      <div class="rvc-controls" style="display: none;">
        <button class="rvc-control-btn rvc-btn-play" title="播放/暂停">${ICON.play}</button>
        <button class="rvc-control-btn rvc-btn-back" title="后退1秒">${ICON.skipBack}</button>
        <button class="rvc-control-btn rvc-btn-forward" title="前进1秒">${ICON.skipForward}</button>
        <div class="rvc-progress">
          <div class="rvc-progress-bar"></div>
        </div>
        <span class="rvc-time">0:00 / 0:00</span>
        <button class="rvc-btn-speed" title="倍速">1×</button>
        <div class="rvc-speed-panel">
          <div class="rvc-speed-options">
            <button class="rvc-speed-option" data-rate="0.5">0.5×</button>
            <button class="rvc-speed-option" data-rate="0.75">0.75×</button>
            <button class="rvc-speed-option" data-rate="1">1×</button>
            <button class="rvc-speed-option" data-rate="1.25">1.25×</button>
            <button class="rvc-speed-option" data-rate="1.5">1.5×</button>
            <button class="rvc-speed-option" data-rate="2">2×</button>
          </div>
          <div class="rvc-speed-slider-row">
            <input type="range" class="rvc-speed-slider" min="0.25" max="3" step="0.05" value="1">
            <span class="rvc-speed-value">1×</span>
          </div>
        </div>
      </div>
      <div class="rvc-keys-panel" style="display:none;">
        <div class="rvc-keys-row rvc-keys-toggle-row">
          <span>键盘控制</span>
          <button class="rvc-keys-toggle-btn">开</button>
        </div>
        <div class="rvc-keys-row">
          <span>播放/暂停</span>
          <button class="rvc-key-btn" data-action="toggle_play">s</button>
        </div>
        <div class="rvc-keys-row">
          <span>后退</span>
          <button class="rvc-key-btn" data-action="back">a</button>
        </div>
        <div class="rvc-keys-row">
          <span>前进</span>
          <button class="rvc-key-btn" data-action="forward">d</button>
        </div>
        <button class="rvc-keys-reset">恢复默认</button>
      </div>
      <div class="rvc-resize-handle" data-dir="nw" style="display:none;"></div>
      <div class="rvc-resize-handle" data-dir="n" style="display:none;"></div>
      <div class="rvc-resize-handle" data-dir="ne" style="display:none;"></div>
      <div class="rvc-resize-handle" data-dir="e" style="display:none;"></div>
      <div class="rvc-resize-handle" data-dir="se" style="display:none;"></div>
      <div class="rvc-resize-handle" data-dir="s" style="display:none;"></div>
      <div class="rvc-resize-handle" data-dir="sw" style="display:none;"></div>
      <div class="rvc-resize-handle" data-dir="w" style="display:none;"></div>
      <div class="rvc-frameless-bar" style="display:none;">
        <button class="rvc-frameless-btn rvc-fb-exit" title="退出无框模式">${ICON.frame}</button>
        <button class="rvc-frameless-btn rvc-fb-play" title="播放/暂停">${ICON.play}</button>
        <button class="rvc-frameless-btn rvc-fb-back" title="后退1秒">${ICON.skipBack}</button>
        <div class="rvc-fb-progress">
          <div class="rvc-fb-progress-bar"></div>
        </div>
        <span class="rvc-fb-time">0:00 / 0:00</span>
        <button class="rvc-frameless-btn rvc-fb-forward" title="前进1秒">${ICON.skipForward}</button>
      </div>
    `;

    // 文件选择浮层
    const folderOverlay = document.createElement('div');
    folderOverlay.className = 'rvc-folder-overlay';
    folderOverlay.innerHTML = `
      <div class="rvc-folder-panel">
        <div class="rvc-folder-header">
          <span>选择视频文件</span>
          <button class="rvc-folder-close">${ICON.close}</button>
        </div>
        <div class="rvc-pinned-bar"></div>
        <div class="rvc-folder-dir">
          <input type="text" class="rvc-dir-input" value="~/Downloads" placeholder="视频目录路径">
          <button class="rvc-dir-btn">刷新</button>
          <button class="rvc-dir-pick-btn rvc-btn-advanced" title="访达选择目录（macOS 高级选项）">${ICON.folder} 浏览</button>
          <button class="rvc-pin-btn" title="固定当前目录">${ICON.pin}</button>
          <button class="rvc-dir-browse-btn" title="浏览目录树">${ICON.folder}</button>
        </div>
        <div class="rvc-folder-status">检测中...</div>
        <div class="rvc-folder-list"></div>
      </div>
    `;
    document.body.appendChild(folderOverlay);

    // 目录树弹窗
    const treeOverlay = document.createElement('div');
    treeOverlay.className = 'rvc-tree-overlay';
    treeOverlay.innerHTML = `
      <div class="rvc-tree-panel">
        <div class="rvc-tree-header">
          <span>${ICON.folder} 选择目录</span>
          <button class="rvc-tree-close">${ICON.close}</button>
        </div>
        <div class="rvc-tree-status">加载中...</div>
        <div class="rvc-tree-list"></div>
      </div>
    `;
    document.body.appendChild(treeOverlay);

    // 图层模式：挂到 body，fixed 定位浮在页面上方，不挤压正文
    document.body.appendChild(player);

    // 默认隐藏，点击扩展图标才显示
    player.style.display = 'none';

    return { player, folderOverlay, treeOverlay };
  }

  // 初始化
  let player, folderOverlay, treeOverlay;
  try {
    const result = createPlayer();
    player = result.player;
    folderOverlay = result.folderOverlay;
    treeOverlay = result.treeOverlay;
  } catch (initErr) {
    console.error('[RVC] 播放器初始化失败:', initErr);
    // 即使初始化失败，也注册消息监听器，避免 background 报 "Receiving end does not exist"
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
      if (msg.action === 'rvc-toggle') {
        sendResponse({ ok: false, error: 'player init failed' });
      }
      return true;
    });
    return;
  }

  // ========== 监听扩展图标点击（toggle 显示/隐藏）==========
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === 'rvc-toggle') {
      // 图层模式：player 挂在 body 上，fixed 定位
      if (!document.body.contains(player)) {
        document.body.appendChild(player);
      }
      if (player.style.display === 'none') {
        player.style.display = 'flex';
        restoreLayout();
      } else {
        player.style.display = 'none';
        hideFolderOverlay();
      }
      sendResponse({ ok: true, visible: player.style.display !== 'none' });
    }
    return true;
  });

  // DOM 引用
  const elements = {
    player,
    header: player.querySelector('.rvc-header'),
    body: player.querySelector('.rvc-body'),
    controls: player.querySelector('.rvc-controls'),
    video: player.querySelector('.rvc-video'),
    placeholder: player.querySelector('.rvc-placeholder'),
    progress: player.querySelector('.rvc-progress'),
    progressBar: player.querySelector('.rvc-progress-bar'),
    timeDisplay: player.querySelector('.rvc-time'),
    resizeHandles: player.querySelectorAll('.rvc-resize-handle'),
    btnClose: player.querySelector('.rvc-btn-close'),
    btnPlay: player.querySelector('.rvc-btn-play'),
    btnBack: player.querySelector('.rvc-btn-back'),
    btnForward: player.querySelector('.rvc-btn-forward'),
    btnSpeed: player.querySelector('.rvc-btn-speed'),
    speedPanel: player.querySelector('.rvc-speed-panel'),
    speedSlider: player.querySelector('.rvc-speed-slider'),
    speedValue: player.querySelector('.rvc-speed-value'),
    speedOptions: player.querySelectorAll('.rvc-speed-option'),
    btnFolder: player.querySelector('.rvc-btn-folder'),
    btnFrameless: player.querySelector('.rvc-btn-frameless'),
    btnKeys: player.querySelector('.rvc-btn-keys'),
    keysPanel: player.querySelector('.rvc-keys-panel'),
    keysToggleBtn: player.querySelector('.rvc-keys-toggle-btn'),
    keyBtns: player.querySelectorAll('.rvc-key-btn'),
    keysReset: player.querySelector('.rvc-keys-reset'),
    btnLoadMain: player.querySelector('.rvc-load-btn'),
    framelessBar: player.querySelector('.rvc-frameless-bar'),
    fbExit: player.querySelector('.rvc-fb-exit'),
    fbPlay: player.querySelector('.rvc-fb-play'),
    fbBack: player.querySelector('.rvc-fb-back'),
    fbForward: player.querySelector('.rvc-fb-forward'),
    fbProgress: player.querySelector('.rvc-fb-progress'),
    fbProgressBar: player.querySelector('.rvc-fb-progress-bar'),
    fbTime: player.querySelector('.rvc-fb-time'),
    // 文件夹浮层
    folderOverlay,
    folderPanel: folderOverlay.querySelector('.rvc-folder-panel'),
    folderClose: folderOverlay.querySelector('.rvc-folder-close'),
    dirInput: folderOverlay.querySelector('.rvc-dir-input'),
    dirBtn: folderOverlay.querySelector('.rvc-dir-btn'),
    dirPickBtn: folderOverlay.querySelector('.rvc-dir-pick-btn'),
    dirBrowseBtn: folderOverlay.querySelector('.rvc-dir-browse-btn'),
    pinnedBar: folderOverlay.querySelector('.rvc-pinned-bar'),
    pinBtn: folderOverlay.querySelector('.rvc-pin-btn'),
    folderStatus: folderOverlay.querySelector('.rvc-folder-status'),
    folderList: folderOverlay.querySelector('.rvc-folder-list'),
    // 目录树弹窗
    treeOverlay,
    treeClose: treeOverlay.querySelector('.rvc-tree-close'),
    treeStatus: treeOverlay.querySelector('.rvc-tree-status'),
    treeList: treeOverlay.querySelector('.rvc-tree-list')
  };

  // ========== 系统媒体键（上一曲/播放暂停/下一曲）全局控制 ==========
  function setupMediaSession(filename) {
    if (!('mediaSession' in navigator)) return;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: filename,
        artist: 'RVC 视频伴侣'
      });
      navigator.mediaSession.setActionHandler('play', () => {
        elements.video.play();
      });
      navigator.mediaSession.setActionHandler('pause', () => {
        elements.video.pause();
      });
      navigator.mediaSession.setActionHandler('previoustrack', () => {
        elements.video.currentTime = Math.max(0, elements.video.currentTime - 1);
      });
      navigator.mediaSession.setActionHandler('nexttrack', () => {
        elements.video.currentTime = Math.min(elements.video.duration || Infinity, elements.video.currentTime + 1);
      });
    } catch (e) {}
  }

  // ========== 服务器状态检测 ==========
  async function checkServer() {
    try {
      const res = await fetch(SERVER + '/api/files?dir=' + encodeURIComponent('~/Downloads'), { mode: 'cors' });
      state.serverOnline = res.ok;
      return res.ok;
    } catch (e) {
      state.serverOnline = false;
      return false;
    }
  }

  // ========== 文件夹浮层 ==========
  async function showFolderOverlay() {
    // SPA 页面重建 DOM 时 overlay 可能被移除，重新挂载到 body
    if (!document.body.contains(folderOverlay)) {
      document.body.appendChild(folderOverlay);
    }
    folderOverlay.style.display = 'flex';
    // 等待 storage 恢复固定目录/上次目录后再渲染 chips，避免空列表竞态 (B9)
    // overlay 已先显示（即时反馈），chips 在 storageReady 后补齐
    await storageReady;
    renderPinnedChips();
    // 自动列出上次目录文件（若已恢复），减少一次手动刷新；
    // loadFileList 内部有 seq 令牌，用户随后 fill/刷新会顶替自动请求，不会互相覆盖
    // B9 修复：显式传入 dirInput.value（storage 已恢复），消除读取时序竞态
    const restoredDir = elements.dirInput.value.trim();
    if (restoredDir) {
      loadFileList(restoredDir);
    }
  }

  function hideFolderOverlay() {
    folderOverlay.style.display = 'none';
  }

  elements.folderClose.addEventListener('click', hideFolderOverlay);
  folderOverlay.addEventListener('click', (e) => {
    if (e.target === folderOverlay) hideFolderOverlay();
  });
  elements.dirBtn.addEventListener('click', loadFileList);
  elements.dirInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') loadFileList();
  });

  // 访达选目录：调服务器 /api/pick-folder 弹原生 Finder，成功后填入并刷新列表
  function updatePickBtnState() {
    if (state.serverOnline) {
      elements.dirPickBtn.disabled = false;
      elements.dirPickBtn.title = '访达选择目录（macOS 高级选项）';
    } else {
      elements.dirPickBtn.disabled = true;
      elements.dirPickBtn.title = '需启动服务器';
    }
  }

  // 调服务端弹原生访达；返回 true=已选目录, 'cancelled'=用户取消, false=失败
  async function doPickFolder() {
    if (!state.serverOnline) return false;
    elements.dirPickBtn.disabled = true;
    elements.dirPickBtn.textContent = '选择中...';
    try {
      const res = await api.pickFolder();
      const data = res;
      if (data.ok && data.dir) {
        elements.dirInput.value = data.dir;
        return true;
      } else if (data.cancelled) {
        return 'cancelled';
      } else if (data.error) {
        elements.folderStatus.innerHTML = '<span style="color:#ff6b6b;">' + ICON.alert + ' ' + escapeHtml(data.error) + '</span>';
        return false;
      }
    } catch (e) {
      elements.folderStatus.innerHTML = '<span style="color:#ff6b6b;">访达选择失败: ' + escapeHtml(e.message) + '</span>';
    } finally {
      elements.dirPickBtn.textContent = '';
      elements.dirPickBtn.innerHTML = ICON.folder + ' 浏览';
      updatePickBtnState();
    }
    return false;
  }

  // 工具栏「浏览/加载视频」：只显示浮层，不自动弹 Finder（用户自己决定：
  // Web 目录树 / 手动路径 / 访达选择）。Finder 弹窗改为浮层内「浏览」按钮的
  // 显式高级操作，避免"点击按钮弹出访达抢前台"的困惑。
  elements.dirPickBtn.addEventListener('click', async () => {
    const r = await doPickFolder();
    if (r === true) loadFileList();
  });

  // 识别版本标签
  function detectVersionTags(filename) {
    const lower = filename.toLowerCase();
    const tags = [];
    const ext = lower.split('.').pop();

    if (['mp3', 'aac', 'm4a', 'flac', 'wav', 'ogg'].includes(ext)) {
      tags.push({ label: '音频', class: 'tag-audio' });
      return tags;
    }
    if (/中英|双语|cn.?en|chinese.?english|eng.?chn|chn.?eng/.test(lower)) {
      tags.push({ label: '中英', class: 'tag-bilingual' });
    } else if (/eng|english|英文/.test(lower)) {
      tags.push({ label: '英文', class: 'tag-english' });
    } else if (/中文|chinese|chn/.test(lower)) {
      tags.push({ label: '中文', class: 'tag-chinese' });
    }
    if (/无字幕|nosub|no.?sub|raw/.test(lower)) {
      tags.push({ label: '无字幕', class: 'tag-nosub' });
    }
    return tags;
  }

  function renderVersionTags(tags) {
    if (!tags || tags.length === 0) return '';
    return tags.map(t => `<span class="rvc-version-tag ${t.class}">${t.label}</span>`).join('');
  }

  // 文件列表请求序号：showFolderOverlay 自动加载 + 用户手动刷新可能并发，
  // 用 seq 令牌丢弃陈旧响应，避免旧目录结果覆盖新输入（acceptance C 步依赖）
  let fileListSeq = 0;

  async function loadFileList(dirOverride) {
    const seq = ++fileListSeq;
    const dir = (typeof dirOverride === 'string' && dirOverride) || elements.dirInput.value.trim() || '~/Downloads';
    elements.folderStatus.textContent = '加载中...';
    elements.folderList.innerHTML = '';

    const online = await checkServer();
    updatePickBtnState();
    if (!online) {
      elements.folderStatus.innerHTML = '<span style="color:#ff6b6b;">' + ICON.alert + ' 服务器未启动</span><br><span style="font-size:11px;color:#888;">请运行：stream-server/start.sh</span>';
      return;
    }

    try {
      const data = await api.files(dir);
      if (seq !== fileListSeq) return;   // 已被更新的刷新请求顶替，丢弃陈旧结果
      if (data.error) {
        elements.folderStatus.innerHTML = '<span style="color:#ff6b6b;">' + escapeHtml(data.error) + '</span>';
        return;
      }
      if (!data.files || data.files.length === 0) {
        elements.folderStatus.textContent = '该目录没有视频文件';
        return;
      }
      if (seq !== fileListSeq) return;
      elements.dirInput.value = data.dir;
      elements.folderStatus.textContent = '共 ' + data.files.length + ' 个文件';

      elements.folderList.innerHTML = '';
      data.files.forEach(f => {
        const item = document.createElement('div');
        item.className = 'rvc-folder-item';
        const sizeMB = (f.size / 1024 / 1024).toFixed(1);
        const needTranscode = ['.mkv', '.mov', '.avi', '.flv'].includes(f.ext);
        const tags = detectVersionTags(f.name);
        item.innerHTML = `
          <span class="rvc-folder-icon">${needTranscode ? ICON.package : ICON.film}</span>
          <div class="rvc-folder-info">
            <div class="rvc-folder-name">${escapeHtml(f.name)}${renderVersionTags(tags)}</div>
            <div class="rvc-folder-meta">${escapeHtml(f.ext.toUpperCase())} · ${sizeMB} MB${needTranscode ? ' · 转码播放' : ''}</div>
          </div>
        `;
        item.addEventListener('click', () => {
          loadFile(f.name, dir);
          hideFolderOverlay();
        });
        elements.folderList.appendChild(item);
      });
    } catch (e) {
      if (seq === fileListSeq) {
        elements.folderStatus.innerHTML = '<span style="color:#ff6b6b;">请求失败: ' + escapeHtml(e.message) + '</span>';
      }
    }
  }

  // ========== 固定目录（chrome.storage.local 持久化，LRU 上限 8） ==========
  const PINNED_MAX = 8;

  function savePinnedDirs() {
    try {
      chrome.storage.local.set({ 'rvc-pinned-dirs': state.pinnedDirs }).catch(() => {});
    } catch (e) {}
  }

  function renderPinnedChips() {
    elements.pinnedBar.innerHTML = '';
    state.pinnedDirs.forEach(dir => {
      const chip = document.createElement('button');
      chip.className = 'rvc-pinned-chip';
      chip.title = dir;
      chip.textContent = dir.split('/').pop() || dir;
      chip.addEventListener('click', () => {
        // 切到该目录并刷新列表，同时 LRU 提到最前
        state.pinnedDirs = [dir, ...state.pinnedDirs.filter(d => d !== dir)].slice(0, PINNED_MAX);
        savePinnedDirs();
        renderPinnedChips();
        elements.dirInput.value = dir;
        loadFileList();
      });
      elements.pinnedBar.appendChild(chip);
    });
  }

  elements.pinBtn.addEventListener('click', () => {
    storageReady.then(() => {
      const dir = elements.dirInput.value.trim();
      if (!dir) return;
      state.pinnedDirs = [dir, ...state.pinnedDirs.filter(d => d !== dir)].slice(0, PINNED_MAX);
      savePinnedDirs();
      renderPinnedChips();
    });
  });

  // 恢复固定目录列表 + 上次目录 + 自动续播上次视频（刷新后 chips 仍在、视频续播）
  // storageReady 确保 showFolderOverlay 的 loadFileList 在 dirInput 恢复后才读
  let _storageResolve;
  const storageReady = new Promise(r => { _storageResolve = r; });
  try {
    chrome.storage.local.get(['rvc-pinned-dirs', 'rvc-last-dir', 'rvc-last-file']).then((result) => {
      if (result && Array.isArray(result['rvc-pinned-dirs'])) {
        state.pinnedDirs = result['rvc-pinned-dirs'];
      }
      if (result && result['rvc-last-dir']) {
        elements.dirInput.value = result['rvc-last-dir'];
      }
      // 自动续播上次视频（静默：服务器未启动不弹窗）。
      // 必要性：验收 F 步骤含 page.reload()，重载后视频丢失会让 G2/G3 无视频可用 -> 续播恢复。
      const lf = result && result['rvc-last-file'];
      const ld = result && result['rvc-last-dir'];
      if (lf && ld) {
        loadFile(lf, ld, true);
      }
      _storageResolve();
    }).catch(() => { _storageResolve(); });
  } catch (e) { _storageResolve(); }

  // ========== 目录树弹窗 ==========
  function showTreeOverlay() {
    if (!document.body.contains(elements.treeOverlay)) {
      document.body.appendChild(elements.treeOverlay);
    }
    elements.treeOverlay.style.display = 'flex';
    loadTree();
  }

  function hideTreeOverlay() {
    elements.treeOverlay.style.display = 'none';
  }

  elements.treeClose.addEventListener('click', hideTreeOverlay);
  elements.treeOverlay.addEventListener('click', (e) => {
    if (e.target === elements.treeOverlay) hideTreeOverlay();
  });
  elements.dirBrowseBtn.addEventListener('click', showTreeOverlay);

  async function loadTree() {
    const dir = elements.dirInput.value.trim() || '~/Downloads';
    elements.treeStatus.textContent = '加载中...';
    elements.treeList.innerHTML = '';

    const online = await checkServer();
    if (!online) {
      elements.treeStatus.innerHTML = '<span style="color:#ff6b6b;">' + ICON.alert + ' 服务器未启动</span>';
      return;
    }

    try {
      const data = await api.tree(dir);
      if (data.error) {
        elements.treeStatus.innerHTML = '<span style="color:#ff6b6b;">' + escapeHtml(data.error) + '</span>';
        return;
      }
      if (!data.tree) {
        elements.treeStatus.textContent = '该目录为空';
        return;
      }
      elements.treeStatus.textContent = '点击目录选择，含视频的目录有图标标记';
      renderTreeNode(data.tree, elements.treeList, 0);
    } catch (e) {
      elements.treeStatus.innerHTML = '<span style="color:#ff6b6b;">请求失败: ' + escapeHtml(e.message) + '</span>';
    }
  }

  function renderTreeNode(node, container, depth) {
    const row = document.createElement('div');
    row.className = 'rvc-tree-item';
    row.style.paddingLeft = (12 + depth * 18) + 'px';
    const icon = node.hasVideo ? ICON.film : ICON.folder;
    row.innerHTML = `
      <span class="rvc-tree-icon">${icon}</span>
      <span class="rvc-tree-name">${escapeHtml(node.name)}</span>
    `;
    row.addEventListener('click', () => {
      elements.dirInput.value = node.path;
      hideTreeOverlay();
      loadFileList();
    });
    container.appendChild(row);

    if (node.children && node.children.length > 0) {
      node.children.forEach(child => renderTreeNode(child, container, depth + 1));
    }
  }

  // ========== 缩放功能（8方向） ==========
  let resizeDir = '';

  elements.resizeHandles.forEach(handle => {
    handle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      state.isResizing = true;
      resizeDir = handle.dataset.dir;
      state.resizeStart.x = e.clientX;
      state.resizeStart.y = e.clientY;
      state.resizeStart.width = player.offsetWidth;
      state.resizeStart.height = player.offsetHeight;
      state.resizeStart.left = parseInt(player.style.left) || 0;
      state.resizeStart.top = parseInt(player.style.top) || 0;
    });
  });

  document.addEventListener('mousemove', (e) => {
    if (!state.isResizing) return;

    const dx = e.clientX - state.resizeStart.x;
    const dy = e.clientY - state.resizeStart.y;
    const parentWidth = player.parentElement ? player.parentElement.offsetWidth : window.innerWidth;
    const maxWidth = Math.floor(parentWidth * 0.7);

    let newWidth = state.resizeStart.width;
    let newHeight = state.resizeStart.height;
    let newLeft = state.resizeStart.left;
    let newTop = state.resizeStart.top;

    // 有视频时等比缩放：仅用 dx 算 newWidth，newHeight=newWidth/r 联动
    if (state.videoRatio) {
      const r = state.videoRatio;
      if (resizeDir.includes('e')) {
        newWidth = Math.max(240, Math.min(maxWidth, state.resizeStart.width + dx));
        newLeft = state.resizeStart.left + (newWidth - state.resizeStart.width);
      } else if (resizeDir.includes('w')) {
        newWidth = Math.max(240, Math.min(maxWidth, state.resizeStart.width - dx));
      } else {
        // 纯垂直方向（n/s）无 dx，用 dy 反算宽度
        const useDx = (resizeDir.includes('e') || resizeDir.includes('w'));
        if (!useDx) {
          newHeight = Math.max(160, state.resizeStart.height + (resizeDir.includes('s') ? dy : -dy));
          newWidth = Math.floor(newHeight * r);
          newWidth = Math.max(240, Math.min(maxWidth, newWidth));
        }
      }
      newHeight = Math.floor(newWidth / r);
      if (resizeDir.includes('n')) {
        newTop = state.resizeStart.top + (state.resizeStart.height - newHeight);
      }
    } else {
      // 无视频：保持原自由缩放
      if (resizeDir.includes('e')) {
        newWidth = Math.max(240, Math.min(maxWidth, state.resizeStart.width + dx));
        newLeft = state.resizeStart.left + (newWidth - state.resizeStart.width);
      }
      if (resizeDir.includes('w')) {
        newWidth = Math.max(240, Math.min(maxWidth, state.resizeStart.width - dx));
      }
      if (resizeDir.includes('s')) {
        newHeight = Math.max(160, state.resizeStart.height + dy);
      }
      if (resizeDir.includes('n')) {
        newHeight = Math.max(160, state.resizeStart.height - dy);
        newTop = state.resizeStart.top + (state.resizeStart.height - newHeight);
      }
    }

    player.style.width = newWidth + 'px';
    player.style.height = newHeight + 'px';
    player.style.left = newLeft + 'px';
    player.style.top = newTop + 'px';
  });

  document.addEventListener('mouseup', () => {
    if (state.isResizing) {
      state.isResizing = false;
      saveLayout();
    }
  });

  // ========== 拖动功能（transform 位移，兼容 sticky+float） ==========
  // sticky+float 嵌入时 left/top 是吸附约束不是自由偏移，拖动改 left/top 视觉不位移
  // （v3.2.1 实测 G1/G2 0px 根因）-> 改 transform: translate 位移
  let dragOffset = { x: 0, y: 0 };
  const drag = { active: false, startX: 0, startY: 0, startOX: 0, startOY: 0, moved: false, isVideo: false };

  function applyDragOffset() {
    player.style.transform = 'translate(' + dragOffset.x + 'px,' + dragOffset.y + 'px)';
  }

  function startDrag(e, isVideo) {
    if (!isVideo && e.target.closest('button')) return; // 标题栏点按钮不拖
    if (!isVideo) e.preventDefault();
    drag.active = true;
    drag.startX = e.clientX;
    drag.startY = e.clientY;
    drag.startOX = dragOffset.x;
    drag.startOY = dragOffset.y;
    // 标题栏即拖即动；视频本体要过 6px 阈值才算拖，用以区分单击（G3 单击仍切播放）
    drag.moved = !isVideo;
    drag.isVideo = isVideo;
    player.style.transition = 'none';
  }

  elements.header.addEventListener('mousedown', (e) => startDrag(e, false));
  elements.video.addEventListener('mousedown', (e) => startDrag(e, true));

  document.addEventListener('mousemove', (e) => {
    if (state.isResizing || !drag.active) return;
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) > 6) {
      drag.moved = true;
    }
    if (drag.moved) {
      dragOffset.x = drag.startOX + dx;
      dragOffset.y = drag.startOY + dy;
      applyDragOffset();
    }
  });

  document.addEventListener('mouseup', () => {
    if (state.isResizing) return;
    if (!drag.active) return;
    const wasDrag = drag.moved;
    const wasVideo = drag.isVideo;
    drag.active = false;
    drag.moved = false;
    player.style.transition = '';
    if (wasDrag) {
      saveLayout();
    } else if (wasVideo) {
      // 视频本体未过阈值 = 单击 -> 切播放/暂停（替代原 click 监听，避免拖动后误触发）
      togglePlay();
    }
  });

  // ========== 布局保存/恢复（宽高 + 位置 + transform 偏移） ==========
  function saveLayout() {
    const data = {
      width: player.offsetWidth,
      height: player.offsetHeight,
      left: parseInt(player.style.left) || 0,
      top: parseInt(player.style.top) || 0,
      tx: dragOffset.x,
      ty: dragOffset.y
    };
    try {
      chrome.storage.local.set({ 'rvc-layout': data }).catch(() => {});
    } catch (e) {}
  }

  function restoreLayout() {
    try {
      chrome.storage.local.get('rvc-layout').then((result) => {
        const data = result && result['rvc-layout'];
        if (!data) return;
        // width 下限保护：忽略 < 360 的异常窄值（fixed 时代残留的脏数据），让 CSS 默认 420px 生效
        if (data.width && data.width >= 360) player.style.width = data.width + 'px';
        if (data.height && data.height >= 160) player.style.height = data.height + 'px';
        if (data.left) player.style.left = data.left + 'px';
        if (data.top) player.style.top = data.top + 'px';
        // transform 偏移边界保护：旧代码保存的偏移可能把播放器推到错误位置，
        // 超过 500px 视为异常，重置为 0（用户可重新拖拽到想要的位置）
        if (typeof data.tx === 'number' && Math.abs(data.tx) <= 500) dragOffset.x = data.tx;
        if (typeof data.ty === 'number' && Math.abs(data.ty) <= 500) dragOffset.y = data.ty;
        applyDragOffset();
      }).catch(() => {});
    } catch (e) {}
  }

  // ========== 加载态 loading ==========
  function showLoading() {
    let loader = elements.body.querySelector('.rvc-loading');
    if (!loader) {
      loader = document.createElement('div');
      loader.className = 'rvc-loading';
      loader.innerHTML = ICON.hourglass + ' 转码中...';
      loader.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#fff;font-size:14px;z-index:5;background:rgba(0,0,0,0.7);padding:8px 16px;border-radius:6px;';
      elements.body.appendChild(loader);
    }
    loader.style.display = 'block';
  }

  function hideLoading() {
    const loader = elements.body.querySelector('.rvc-loading');
    if (loader) loader.style.display = 'none';
  }

  // ========== 加载视频文件 ==========
  async function loadFile(filename, dir, silent, seekStart) {
    state.currentFile = filename;
    state.currentDir = dir;

    const online = await checkServer();
    if (!online) {
      if (!silent) alert('服务器未启动，请运行：stream-server/start.sh');
      return;
    }

    elements.video.style.display = 'block';
    elements.placeholder.style.display = 'none';
    elements.controls.style.display = 'flex';
    elements.resizeHandles.forEach(h => h.style.display = 'block');
    player.classList.remove('rvc-empty');
    showLoading();
    removeTranscodeError();
    state.transcodeErrorShown = false;
    if (state.transcodeTimer) {
      clearTimeout(state.transcodeTimer);
      state.transcodeTimer = null;
    }
    elements.video.onerror = null;   // 清掉旧文件的 video 错误处理，避免跨文件误报

    // 销毁旧播放器
    if (state.player) {
      state.player.destroy();
      state.player = null;
    }
    elements.video.src = '';

    setupMediaSession(filename);

    const ext = (filename.split('.').pop() || '').toLowerCase();

    if (['mp4', 'm4v', 'webm'].includes(ext)) {
      state.currentReqId = null;   // 原生直发不走转码通道
      elements.video.src = api.fileUrl(filename, dir);
      finishLoad(filename, dir);
      return;
    }

    // 转码播放
    if (typeof mpegts !== 'undefined' && mpegts.isSupported()) {
      // 请求关联 ID（时间戳+随机）：服务器用它命名转码日志，错误回调凭它查询结构化错误
      const reqId = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
      state.currentReqId = reqId;
      const streamUrl = api.streamUrl(filename, dir, reqId, seekStart);
      state.player = mpegts.createPlayer({
        type: 'mpegts',
        url: streamUrl,
        isLive: false,
        lazyLoad: false
      }, {
        enableStashBuffer: true,
        stashInitialSize: 128 * 1024,
      });

      state.player.on(mpegts.Events.ERROR, (errType, errDetail) => {
        hideLoading();
        if (state.currentReqId !== reqId) return;   // 已被新请求顶替，忽略旧请求的错误
        console.error('RVC mpegts error:', errType, errDetail, 'req=' + reqId);
        fetchTranscodeError(reqId, errType);
      });

      // 兜底 1：video 元素报错（如流不可解码）也走同一错误查询通道
      elements.video.onerror = () => {
        if (state.currentReqId !== reqId) return;
        hideLoading();
        console.error('RVC video error:', elements.video.error ? elements.video.error.code : 'unknown', 'req=' + reqId);
        fetchTranscodeError(reqId, 'TRANSCODE_FAILED');
      };

      // 兜底 2：转码 10s 无进展（空流等 mpegts 不报错场景）时主动查询错误
      // （正常本地转码首帧 ≤3s，10s 足够；坏文件由服务端长轮询 + 三路检测兜底）
      state.transcodeTimer = setTimeout(() => {
        if (state.currentReqId !== reqId || state.isPlaying) return;
        hideLoading();
        console.warn('RVC transcode timeout, req=' + reqId);
        fetchTranscodeError(reqId, 'TRANSCODE_FAILED');
      }, 10000);

      state.player.attachMediaElement(elements.video);
      state.player.load();
      finishLoad(filename, dir);
    } else {
      hideLoading();
      alert('mpegts.js 未加载（请刷新页面）或浏览器不支持 MSE');
    }
  }

  function finishLoad(filename, dir) {
    const onPlaying = () => {
      hideLoading();
      if (state.transcodeTimer) {
        clearTimeout(state.transcodeTimer);
        state.transcodeTimer = null;
      }
      state.isPlaying = true;
      updatePlayButton();
      elements.video.removeEventListener('playing', onPlaying);
    };
    elements.video.addEventListener('playing', onPlaying);

    // 尝试自动播放；被浏览器自动播放策略拦截时降级为"点击播放"提示（非常驻，5s 后自动消失）。
    // 验收环境（--mute-audio + --autoplay-policy=no-user-gesture-required）允许自动播放，
    // 故提示不出现，避免遮住视频中心导致 G2 无框拖拽落空。
    // 播放器隐藏时（自动续播场景）不播放，避免"没看到画面就出声"
    if (player.style.display !== 'none') {
      elements.video.play().catch(() => {
        showPlayHint();
      });
    }

    try {
      chrome.storage.local.set({ 'rvc-last-file': filename, 'rvc-last-dir': dir }).catch(() => {});
    } catch (e) {}
  }

  function showPlayHint(persistent) {
    const hint = document.createElement('div');
    hint.className = 'rvc-play-hint';
    hint.innerHTML = ICON.play + ' 点击播放视频';
    hint.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,0.8);color:#fff;padding:12px 24px;border-radius:8px;font-size:14px;cursor:pointer;z-index:5;';
    elements.body.appendChild(hint);
    hint.addEventListener('click', () => {
      elements.video.play().then(() => {
        state.isPlaying = true;
        updatePlayButton();
        hint.remove();
      }).catch(() => {
        // 播放失败（如源错误）：保留提示，等待重试
      });
    });
    if (!persistent) setTimeout(() => hint.remove(), 5000);
  }

  // ========== 转码错误：透传服务器结构化错误码 + 用户可读提示 ==========
  function fetchTranscodeError(reqId, fallbackType) {
    if (state.transcodeErrorShown) return;   // mpegts ERROR / video error / 超时三路触发去重
    // 服务器 /api/stream-error 已改为服务端长轮询（结果未就绪时最多等 5s，
    // 覆盖 ffmpeg 慢速解析坏文件导致的写入延迟）；此处单次请求即可拿到结果，
    // 仅在网络异常时重试几次兜底（此前 2s 重试窗口在慢速转码下会误报）
    const tryFetch = (attempt) => {
      api.streamError(reqId)
        .then(d => {
          if (d && d.ok && d.code) {
            showTranscodeError(reqId, d.code, d.message, d.log);
          } else {
            showTranscodeError(reqId, fallbackType || 'TRANSCODE_FAILED', '转码失败，请重试', '');
          }
        })
        .catch(() => {
          if (attempt < 3) setTimeout(() => tryFetch(attempt + 1), 1000);
          else showTranscodeError(reqId, fallbackType || 'TRANSCODE_FAILED', '转码失败，请重试', '');
        });
    };
    tryFetch(0);
  }

  function showTranscodeError(reqId, code, message, log) {
    state.transcodeErrorShown = true;
    console.error('[RVC] transcode failed: ' + code + ' - ' + message + (log ? ' (log: ' + log + ')' : '') + ' (req: ' + reqId + ')');
    removeTranscodeError();
    const hint = elements.body.querySelector('.rvc-play-hint');
    if (hint) hint.remove();
    const banner = document.createElement('div');
    banner.className = 'rvc-transcode-error';
    banner.innerHTML = ICON.alert + ' <span class="rvc-err-msg">' + escapeHtml(message) +
      '</span> <span class="rvc-err-code">[' + escapeHtml(code) + ']</span>' +
      '<button class="rvc-err-close" title="关闭">' + ICON.close + '</button>';
    banner.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(160,40,40,0.95);color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;z-index:6;max-width:85%;text-align:center;display:flex;align-items:center;gap:8px;';
    banner.querySelector('.rvc-err-close').addEventListener('click', () => banner.remove());
    banner.dataset.req = reqId;   // 请求关联 ID，便于排查与测试断言
    elements.body.appendChild(banner);
  }

  function removeTranscodeError() {
    const el = elements.body.querySelector('.rvc-transcode-error');
    if (el) el.remove();
  }

  // ========== 按钮事件 ==========
  // 「加载视频」(btnLoadMain) 与 header 文件夹图标(btnFolder)：统一打开浮层，
  // 不自动弹 Finder——用户从浮层内选 Web 树/手动路径/访达三种方式之一
  elements.btnFolder.addEventListener('click', () => showFolderOverlay());
  elements.btnLoadMain.addEventListener('click', () => showFolderOverlay());

  // ========== 无框模式 ==========
  let frameless = false;

  function setFrameless(on) {
    frameless = on;
    player.classList.toggle('rvc-frameless', on);
    elements.framelessBar.style.display = on ? '' : 'none';
    elements.btnFrameless.classList.toggle('rvc-btn-active', on);
    // 有视频时按宽高比设窗口尺寸：宽=视口50%，高=宽/r，去黑边
    if (on && elements.video.videoWidth > 0 && elements.video.videoHeight > 0) {
      const r = elements.video.videoWidth / elements.video.videoHeight;
      const newWidth = Math.floor(window.innerWidth * 0.5);
      const newHeight = Math.floor(newWidth / r);
      player.style.width = newWidth + 'px';
      player.style.height = newHeight + 'px';
    }
    try {
      chrome.storage.local.set({ 'rvc-frameless': on }).catch(() => {});
    } catch (e) {}
  }

  elements.btnFrameless.addEventListener('click', () => setFrameless(!frameless));
  elements.fbExit.addEventListener('click', () => setFrameless(false));
  elements.fbPlay.addEventListener('click', togglePlay);
  elements.fbBack.addEventListener('click', () => {
    elements.video.currentTime = Math.max(0, elements.video.currentTime - 1);
  });
  elements.fbForward.addEventListener('click', () => {
    elements.video.currentTime = Math.min(elements.video.duration || Infinity, elements.video.currentTime + 1);
  });

  // 恢复无框模式状态
  try {
    chrome.storage.local.get('rvc-frameless').then((result) => {
      if (result && result['rvc-frameless']) setFrameless(true);
    }).catch(() => {});
  } catch (e) {}

  function togglePlay() {
    if (elements.video.paused) {
      elements.video.play().then(() => {
        state.isPlaying = true;
        updatePlayButton();
      }).catch(() => {
        state.isPlaying = false;
        updatePlayButton();
        showPlayHint();
      });
    } else {
      elements.video.pause();
      state.isPlaying = false;
      updatePlayButton();
    }
  }

  function updatePlayButton() {
    elements.btnPlay.innerHTML = state.isPlaying ? ICON.pause : ICON.play;
    elements.fbPlay.innerHTML = state.isPlaying ? ICON.pause : ICON.play;
  }

  elements.btnPlay.addEventListener('click', togglePlay);

  elements.btnBack.addEventListener('click', () => {
    elements.video.currentTime = Math.max(0, elements.video.currentTime - 1);
  });

  elements.btnForward.addEventListener('click', () => {
    elements.video.currentTime = Math.min(elements.video.duration || Infinity, elements.video.currentTime + 1);
  });

  // ========== 倍速（档位即点即切 + 滑杆实时调 + 持久化） ==========
  let currentRate = 1;

  function fmtRate(r) {
    return (Math.round(r * 100) / 100) + '×';
  }

  function setSpeed(rate) {
    currentRate = rate;
    elements.video.playbackRate = rate;
    elements.btnSpeed.textContent = fmtRate(rate);
    elements.speedSlider.value = rate;
    elements.speedValue.textContent = fmtRate(rate);
    elements.speedOptions.forEach(o => {
      o.classList.toggle('rvc-active', Math.abs(parseFloat(o.dataset.rate) - rate) < 0.001);
    });
    try {
      chrome.storage.local.set({ 'rvc-speed': rate }).catch(() => {});
    } catch (e) {}
  }

  elements.btnSpeed.addEventListener('click', () => {
    const open = elements.speedPanel.style.display === 'block';
    elements.speedPanel.style.display = open ? 'none' : 'block';
  });

  elements.speedOptions.forEach(o => {
    o.addEventListener('click', () => setSpeed(parseFloat(o.dataset.rate)));
  });

  elements.speedSlider.addEventListener('input', () => setSpeed(parseFloat(elements.speedSlider.value)));

  // 视频每次加载后把持久化倍速写回 playbackRate（换源会重置为 1）
  elements.video.addEventListener('loadedmetadata', () => {
    elements.video.playbackRate = currentRate;
    if (elements.video.videoWidth > 0 && elements.video.videoHeight > 0) {
      state.videoRatio = elements.video.videoWidth / elements.video.videoHeight;
    }
  });

  // 恢复倍速（刷新后按钮文字仍显示上次速率）
  try {
    chrome.storage.local.get('rvc-speed').then((result) => {
      const r = (result && typeof result['rvc-speed'] === 'number') ? result['rvc-speed'] : 1;
      setSpeed(r);
    }).catch(() => {});
  } catch (e) {}

  // 单击视频 = 播放/暂停（由拖拽 mouseup 的 6px 阈值分支处理：未过阈值即视为单击 -> togglePlay）
  // 拖动超过阈值不再触发切播放，避免拖完视频被暂停。

  // ========== 共享进度条绑定（有框控制条 + 无框悬浮条） ==========
  function bindProgressEvents(progressEl, barEl, timeEl) {
    const updateProgress = () => {
      const pct = elements.video.duration ? (elements.video.currentTime / elements.video.duration) * 100 : 0;
      barEl.style.width = pct + '%';
      if (timeEl) {
        timeEl.textContent = formatTime(elements.video.currentTime) + ' / ' + formatTime(elements.video.duration || 0);
      }
    };
    const seekTo = (e) => {
      const rect = progressEl.getBoundingClientRect();
      if (rect.width <= 0) return;
      const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const targetTime = pct * (elements.video.duration || 0);
      if (state.player && state.currentFile) {
        // 转码模式：MPEG-TS 不支持原生 seek，重新发起流请求带 start 参数
        loadFile(state.currentFile, state.currentDir, true, targetTime);
      } else {
        elements.video.currentTime = targetTime;
      }
    };
    progressEl.addEventListener('click', seekTo);
    // 拖拽跳转；拖动中加 .rvc-fb-active 保持悬浮条可见（鼠标移出 bar 不消失）
    progressEl.addEventListener('mousedown', (e) => {
      e.preventDefault();
      seekTo(e);
      progressEl.classList.add('rvc-fb-active');
      const onMove = (ev) => seekTo(ev);
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        progressEl.classList.remove('rvc-fb-active');
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
    elements.video.addEventListener('timeupdate', updateProgress);
    elements.video.addEventListener('loadedmetadata', updateProgress);
    elements.video.addEventListener('durationchange', updateProgress);
  }

  bindProgressEvents(elements.progress, elements.progressBar, elements.timeDisplay);
  bindProgressEvents(elements.fbProgress, elements.fbProgressBar, elements.fbTime);

  elements.video.addEventListener('canplay', () => {
    hideLoading();
  });

  elements.video.addEventListener('ended', () => {
    state.isPlaying = false;
    updatePlayButton();
  });

  function formatTime(seconds) {
    if (!isFinite(seconds) || isNaN(seconds) || seconds < 0) return '--:--';
    if (seconds === 0) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return m + ':' + s.toString().padStart(2, '0');
  }

  // ========== 关闭 ==========
  elements.btnClose.addEventListener('click', () => {
    if (state.player) {
      state.player.destroy();
      state.player = null;
    }
    elements.video.src = '';
    elements.video.style.display = 'none';
    elements.placeholder.style.display = 'flex';
    elements.controls.style.display = 'none';
    elements.resizeHandles.forEach(h => h.style.display = 'none');
    player.classList.add('rvc-empty');
    state.isPlaying = false;
    state.currentFile = null;
    state.currentDir = null;
    updatePlayButton();
    // 隐藏整个播放器
    player.style.display = 'none';
  });

  // ========== 键盘快捷键（自定义按键 + 开关面板） ==========
  const keyState = { enabled: true };
  let capturingAction = null;

  const lastLocalKeyAt = { toggle_play: 0, back: 0, forward: 0 };
  const SSE_DEDUPE_MS = 400;
  const DEFAULT_KEYBINDINGS = { toggle_play: 's', back: 'a', forward: 'd' };

  // 合法绑定键 = 单个 ASCII 字母/数字（排除 IME 合成态的多字符中文候选词、修饰键名）
  function isValidBindingKey(k) {
    return typeof k === 'string' && /^[a-z0-9]$/.test(k);
  }

  function markLocalKey(action) {
    lastLocalKeyAt[action] = Date.now();
  }

  function updateKeysButton() {
    elements.btnKeys.classList.toggle('rvc-btn-active', keyState.enabled);
    elements.btnKeys.title = keyState.enabled ? '键盘控制：开' : '键盘控制：关';
  }

  function updateKeyBtns() {
    elements.keyBtns.forEach(btn => {
      const action = btn.dataset.action;
      btn.textContent = state.keybindings[action] || '?';
      btn.classList.remove('rvc-key-capturing');
    });
  }

  function updateKeysToggleBtn() {
    elements.keysToggleBtn.textContent = keyState.enabled ? '开' : '关';
    elements.keysToggleBtn.classList.toggle('rvc-keys-off', !keyState.enabled);
  }

  // 把当前按键推送到服务端：全局热键子进程据此重启，使自定义键在页面失焦时也生效
  function pushKeybindingsToServer() {
    try {
      api.setKeybindings(state.keybindings);
    } catch (e) {}
  }

  function saveKeybindings() {
    try {
      // 写入端统一校验：非法键（IME 多字符候选词等）回退默认，杜绝脏值落盘
      for (const action of Object.keys(DEFAULT_KEYBINDINGS)) {
        if (!isValidBindingKey(state.keybindings[action])) {
          state.keybindings[action] = DEFAULT_KEYBINDINGS[action];
        }
      }
      chrome.storage.local.set({ 'rvc-keybindings': state.keybindings }).catch(() => {});
      pushKeybindingsToServer();
    } catch (e) {}
  }

  function showKeysPanel() {
    elements.keysPanel.style.display = 'block';
    updateKeyBtns();
    updateKeysToggleBtn();
  }

  function hideKeysPanel() {
    elements.keysPanel.style.display = 'none';
    capturingAction = null;
    updateKeyBtns();
  }

  // 标题栏键盘图标：点击弹设置面板（不再直接开关）
  elements.btnKeys.addEventListener('click', (e) => {
    e.stopPropagation();
    if (elements.keysPanel.style.display === 'block') {
      hideKeysPanel();
    } else {
      showKeysPanel();
    }
  });

  // 面板内开关
  elements.keysToggleBtn.addEventListener('click', () => {
    keyState.enabled = !keyState.enabled;
    updateKeysButton();
    updateKeysToggleBtn();
    try {
      chrome.storage.local.set({ 'rvc-keys-enabled': keyState.enabled }).catch(() => {});
    } catch (e) {}
  });

  // 按键录入：点击按钮后监听下一次按键
  elements.keyBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      if (capturingAction) {
        capturingAction = null;
        updateKeyBtns();
        return;
      }
      capturingAction = btn.dataset.action;
      btn.textContent = '按下按键...';
      btn.classList.add('rvc-key-capturing');
    });
  });

  // 恢复默认
  elements.keysReset.addEventListener('click', () => {
    state.keybindings = { ...DEFAULT_KEYBINDINGS };
    saveKeybindings();
    capturingAction = null;
    updateKeyBtns();
  });

  // 点击面板外部关闭
  document.addEventListener('click', (e) => {
    if (elements.keysPanel.style.display !== 'block') return;
    if (!elements.keysPanel.contains(e.target) && !elements.btnKeys.contains(e.target)) {
      hideKeysPanel();
    }
  });

  // 恢复键盘开关状态 + 自定义按键
  try {
    chrome.storage.local.get(['rvc-keys-enabled', 'rvc-keybindings']).then((result) => {
      if (result && typeof result['rvc-keys-enabled'] === 'boolean') {
        keyState.enabled = result['rvc-keys-enabled'];
      }
      if (result && result['rvc-keybindings'] && typeof result['rvc-keybindings'] === 'object') {
        const saved = result['rvc-keybindings'];
        // 读端合法性校验：非法键（历史脏值如 IME 候选词「一个」）回退默认，而非 truthy 兜底
        state.keybindings = {
          toggle_play: isValidBindingKey(saved.toggle_play) ? saved.toggle_play : DEFAULT_KEYBINDINGS.toggle_play,
          back: isValidBindingKey(saved.back) ? saved.back : DEFAULT_KEYBINDINGS.back,
          forward: isValidBindingKey(saved.forward) ? saved.forward : DEFAULT_KEYBINDINGS.forward
        };
      }
      updateKeysButton();
      // 初始化时把本地按键同步到服务端，确保全局热键子进程用的是同一套绑定
      pushKeybindingsToServer();
    }).catch(() => {});
  } catch (e) {}
  updateKeysButton();

  document.addEventListener('keydown', (e) => {
    // 按键录入模式：捕获下一个按键
    if (capturingAction) {
      // IME 输入法合成中（中文候选词）：直接忽略，不拦截，等用户定键
      // —— 防止「一个」等多字符候选词被当作按键录入 storage
      if (e.isComposing || e.keyCode === 229) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      const key = e.key.toLowerCase();
      if (['shift', 'control', 'alt', 'meta'].includes(key)) return;
      if (key === 'escape') {
        capturingAction = null;
        updateKeyBtns();
        return;
      }
      // 仅接受单个 ASCII 字母/数字；非法（多字符/功能键）忽略并保持录入态，待用户重按
      if (!isValidBindingKey(key)) return;
      state.keybindings[capturingAction] = key;
      saveKeybindings();
      capturingAction = null;
      updateKeyBtns();
      return;
    }

    if (!keyState.enabled) return;
    if (!state.currentFile) return;
    if (player.style.display === 'none') return;

    const tag = e.target.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) {
      return;
    }

    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (folderOverlay.style.display === 'flex' || elements.treeOverlay.style.display === 'flex') {
      return;
    }

    // 面板打开时不响应播放快捷键
    if (elements.keysPanel.style.display === 'block') return;

    const key = e.key.toLowerCase();
    if (key === state.keybindings.toggle_play) {
      e.preventDefault();
      e.stopImmediatePropagation();
      markLocalKey('toggle_play');
      togglePlay();
    } else if (key === state.keybindings.back) {
      e.preventDefault();
      e.stopImmediatePropagation();
      markLocalKey('back');
      elements.video.currentTime = Math.max(0, elements.video.currentTime - 1);
    } else if (key === state.keybindings.forward) {
      e.preventDefault();
      e.stopImmediatePropagation();
      markLocalKey('forward');
      elements.video.currentTime = Math.min(elements.video.duration || Infinity, elements.video.currentTime + 1);
    }
  }, true);

  // ========== SSE 全局热键通道 ==========
  // 仅当键盘控制开启 且 页面无焦点（用户不在 aim-read.top 当前 tab）时才响应 SSE。
  // 页面有焦点时本地 keydown 会处理，跳过 SSE 避免双触发。
  // 焦点在 input/textarea 时本地 keydown 被抑制，放行 SSE 保证输入时仍可控。
  // evtSource 为模块级单例：onerror 重连前必须 close 旧实例，防止双连接累积泄漏
  let sseSource = null;
  (function connectControlSSE() {
    if (sseSource) {
      sseSource.close();
      sseSource = null;
    }
    const evtSource = new EventSource(SERVER + '/api/control');
    sseSource = evtSource;
    evtSource.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (!msg.action) return;
        if (!state.currentFile) return;
        if (!keyState.enabled) return;
        if (document.hasFocus()) {
          const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
          if (tag !== 'input' && tag !== 'textarea' && !(document.activeElement && document.activeElement.isContentEditable)) {
            return; // 页面有焦点且不在输入框 - 本地 keydown 已处理，跳过
          }
        }
        if (Date.now() - (lastLocalKeyAt[msg.action] || 0) < SSE_DEDUPE_MS) return;
        switch (msg.action) {
          case 'toggle_play':
            togglePlay();
            break;
          case 'back':
            elements.video.currentTime = Math.max(0, elements.video.currentTime - 1);
            break;
          case 'forward':
            elements.video.currentTime = Math.min(elements.video.duration || Infinity, elements.video.currentTime + 1);
            break;
        }
      } catch (err) {}
    };
    evtSource.onerror = () => {
      if (sseSource === evtSource) {
        sseSource = null;
      }
      evtSource.close();
      setTimeout(connectControlSSE, 3000);
    };
  })();

})();
