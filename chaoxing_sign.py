import threading
import requests
import logging
import re
import time

# 全局配置
lock = threading.Lock()
current_code_index = 0
found = False
end_code_index = None  # 动态计算结束索引
thread_count = 300  # 可调整线程数

# 日志配置
logging.basicConfig(
    filename='sign_log.txt',
    filemode='w',
    format='%(asctime)s %(message)s',
    level=logging.INFO,
    encoding='utf-8'
)

# 生成符合九宫格规则的手势签到码
def is_valid_move(path, next_point):
    """检查从当前路径到下一个点是否有效"""
    if next_point in path:
        return False  # 不能重复经过同一个点

    if len(path) == 0:
        return True  # 起始点总是有效的

    last_point = path[-1]
    # 定义九宫格中间点的跳跃规则
    jump_rules = {
        (1, 3): 2, (3, 1): 2,
        (1, 7): 4, (7, 1): 4,
        (3, 9): 6, (9, 3): 6,
        (7, 9): 8, (9, 7): 8,
        (1, 9): 5, (9, 1): 5,
        (3, 7): 5, (7, 3): 5,
        (2, 8): 5, (8, 2): 5,
        (4, 6): 5, (6, 4): 5
    }

    # 检查是否需要跳过中间点
    if (last_point, next_point) in jump_rules:
        middle_point = jump_rules[(last_point, next_point)]
        if middle_point not in path:
            return False  # 如果中间点未被访问，则跳跃无效

    return True


def generate_gesture_codes():
    """生成符合九宫格规则的手势签到码"""
    def backtrack(path):
        if len(path) >= 4:  # 至少4个点
            gesture_codes.append(''.join(map(str, path)))
        if len(path) == 9:  # 最多9个点
            return

        for next_point in range(1, 10):  # 九宫格点 1 到 9
            if is_valid_move(path, next_point):
                backtrack(path + [next_point])

    gesture_codes = []
    for start_point in range(1, 10):  # 从每个点开始
        backtrack([start_point])
    return gesture_codes


# 调用生成函数
gesture_codes = generate_gesture_codes()
end_code_index = len(gesture_codes) - 1


def worker(active_id, cookie):
    """工作线程函数"""
    global current_code_index, found

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'Cookie': cookie
    })

    while True:
        with lock:
            if found or current_code_index > end_code_index:
                break
            sign_code = gesture_codes[current_code_index]
            current_code_index += 1

        try:
            # 尝试签到码
            check_url = f"https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/checkSignCode?activeId={active_id}&signCode={sign_code}"
            response = session.get(check_url, timeout=10)

            # 记录日志
            log_msg = f"[Thread {threading.get_ident()}] Code: {sign_code} | Status: {response.status_code} | Response: {response.text[:80]}"
            logging.info(log_msg)

            if response.status_code == 200 and '"result":1' in response.text:
                with lock:
                    found = True

                # 记录成功日志
                success_msg = f"[SUCCESS] 有效签到码: {sign_code}"
                logging.info(success_msg)
                print(f"\n{success_msg}")

                # 发送后续请求
                validate_url = f"https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/checkIfValidate?activeId={active_id}"
                session.get(validate_url)

                signin_url = f"https://mobilelearn.chaoxing.com/v2/apis/sign/signIn?activeId={active_id}&signCode={sign_code}"
                session.get(signin_url)

                return

        except Exception as e:
            logging.error(f"请求异常: {str(e)[:100]}")


def main():
    """主函数"""
    print("超星签到码爆破工具")
    print("-" * 40)

    # 获取输入
    active_id = input("请输入 activeId: ").strip()
    cookie = input("请粘贴完整 Cookie: ").strip()

    # 验证必要参数
    if not active_id:
        print("错误：activeId 不能为空")
        return
    if "JSESSIONID" not in cookie:
        print("警告：Cookie 中未检测到 JSESSIONID")

    # 清理 Cookie 格式
    clean_cookie = re.sub(r'\s+', '', cookie)  # 移除所有空白字符

    # 记录启动信息
    logging.info(f"[程序启动] activeId: {active_id}")
    logging.info(f"[Cookie 摘要] JSESSIONID: {re.findall('JSESSIONID=([^;]+)', cookie)[0][:8]}...")

    # 创建线程
    threads = []
    for _ in range(thread_count):
        t = threading.Thread(target=worker, args=(active_id, clean_cookie))
        t.start()
        threads.append(t)

    # 显示进度
    print("\n运行状态:")
    total_codes = len(gesture_codes)
    while any(t.is_alive() for t in threads):
        with lock:
            current = current_code_index
        progress = (current / total_codes) * 100
        print(f"\r进度: {progress:.2f}% | 已尝试: {current} 次 | 最新代码: {gesture_codes[current - 1] if current > 0 else 'N/A'}   ", end='')
        time.sleep(0.5)

    # 输出结果
    if found:
        print("\n\n签到成功！请查看日志文件获取详细信息")
    else:
        print("\n\n未找到有效签到码")


if __name__ == "__main__":
    main()