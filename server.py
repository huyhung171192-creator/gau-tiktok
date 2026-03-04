import os
import threading
import asyncio
import datetime
import re
from flask import Flask, render_template
from flask_socketio import SocketIO
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Biến thần thánh để ra lệnh "giết" luồng cũ
stop_flags = {}

def detect_phone(text):
    clean_numbers = re.sub(r'\D', '', text)
    return True if re.search(r'0[35789]\d{8}', clean_numbers) else False

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_live')
def handle_start(data):
    global stop_flags
    tiktok_id = data['tiktok_id']
    
    # 1. Bật cờ "True" cho TẤT CẢ các luồng đang chạy ngầm để ép chúng nó dừng lại
    for k in stop_flags.keys():
        stop_flags[k] = True
        
    # 2. Tạo cờ "False" (cho phép chạy) cho cái ID mới này
    stop_flags[tiktok_id] = False
    
    socketio.emit('sys_log', {'msg': f"Đang dò tìm phòng live: {tiktok_id}..."})
    threading.Thread(target=run_tiktok_listener, args=(tiktok_id,), daemon=True).start()

def run_tiktok_listener(tiktok_id):
    global stop_flags
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=tiktok_id)

    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        socketio.emit('sys_log', {'msg': "✅ KẾT NỐI THÀNH CÔNG! SẴN SÀNG LÊN ĐƠN!"})

    @client.on(DisconnectEvent)
    async def on_disconnect(event: DisconnectEvent):
        socketio.emit('sys_log', {'msg': "❌ PHIÊN LIVE KẾT THÚC HOẶC MẤT KẾT NỐI."})

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        # NẾU CỜ BỊ ĐỔI THÀNH TRUE -> NGẮT KẾT NỐI LUỒNG NÀY NGAY LẬP TỨC
        if stop_flags.get(tiktok_id, False):
            client.disconnect()
            return

        time_now = datetime.datetime.now().strftime('%H:%M:%S')
        comment_text = event.comment
        has_phone = detect_phone(comment_text)
        
        socketio.emit('new_comment', {
            'time': time_now,
            'user': event.user.nickname,
            'comment': comment_text,
            'has_phone': has_phone
        })

    try:
        client.run()
    except Exception as e:
        socketio.emit('sys_log', {'msg': f"Lỗi: {str(e)}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
