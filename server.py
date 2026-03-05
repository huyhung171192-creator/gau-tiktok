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

# Cờ hiệu để quản lý và "giết" luồng cũ
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
    
    # Ép các luồng cũ dừng lại
    for k in stop_flags.keys():
        stop_flags[k] = True
        
    # Mở cửa cho ID mới
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
        # Ngắt kết nối an toàn nếu có lệnh đổi phòng
        if stop_flags.get(tiktok_id, False):
            await client.disconnect()
            return

        # Giờ chuẩn Việt Nam (UTC+7)
        time_now = (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).strftime('%H:%M:%S')
        comment_text = event.comment
        has_phone = detect_phone(comment_text)
        
        socketio.emit('new_comment', {
            'time': time_now,
            'user': event.user.nickname,
            'unique_id': event.user.unique_id,  # Lấy ID chuẩn (@) không sợ trùng tên
            'comment': comment_text,
            'has_phone': has_phone
        })

    try:
        client.run()
    except Exception as e:
        socketio.emit('sys_log', {'msg': f"Lỗi: {str(e)}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # Mở khóa cho phép chạy trên Render (Production)
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
