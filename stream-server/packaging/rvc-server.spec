# -*- mode: python ; coding: utf-8 -*-
# RVC 视频伴侣 Mac .app 打包配置（PyInstaller）
# 用法：packaging/build.sh（会先做 ffmpeg 依赖收集，再调用本 spec）
import os

SPEC_DIR = SPECPATH  # PyInstaller 6: SPECPATH 即 spec 文件所在目录
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, '..', '..'))
STREAM_DIR = os.path.join(PROJECT_ROOT, 'stream-server')
STAGING = os.path.join(SPEC_DIR, 'build', 'staging')

# ---- datas：静态文件 + 内置 ffmpeg/ffprobe + 其依赖 dylib ----
datas = [
    (os.path.join(STREAM_DIR, 'player.html'), '.'),
    (os.path.join(STREAM_DIR, 'mpegts.min.js'), '.'),
    (os.path.join(STAGING, 'ffmpeg', 'bin', 'ffmpeg'), os.path.join('ffmpeg', 'bin')),
    (os.path.join(STAGING, 'ffmpeg', 'bin', 'ffprobe'), os.path.join('ffmpeg', 'bin')),
]
_lib_dir = os.path.join(STAGING, 'ffmpeg', 'lib')
if os.path.isdir(_lib_dir):
    for name in sorted(os.listdir(_lib_dir)):
        datas.append((os.path.join(_lib_dir, name), os.path.join('ffmpeg', 'lib')))

# ---- pynput 平台模块（Mac 需要，防止漏收集） ----
hiddenimports = [
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._darwin',
    'pynput.mouse',
    'pynput.mouse._darwin',
    'pynput._util.darwin',
]

a = Analysis(
    [os.path.join(STREAM_DIR, 'server.py')],
    pathex=[STREAM_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='rvc-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # 保留终端窗口显示服务器日志（内部版友好）
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='rvc-server',
)

# 注：不做 BUNDLE（其布局不可控，ffmpeg 会被拆到 Frameworks）。
# .app 结构由 build.sh 手动组装（onedir -> Contents/MacOS + Contents/Resources/_internal），
# 保证 sys._MEIPASS = Contents/Resources/_internal，ffmpeg 依赖路径全部可控。
