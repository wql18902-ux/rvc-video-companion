#!/usr/bin/env python3
"""
RVC 流式转码服务器
实时把 MKV/MOV(AC3/DTS 音频)转码为 MPEG-TS 流，浏览器用 mpegts.js 边接收边播放
不再需要等整个文件转完——几秒后即可开始播放
"""

import http.server
import socketserver
import subprocess
import os
import json
import urllib.parse
import threading
import signal
import sys
import queue
import time

PORT = 8765
DEFAULT_DIR = os.path.expanduser("~/Downloads")
VIDEO_EXTS = {'.mkv', '.mov', '.avi', '.flv', '.webm', '.mp4', '.m4v'}


def find_ffmpeg_bin():
    """PyInstaller 打包后优先使用 .app 内置的 ffmpeg/ffprobe，否则退回 PATH"""
    candidates = []
    if hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, 'ffmpeg', 'bin'))
    if getattr(sys, 'frozen', False):
        # macOS .app：Contents/Resources 目录
        res = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), '..', 'Resources')
        candidates.append(os.path.join(res, 'ffmpeg', 'bin'))
    for c in candidates:
        if os.path.isfile(os.path.join(c, 'ffmpeg')):
            return c
    return None


FFMPEG_BIN = find_ffmpeg_bin()


def ffmpeg_cmd(binary):
    """返回 ffmpeg/ffprobe 可执行文件路径（打包优先内置，未打包用 PATH 原名）"""
    if FFMPEG_BIN:
        return os.path.join(FFMPEG_BIN, binary)
    return binary

# 全局：当前 ffmpeg 进程
current_proc = None
proc_lock = threading.Lock()

# 全局热键事件队列（线程安全）
control_queue = queue.Queue()
control_clients = []          # SSE 连接列表
control_clients_lock = threading.Lock()
hotkey_thread = None


def broadcast_control_event(action):
    """把热键事件广播给所有 SSE 客户端"""
    with control_clients_lock:
        dead = []
        for q in control_clients:
            try:
                q.put_nowait(action)
            except queue.Full:
                dead.append(q)
        for q in dead:
            if q in control_clients:
                control_clients.remove(q)


def start_hotkey_listener():
    """启动全局热键子进程（A/D/S 控制视频）。
    热键监听隔离到独立子进程：无「输入监控」权限时 pynput 进程会被 macOS SIGKILL，
    隔离后只死子进程，HTTP 服务不受影响。主进程不 wait、不重启；
    子进程连续 POST 失败 10 次自行退出。"""
    if getattr(sys, 'frozen', False):
        cmd = [sys.executable, '--hotkey-child']
    else:
        cmd = [sys.executable, os.path.abspath(__file__), '--hotkey-child']
    try:
        proc = subprocess.Popen(cmd)
        print(f"  [OK] 全局热键子进程已启动（pid={proc.pid}）：A=后退1秒  D=前进1秒  S=暂停/播放")
    except Exception as e:
        print(f"  [WARN] 热键子进程启动失败：{e}（全局热键不可用，浏览/播放等其余功能不受影响）")


def run_hotkey_child():
    """热键子进程入口：只跑 pynput 监听，按键 POST 到主进程 /api/control-key。
    连续 POST 失败 10 次自行退出（主进程已死）。"""
    import urllib.request
    try:
        from pynput import keyboard
    except ImportError:
        print("[hotkey-child] 未安装 pynput，退出")
        return

    state = {'fail': 0}
    FAIL_LIMIT = 10
    listener_box = [None]

    def post_action(action):
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:{PORT}/api/control-key',
                data=json.dumps({'action': action}).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=2).close()
            state['fail'] = 0
        except Exception:
            state['fail'] += 1
            if state['fail'] >= FAIL_LIMIT:
                print(f"[hotkey-child] 连续 {FAIL_LIMIT} 次 POST 失败，主进程可能已退出，自行退出")
                if listener_box[0] is not None:
                    listener_box[0].stop()

    def on_press(key):
        try:
            if hasattr(key, 'char'):
                if key.char == 's' or key.char == 'S':
                    post_action('toggle_play')
                elif key.char == 'a' or key.char == 'A':
                    post_action('back')
                elif key.char == 'd' or key.char == 'D':
                    post_action('forward')
        except Exception:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener_box[0] = listener
    listener.start()
    listener.join()


def kill_current_proc():
    """终止当前 ffmpeg 进程"""
    global current_proc
    with proc_lock:
        if current_proc:
            try:
                current_proc.kill()
                current_proc.wait(timeout=5)
            except Exception:
                pass
            current_proc = None


class StreamHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == '/':
            self.serve_html('player.html')
        elif path == '/mpegts.min.js':
            self.serve_static('mpegts.min.js', 'application/javascript')
        elif path == '/api/files':
            self.serve_file_list(params)
        elif path == '/api/tree':
            self.serve_tree(params)
        elif path == '/api/pick-folder':
            self.serve_pick_folder()
        elif path == '/api/file':
            self.serve_file(params)
        elif path == '/api/stream':
            self.serve_stream(params)
        elif path == '/api/duration':
            self.serve_duration(params)
        elif path == '/api/control':
            self.serve_control_sse()
        elif path == '/api/stop':
            kill_current_proc()
            self.send_json({'ok': True})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/control-key':
            self.serve_control_key()
        else:
            self.send_error(404)

    def serve_control_key(self):
        """内部端点：接收热键子进程 POST 的事件，转手广播给 SSE 客户端"""
        length = int(self.headers.get('Content-Length', 0))
        try:
            body = self.rfile.read(length) if length > 0 else b''
            data = json.loads(body) if body else {}
        except Exception:
            self.send_json({'ok': False, 'error': 'bad json'})
            return
        action = data.get('action')
        if action in ('toggle_play', 'back', 'forward'):
            broadcast_control_event(action)
            self.send_json({'ok': True})
        else:
            self.send_json({'ok': False, 'error': 'unknown action'})

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def serve_html(self, filename):
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if not os.path.isfile(html_path):
            self.send_error(404, f"{filename} not found")
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        with open(html_path, 'rb') as f:
            self.wfile.write(f.read())

    def serve_static(self, filename, content_type):
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if not os.path.isfile(file_path):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())

    def serve_file_list(self, params):
        dir_path = params.get('dir', [DEFAULT_DIR])[0]
        dir_path = os.path.expanduser(dir_path)
        if not os.path.isdir(dir_path):
            self.send_json({'files': [], 'error': '目录不存在'})
            return
        files = []
        for f in sorted(os.listdir(dir_path)):
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTS and not f.endswith('.downloading'):
                full = os.path.join(dir_path, f)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                files.append({
                    'name': f,
                    'size': size,
                    'ext': ext
                })
        self.send_json({'files': files, 'dir': dir_path})

    def serve_tree(self, params):
        """返回目录树，用于浏览器式目录选择"""
        dir_path = params.get('dir', [DEFAULT_DIR])[0]
        dir_path = os.path.expanduser(dir_path)
        if not os.path.isdir(dir_path):
            self.send_json({'tree': [], 'error': '目录不存在'})
            return

        def scan(path, depth=0):
            if depth > 3:
                return None
            try:
                entries = sorted(os.listdir(path))
            except OSError:
                return None

            has_video = False
            children = []
            for name in entries:
                if name.startswith('.'):
                    continue
                full = os.path.join(path, name)
                if os.path.isdir(full):
                    child = scan(full, depth + 1)
                    if child:
                        children.append(child)
                else:
                    ext = os.path.splitext(name)[1].lower()
                    if ext in VIDEO_EXTS:
                        has_video = True

            return {
                'name': os.path.basename(path),
                'path': path,
                'hasVideo': has_video,
                'children': children
            }

        tree = scan(dir_path)
        self.send_json({'tree': tree, 'dir': dir_path})

    def serve_pick_folder(self):
        """弹出原生文件选择对话框，选择视频目录。
        成功返回 {ok:true,dir:/abs/path/}；用户取消返回 {cancelled:true}；
        超时/报错返回 {ok:false,error:...}。"""
        # 单段 AppleScript：activate 与 choose folder 同在 tell "System Events" 块内，
        # 确保对话框弹到最前面（choose folder 单独调用会躲在浏览器后）。
        clean_env = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH')}
        try:
            result = subprocess.run(
                ['osascript', '-e',
                 'tell application "System Events"',
                 '-e', 'activate',
                 '-e', 'set f to choose folder',
                 '-e', 'end tell',
                 '-e', 'return POSIX path of f'],
                capture_output=True, text=True, timeout=60, env=clean_env
            )
        except subprocess.TimeoutExpired:
            self.send_json({'ok': False, 'error': '选择超时（60s）'})
            return
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)})
            return

        if result.returncode != 0:
            # 按 stderr 分流：仅「User canceled」才当取消静默，其余报错前端可见
            err = result.stderr.strip() if result.stderr else ''
            if 'User canceled' in err:
                self.send_json({'cancelled': True})
            else:
                self.send_json({'ok': False, 'error': err or f'osascript 退出码 {result.returncode}'})
            return

        dir_path = result.stdout.strip()
        if not dir_path:
            self.send_json({'cancelled': True})
            return
        self.send_json({'ok': True, 'dir': dir_path})

    def serve_duration(self, params):
        """用 ffprobe 获取视频时长"""
        file_path = params.get('file', [''])[0]
        dir_path = params.get('dir', [DEFAULT_DIR])[0]
        dir_path = os.path.expanduser(dir_path)
        full_path = os.path.join(dir_path, file_path)
        if not os.path.isfile(full_path):
            self.send_json({'error': '文件不存在'})
            return
        try:
            result = subprocess.run(
                [ffmpeg_cmd('ffprobe'), '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', full_path],
                capture_output=True, text=True, timeout=10
            )
            duration = float(result.stdout.strip()) if result.stdout.strip() else 0
            self.send_json({'duration': duration})
        except Exception as e:
            self.send_json({'error': str(e)})

    def serve_file(self, params):
        """原生分发视频文件（支持 HTTP Range），供 MP4/M4V/WebM 直接播放"""
        file_path = params.get('file', [''])[0]
        dir_path = params.get('dir', [DEFAULT_DIR])[0]
        dir_path = os.path.expanduser(dir_path)
        full_path = os.path.join(dir_path, file_path)

        if not os.path.isfile(full_path):
            self.send_error(404, "文件不存在")
            return

        ext = os.path.splitext(full_path)[1].lower()
        ctype = {
            '.mp4': 'video/mp4',
            '.m4v': 'video/mp4',
            '.webm': 'video/webm',
        }.get(ext, 'application/octet-stream')

        size = os.path.getsize(full_path)
        range_header = self.headers.get('Range')

        # 解析 Range: bytes=start-end
        start, end = 0, size - 1
        is_range = False
        if range_header:
            try:
                _, rng = range_header.split('=', 1)
                start_s, _, end_s = rng.partition('-')
                if start_s:
                    start = int(start_s)
                if end_s:
                    end = int(end_s)
                end = min(end, size - 1)
                if 0 <= start <= end:
                    is_range = True
            except (ValueError, AttributeError):
                start, end = 0, size - 1

        length = end - start + 1

        try:
            f = open(full_path, 'rb')
        except OSError:
            self.send_error(404, "无法读取文件")
            return

        self.send_response(206 if is_range else 200)
        self.send_header('Content-Type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(length))
        self.send_header('Access-Control-Allow-Origin', '*')
        if is_range:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()

        f.seek(start)
        remaining = length
        try:
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            # 客户端暂停/拖动进度会主动断开，属正常
            pass
        finally:
            f.close()

    def serve_control_sse(self):
        """SSE 端点：全局热键事件流，播放器页面连接后实时接收控制指令"""
        client_q = queue.Queue(maxsize=8)
        with control_clients_lock:
            control_clients.append(client_q)

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()

        try:
            while True:
                action = client_q.get(timeout=30)
                data = json.dumps({'action': action, 't': time.time()})
                self.wfile.write(f'data: {data}\n\n'.encode())
                self.wfile.flush()
        except queue.Empty:
            pass
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with control_clients_lock:
                if client_q in control_clients:
                    control_clients.remove(client_q)

    def serve_stream(self, params):
        """启动 ffmpeg 实时转码，流式输出 MPEG-TS"""
        global current_proc
        file_path = params.get('file', [''])[0]
        dir_path = params.get('dir', [DEFAULT_DIR])[0]
        start = params.get('start', ['0'])[0]

        dir_path = os.path.expanduser(dir_path)
        full_path = os.path.join(dir_path, file_path)

        if not os.path.isfile(full_path):
            self.send_error(404, "文件不存在")
            return

        # 终止旧进程
        kill_current_proc()

        # 允许 CORS（虽然同源，但保险起见）
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp2t')
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 构建 ffmpeg 命令
        cmd = [ffmpeg_cmd('ffmpeg')]
        # 输入端 seek（快速定位，用于跳转）
        try:
            start_val = float(start)
        except (ValueError, TypeError):
            start_val = 0
        if start_val > 0:
            cmd.extend(['-ss', str(start_val)])
        cmd.extend([
            '-i', full_path,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-ac', '2',  # 确保立体声（某些 5.1 声道 AAC 解码有问题）
            '-f', 'mpegts',
        ])
        cmd.append('pipe:1')

        try:
            with proc_lock:
                current_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
        except Exception as e:
            self.log_message(f"ffmpeg 启动失败: {e}")
            return

        # 流式转发
        try:
            while True:
                chunk = current_proc.stdout.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # 客户端断开（用户关页面或跳转）
            pass
        except Exception:
            pass
        finally:
            kill_current_proc()

    def log_message(self, format, *args):
        # 简化日志，只打印非静态资源请求
        msg = format % args
        if '/mpegts' not in msg and '/api/' in msg:
            print(f"  {msg}")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def signal_handler(sig, frame):
    kill_current_proc()
    print("\n已停止")
    sys.exit(0)


def is_port_in_use(port):
    """检测端口是否被占用"""
    import socket as _socket
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--hotkey-child':
        run_hotkey_child()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动前检测端口是否被占用
    if is_port_in_use(PORT):
        print("=" * 50)
        print("  [OK] 服务器已在运行（无需重复启动）")
        print(f"  [INFO] 地址：http://127.0.0.1:{PORT}")
        print("=" * 50)
        print()
        print("直接打开浏览器使用即可。")
        print("如需重启：先 kill 旧进程：")
        print(f"  lsof -ti:{PORT} | xargs kill")
        print()
        sys.exit(0)

    server = ThreadedHTTPServer(('127.0.0.1', PORT), StreamHandler)
    print("=" * 50)
    print("  [INFO] RVC 流式播放器")
    print(f"  [INFO] 地址：http://127.0.0.1:{PORT}")
    print(f"  [INFO] 默认目录：{DEFAULT_DIR}")
    print("=" * 50)
    print()

    start_hotkey_listener()
    print()
    print("在浏览器打开上面的地址即可开始使用")
    print("按 Ctrl+C 停止服务")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        signal_handler(None, None)
