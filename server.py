import threading
import asyncio
import datetime
import re
from flask import Flask, render_template
from flask_socketio import SocketIO
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent

app = Flask(__name__)
# Thiết lập SocketIO cho phép mọi thiết bị kết nối vào
socketio = SocketIO(app, cors_allowed_origins="*")

# --- HÀM LỌC SỐ ĐIỆN THOẠI ---
def detect_phone(text):
    clean_numbers = re.sub(r'\D', '', text)
    return True if re.search(r'0[35789]\d{8}', clean_numbers) else False

# --- GIAO DIỆN WEB ---
@app.route('/')
def index():
    return render_template('index.html')

# --- LẮNG NGHE LỆNH TỪ ĐIỆN THOẠI ---
@socketio.on('start_live')
def handle_start(data):
    tiktok_id = data['tiktok_id']
    print(f"[*] Điện thoại yêu cầu dò tìm ID: {tiktok_id}")
    socketio.emit('sys_log', {'msg': f"Đang dò tìm phòng live: {tiktok_id}..."})
    
    # Chạy TikTokLive trên một luồng riêng để không đơ Web
    threading.Thread(target=run_tiktok_listener, args=(tiktok_id,), daemon=True).start()

def run_tiktok_listener(tiktok_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=tiktok_id)

    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        # Đẩy thông báo xuống điện thoại
        socketio.emit('sys_log', {'msg': "✅ KẾT NỐI THÀNH CÔNG! SẴN SÀNG LÊN ĐƠN!"})

    @client.on(DisconnectEvent)
    async def on_disconnect(event: DisconnectEvent):
        socketio.emit('sys_log', {'msg': "❌ PHIÊN LIVE KẾT THÚC HOẶC MẤT KẾT NỐI."})

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        time_now = datetime.datetime.now().strftime('%H:%M:%S')
        comment_text = event.comment
        has_phone = detect_phone(comment_text)
        
        # Đóng gói data gửi hỏa tốc xuống màn hình điện thoại
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
    # Lấy cổng từ hệ thống Cloud, mặc định là 5000 nếu chạy ở nhà
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)