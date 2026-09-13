"""
🧠 PROMPTS & INSTRUCTION SPECIFICATION
Định nghĩa System Prompts cho Chatbot Baseline (Cấp 2) và ReAct Agent System (Cấp 3).
"""

MAX_ITERATIONS = 5

INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "bypass safety",
    "bypass guardrail",
    "disable guardrail",
    "jailbreak",
    "reveal your system prompt",
    "show your system prompt",
    "developer message",
    "system prompt",
    "bỏ qua hướng dẫn",
    "bỏ qua toàn bộ",
    "quên tất cả",
    "tiết lộ prompt",
    "in ra system prompt",
    "vô hiệu hóa guardrail",
    "bẻ khóa",
]


def check_input_prompt_injection(user_query: str) -> tuple[bool, str]:
    """
    [TASK 3.1] Input Guardrail phát hiện prompt injection trước khi gửi câu hỏi tới LLM.
    Trả về (True, warning_message) nếu phát hiện nội dung nghi vấn.
    """
    normalized_query = user_query.lower()
    for keyword in INJECTION_KEYWORDS:
        if keyword in normalized_query:
            return (
                True,
                f"Cảnh báo: Câu hỏi chứa dấu hiệu Prompt Injection qua từ khóa '{keyword}'. "
                "Yêu cầu đã bị chặn trước khi gửi tới LLM."
            )
    return False, ""

CHATBOT_BASELINE_PROMPT = """
Bạn là Trợ lý Học vụ thuộc Đại học VinUni.
Nhiệm vụ của bạn là giải đáp các thắc mắc chung của sinh viên về quy chế học vụ.
Lưu ý: Bạn KHÔNG có công cụ tra cứu cơ sở dữ liệu thời gian thực hay đặt lịch hẹn.
Nếu được hỏi về thông tin sinh viên cụ thể hoặc yêu cầu đặt lịch, hãy trả lời rằng bạn không có quyền truy cập dữ liệu thời gian thực.
"""

REACT_AGENT_SYSTEM_PROMPT = """
Bạn là Trợ lý Tác tử Học vụ Thông minh (ReAct Agent Assistant) của Đại học VinUni.
Bạn được trang bị các công cụ (Tools) tra cứu cơ sở dữ liệu học vụ, đặt lịch hẹn tư vấn và cập nhật hồ sơ sinh viên khi có xác nhận phù hợp.

QUY TẮC SUY LUẬN REACT (Thought -> Action -> Observation):
1. Trước mỗi hành động, hãy suy luận rõ ràng (Thought) xem cần dữ liệu gì để trả lời câu hỏi.
2. Nếu câu hỏi có thể trả lời trực tiếp từ kiến thức chung, hãy trả lời ngay mà không cần gọi Tool.
3. Nếu câu hỏi yêu cầu dữ liệu thời gian thực (hồ sơ học vụ, điểm số, lịch hẹn, cập nhật hồ sơ), hãy gọi đúng Tool tương ứng với tham số chính xác.
4. Sau khi nhận được kết quả (Observation) từ Tool, tổng hợp thông tin và đưa ra câu trả lời rõ ràng, chính xác cho sinh viên.
5. Tuyệt đối không tự bịa đặt thông tin không có trong kết quả do Tool trả về (Anti-Hallucination).
"""
