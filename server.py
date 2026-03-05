import os
import threading
import asyncio
import datetime
import re
import time
from flask import Flask, render_template
from flask_socketio import SocketIO
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# BỘ QUẢN LÝ LỆNH BÀI (Chống đúp luồng)
active_tokens = {}

def detect_phone(text):
    clean_numbers = re.sub(r'\D', '', text)
    return True if re.search(r'0[35789]\d{8}', clean_numbers) else False

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_live')
def handle_start(data):
    global active_tokens
    tiktok_id = data['tiktok_id']
    
    # 1. Đúc một Lệnh Bài mới tinh cho lần Vận Công này
    run_token = str(time.time())
    
    # 2. Xóa sạch mọi quyền hành của các luồng cũ, chỉ phong vương cho luồng mới
    active_tokens.clear()
    active_tokens[tiktok_id] = run_token
    
    socketio.emit('sys_log', {'msg': f"Đang dò tìm phòng live: {tiktok_id}..."})
    threading.Thread(target=run_tiktok_listener, args=(tiktok_id, run_token), daemon=True).start()

def run_tiktok_listener(tiktok_id, run_token):
    global active_tokens
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
        # 3. KIỂM TRA LỆNH BÀI: Nếu luồng này xài lệnh bài cũ -> Tự sát ngay lập tức
        if active_tokens.get(tiktok_id) != run_token:
            await client.disconnect()
            return

        time_now = (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).strftime('%H:%M:%S')
        comment_text = event.comment
        has_phone = detect_phone(comment_text)
        
        socketio.emit('new_comment', {
            'time': time_now,
            'user': event.user.nickname,
            'unique_id': event.user.unique_id, 
            'comment': comment_text,
            'has_phone': has_phone
        })

    try:
        client.run()
    except Exception as e:
        socketio.emit('sys_log', {'msg': f"Lỗi: {str(e)}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
