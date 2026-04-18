from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from datetime import datetime, timedelta
import re

app = Flask(__name__)
app.secret_key = "test123456"

# 本地内存存留言（重启消失，不影响测试）
messages = []

# 订阅者列表
subscribers = []

# 祈福语库
prayer_texts = []

# 用户数据存储（实际生产环境应使用数据库）
user_data = {}

def get_user_id():
    """获取或创建用户ID（基于session）"""
    if 'user_id' not in session:
        session['user_id'] = f"user_{len(user_data) + 1}"
        if session['user_id'] not in user_data:
            user_data[session['user_id']] = {
                'check_in': {
                    'continuous_days': 0,
                    'total_days': 0,
                    'last_check_date': None,
                    'history': []
                },
                'prayer': {
                    'total_count': 0,
                    'last_prayer_date': None,
                    'history': []
                },
                'meditation': {
                    'total_minutes': 0,
                    'calmness_points': 0,
                    'today_completed': False,
                    'last_meditation_date': None,
                    'history': []
                },
                'daily_tasks': {
                    'check_in': False,
                    'prayer': False,
                    'meditation': False,
                    'last_reset_date': None
                }
            }
    return session['user_id']

def reset_daily_tasks_if_needed(user_id):
    """检查并重置每日任务状态（以服务器时间0点为准）"""
    today = datetime.now().strftime("%Y-%m-%d")
    user = user_data[user_id]
    
    if user['daily_tasks']['last_reset_date'] != today:
        user['daily_tasks'] = {
            'check_in': False,
            'prayer': False,
            'meditation': False,
            'last_reset_date': today
        }

def get_calmness_level(minutes):
    """根据累计静心时长获取等级"""
    if minutes <= 30:
        return {'level': '初心', 'color': '#999999'}
    elif minutes <= 100:
        return {'level': '静心', 'color': '#87CEEB'}
    elif minutes <= 300:
        return {'level': '安定', 'color': '#4169E1'}
    else:
        return {'level': '圆满', 'color': '#191970'}

# ------------------- 页面路由 -------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shrine')
def shrine():
    return render_template('shrine.html')

@app.route('/daily-prayer')
def daily_prayer():
    return render_template('daily_prayer.html')

@app.route('/daily-checkin')
def daily_checkin():
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    return render_template('daily_checkin.html', 
                         continuous_days=user['check_in']['continuous_days'],
                         total_days=user['check_in']['total_days'],
                         today_completed=user['daily_tasks']['check_in'])

@app.route('/meditation')
def meditation():
    return render_template('meditation.html')

@app.route('/profile')
def profile():
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    
    calmness_info = get_calmness_level(user['meditation']['total_minutes'])
    
    return render_template('profile.html',
                         continuous_days=user['check_in']['continuous_days'],
                         total_days=user['check_in']['total_days'],
                         prayer_count=user['prayer']['total_count'],
                         meditation_minutes=user['meditation']['total_minutes'],
                         calmness_level=calmness_info['level'],
                         calmness_color=calmness_info['color'],
                         daily_tasks=user['daily_tasks'])

# ------------------- 留言提交接口 -------------------
@app.route('/api/submit', methods=['POST'])
def api_submit():
    data = request.get_json()
    name = data.get("name", "匿名信眾")
    content = data.get("content")

    if not content:
        return jsonify({"error": "請輸入內容"}), 400

    messages.insert(0, {
        "id": len(messages) + 1,
        "name": name,
        "content": content,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return jsonify({"message": "呈送成功"}), 200

# ------------------- 邮箱订阅接口 -------------------
@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "請輸入郵箱地址"}), 400

    # 简单的邮箱格式验证
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return jsonify({"error": "郵箱格式不正確"}), 400

    # 检查是否已经订阅
    for subscriber in subscribers:
        if subscriber['email'] == email:
            return jsonify({"error": "此郵箱已訂閱"}), 400

    subscribers.insert(0, {
        "id": len(subscribers) + 1,
        "email": email,
        "subscribe_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({"message": "訂閱成功"}), 200

# ------------------- 祈福语管理接口 -------------------
@app.route('/api/prayer-texts', methods=['GET'])
def api_get_prayer_texts():
    """获取所有祈福语（按添加时间倒序）"""
    sorted_texts = sorted(prayer_texts, key=lambda x: x['id'], reverse=True)
    return jsonify(sorted_texts), 200

@app.route('/api/prayer-texts', methods=['POST'])
def api_add_prayer_text():
    """添加祈福语"""
    data = request.get_json()
    content = data.get("content", "").strip()
    
    if not content:
        return jsonify({"error": "內容不能為空"}), 400
    
    if len(content) > 30:
        return jsonify({"error": "內容不能超過30字"}), 400
    
    # 简单敏感词校验
    sensitive_words = ['违法', '极端', '低俗', '暴力', '色情']
    for word in sensitive_words:
        if word in content:
            return jsonify({"error": "內容包含敏感詞，請修改後再提交"}), 400
    
    new_text = {
        "id": len(prayer_texts) + 1,
        "content": content,
        "add_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    prayer_texts.append(new_text)
    
    return jsonify({"message": "添加成功", "data": new_text}), 200

@app.route('/api/prayer-texts/<int:text_id>', methods=['DELETE'])
def api_delete_prayer_text(text_id):
    """删除祈福语"""
    global prayer_texts
    original_count = len(prayer_texts)
    prayer_texts = [t for t in prayer_texts if t['id'] != text_id]
    
    if len(prayer_texts) == original_count:
        return jsonify({"error": "祈福語不存在"}), 404
    
    return jsonify({"message": "刪除成功"}), 200

# ------------------- 每日祈愿接口 -------------------
@app.route('/api/prayer/draw', methods=['POST'])
def api_prayer_draw():
    """抽取祈福语"""
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    
    # 检查今日是否已祈愿
    if user['daily_tasks']['prayer']:
        return jsonify({"error": "今日祈願已完成，明日再來"}), 400
    
    # 检查祈福语库是否为空
    if not prayer_texts:
        return jsonify({"error": "祈福準備中，請稍後再來"}), 400
    
    # 随机抽取一条祈福语
    import random
    selected = random.choice(prayer_texts)
    
    # 更新用户数据
    user['prayer']['total_count'] += 1
    user['prayer']['last_prayer_date'] = datetime.now().strftime("%Y-%m-%d")
    user['prayer']['history'].append({
        "text_id": selected['id'],
        "content": selected['content'],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    user['daily_tasks']['prayer'] = True
    
    return jsonify({
        "message": "祈願成功",
        "content": selected['content']
    }), 200

# ------------------- 每日签到接口 -------------------
@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    """执行签到"""
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 检查今日是否已签到
    if user['daily_tasks']['check_in']:
        return jsonify({"error": "今日已簽到", "already_signed": True}), 200
    
    # 计算连续签到天数
    last_date = user['check_in']['last_check_date']
    
    if last_date:
        last_date_obj = datetime.strptime(last_date, "%Y-%m-%d")
        today_obj = datetime.strptime(today, "%Y-%m-%d")
        days_diff = (today_obj - last_date_obj).days
        
        if days_diff == 1:
            # 连续签到
            user['check_in']['continuous_days'] += 1
        else:
            # 断签，重置连续天数
            user['check_in']['continuous_days'] = 1
    else:
        # 首次签到
        user['check_in']['continuous_days'] = 1
    
    # 更新累计签到天数
    user['check_in']['total_days'] += 1
    user['check_in']['last_check_date'] = today
    user['check_in']['history'].append(today)
    user['daily_tasks']['check_in'] = True
    
    # 检查是否获得连续签到奖励
    reward_days = [3, 7, 14, 21, 30]
    got_reward = user['check_in']['continuous_days'] in reward_days
    
    return jsonify({
        "message": "簽到成功",
        "continuous_days": user['check_in']['continuous_days'],
        "total_days": user['check_in']['total_days'],
        "got_reward": got_reward
    }), 200

# ------------------- 静心仪式接口 -------------------
@app.route('/api/meditation/start', methods=['POST'])
def api_meditation_start():
    """开始静心（仅记录，不验证完成）"""
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    
    data = request.get_json()
    duration = data.get("duration")  # 3, 5, 10, 15
    
    if duration not in [3, 5, 10, 15]:
        return jsonify({"error": "無效的靜心時長"}), 400
    
    # 检查今日是否已完成静心
    if user['daily_tasks']['meditation']:
        return jsonify({"error": "今日靜心已完成"}), 400
    
    return jsonify({"message": "靜心開始", "duration": duration}), 200

@app.route('/api/meditation/complete', methods=['POST'])
def api_meditation_complete():
    """完成静心"""
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    
    data = request.get_json()
    duration = data.get("duration")
    
    if duration not in [3, 5, 10, 15]:
        return jsonify({"error": "無效的靜心時長"}), 400
    
    # 检查今日是否已完成静心
    if user['daily_tasks']['meditation']:
        return jsonify({"error": "今日靜心已完成"}), 400
    
    # 计算静心值
    points_map = {3: 1, 5: 2, 10: 5, 15: 8}
    points = points_map[duration]
    
    # 更新用户数据
    user['meditation']['total_minutes'] += duration
    user['meditation']['calmness_points'] += points
    user['meditation']['last_meditation_date'] = datetime.now().strftime("%Y-%m-%d")
    user['meditation']['history'].append({
        "duration": duration,
        "points": points,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    user['daily_tasks']['meditation'] = True
    
    return jsonify({
        "message": "靜心圓滿",
        "minutes_added": duration,
        "points_added": points,
        "total_minutes": user['meditation']['total_minutes']
    }), 200

@app.route('/api/meditation/cancel', methods=['POST'])
def api_meditation_cancel():
    """取消静心（不计入统计）"""
    return jsonify({"message": "本次靜心未完成，不計入時長哦"}), 200

# ------------------- 后台 -------------------
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == '123456':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('admin_login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html', 
                         messages=messages, 
                         subscribers=subscribers,
                         prayer_texts=sorted(prayer_texts, key=lambda x: x['id'], reverse=True))

@app.route('/admin/logout')
def logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ------------------- 启动 -------------------
if __name__ == '__main__':
    app.run(debug=True)