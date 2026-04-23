import streamlit as st
import requests

# 定义 CoinGecko API 的 URL
API_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"

def fetch_bitcoin_price():
    """
    从 CoinGecko API 获取当前比特币价格和24小时变化数据。
    Returns:
        tuple: 当前价格(float), 24小时变化百分比(float)
        如果数据获取失败，则返回 (None, None)
    """
    try:
        # 调用 API 获取数据
        response = requests.get(API_URL, timeout=10)  # 设置超时时间为10秒
        response.raise_for_status()  # 如果返回错误状态码，抛出异常
        data = response.json()

        # 提取比特币价格和24小时百分比变化
        price = data["bitcoin"]["usd"]
        change_24h = data["bitcoin"]["usd_24h_change"]
        return price, change_24h
    except requests.exceptions.RequestException as e:
        # 捕获任何请求异常并记录错误
        st.error(f"无法获取数据: {e}")
        return None, None

# Streamlit 页面配置
st.set_page_config(page_title="Bitcoin Price Tracker", layout="centered")

# 应用标题
st.title("📈 Bitcoin Price Tracker")
st.markdown(
    "欢迎使用比特币价格追踪应用！\n"
    "获取比特币实时价格以及24小时价格变化趋势。"
)

# 创建一个容器用于显示价格和变化
placeholder = st.empty()

# 页面加载时显示数据
with placeholder.container():
    with st.spinner("正在获取数据..."):
        # 第一次加载或刷新时调用数据获取函数
        price, change_24h = fetch_bitcoin_price()

    # 判断数据是否返回成功
    if price is not None:
        # 显示实时价格
        st.metric("当前比特币价格 (USD)", f"${price:,.2f}")

        # 显示24小时变化
        change_direction = "🔺" if change_24h > 0 else "🔻"
        st.metric("24小时价格变化", f"{change_direction} {change_24h:.2f}%")
    else:
        # 如果数据加载失败
        st.error("无法加载比特币价格，请稍后重试。")

# 手动刷新按钮
if st.button("🔄 刷新价格"):
    with st.spinner("正在刷新数据..."):
        # 再次调用数据获取
        price, change_24h = fetch_bitcoin_price()

    with placeholder.container():
        if price is not None:
            # 刷新数据成功后更新显示
            st.metric("当前比特币价格 (USD)", f"${price:,.2f}")
            change_direction = "🔺" if change_24h > 0 else "🔻"
            st.metric("24小时价格变化", f"{change_direction} {change_24h:.2f}%")
        else:
            # 刷新失败时显示错误
            st.error("更新失败，请检查网络连接或稍后尝试。")



### 示例界面说明

# 1. **标题和描述**：
#    - 标题 “Bitcoin Price Tracker” 显示在页面顶部。
#    - 描述文本提供应用功能说明（实时价格和变化趋势）。

# 2. **实时价格和变化显示**：
#    - 当前价格以 `st.metric` 显示（格式化为美元）。
#    - 24 小时变化显示涨跌符号（🔺 / 🔻）和变化百分比。

# 3. **刷新按钮**：
#    - 用户点击 “🔄 刷新价格” 按钮后，应用重新获取最新数据并更新显示。

# 4. **错误提示**：
#    - 如果数据获取失败，用户会看到友好的错误信息提示，指导其稍后重试。

# 代码整体实现符合需求，结构清晰，功能完整，以下是审查的重点内容与意见。

# ---

# #### **代码质量**

# 1. **模块化设计**
#    - `fetch_bitcoin_price()` 函数封装了 API 数据获取逻辑，符合单一职责原则。
#    - Streamlit 页面结构清晰，交互设计合理。
#    - 数据获取、刷新容器和界面更新逻辑分离明晰，避免代码混乱。

# 2. **代码的可读性**
#    - 添加了详细的注释解释，便于维护。
#    - 使用合理的变量命名（如 `price` 和 `change_24h`），直观表达具体含义。

# 3. **性能优化**
#    - 数据请求设置了超时时间（`timeout=10`），防止长时间被阻塞。
#    - 界面更新操作集中在 `placeholder.container()`，有效减少冗余界面刷新。

# ---

# #### **安全性**

# 1. **异常处理**
#    - 捕获了所有可能发生的 HTTP 请求异常，如网络连接错误或 API 响应不正确（`requests.exceptions.RequestException`）。这是正确且必要的。
#    - `response.raise_for_status()` 能够及时处理非 200 状态码的响应，确保错误信息不会被忽略。

# 2. **潜在问题**
#    - **未处理 API 数据验证问题**：
#      虽然代码假设返回数据总是包含 `bitcoin`、`usd` 和 `usd_24hr_change`，但实际开发中应验证 API 数据结构是否如预期。
#      建议在 `fetch_bitcoin_price()` 中增加数据完整性的校验，例如：
#      ```python
#      if "bitcoin" not in data or "usd" not in data["bitcoin"] or "usd_24h_change" not in data["bitcoin"]:
#          st.error("API 数据结构错误")
#          return None, None
#      ```

# ---

#### **最佳实践**

# 1. **加载状态**
#    - 使用了 `st.spinner` 显示加载状态，提升了用户体验，用户不会看到空白界面。

# 2. **刷新功能**
#    - 刷新按钮功能实现合理，确保用户随时可以更新价格数据。同时维护了加载状态一致性。

# 3. **格式化展示**
#    - 使用 `st.metric` 展示数字信息，并配合格式化（如 `f"${price:,.2f}"`），使信息简洁直观，符合最佳 UI 设计。

# ---

# #### **错误处理**

# 1. **网络异常提示**
#    - 使用 `st.error()` 显示友好的用户错误信息，避免用户困惑且界面更加专业。
#    - 不过，具体异常内容（如 `e` 的详情）可能对普通用户多余，建议缩减为通俗易懂的信息：
#      ```python
#      st.error("无法获取网络数据，可能是连接问题，请稍后重试。")
#      ```

# 2. **数据加载失败处理**
#    - 当数据返回 `None` 时，应用逻辑能够避免界面崩溃，并显示错误提示，这点设计优秀。

# ---

# #### **界面优化建议**

# 1. **布局改进**
#    - 页面顶部标题与文字过于简洁，可以增加背景颜色或分割线，增强视觉效果。
#    - 如使用 `st.markdown` 增添更丰富的样式：
#      ```python
#      st.markdown("---")
#      ```

# 2. **价格单位补充**
#    - 在标题或展示内容中可明确告知数据单位为 “美元”，避免用户产生疑问（虽然代码中以 `USD` 命名，但在界面描述中也应体现）。

# ---

# #### **代码扩展性**

# 1. 如需添加更多功能（例如显示其他加密货币价格），可以通过动态调整 URL 或创建下拉选择框来实现。这种方式扩展性强，建议提前设计框架以支持。
#    - 示例扩展：
#      ```python
#      selected_currency = st.selectbox(
#          '选择查看的加密货币',
#          ['bitcoin', 'ethereum', 'dogecoin']
#      )
#      ```

# 2. 如果页面访问量增多，建议添加缓存机制避免频繁的 API 请求：
#    ```python
#    @st.cache(ttl=60)  # 数据缓存1分钟
#    def fetch_bitcoin_price():